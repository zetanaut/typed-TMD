"""Exact, finite replay of native PDF and alpha_s values exported for H002."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .contracts import ContractError


class ReplayError(ContractError):
    pass


class MissingQueryError(ReplayError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def hex_float(value: float) -> str:
    if isinstance(value, bool):
        raise ReplayError("boolean_is_not_float")
    result = float(value)
    if not math.isfinite(result):
        raise ReplayError("nonfinite_float")
    return result.hex()


def parse_hex(value: str) -> float:
    if not isinstance(value, str):
        raise ReplayError("hex_string_required")
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise ReplayError("bad_hex_float") from exc
    if not math.isfinite(result) or result.hex() != value:
        raise ReplayError("noncanonical_or_nonfinite_hex")
    return result


def document(path: Path) -> dict:
    path = Path(path)
    data = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReplayError("duplicate_json_key")
            result[key] = value
        return result
    try:
        doc = json.loads(data, object_pairs_hook=unique_pairs,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except ReplayError:
        raise
    except ValueError as exc:
        raise ReplayError("invalid_json") from exc
    if set(doc) != {"schema", "payload", "payload_sha256", "run_evidence"}:
        raise ReplayError("document_shape")
    if digest(doc["payload"]) != doc["payload_sha256"]:
        raise ReplayError("payload_digest_mismatch")
    return doc


def write_document(path: Path, schema: str, payload: dict, evidence: dict | None = None) -> dict:
    path = Path(path)
    doc = {"schema": schema, "payload": payload, "payload_sha256": digest(payload),
           "run_evidence": evidence or {}}
    data = canonical(doc) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.suffix == ".gz":
        with tmp.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as target:
                target.write(data)
    else:
        tmp.write_bytes(data)
    if path.exists() and path.read_bytes() != tmp.read_bytes():
        tmp.unlink()
        raise ReplayError("immutable_output_collision")
    tmp.replace(path)
    return doc


def query_id(kind: str, coordinates: dict) -> str:
    return digest({"kind": kind, "coordinates": coordinates})


class ReplayProvider:
    """No interpolation, native imports, or fallback on a cache miss."""

    def __init__(self, inspection: dict, plan: dict, snapshot: dict):
        if (inspection.get("schema") != "typed_tmd.provider_inspection.v1"
                or plan.get("schema") != "typed_tmd.provider_query_plan.v1"
                or snapshot.get("schema") != "typed_tmd.provider_snapshot.v1"):
            raise ReplayError("schema_mismatch")
        for doc in (inspection, plan, snapshot):
            if digest(doc["payload"]) != doc["payload_sha256"]:
                raise ReplayError("payload_digest_mismatch")
        ip, pp, sp = inspection["payload"], plan["payload"], snapshot["payload"]
        if (pp["inspection_sha256"] != inspection["payload_sha256"]
                or sp["inspection_sha256"] != inspection["payload_sha256"]
                or sp["plan_sha256"] != plan["payload_sha256"]
                or sp["provider_id"] != pp["provider_id"]
                or (sp["set"], sp["member"]) != ("CT18NNLO", 0)
                or (pp["set"], pp["member"]) != ("CT18NNLO", 0)
                or not sp.get("complete")):
            raise ReplayError("provider_identity_mismatch")
        queries = pp["queries"]
        results = sp["results"]
        if len(queries) != len(results):
            raise ReplayError("incomplete_snapshot")
        self._values: dict[str, dict] = {}
        self._coords: dict[str, dict] = {}
        for query, result in zip(queries, results):
            coords = query.get("coordinates", {})
            expected_coords = ({"pid", "x_hex", "mu_GeV_hex"}
                               if query.get("kind") == "pdf_value" else {"mu_GeV_hex"})
            if (set(query) != {"query_id", "kind", "coordinates", "roles"}
                    or query["kind"] not in ("pdf_value", "alpha_s_value")
                    or set(coords) != expected_coords
                    or not isinstance(query["roles"], list) or not query["roles"]
                    or query["query_id"] != query_id(query["kind"], query["coordinates"])
                    or query["query_id"] in self._values
                    or result["query_id"] != query["query_id"]
                    or result["kind"] != query["kind"]
                    or result["coordinates"] != query["coordinates"]
                    or result["status"] != "passed"):
                raise ReplayError("invalid_or_duplicate_query")
            if query["kind"] == "pdf_value":
                if type(coords["pid"]) is not int or coords["pid"] not in {-3, -2, -1, 1, 2, 3} or not 0 < parse_hex(coords["x_hex"]) < 1:
                    raise ReplayError("invalid_pdf_coordinate")
            if parse_hex(coords["mu_GeV_hex"]) <= 0:
                raise ReplayError("invalid_mu_coordinate")
            value = result["value"]
            expected = {"native_xf_hex", "f_hex"} if query["kind"] == "pdf_value" else {"alpha_s_hex"}
            if set(value) != expected:
                raise ReplayError("value_shape")
            for item in value.values():
                parse_hex(item)
            if query["kind"] == "pdf_value":
                if (parse_hex(value["native_xf_hex"]) / parse_hex(coords["x_hex"])).hex() != value["f_hex"]:
                    raise ReplayError("xf_to_f_conversion_mismatch")
            self._values[query["query_id"]] = value
            self._coords[query["query_id"]] = query["coordinates"]
        self.inspection = inspection
        self.plan = plan
        self.snapshot = snapshot
        self.identifier = pp["provider_id"]
        self.snapshot_id = snapshot["payload_sha256"]
        self.quantity = "f"
        self._bounds = {key: parse_hex(value) for key, value in ip["bounds"].items()}
        self._flavors = set(ip["flavors"])

    def _lookup(self, kind: str, coordinates: dict) -> dict:
        qid = query_id(kind, coordinates)
        try:
            return self._values[qid]
        except KeyError as exc:
            raise MissingQueryError(f"missing_query {kind} {coordinates} snapshot={self.snapshot_id}") from exc

    def f(self, pid: int, x: float, mu_GeV: float) -> float:
        if type(pid) is not int or pid not in {-3, -2, -1, 1, 2, 3} or pid not in self._flavors:
            raise ReplayError("unsupported_pid")
        xh, mh = hex_float(x), hex_float(mu_GeV)
        x, mu = parse_hex(xh), parse_hex(mh)
        b = self._bounds
        if (not 0 < x < 1 or not b["x_min"] <= x <= b["x_max"]
                or not b["q_min"] <= mu <= b["q_max"]):
            raise ReplayError("pdf_out_of_support")
        return parse_hex(self._lookup("pdf_value", {"pid": pid, "x_hex": xh,
                                                    "mu_GeV_hex": mh})["f_hex"])

    def alpha_s(self, mu_GeV: float) -> float:
        mh = hex_float(mu_GeV)
        mu = parse_hex(mh)
        b = self._bounds
        if not b["alpha_min"] <= mu <= b["alpha_max"]:
            raise ReplayError("alpha_out_of_support")
        value = parse_hex(self._lookup("alpha_s_value", {"mu_GeV_hex": mh})["alpha_s_hex"])
        if value <= 0:
            raise ReplayError("nonpositive_alpha_s")
        return value
