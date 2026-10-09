"""Offline regressions for toolkit target selection and explicit cache ownership."""

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import hosts
import install
import runtime_layout
from ownership import InstallError, digest, json_bytes


class LifecycleTests(unittest.TestCase):
    def test_install_summary_is_actionable_without_changing_machine_result(self):
        result = {"status": "installed", "version": "0.3.1", "targets": ["codex"]}
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["entry.py", "install", "--dry-run"]), patch.object(
            install, "install", return_value=result
        ), patch.object(install, "discover", return_value={"clients": [{"target": "codex", "status": "detected"}]}), \
                patch.object(install, "load_manifest", return_value={}), \
                patch.object(install, "assert_default_profiles"), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(install.main(), 0)
        self.assertEqual(json.loads(stdout.getvalue()), result)
        self.assertIn("0.3.1 is installed for Codex", stderr.getvalue())
        self.assertIn("Check now", stderr.getvalue())
        self.assertIn("Open a new terminal", stderr.getvalue())
        self.assertIn("Restart Codex", stderr.getvalue())
        self.assertNotIn("Restart Claude", stderr.getvalue())

    def test_interactive_summary_and_explicit_json(self):
        for json_requested in (False, True):
            stdout, stderr = io.StringIO(), io.StringIO()
            arguments = ["entry.py", "status"] + (["--json"] if json_requested else [])
            result = {"status": "not-installed"}
            with patch.object(sys, "argv", arguments), patch.object(install, "status", return_value=result), \
                    patch.object(stdout, "isatty", return_value=True), redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(install.main(), 0)
            self.assertEqual(bool(stdout.getvalue()), json_requested)
            if json_requested:
                self.assertEqual(json.loads(stdout.getvalue()), result)

    def test_upgrade_redetects_and_requires_explicit_removal(self):
        report = {"clients": [{"target": "codex", "status": "detected"}]}
        self.assertEqual(install.select_targets("auto", report, {"targets": ["codex"]}), ["codex"])
        self.assertEqual(install.select_targets("auto", report, {}), ["codex"])
        with self.assertRaisesRegex(InstallError, "not rediscovered"):
            install.select_targets("auto", report, {"targets": ["codex", "claude"]})
        self.assertEqual(install.select_targets("claude", report, {"targets": ["codex"]}), ["claude"])
        with self.assertRaises(InstallError):
            install.select_targets("codex,codex", report, {})

    def test_cleanup_summary_preserves_reasons_and_distinguishes_preview(self):
        for status, action in [("planned", "Would remove"), ("cleaned", "Removed")]:
            result = {"status": status, "inactive_releases": ["old"], "preserved": [
                {"path": "current", "reason": "active release or executing installer"}
            ]}
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                install.completion(result, "cleanup")
            self.assertIn(f"{action} 1 inactive cached release(s)", stderr.getvalue())
            self.assertIn("Kept current: active release or executing installer", stderr.getvalue())
            self.assertEqual("No changes were applied" in stderr.getvalue(), status == "planned")

    def test_unselected_host_override_does_not_block_install(self):
        with patch.dict(hosts.os.environ, {"CLAUDE_CONFIG_DIR": "/custom/claude", "CODEX_HOME": ""}):
            hosts.assert_default_profiles(["codex"])
            with self.assertRaisesRegex(InstallError, "CLAUDE_CONFIG_DIR"):
                hosts.assert_default_profiles(["claude"])

    def test_universal_mac_python_uses_process_architecture(self):
        for machine, expected in [("x86_64", "darwin-x64"), ("arm64", "darwin-arm64")]:
            with patch.object(runtime_layout.sys, "platform", "darwin"), patch.object(
                runtime_layout.platform, "machine", return_value=machine
            ), patch.object(runtime_layout.sysconfig, "get_platform", return_value="macosx-10.9-universal2"):
                self.assertEqual(runtime_layout.current_target(), expected)

    def test_cleanup_preserves_active_executing_unknown_and_modified_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            # macOS exposes its temp directory through the system /var symlink.
            state = Path(temporary).resolve()
            versions = state / "versions"
            versions.mkdir()
            active = versions / "0.3.0-aaaaaaaaaaaaaaaa"
            executing = versions / "0.2.1-bbbbbbbbbbbbbbbb"
            unknown = versions / "user-files"
            changed = versions / "0.2.0-cccccccccccccccc"
            data = {"version": "0.1.0"}
            raw = json_bytes(data)
            old = versions / ("0.1.0-" + digest(raw)[:16])
            for path in (active, executing, unknown, changed, old):
                path.mkdir()
                (path / "keep.txt").write_text("data")

            def package(path):
                if path != old:
                    raise InstallError("Unverified payload")
                return json.loads(raw), raw

            with patch.object(install, "state_root", return_value=state), patch.object(
                install, "load_manifest", return_value={"release": active.name}
            ), patch.object(install, "legacy_state_root", return_value=None), patch.object(
                install, "ROOT", executing
            ), patch.object(install, "package", side_effect=package
            ), patch.object(install, "verify_release"):
                planned = install.cleanup(True)
                self.assertEqual(planned["inactive_releases"], [str(old)])
                self.assertTrue(old.exists())
                result = install.cleanup(False)
                self.assertEqual(result["inactive_releases"], [str(old)])
                self.assertFalse(old.exists())
                self.assertTrue(all(path.exists() for path in (active, executing, unknown, changed)))


if __name__ == "__main__":
    unittest.main()
