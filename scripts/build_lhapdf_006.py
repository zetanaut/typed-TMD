#!/usr/bin/env python3
"""Build a pinned native LHAPDF library in a fresh user-selected prefix.

No Python binding or system package modification is needed for the external
Fortran experiment. Source archive is fetched from LHAPDF's official server.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import urllib.request

URL = "https://lhapdf.hepforge.org/downloads/?f=LHAPDF-6.5.5.tar.gz"
SHA256 = "641d5ea0942b79e4447e15e5a33491ff3c7032d71d618119935e14ad27f5e3a5"
SIZE = 946776


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    work, prefix = args.work.resolve(), args.prefix.resolve()
    work.mkdir(parents=True, exist_ok=False)
    if prefix.exists():
        raise ValueError("Use a fresh install prefix; existing libraries are preserved")
    receipt = {"url": URL, "sha256": SHA256, "bytes": SIZE, "version": "6.5.5", "commands": [],
               "documentation": "https://www.lhapdf.org/install.html", "status": "in_progress"}
    try:
        data = urllib.request.urlopen(URL, timeout=60).read()
        if len(data) != SIZE or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("LHAPDF source identity mismatch")
        archive = work/"LHAPDF-6.5.5.tar.gz"
        archive.write_bytes(data)
        with tarfile.open(archive) as source:
            source.extractall(work, filter="data")
        source_dir = work/"LHAPDF-6.5.5"
        for stage, argv in (("configure", ["./configure", "--prefix="+str(prefix), "--disable-python", "CXX=clang++"]),
                            ("build", ["make", "-j2"]), ("install", ["make", "install"])):
            start = time.perf_counter()
            with (work/(stage+".log")).open("w") as log:
                result = subprocess.run(argv, cwd=source_dir, stdout=log, stderr=subprocess.STDOUT)
            receipt["commands"].append({"argv": argv, "returncode": result.returncode, "seconds": time.perf_counter()-start})
            if result.returncode:
                raise RuntimeError(stage+" failed; see retained log")
        receipt.update(status="passed", prefix=str(prefix),
            native_libraries=[{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                              for p in (prefix/"lib").glob("libLHAPDF*") if p.is_file() and not p.is_symlink()])
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        (work/"build_receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")


if __name__ == "__main__":
    main()
