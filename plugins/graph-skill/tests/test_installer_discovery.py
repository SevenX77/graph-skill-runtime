"""Installer selection and owned writes in disposable homes; no client launches."""

from __future__ import annotations

import contextlib
import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import discovery  # noqa: E402
import hosts  # noqa: E402
import install  # noqa: E402
from ownership import InstallError, digest, json_bytes  # noqa: E402
from runtime_layout import current_target, executable_paths  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="graph-client-中文-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve()

    def file(self, relative, value=b"fixture"):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        path.chmod(0o755)
        return path

    def detect(self, **kwargs):
        options = {"home": self.home, "environment": {}, "platform": "win32",
                   "which": lambda *args, **kwargs: None, "package_query": lambda env: []}
        options.update(kwargs)
        return discovery.discover(**options)


class DiscoveryTests(Fixture):
    def test_stale_config_and_directories_are_not_clients(self):
        self.file(".codex/config.toml")
        self.file(".claude/settings.json")
        (self.home / ".local/bin/claude.exe").mkdir(parents=True)
        report = self.detect()
        self.assertEqual([c["status"] for c in report["clients"]], ["not-detected", "not-detected"])
        with self.assertRaisesRegex(InstallError, "No Codex or Claude"):
            discovery.select_targets("auto", report, {})

    def appx(self, target, *, hidden=False):
        family = next(family for family, name in discovery.APPX_FAMILIES.items() if name == target)
        executable = self.file(f"apps/{target}/app/client.exe")
        visibility = ' AppListEntry="none"' if hidden else ""
        manifest = (f'<Package xmlns="urn:appx"><Applications><Application Id="Main" '
                    f'Executable="app\\client.exe"><VisualElements{visibility}/>'
                    '</Application></Applications></Package>')
        self.file(f"apps/{target}/AppxManifest.xml", manifest.encode())
        return {"PackageFamilyName": family, "InstallLocation": str(executable.parent.parent), "Version": "1.2.3"}

    def test_desktop_only_windows_detects_both_without_path(self):
        packages = [self.appx("codex"), self.appx("claude")]
        with patch.object(subprocess, "run", side_effect=AssertionError("client must not run")):
            report = self.detect(package_query=lambda env: packages)
        self.assertEqual(discovery.select_targets("auto", report, {}), ["codex", "claude"])
        self.assertTrue(all(c["evidence"][0]["source"] == "windows-package" for c in report["clients"]))

    def test_hidden_helper_is_not_a_desktop_client(self):
        package = self.appx("codex", hidden=True)
        report = self.detect(package_query=lambda env: [package])
        self.assertEqual(report["clients"][0]["status"], "unknown")
        self.assertEqual(report["clients"][0]["evidence"], [])

    def test_duplicates_select_one_adapter_and_keep_evidence(self):
        executable = self.file(".local/bin/claude.exe")
        package = self.appx("claude")
        report = self.detect(which=lambda name, **kwargs: str(executable) if name == "claude" else None,
                             package_query=lambda env: [package])
        self.assertEqual(discovery.select_targets("auto", report, {}), ["claude"])
        self.assertEqual({e["kind"] for e in report["clients"][1]["evidence"]}, {"cli", "desktop"})

    def test_package_failure_is_unknown_and_explicit_selection_is_available(self):
        def unavailable(env):
            raise subprocess.TimeoutExpired("inventory", 30)
        report = self.detect(package_query=unavailable)
        self.assertEqual([c["status"] for c in report["clients"]], ["unknown", "unknown"])
        with self.assertRaisesRegex(InstallError, "incomplete"):
            discovery.select_targets("auto", report, {})
        self.assertEqual(discovery.select_targets("codex", report, {}), ["codex"])

    def test_registered_missing_executable_is_unknown(self):
        package = self.appx("claude")
        (Path(package["InstallLocation"]) / "app/client.exe").unlink()
        report = self.detect(package_query=lambda env: [package])
        self.assertEqual(report["clients"][1]["status"], "unknown")

    def test_package_executable_cannot_escape_location(self):
        package = self.appx("claude")
        manifest = Path(package["InstallLocation"]) / "AppxManifest.xml"
        manifest.write_text(manifest.read_text().replace("app\\client.exe", "../../outside.exe"))
        report = self.detect(package_query=lambda env: [package])
        self.assertIn("invalid package executable", report["clients"][1]["diagnostics"][0])

    def test_macos_desktop_bundles_require_actual_executable(self):
        self.file("Applications/Codex.app/Contents/MacOS/Codex")
        self.file("Applications/Codex.app/Contents/Info.plist",
                  plistlib.dumps({"CFBundleExecutable": "Codex", "CFBundleIdentifier": "fixture.codex"}))
        report = self.detect(platform="darwin", applications=[self.home / "Applications"])
        self.assertEqual(discovery.select_targets("auto", report, {}), ["codex"])
        (self.home / "Applications/Codex.app/Contents/MacOS/Codex").unlink()
        self.assertEqual(self.detect(platform="darwin", applications=[self.home / "Applications"])
                         ["clients"][0]["status"], "unknown")

    def test_linux_native_path_and_custom_codex_location(self):
        self.file(".local/bin/claude")
        executable = self.file("custom tools/codex")
        report = self.detect(platform="linux", environment={"CODEX_INSTALL_DIR": str(executable.parent)})
        self.assertEqual(discovery.select_targets("auto", report, {}), ["codex", "claude"])

    def test_windows_environment_case_and_probe_failure(self):
        result = subprocess.CompletedProcess([], 0, "[]", "")
        with patch.object(subprocess, "run", return_value=result) as run:
            self.assertEqual(discovery.windows_packages({"SYSTEMROOT": str(self.home)}), [])
            self.assertIn(str(self.home), run.call_args.args[0][0])
            self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}", "")):
            with self.assertRaisesRegex(InstallError, "invalid inventory"):
                discovery.windows_packages({"SYSTEMROOT": str(self.home)})


class InstallerTests(Fixture):
    def setUp(self):
        super().setUp()
        self.state = self.home / "product-state"
        self.source = self.home / "bundle"
        self.source.mkdir()
        self.enterContext(patch.object(Path, "home", return_value=self.home))
        self.enterContext(patch.object(install, "state_root", return_value=self.state))
        self.enterContext(patch.object(install, "path_plan", return_value=None))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.make_bundle()

    def make_bundle(self):
        paths = [*executable_paths(current_target()).values(), "runtime/runtime.whl"]
        for skill in ("graph-skill", "graph-skill-canvas"):
            paths.append(f"skills/{skill}/SKILL.md")
        content = b"private command {{GSKILL_COMMAND}}\n"
        for name in paths:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        info = {"schema": "graph-skill.toolkit-bundle.v2", "version": "1.0.0", "target": current_target(),
                "runtimes": {"executables": executable_paths(current_target())},
                "runtime_wheel": "runtime/runtime.whl", "files": {name: digest(content) for name in paths}}
        (self.source / "bundle.json").write_bytes(json_bytes(info))

    def report(self, targets):
        return {"schema": "graph-skill.client-discovery.v1", "clients": [
            {"target": t, "status": "detected" if t in targets else "not-detected"}
            for t in discovery.TARGETS
        ]}

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def test_install_codex_only_writes_selected_profile(self):
        self.file(".claude/settings.json", b'{"unrelated": true}')
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home / "custom-claude")}):
            result = install.install(self.source, "auto", False, self.report(["codex"]))
        self.assertEqual(result["targets"], ["codex"])
        self.assertTrue((self.home / ".codex/config.toml").is_file())
        self.assertEqual((self.home / ".claude/settings.json").read_bytes(), b'{"unrelated": true}')
        self.assertFalse((self.home / ".claude.json").exists())
        self.assertFalse((self.home / ".claude/skills").exists())

    def test_install_claude_only_preserves_codex_and_custom_codex_override(self):
        self.file(".codex/config.toml", b"unrelated = true\n")
        with patch.dict(os.environ, {"CODEX_HOME": str(self.home / "custom-codex")}):
            result = install.install(self.source, "auto", False, self.report(["claude"]))
        self.assertEqual(result["targets"], ["claude"])
        self.assertTrue((self.home / ".claude/skills/graph-skill/SKILL.md").is_file())
        self.assertEqual((self.home / ".codex/config.toml").read_bytes(), b"unrelated = true\n")
        self.assertFalse((self.home / ".agents").exists())

    def test_install_both_actual_owned_files_and_uninstall(self):
        self.file(".claude.json", b'{"mcpServers":{"other":{"command":"other"}}}')
        install.install(self.source, "auto", False, self.report(["codex", "claude"]))
        installed = install.load_manifest(self.state)
        self.assertEqual(installed["targets"], ["codex", "claude"])
        self.assertEqual(install.status()["status"], "installed-files-present")
        result = install.uninstall(False)
        self.assertEqual(result["status"], "uninstalled")
        self.assertFalse((self.home / ".agents/skills/graph-skill/SKILL.md").exists())
        self.assertEqual(json.loads((self.home / ".claude.json").read_text())["mcpServers"],
                         {"other": {"command": "other"}})

    def test_missing_or_unknown_discovery_leaves_no_product_state(self):
        for status in ("not-detected", "unknown"):
            report = self.report([])
            report["clients"][0]["status"] = status
            before = self.snapshot()
            with patch.object(install, "discover", return_value=report), \
                    patch.object(sys, "argv", ["installer", "install", str(self.source)]), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(install.main(), 1)
            self.assertEqual(before, self.snapshot())
            self.assertFalse(self.state.exists())

    def test_missing_prior_target_preserved_until_explicit_selection(self):
        install.install(self.source, "auto", False, self.report(["codex", "claude"]))
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "not rediscovered"):
            install.install(self.source, "auto", False, self.report(["codex"]))
        self.assertEqual(before, self.snapshot())
        install.install(self.source, "codex", False, self.report(["codex"]))
        self.assertFalse((self.home / ".claude/skills/graph-skill/SKILL.md").exists())
        self.assertEqual(install.load_manifest(self.state)["targets"], ["codex"])

    def test_edited_owned_resource_blocks_all_changes(self):
        install.install(self.source, "auto", False, self.report(["codex"]))
        self.file(".agents/skills/graph-skill/SKILL.md", b"user edit")
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "Managed file changed"):
            install.install(self.source, "auto", False, self.report(["codex", "claude"]))
        self.assertEqual(before, self.snapshot())

    def test_unmanaged_collision_blocks_all_changes(self):
        self.file(".claude.json", b'{"mcpServers":{"graph-skill-canvas":{"command":"user"}}}')
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "Unmanaged MCP"):
            install.install(self.source, "auto", False, self.report(["codex", "claude"]))
        self.assertEqual(before, self.snapshot())

    def test_selected_custom_profile_is_refused_before_writes(self):
        before = self.snapshot()
        with patch.dict(os.environ, {"CODEX_HOME": str(self.home / "elsewhere")}), \
                patch.object(install, "discover", return_value=self.report(["codex"])), \
                patch.object(sys, "argv", ["installer", "install", str(self.source)]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(), 1)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.state.exists())

    def test_dry_run_and_detect_do_not_write(self):
        before = self.snapshot()
        result = install.install(self.source, "auto", True, self.report(["codex"]))
        self.assertEqual(result["status"], "planned")
        with patch.object(install, "discover", return_value=self.report(["claude"])), \
                patch.object(sys, "argv", ["installer", "detect"]), contextlib.redirect_stdout(io.StringIO()) as output, \
                patch.object(output, "isatty", return_value=True):
            self.assertEqual(install.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["schema"], "graph-skill.client-discovery.v1")
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.state.exists())

    def test_older_source_does_not_replace_newer_installation(self):
        install.install(self.source, "auto", False, self.report(["codex"]))
        info = json.loads((self.source / "bundle.json").read_text())
        info["version"] = "0.9.0"
        (self.source / "bundle.json").write_bytes(json_bytes(info))
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "older than installed"):
            install.install(self.source, "auto", False, self.report(["codex"]))
        self.assertEqual(before, self.snapshot())

    def test_rejected_selection_is_explicit(self):
        for option in ("", "auto,codex", "codex,codex", "unknown"):
            with self.assertRaises(InstallError):
                discovery.select_targets(option, self.report(["codex"]), {})
        self.assertEqual(discovery.select_targets("claude", self.report([]), {}), ["claude"])
        with patch.dict(os.environ, {"CODEX_HOME": str(self.home / "elsewhere")}):
            self.assertFalse(discovery.configuration(self.home, "codex", dict(os.environ))["supported"])
            hosts.assert_default_profiles(["claude"])


if __name__ == "__main__":
    unittest.main()
