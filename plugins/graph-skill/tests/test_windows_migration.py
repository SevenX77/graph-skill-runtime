"""Causal regressions for migrating owned AppData installs to shared host paths."""

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import install  # noqa: E402
import ownership  # noqa: E402
import test_installer_discovery as fixtures  # noqa: E402
from locking import installer_lock  # noqa: E402
from ownership import InstallError, json_bytes  # noqa: E402


class MigrationTests(fixtures.Fixture):
    make_bundle = fixtures.InstallerTests.make_bundle
    report = fixtures.InstallerTests.report
    snapshot = fixtures.InstallerTests.snapshot

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
        self.legacy = self.home / "AppData/Local/GraphSkill"
        self.enterContext(patch.object(install, "legacy_state_root", return_value=self.legacy))
        with patch.object(install, "state_root", return_value=self.legacy):
            install.install(self.source, "auto", False, self.report(["codex", "claude"]))
        self.original = install.load_manifest(self.legacy)

    def migrate(self, dry_run=False):
        return install.install(self.source, "auto", dry_run, self.report(["codex", "claude"]))

    def test_migration_updates_real_resources_and_preserves_unrelated_data(self):
        config = self.home / ".claude.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        data["unrelated"] = {"keep": True}
        config.write_bytes(json_bytes(data))
        self.file("AppData/Local/GraphSkill/user-note.txt", b"keep")
        before = self.snapshot()
        result = self.migrate(True)
        self.assertEqual(result["migrated_from"], str(self.legacy))
        self.assertEqual(before, self.snapshot())
        self.migrate()
        current = install.load_manifest(self.state)
        self.assertTrue(Path(current["node"]).is_relative_to(self.state))
        self.assertTrue(Path(current["python"]).is_relative_to(self.state))
        for record in current["resources"]:
            content = Path(record["path"]).read_text(encoding="utf-8")
            self.assertNotIn(str(self.legacy).replace("\\", "\\\\"), content)
        self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["unrelated"], {"keep": True})
        self.assertFalse((self.legacy / "bin/graph-skill.cmd").exists())
        self.assertFalse((self.legacy / "bin/graph-skill").exists())
        self.assertEqual(install.status()["status"], "installed-files-present")
        with self.assertRaisesRegex(InstallError, "schema"):
            install.load_manifest(self.legacy)  # Old installer cannot adopt the migrated owner.
        self.migrate()  # Repeated install is idempotent after the cutover.
        legacy_release = self.legacy / "versions" / self.original["release"]
        self.assertTrue(legacy_release.exists())
        self.assertIn(str(legacy_release), install.cleanup(True)["inactive_releases"])
        install.cleanup(False)
        self.assertFalse(legacy_release.exists())
        self.assertEqual((self.legacy / "user-note.txt").read_bytes(), b"keep")
        install.uninstall(False)
        self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["unrelated"], {"keep": True})

    def test_changed_legacy_resource_blocks_migration_without_writes(self):
        self.file(".claude/skills/graph-skill/SKILL.md", b"user edit")
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "Managed file changed"):
            self.migrate()
        self.assertEqual(before, self.snapshot())

    def test_conflicting_new_owner_is_not_adopted(self):
        self.state.mkdir()
        (self.state / "install.json").write_bytes(json_bytes({
            **self.original, "resources": [],
        }))
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "Two active"):
            self.migrate()
        self.assertEqual(before, self.snapshot())

    def test_failed_migration_restores_old_owner_and_host_files(self):
        before = self.snapshot()
        real_replace = ownership.replace

        def fail_receipt(path, old, new):
            if path == self.legacy / "install.json" and new != old:
                raise OSError("injected migration write failure")
            real_replace(path, old, new)

        with patch.object(ownership, "replace", side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError, "injected"):
                self.migrate()
        after = self.snapshot()
        for name, content in before.items():
            self.assertEqual(after[name], content)
        self.assertFalse((self.state / "install.json").exists())
        self.migrate()  # Retry can use the validated, retained payload.

    def test_migration_rejects_older_bundle_and_undiscovered_previous_host(self):
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "not rediscovered"):
            install.install(self.source, "auto", False, self.report(["codex"]))
        self.assertEqual(before, self.snapshot())
        data = json.loads((self.source / "bundle.json").read_text(encoding="utf-8"))
        data["version"] = "0.9.0"
        (self.source / "bundle.json").write_bytes(json_bytes(data))
        before = self.snapshot()
        with self.assertRaisesRegex(InstallError, "older than installed"):
            self.migrate()
        self.assertEqual(before, self.snapshot())

    def test_old_installer_lock_blocks_migration_before_new_state_creation(self):
        report = self.report(["codex", "claude"])
        with installer_lock(self.legacy), patch.object(install, "discover", return_value=report), \
                patch.object(sys, "argv", ["installer", "install", str(self.source)]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(), 1)
        self.assertFalse(self.state.exists())

    def test_status_does_not_migrate_and_cleanup_cannot_delete_active_legacy(self):
        before = self.snapshot()
        self.assertEqual(install.status()["status"], "migration-required")
        for action in (install.cleanup, install.uninstall):
            with self.assertRaisesRegex(InstallError, "requires install/update migration"):
                action(False)
        self.assertEqual(before, self.snapshot())


class PathTests(unittest.TestCase):
    def test_current_root_does_not_depend_on_appdata(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "unavailable-package-view"}):
            self.assertEqual(install.state_root(), Path.home() / ".local/share/graph-skill")

    @unittest.skipUnless(os.name == "nt", "Windows registry PATH contract")
    def test_migrating_path_removes_only_owned_old_entry(self):
        old, new = Path("C:/old"), Path("C:/new")
        original = (f"user;{old / 'bin'};other", 2)
        with patch.object(install, "windows_path", return_value=original):
            result = install.path_plan(new, {"path_added": True}, False, old)
            self.assertEqual(result, (original, (f"{new / 'bin'};user;other", 2), True))
            result = install.path_plan(new, {"path_added": False}, False, old)
            self.assertIn(str(old / "bin"), result[1][0])
        with patch.object(install, "windows_path", return_value=("user", 2)):
            with self.assertRaisesRegex(InstallError, "Managed PATH entry changed"):
                install.path_plan(new, {"path_added": True}, False, old)


if __name__ == "__main__":
    unittest.main()
