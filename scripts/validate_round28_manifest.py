#!/usr/bin/env python
from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT
DEFAULT_SOURCE_INCLUDE_GLOBS = ("src/graph_skill_runtime/**/*.py",)
DEFAULT_SOURCE_EXCLUDE_GLOBS: tuple[str, ...] = ()
def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _fail(errors: list[str], code: str, detail: str) -> None:
    errors.append(f"{code}: {detail}")


def _features(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        return [feature for feature in data["features"] if isinstance(feature, dict)]
    if isinstance(data, dict) and data.get("id"):
        return [data]
    return []


def _source_map(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict) and isinstance(data.get("source_file_map"), dict):
        return data["source_file_map"]
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        return data
    return None


def _contract_map(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict) and {"public_api_symbols", "skill_spec_sections", "consumer_files"} <= data.keys():
        return data
    return None


def _source_globs(source_map: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    config = source_map.get("config") if isinstance(source_map, dict) else None
    if not isinstance(config, dict):
        return list(DEFAULT_SOURCE_INCLUDE_GLOBS), list(DEFAULT_SOURCE_EXCLUDE_GLOBS)
    include_globs = config.get("include_globs") or list(DEFAULT_SOURCE_INCLUDE_GLOBS)
    exclude_globs = config.get("exclude_globs") or list(DEFAULT_SOURCE_EXCLUDE_GLOBS)
    return [str(pattern) for pattern in include_globs], [str(pattern) for pattern in exclude_globs]


def _glob_repo_files(patterns: list[str]) -> set[str]:
    files: set[str] = set()
    for pattern in patterns:
        files.update(
            path.relative_to(REPO_ROOT).as_posix()
            for path in REPO_ROOT.glob(pattern)
            if path.is_file()
        )
    return files


def _actual_src_files(source_map: dict[str, Any] | None = None) -> set[str]:
    include_globs, exclude_globs = _source_globs(source_map)
    return _glob_repo_files(include_globs) - _glob_repo_files(exclude_globs)


def _public_api_symbols() -> set[str]:
    contract = (REPO_ROOT / "docs/public-api-contract.md").read_text(encoding="utf-8")
    return {
        match.group(1)
        for match in re.finditer(r"^## ([A-Za-z_][A-Za-z0-9_]*)$", contract, re.MULTILINE)
        if match.group(1) != "Coverage"
    }


def _declared_public_api_symbols() -> set[str]:
    tree = ast.parse((REPO_ROOT / "src/graph_skill_runtime/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, list) and all(isinstance(symbol, str) for symbol in value):
                return set(value)
    raise ValueError("src/graph_skill_runtime/__init__.py must declare a literal string __all__ list")


def _error_codes() -> set[str]:
    text = (REPO_ROOT / "docs/skill-spec/11-error-code-spec.md").read_text(encoding="utf-8")
    codes = set(re.findall(r"`(\[F-v3-[a-z0-9-]+\])`", text))
    return {code for code in codes if "<" not in code and "*" not in code}


def _callback_events() -> set[str]:
    tree = ast.parse((PACKAGE_ROOT / "src/graph_skill_runtime/callbacks/events.py").read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Event") and node.name != "_EventBase"
    }


def _runtime_compat_files() -> set[str]:
    files: set[str] = set()
    patches_root = PACKAGE_ROOT / "src/graph_skill_runtime/patches"
    if patches_root.exists():
        files.update(path.relative_to(REPO_ROOT).as_posix() for path in patches_root.rglob("*.py"))
    return files


def _validate_collectable_tests(features: list[dict[str, Any]], errors: list[str]) -> None:
    nodeids = [nodeid for feature in features for nodeid in feature.get("targeted_tests", [])]
    if not nodeids:
        return
    result = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q", *nodeids],
        cwd=PACKAGE_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        _fail(errors, "R28_TARGETED_TEST_UNCOLLECTABLE", result.stdout + result.stderr)


def _validate_features(features: list[dict[str, Any]], errors: list[str], *, full_manifest: bool) -> None:
    error_owners: dict[str, str] = {}
    event_owners: dict[str, str] = {}
    for feature in features:
        feature_id = str(feature.get("id", "<missing-feature>"))
        for code in feature.get("error_codes_primary", []):
            if code in error_owners:
                _fail(errors, "R28_PRIMARY_OWNER_DUPLICATE", f"{code} owned by {error_owners[code]} and {feature_id}")
            error_owners[code] = feature_id
        for event in feature.get("events_primary", []):
            if event in event_owners:
                _fail(errors, "R28_PRIMARY_OWNER_DUPLICATE", f"{event} owned by {event_owners[event]} and {feature_id}")
            event_owners[event] = feature_id

        for section in feature.get("skill_spec_sections", []):
            path_text, _, anchor = str(section).partition("#")
            target = REPO_ROOT / path_text
            if not anchor or not target.exists():
                _fail(errors, "R28_SKILL_SPEC_ANCHOR_MISSING", section)

    if full_manifest:
        missing_errors = sorted(_error_codes() - set(error_owners))
        missing_events = sorted(_callback_events() - set(event_owners))
        if missing_errors:
            _fail(errors, "R28_PRIMARY_OWNER_MISSING", "missing error code owners: " + ", ".join(missing_errors[:5]))
        if missing_events:
            _fail(errors, "R28_PRIMARY_OWNER_MISSING", "missing event owners: " + ", ".join(missing_events[:5]))

        runtime_files = _runtime_compat_files()
        covered = {
            entry["path"]
            for feature in features
            for entry in feature.get("core_paths", [])
            if isinstance(entry, dict) and entry.get("path") in runtime_files
        }
        runtime_feature_ids = {
            str(feature.get("id"))
            for feature in features
            if "runtime-compatibility" in str(feature.get("id"))
            or "compatibility" in str(feature.get("description", "")).lower()
        }
        runtime_feature_paths = {
            entry["path"]
            for feature in features
            if str(feature.get("id")) in runtime_feature_ids
            for entry in feature.get("core_paths", [])
            if isinstance(entry, dict)
        }
        if not runtime_files <= covered or not runtime_files <= runtime_feature_paths:
            _fail(errors, "R28_RUNTIME_COMPAT_FEATURE_MISSING", "patch files missing runtime compatibility feature")

    _validate_collectable_tests(features, errors)


def _validate_source_map(source_map: dict[str, Any], features: list[dict[str, Any]], errors: list[str]) -> None:
    entries = [entry for entry in source_map.get("files", []) if isinstance(entry, dict)]
    paths = [str(entry.get("path")) for entry in entries if isinstance(entry.get("path"), str)]
    mapped = set(paths)
    duplicates = sorted(path for path, count in Counter(paths).items() if count > 1)
    if duplicates:
        _fail(errors, "R28_SOURCE_FILE_DUPLICATE", "duplicate source files: " + ", ".join(duplicates[:5]))
    actual_src_files = _actual_src_files(source_map)
    config = source_map.get("config")
    complete_inventory = isinstance(config, dict) and config.get("complete_inventory") is True
    if complete_inventory or not features:
        missing = sorted(actual_src_files - mapped)
        stale = sorted(mapped - actual_src_files)
        if missing:
            _fail(errors, "R28_SOURCE_FILE_UNMAPPED", "missing source files: " + ", ".join(missing[:5]))
        if stale:
            _fail(errors, "R28_SOURCE_FILE_STALE", "stale source files: " + ", ".join(stale[:5]))

    feature_core_paths: dict[str, set[str]] = {}
    for feature in features:
        feature_core_paths[str(feature.get("id"))] = {
            entry["path"]
            for entry in feature.get("core_paths", [])
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }

    owners_by_path: dict[str, set[str]] = {}
    for entry in entries:
        path = str(entry.get("path"))
        if entry.get("classification") == "debt" and not entry.get("exemption_id"):
            _fail(errors, "R28_DEBT_EXEMPTION_REQUIRED", path)
        if entry.get("classification") == "feature":
            feature_ids = {str(feature_id) for feature_id in entry.get("feature_ids", [])}
            owners_by_path[path] = feature_ids
            for feature_id in feature_ids:
                if features and feature_id not in feature_core_paths:
                    _fail(errors, "R28_SOURCE_OWNER_UNKNOWN", f"{path} names unknown feature {feature_id}")
                if path not in feature_core_paths.get(feature_id, set()):
                    _fail(errors, "R28_FEATURE_FILE_NOT_IN_CORE_PATHS", f"{path} not in {feature_id}.core_paths")
        elif entry.get("classification") == "detail":
            feature_id = str(entry.get("feature_id"))
            owners_by_path[path] = {feature_id}
            if features and feature_id not in feature_core_paths:
                _fail(errors, "R28_SOURCE_OWNER_UNKNOWN", f"{path} names unknown feature {feature_id}")

    if features:
        for feature_id, core_paths in feature_core_paths.items():
            for path in sorted(core_paths):
                if feature_id not in owners_by_path.get(path, set()):
                    _fail(errors, "R28_FEATURE_CORE_PATH_UNOWNED", f"{feature_id}.core_paths contains unowned {path}")


def _validate_contract_map(contract_map: dict[str, Any], errors: list[str]) -> None:
    symbols = set((contract_map.get("public_api_symbols") or {}).keys())
    declared = _declared_public_api_symbols()
    documented = _public_api_symbols()
    missing_public = sorted(declared - symbols)
    stale_public = sorted(symbols - declared)
    undocumented = sorted(declared - documented)
    stale_documentation = sorted(documented - declared)
    if missing_public:
        _fail(errors, "R28_PUBLIC_API_UNMAPPED", "missing public symbols: " + ", ".join(missing_public[:5]))
    if stale_public:
        _fail(errors, "R28_PUBLIC_API_MAP_STALE", "stale public symbols: " + ", ".join(stale_public[:5]))
    if undocumented:
        _fail(errors, "R28_PUBLIC_API_UNDOCUMENTED", "undocumented public symbols: " + ", ".join(undocumented[:5]))
    if stale_documentation:
        _fail(
            errors,
            "R28_PUBLIC_API_DOC_STALE",
            "documented non-public symbols: " + ", ".join(stale_documentation[:5]),
        )


def _validate_contract_feature_ids(contract_map: dict[str, Any], feature_ids: set[str], errors: list[str]) -> None:
    if not feature_ids:
        return
    referenced: set[str] = set()
    for entry in (contract_map.get("public_api_symbols") or {}).values():
        if isinstance(entry, dict):
            referenced.update(str(feature_id) for feature_id in entry.get("feature_ids", []))
    for entry in (contract_map.get("skill_spec_sections") or {}).values():
        if isinstance(entry, dict):
            referenced.update(str(feature_id) for feature_id in entry.get("feature_ids", []))
    for entry in contract_map.get("consumer_files", []):
        if isinstance(entry, dict):
            referenced.update(str(feature_id) for feature_id in entry.get("feature_ids", []))
    dangling = sorted(referenced - feature_ids)
    if dangling:
        _fail(
            errors,
            "R28_CONTRACT_FEATURE_DANGLING",
            "contract_map references unknown features: " + ", ".join(dangling),
        )


def _validate_cutover(data: dict[str, Any], errors: list[str]) -> None:
    cutover = data.get("cutover")
    if not isinstance(cutover, dict):
        return
    if int(cutover.get("dual_run_hours") or 0) < 24 or int(cutover.get("independent_main_green_prs") or 0) < 1:
        _fail(errors, "R28_CUTOVER_OVERLAP_ATTESTATION_MISSING", "cutover must attest 24h overlap and one green PR")


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: validate_round28_manifest.py <manifest.yaml> [...]", file=sys.stderr)
        return 2

    errors: list[str] = []
    loaded: list[tuple[Path, Any]] = [(Path(arg), _load_yaml(Path(arg))) for arg in argv]
    all_features: list[dict[str, Any]] = []
    source_maps: list[dict[str, Any]] = []
    contract_maps: list[dict[str, Any]] = []
    has_combined_manifest = False
    for _path, data in loaded:
        features = _features(data)
        if features:
            all_features.extend(features)
            has_combined_manifest = has_combined_manifest or (
                isinstance(data, dict) and "features" in data and "source_file_map" in data
            )
        if source_map := _source_map(data):
            source_maps.append(source_map)
        if contract_map := _contract_map(data):
            contract_maps.append(contract_map)
        if isinstance(data, dict):
            _validate_cutover(data, errors)

    full_manifest = bool(all_features) and not has_combined_manifest
    if all_features:
        _validate_features(all_features, errors, full_manifest=full_manifest)
    for source_map in source_maps:
        _validate_source_map(source_map, all_features, errors)
    for contract_map in contract_maps:
        _validate_contract_map(contract_map, errors)
        _validate_contract_feature_ids(contract_map, {str(feature.get("id")) for feature in all_features}, errors)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
