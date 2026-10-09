"""Read-only client evidence and target selection, independent of provisioning."""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ownership import InstallError

TARGETS = ("codex", "claude")
APPX_FAMILIES = {
    "OpenAI.Codex_2p2nqsd0c76g0": "codex",
    "Claude_pzs8sxrjxfjjc": "claude",
}


def windows_packages(environment: dict[str, str]) -> list[dict]:
    """Query current-user package registration; never activate an application."""
    system_root = environment.get("SystemRoot") or environment.get("SYSTEMROOT")
    if not system_root:
        raise InstallError("SystemRoot is unavailable for Windows package discovery")
    executable = Path(system_root) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$items=@(Get-AppxPackage | Where-Object { "
        "$_.PackageFamilyName -in @('OpenAI.Codex_2p2nqsd0c76g0','Claude_pzs8sxrjxfjjc') "
        "} | Select-Object PackageFamilyName,InstallLocation,Version); "
        "ConvertTo-Json -InputObject $items -Compress"
    )
    # This 30-second limit bounds one OS inventory probe, not installation or
    # client execution. A timeout is reported as unknown, never as absence.
    result = subprocess.run(
        [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise InstallError(f"Windows package discovery failed: {result.stderr.strip()}")
    records = json.loads(result.stdout.lstrip("\ufeff"))
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise InstallError("Windows package discovery returned an invalid inventory")
    return records


def configuration(home: Path, target: str, environment: dict[str, str]) -> dict:
    """Describe this installer's profile boundary without opening host secrets."""
    variable, directory = ("CODEX_HOME", ".codex") if target == "codex" else ("CLAUDE_CONFIG_DIR", ".claude")
    default = home / directory
    value = environment.get(variable)
    requested = Path(value).expanduser().absolute() if value else default
    supported = requested.resolve() == default.resolve()
    return {
        "profile": str(requested),
        "source": variable if value else "default",
        "supported": supported,
        "destinations": (
            [str(home / ".codex/config.toml"), str(home / ".codex/hooks.json"), str(home / ".agents/skills")]
            if target == "codex"
            else [str(home / ".claude.json"), str(home / ".claude/settings.json"), str(home / ".claude/skills")]
        ) if supported else [],
    }


class Inventory:
    def __init__(self, home: Path, environment: dict[str, str], platform: str) -> None:
        self.home, self.environment, self.platform = home, environment, platform
        self.clients = {
            target: {"target": target, "evidence": [], "diagnostics": [],
                     "configuration": configuration(home, target, environment)}
            for target in TARGETS
        }

    def add(self, target: str, path: Path, kind: str, source: str, **metadata) -> bool:
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                return False
            if self.platform != "win32" and not os.access(path, os.X_OK):
                return False
            resolved = str(path.resolve())
        except FileNotFoundError:
            return False
        except OSError as exc:
            self.clients[target]["diagnostics"].append(f"Cannot inspect {path}: {exc}")
            return False
        entry = {"kind": kind, "source": source, "path": resolved, **metadata}
        if entry not in self.clients[target]["evidence"]:
            self.clients[target]["evidence"].append(entry)
        return True

    def cli(self, which) -> None:
        for target in TARGETS:
            try:
                found = which(target, path=self.environment.get("PATH", ""))
                if found:
                    self.add(target, Path(found), "cli", "PATH")
            except OSError as exc:
                self.clients[target]["diagnostics"].append(f"Cannot inspect PATH: {exc}")
            suffix = ".exe" if self.platform == "win32" else ""
            self.add(target, self.home / ".local/bin" / (target + suffix), "cli", "user-native-install")
        default = (self.home / ".local/bin")
        if self.platform == "win32":
            default = Path(self.environment.get("LOCALAPPDATA", str(self.home / "AppData/Local")))
            default /= "Programs/OpenAI/Codex/bin"
        codex_bin = Path(self.environment.get("CODEX_INSTALL_DIR", str(default)))
        self.add("codex", codex_bin / ("codex.exe" if self.platform == "win32" else "codex"),
                 "cli", "standalone-install")

    def windows(self, package_query) -> None:
        local = Path(self.environment.get("LOCALAPPDATA", str(self.home / "AppData/Local")))
        for target, path in (
            ("claude", local / "AnthropicClaude/Claude.exe"),
            ("claude", local / "Programs/Claude/Claude.exe"),
            ("codex", local / "Programs/Codex/Codex.exe"),
        ):
            self.add(target, path, "desktop", "desktop-install-location")
        try:
            packages = package_query(self.environment)
        except (OSError, ValueError, InstallError, subprocess.SubprocessError) as exc:
            for client in self.clients.values():
                client["diagnostics"].append(f"Windows package inventory unavailable: {exc}")
            return
        for package in packages:
            family = package.get("PackageFamilyName")
            target = APPX_FAMILIES.get(family)
            if target is None:
                continue
            try:
                self.appx(target, package)
            except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
                self.clients[target]["diagnostics"].append(f"Cannot inspect package {family}: {exc}")

    def appx(self, target: str, package: dict) -> None:
        location = Path(package["InstallLocation"])
        if not location.is_absolute():
            raise ValueError("package location must be absolute")
        manifest = ET.parse(location / "AppxManifest.xml")
        found = False
        for app in manifest.findall(".//{*}Application"):
            visual = app.find("./{*}VisualElements")
            if visual is None or visual.get("AppListEntry") == "none":
                continue
            relative = Path(app.get("Executable", "").replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
                raise ValueError("invalid package executable")
            path = location / relative
            if not path.resolve().is_relative_to(location.resolve()):
                raise ValueError("package executable escapes registered location")
            found = self.add(target, path, "desktop", "windows-package",
                             package_family=package["PackageFamilyName"],
                             application_id=app.get("Id", ""),
                             version=str(package.get("Version", ""))) or found
        if not found:
            raise ValueError("registered package has no accessible application executable")

    def macos(self, roots: list[Path]) -> None:
        for target, name in (("codex", "Codex"), ("claude", "Claude")):
            for base in roots:
                bundle = base / f"{name}.app"
                try:
                    self.macos_bundle(target, bundle)
                except FileNotFoundError:
                    if bundle.exists():
                        self.clients[target]["diagnostics"].append(f"Incomplete application bundle: {bundle}")
                except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException) as exc:
                    self.clients[target]["diagnostics"].append(f"Cannot inspect {bundle}: {exc}")

    def macos_bundle(self, target: str, bundle: Path) -> None:
        with (bundle / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        executable = info["CFBundleExecutable"]
        if not isinstance(executable, str) or not executable or Path(executable).name != executable:
            raise ValueError("invalid application executable")
        if not self.add(target, bundle / "Contents/MacOS" / executable, "desktop", "macos-bundle",
                        bundle_id=str(info.get("CFBundleIdentifier", ""))):
            raise ValueError("application bundle has no accessible executable")


def discover(
    *, home: Path | None = None, environment: dict[str, str] | None = None,
    platform: str | None = None, which=None, package_query=None, applications: list[Path] | None = None,
) -> dict:
    home = home if home is not None else Path.home()
    environment = dict(os.environ) if environment is None else environment
    platform = sys.platform if platform is None else platform
    inventory = Inventory(home, environment, platform)
    inventory.cli(shutil.which if which is None else which)
    if platform == "win32":
        inventory.windows(windows_packages if package_query is None else package_query)
    elif platform == "darwin":
        inventory.macos(applications if applications is not None else [Path("/Applications"), home / "Applications"])
    elif platform != "linux":
        for client in inventory.clients.values():
            client["diagnostics"].append(f"Native inventory is unavailable on {platform}")
    clients = inventory.clients
    for client in clients.values():
        client["status"] = "detected" if client["evidence"] else "unknown" if client["diagnostics"] else "not-detected"
    return {"schema": "graph-skill.client-discovery.v1", "platform": platform, "clients": list(clients.values())}


def select_targets(option: str, report: dict, previous: dict) -> list[str]:
    if option != "auto":
        targets = option.split(",")
        if not targets or len(set(targets)) != len(targets) or not set(targets).issubset(TARGETS):
            raise InstallError("--targets must be auto, codex, claude, or codex,claude")
        return targets
    unknown = [client["target"] for client in report["clients"] if client["status"] == "unknown"]
    if unknown:
        raise InstallError(f"Client discovery is incomplete for {', '.join(unknown)}. Run graph-skill detect; "
                           "resolve the diagnostic or select the intended --targets explicitly.")
    targets = [client["target"] for client in report["clients"] if client["status"] == "detected"]
    if not targets:
        raise InstallError("No Codex or Claude Code client detected. Install a client, or use --targets "
                           "for a verified nonstandard installation. No adapters were installed.")
    missing = set(previous.get("targets", [])) - set(targets)
    if missing:
        raise InstallError(f"Previously configured clients were not rediscovered: {', '.join(sorted(missing))}. "
                           "Existing adapters are preserved. Use --targets to explicitly choose the new target set.")
    return targets
