"""Source relocation evidence crosses the real archive-to-process boundary."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "installer"))

from bundle import product_files  # noqa: E402


class BundleLayoutTests(unittest.TestCase):
    def test_product_inventory_resolves_source_modules_and_single_mod_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "runtime.whl"
            wheel.write_bytes(b"inventory-only wheel")
            files = product_files(wheel)
            missing = [name for name, path in files.items() if not path.is_file()]
            self.assertEqual(missing, [])
            self.assertIn("installer/entry/main.py", files)
            self.assertIn("installer/install/__init__.py", files)
            self.assertFalse(any(name.startswith("packaging/") for name in files))
            self.assertEqual(
                files["claude-mod/hooks/register.js"],
                ROOT / "adapters/claude/mod/hooks/register.js",
            )

    def test_materialized_installer_boots_in_isolated_mode_from_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            payload = work / "payload"
            wheel = work / "runtime.whl"
            wheel.write_bytes(b"inventory-only wheel")
            for name, path in product_files(wheel).items():
                if name.startswith("installer/"):
                    destination = payload / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, destination)
            unrelated = work / "unrelated"
            unrelated.mkdir()
            (unrelated / "install.py").write_text(
                "raise RuntimeError('ambient installer must not load')",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-X",
                    "utf8",
                    str(payload / "installer/entry/main.py"),
                    "detect",
                ],
                cwd=unrelated,
                capture_output=True,
                env=os.environ.copy(),
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            report = json.loads(result.stdout.decode("utf-8"))
            self.assertEqual(report["schema"], "graph-skill.client-discovery.v1")
            self.assertEqual({item["target"] for item in report["clients"]}, {"codex", "claude"})
            self.assertEqual(list(payload.glob("install.json")), [])


if __name__ == "__main__":
    unittest.main()
