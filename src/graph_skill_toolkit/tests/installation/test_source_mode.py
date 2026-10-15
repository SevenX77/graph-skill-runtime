"""Source-mode switching keeps one installer owner and restores both host projections."""

from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "installer"))

import hosts  # noqa: E402
import install  # noqa: E402
import mode  # noqa: E402
from ownership import InstallError, json_bytes  # noqa: E402


def fixture_tree(root: Path, *, test: bool) -> None:
    for skill in ("graph-skill", "graph-skill-canvas", *(("plugin-interface-lab",) if test else ())):
        file = root / "skills" / skill / "SKILL.md"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("tool {{TOOLKIT_COMMAND}} spec {{PORTABLE_SPEC}}\n", encoding="utf-8")
    mod_base = root / "dist" if test else root
    for member in hosts.CLAUDE_MOD_FILES:
        file = mod_base / member
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(member, encoding="utf-8")
    for name in ("server.mjs", "after-tool.mjs", "canvas.html", *(("interface-lab.html",) if test else ())):
        file = root / "dist" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("test " + name if test else "installed " + name, encoding="utf-8")
    if test:
        (root / "package.json").write_text('{"name":"graph-skill-toolkit","version":"0.3.5"}', encoding="utf-8")
        command = root / "bin/graph-skill.mjs"
        command.parent.mkdir(parents=True, exist_ok=True)
        command.write_text("// test command\n", encoding="utf-8")
        script = root / "scripts/build/main.mjs"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("// test fixture\n", encoding="utf-8")
        spec = root.parents[1] / "docs/skill-spec" / mode.SOURCE_SPEC
    else:
        spec = root / "references" / "portable-gskill.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("portable spec\n", encoding="utf-8")


class SourceModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.home = base / "home"
        self.state = self.home / ".local/share/graph-skill"
        self.release = self.state / "versions/0.3.5-aaaaaaaaaaaaaaaa"
        self.source = base / "repository/src/graph_skill_toolkit"
        self.home.mkdir()
        self.state.mkdir(parents=True)
        self.release.mkdir(parents=True)
        self.source.mkdir(parents=True)
        fixture_tree(self.release, test=False)
        fixture_tree(self.source, test=True)
        (self.release / "bundle.json").write_text("{}", encoding="utf-8")
        (self.home / ".codex").mkdir()
        (self.home / ".codex/config.toml").write_text("[unrelated]\nvalue = 1\n", encoding="utf-8")
        (self.home / ".claude.json").write_text('{"unrelated":"keep"}\n', encoding="utf-8")
        self.python = self.release / "runtimes/python/python.exe"
        self.node = self.release / "runtimes/node/node.exe"
        self.patches = (
            patch.object(Path, "home", return_value=self.home),
            patch.object(install, "state_root", return_value=self.state),
            patch.object(install, "verify_release"),
            patch.object(install, "runtime_python", return_value=self.python),
            patch.object(install, "runtime_node", return_value=self.node),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        resources = hosts.projections(
            self.home, self.release, self.python, self.node,
            ["codex", "claude"], self.release,
        ) + install.launchers(self.state, self.release, self.node)
        transaction, owned = install.plan(resources, {}, self.state)
        transaction.apply()
        self.manifest = {
            "schema": install.SCHEMA, "home": str(self.home), "version": "0.3.5",
            "release": self.release.name, "targets": ["codex", "claude"],
            "resources": owned,
        }
        (self.state / "install.json").write_bytes(json_bytes(self.manifest))
        self.installed_config = {
            path: path.read_bytes() for path in (
                self.home / ".codex/config.toml", self.home / ".codex/hooks.json",
                self.home / ".claude.json", self.home / ".claude/settings.json",
                self.home / ".agents" / "skills" / "graph-skill-canvas" / "SKILL.md",
                self.home / ".claude" / "skills" / "graph-skill-canvas" / "SKILL.md",
            )
        }

    def test_both_hosts_switch_to_test_and_restore_installed_paths(self) -> None:
        before = (self.home / ".codex/config.toml").read_bytes()
        self.assertEqual(mode.switch("installed", None, True)["changes"], [])
        preview = mode.switch("test", self.source, True)
        self.assertEqual(preview["status"], "planned")
        self.assertEqual((self.home / ".codex/config.toml").read_bytes(), before)
        result = mode.switch("test", self.source)
        self.assertEqual(result["targets"], ["codex", "claude"])
        self.assertEqual(install.load_manifest(self.state)["source_mode"], "test")
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(codex["mcp_servers"][hosts.SERVER]["args"], [str(self.source / "dist/server.mjs")])
        self.assertEqual(
            json.loads((self.home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"][hosts.SERVER]["args"],
            [str(self.source / "dist/server.mjs")],
        )
        settings = json.loads((self.home / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertIn(str(self.source / "dist/claude-mod"), settings["env"][hosts.PLUGIN_DIRS])
        skill_text = (self.home / ".claude" / "skills" / "graph-skill-canvas" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn((self.source / "bin/graph-skill.mjs").as_posix(), skill_text)
        # Test mode alone serves the Interface Lab and installs its Skill.
        self.assertEqual(codex["mcp_servers"][hosts.SERVER]["env"][hosts.INTERFACE_LAB_ENV], "1")
        claude_env = json.loads((self.home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"][hosts.SERVER]["env"]
        self.assertEqual(claude_env[hosts.INTERFACE_LAB_ENV], "1")
        lab_skills = [self.home / ".agents/skills/plugin-interface-lab/SKILL.md", self.home / ".claude/skills/plugin-interface-lab/SKILL.md"]
        self.assertTrue(all(path.is_file() for path in lab_skills))
        self.assertEqual(mode.source_status()["status"], "configured")
        self.assertEqual(mode.switch("test", self.source)["status"], "unchanged")
        (self.source / "dist/canvas.html").write_text("changed after selection", encoding="utf-8")
        self.assertEqual(mode.source_status()["status"], "configuration-changed")
        (self.source / "dist/server.mjs").unlink()
        mode.switch("installed", None)
        self.assertEqual(mode.source_status()["mode"], "installed")
        for path, content in self.installed_config.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        self.assertFalse(any(path.exists() for path in lab_skills))
        self.assertEqual(json.loads((self.home / ".claude.json").read_text(encoding="utf-8"))["unrelated"], "keep")

    def test_modified_managed_config_blocks_restore_without_overwriting(self) -> None:
        mode.switch("test", self.source)
        config = self.home / ".codex/config.toml"
        changed = config.read_bytes().replace(b"server.mjs", b"other-server.mjs")
        config.write_bytes(changed)
        before = (self.state / "install.json").read_bytes()
        with self.assertRaisesRegex(InstallError, "Managed block changed"):
            mode.switch("installed", None)
        self.assertEqual(config.read_bytes(), changed)
        self.assertEqual((self.state / "install.json").read_bytes(), before)

    def test_missing_build_asset_refuses_switch_before_mutation(self) -> None:
        missing = self.source / "dist/server.mjs"
        missing.unlink()
        before = (self.state / "install.json").read_bytes()
        with self.assertRaisesRegex(InstallError, "Build the test source first"):
            mode.switch("test", self.source)
        self.assertEqual((self.state / "install.json").read_bytes(), before)
        for path, content in self.installed_config.items():
            self.assertEqual(path.read_bytes(), content, str(path))


if __name__ == "__main__":
    unittest.main()
