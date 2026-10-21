"""Focused H002 contract tests independent of the large native snapshot."""
from dataclasses import replace
import math
import unittest

from typed_tmd.contracts import (AccuracySpec, CoefficientOrders, ContractError,
                                 ExternalInput, Provenance, ScalePoint, TMDContext)
from typed_tmd.expressions import BoundaryTMD
from typed_tmd.provider_replay import MissingQueryError, ReplayError, ReplayProvider, digest, query_id
from typed_tmd.qcd_forward import QCDProduction
from typed_tmd.qcd_plan import profile_mu


def wrapped(schema, payload):
    return {"schema": schema, "payload": payload, "payload_sha256": digest(payload), "run_evidence": {}}


def tiny_documents(raw=-0.2, x=0.2):
    inspection = wrapped("typed_tmd.provider_inspection.v1", {
        "bounds": {"x_min": float(0.01).hex(), "x_max": float(0.99).hex(),
                   "q_min": float(1).hex(), "q_max": float(100).hex(),
                   "alpha_min": float(1).hex(), "alpha_max": float(100).hex()},
        "flavors": [2],
    })
    coords = {"pid": 2, "x_hex": x.hex(), "mu_GeV_hex": float(5).hex()}
    qid = query_id("pdf_value", coords)
    plan = wrapped("typed_tmd.provider_query_plan.v1", {
        "inspection_sha256": inspection["payload_sha256"], "set": "CT18NNLO", "member": 0,
        "provider_id": "fixed-provider-fingerprint", "queries": [
            {"query_id": qid, "kind": "pdf_value", "coordinates": coords, "roles": ["test"]}],
    })
    snapshot = wrapped("typed_tmd.provider_snapshot.v1", {
        "inspection_sha256": inspection["payload_sha256"],
        "plan_sha256": plan["payload_sha256"], "provider_id": "fixed-provider-fingerprint",
        "set": "CT18NNLO", "member": 0, "complete": True,
        "results": [{"query_id": qid, "kind": "pdf_value", "coordinates": coords,
                     "status": "passed", "value": {"native_xf_hex": raw.hex(),
                                                   "f_hex": (raw / x).hex()}}],
    })
    return inspection, plan, snapshot


class ReplayContractTests(unittest.TestCase):
    def test_signed_f_from_xf_and_missing_or_out_of_support_nodes(self):
        replay = ReplayProvider(*tiny_documents())
        self.assertEqual(replay.f(2, 0.2, 5), -1.0)
        with self.assertRaises(MissingQueryError):
            replay.f(2, 0.3, 5)
        with self.assertRaisesRegex(ReplayError, "pdf_out_of_support"):
            replay.f(2, 0.2, 101)
        with self.assertRaisesRegex(ReplayError, "unsupported_pid"):
            replay.f(4, 0.2, 5)

    def test_signed_zero_and_snapshot_integrity(self):
        inspection, plan, snapshot = tiny_documents(raw=-0.0)
        self.assertEqual(math.copysign(1.0, ReplayProvider(inspection, plan, snapshot).f(2, 0.2, 5)), -1.0)
        broken = dict(snapshot)
        broken["payload_sha256"] = "0" * 64
        with self.assertRaisesRegex(ReplayError, "payload_digest_mismatch"):
            ReplayProvider(inspection, plan, broken)
        altered = dict(snapshot["payload"])
        altered["member"] = 1
        with self.assertRaisesRegex(ReplayError, "provider_identity_mismatch"):
            ReplayProvider(inspection, plan, wrapped(snapshot["schema"], altered))

    def test_duplicate_and_unknown_query_rejected(self):
        inspection, plan, snapshot = tiny_documents()
        q = plan["payload"]["queries"][0]
        doubled_plan = wrapped(plan["schema"], {**plan["payload"], "queries": [q, q]})
        doubled_snapshot = wrapped(snapshot["schema"], {**snapshot["payload"],
            "plan_sha256": doubled_plan["payload_sha256"], "results": snapshot["payload"]["results"] * 2})
        with self.assertRaisesRegex(ReplayError, "invalid_or_duplicate_query"):
            ReplayProvider(inspection, doubled_plan, doubled_snapshot)
        unknown = {**q, "kind": "nearest_neighbor"}
        unknown_plan = wrapped(plan["schema"], {**plan["payload"], "queries": [unknown]})
        unknown_snapshot = wrapped(snapshot["schema"], {**snapshot["payload"],
            "plan_sha256": unknown_plan["payload_sha256"]})
        with self.assertRaises(ReplayError):
            ReplayProvider(inspection, unknown_plan, unknown_snapshot)

    def test_nonfinite_value_and_synthetic_expression_rejected(self):
        inspection, plan, snapshot = tiny_documents()
        altered = {**snapshot["payload"], "results": [{**snapshot["payload"]["results"][0],
            "value": {"native_xf_hex": "nan", "f_hex": float(-1).hex()}}]}
        with self.assertRaises(ReplayError):
            ReplayProvider(inspection, plan, wrapped(snapshot["schema"], altered))
        production = QCDProduction.__new__(QCDProduction)
        production.context = TMDContext(provider_id="physical-provider")
        synthetic = BoundaryTMD(TMDContext(), 2, ScalePoint(2, 4), "fixture", "fixture", "fixture",
                                Provenance("fixture", "synthetic"))
        with self.assertRaises(ContractError):
            production.evaluate(synthetic, 0.2, 0.5)

    def test_external_inventory_requires_both_real_identities(self):
        external = ExternalInput("native-id", "CT18NNLO/0", "native", "sha256", "OrderQCD=2",
                                 "native NNLO PDF", "variable flavor")
        local = CoefficientOrders(H=0, C=0, K=1, gamma=1, cusp=1)
        with self.assertRaises(ContractError):
            AccuracySpec(mode="external_inputs", expansion_parameter="a_s=alpha_s/(4*pi)",
                         coefficients=local, external_collinear=external,
                         kernel_completion="RG_integral_of_one_loop_gamma_K_with_native_alpha_s")
        coupling = replace(external, provider_id="other")
        with self.assertRaises(ContractError):
            AccuracySpec(mode="external_inputs", expansion_parameter="a_s=alpha_s/(4*pi)",
                         coefficients=local, external_collinear=external, external_coupling=coupling,
                         kernel_completion="RG_integral_of_one_loop_gamma_K_with_native_alpha_s")

    def test_profile_has_correct_endpoint_scales(self):
        self.assertAlmostEqual(profile_mu(12.0), 2.2477866, places=6)
        self.assertGreater(profile_mu(0.000025), 40000)


if __name__ == "__main__":
    unittest.main()
