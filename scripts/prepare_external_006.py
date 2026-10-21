#!/usr/bin/env python3
"""Fetch/pin and build the one H006 SV19 backend in caller-selected local paths.

Requires an existing Python 3.11/NumPy 1.26 environment, Fortran compiler and
LHAPDF 6.5.5 native prefix. It never modifies the LHAPDF prefix or global Python.
Only central PDF files are fetched; external sources remain in ignored cache.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

CODE_URL = "https://github.com/VladimirovAlexey/artemide-public.git"
CODE_COMMIT = "ea0af1a75e21e316c1ac4ece51933988836a6650"
INPUT_URL = "https://github.com/VladimirovAlexey/artemide-DataProcessor.git"
INPUT_COMMIT = "18967d1c52dabf93e17a640405b548071904cfcc"
PDF = "NNPDF31_nnlo_as_0118_1000"
PDF_HASHES = {
    PDF+".info": "f5fc2f70655a00dd426dda9294d5b7a3c617aaec63f84b8ada79637745404fde",
    PDF+"_0000.dat": "b367000f810148b25b1b1b65a4b37138d2d27dd4351497b6674283f834bd090d",
}
CONSTANTS = "Models/SV19/constants-files/DY_nnlo/const-NNPDF31_NNLO"
REPLICAS = "Models/SV19/Replicas/DY_nnlo/DY_NNPDF31_nnlo.rep"
FIXED = [1.86041, 0.029551, 0.253434, 9.04351, 346.999, 2.47992, -5.69988, 0., 0.]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")


def precision_config(text, changes):
    """Change identified numerical/I/O fields; retain every other input line."""
    lines = text.splitlines(keepends=True)
    main, sub, found = None, "", set()
    for i, line in enumerate(lines):
        if not line.startswith("*"):
            continue
        token = line[1:].split()[0]
        if token.isdigit():
            main, sub = int(token), ""
        elif token.isalpha() and len(token) == 1:
            sub = token
        elif token.startswith("p") and token[1:].isdigit():
            key = (main, sub, int(token[1:]))
            if key in changes:
                if key in found:
                    raise ValueError("Duplicate configuration key")
                lines[i+1] = " " + str(changes[key]) + "\n"
                found.add(key)
    if found != set(changes):
        raise ValueError("Configuration field not found: " + repr(set(changes)-found))
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--env-prefix", type=Path, required=True)
    ap.add_argument("--fortran", type=Path, required=True)
    ap.add_argument("--lhapdf-prefix", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    cache, prefix, lha, out = [p.resolve() for p in (args.cache, args.env_prefix, args.lhapdf_prefix, args.output)]
    out.mkdir(parents=True, exist_ok=False)
    cache.mkdir(parents=True, exist_ok=True)
    compiler = args.fortran.resolve()
    env = dict(os.environ, PATH=str(prefix/"bin")+os.pathsep+os.environ["PATH"],
               CC=shutil.which("clang") or "cc", CXX=shutil.which("clang++") or "c++")
    if sys.platform == "darwin":
        env.update(SDKROOT=subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip(),
                   MACOSX_DEPLOYMENT_TARGET="11.0", LDFLAGS="-Wl,-rpath,"+str(lha/"lib"))
    commands = []

    def run(stage, cmd, cwd=None):
        start = time.perf_counter()
        with (out/(stage+".log")).open("w") as stream:
            result = subprocess.run(list(map(str, cmd)), cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append({"stage": stage, "argv": list(map(str, cmd)), "cwd": str(cwd or Path.cwd()),
                         "returncode": result.returncode, "elapsed_seconds": time.perf_counter()-start})
        write_json(out/"commands.json", commands)
        if result.returncode:
            raise RuntimeError(stage+" failed; see retained log")

    try:
        for name, url, commit in (("artemide-public", CODE_URL, CODE_COMMIT),
                                  ("artemide-DataProcessor", INPUT_URL, INPUT_COMMIT)):
            dest = cache/name
            if not dest.exists():
                run("clone_"+name, ["git", "clone", "--filter=blob:none", url, dest])
            actual = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
            if actual != commit:
                if subprocess.check_output(["git", "-C", str(dest), "status", "--porcelain"], text=True).strip():
                    raise RuntimeError("Preserve changed upstream checkout; choose a fresh cache")
                run("checkout_"+name, ["git", "-C", dest, "checkout", "--detach", commit])
        backend, inputs = cache/"artemide-public", cache/"artemide-DataProcessor"
        # Refuse unknown source edits in a reused cache, while allowing exactly
        # the documented replacement by bundled SV19 model files.
        changed = subprocess.check_output(["git", "-C", str(backend), "diff", "--name-only"], text=True).splitlines()
        allowed = {"src/Model/"+p.name for p in (backend/"Models/SV19/Model").glob("*.f90")}
        if not set(changed) <= allowed:
            raise RuntimeError("Unknown upstream source changes: " + repr(changed))
        models = []
        for p in sorted((backend/"Models/SV19/Model").glob("*.f90")):
            dest = backend/"src/Model"/p.name
            if str(dest.relative_to(backend)) in changed and dest.read_bytes() != p.read_bytes():
                raise RuntimeError("Changed selected model; preserve it")
            shutil.copyfile(p, dest)
            models.append({"source": str(p.relative_to(backend)), "destination": str(dest.relative_to(backend)), "sha256": digest(p)})
        pdfdir = cache/"pdfsets"/PDF
        pdfdir.mkdir(parents=True, exist_ok=True)
        pdf_inputs = []
        for name, expected in PDF_HASHES.items():
            url = "https://lhapdfsets.web.cern.ch/current/"+PDF+"/"+name
            target = pdfdir/name
            if not target.exists():
                target.write_bytes(urllib.request.urlopen(url, timeout=60).read())
            if digest(target) != expected:
                raise RuntimeError("PDF input digest mismatch: "+name)
            pdf_inputs.append({"url": url, "name": name, "bytes": target.stat().st_size, "sha256": expected,
                               "distribution": "fetch from official origin; grids excluded from software export"})
        for name in ("obj", "mod", "bin"):
            (backend/name).mkdir(exist_ok=True)
        flags = "-O2 -fPIC -fallow-argument-mismatch"
        run("native_objects", ["make", "obj", "aTMDeHOME="+str(backend), "FCompilator="+str(compiler),
                               "Fflags="+flags, "FOPT=-L"+str(lha/"lib")+" -lLHAPDF"], backend)
        objects = sorted((backend/"obj").glob("*.o"))
        run("harpy_extension", [prefix/"bin/python", "-m", "numpy.f2py", "-c", "harpy/artemide.pyf", "harpy/harpy.f90",
            *objects, "--f90exec="+str(compiler), "--f77exec="+str(compiler), "--f90flags="+flags,
            "-I"+str(backend/"mod"), "-L"+str(lha/"lib"), "-lLHAPDF"], backend)
        libraries = list(backend.glob("artemide*.so"))
        if len(libraries) != 1:
            raise RuntimeError("Expected one native extension")
        shutil.copyfile(libraries[0], backend/"harpy"/libraries[0].name)
        changes = {(0, "A", 2): 0, (9, "B", 1): "2.0E-7", (9, "B", 2): 32, (7, "A", 1): "1.0E-6"}
        original = (backend/CONSTANTS).read_text()
        config = out/"native_constants.txt"
        config.write_text(precision_config(original, changes))
        # Secondary numerical pilot: tighter native bin integration only.
        refined = out/"native_refined_constants.txt"
        refined.write_text(precision_config(original, {**changes, (9, "B", 1): "1.0E-7", (9, "B", 2): 64}))
        source_hashes = {str(p.relative_to(backend)): digest(p) for folder in ("src", "harpy")
                         for p in (backend/folder).rglob("*") if p.suffix in {".f90", ".py", ".pyf"}}
        source_hashes["makefile"] = digest(backend/"makefile")
        lock = {"schema": "typed-tmd/external-lock/1", "backend": "arTeMiDe", "tag": "v2.05",
            "code_url": CODE_URL, "code_commit": CODE_COMMIT, "input_url": INPUT_URL, "input_commit": INPUT_COMMIT,
            "model": "SV19 DY NNLO with central NNPDF31 member 0", "model_selection": models,
            "source_files": source_hashes, "original_constants": {"path": CONSTANTS, "sha256": digest(backend/CONSTANTS)},
            "constant_changes": [{"key": list(k), "value": v} for k, v in changes.items()],
            "constants_sha256": digest(config), "refined_constants_sha256": digest(refined),
            "native_refinement": {"minimum_qT_sections": 64, "Q_y_tolerance": "1.0E-7"},
            "lhapdf": {"version": "6.5.5", "source_url": "https://lhapdf.hepforge.org/downloads/?f=LHAPDF-6.5.5.tar.gz",
                "source_sha256": "641d5ea0942b79e4447e15e5a33491ff3c7032d71d618119935e14ad27f5e3a5", "source_bytes": 946776},
            "parameter_source": {"path": REPLICAS, "sha256": digest(backend/REPLICAS), "row": "0 (published mean)"},
            "fixed_parameter_vector": FIXED, "pdf_set": PDF, "pdf_member": 0, "pdf_inputs": pdf_inputs,
            "dataset_file": "DataLib/unpolDY/A8-00y04.csv",
            "dataset_sha256": digest(inputs/"DataLib/unpolDY/A8-00y04.csv"),
            "upstream_license": "CC BY-NC-SA 4.0; external code fetched separately, not relicensed",
            "dataprocessor_license": "no explicit license located at pin; fetch only, no source redistribution"}
        write_json(out/"external.lock.json", lock)
        run("compiler_version", [compiler, "--version"])
        run("lhapdf_version", [lha/"bin/lhapdf-config", "--version"])
        if sys.platform == "darwin":
            run("native_linkage", ["otool", "-L", backend/"harpy"/libraries[0].name])
        write_json(out/"runtime.json", {"backend_dir": str(backend), "inputs_dir": str(inputs), "config": str(config),
            "refined_config": str(refined), "python": str(prefix/"bin/python"), "pdf_data_path": str(cache/"pdfsets"),
            "native_library_sha256": digest(backend/"harpy"/libraries[0].name), "compiler": str(compiler),
            "lhapdf_libraries": [{"name": p.name, "sha256": digest(p), "bytes": p.stat().st_size}
                                  for p in (lha/"lib").glob("libLHAPDF*") if p.is_file() and not p.is_symlink()],
            "lhapdf_prefix": str(lha), "platform": platform.platform(), "flags": flags, "openmp": False,
            "environment": {k: env[k] for k in ("SDKROOT", "MACOSX_DEPLOYMENT_TARGET", "LDFLAGS") if k in env}})
        write_json(out/"summary.json", {"status": "passed", "scope": "external build and input preparation only; no physics gate"})
    except BaseException as exc:
        write_json(out/"failure_summary.json", {"status": "failed", "error": str(exc)})
        raise


if __name__ == "__main__":
    main()
