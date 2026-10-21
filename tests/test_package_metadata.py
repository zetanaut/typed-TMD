"""Check the version exposed by the import and the build metadata agree."""
from pathlib import Path
import tomllib
import unittest
import typed_tmd


class PackageMetadataTests(unittest.TestCase):
    def test_runtime_and_build_versions_agree(self):
        path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        metadata = tomllib.loads(path.read_text())
        self.assertEqual(typed_tmd.__version__, metadata["project"]["version"])
