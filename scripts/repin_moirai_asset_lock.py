"""Re-pin the MoirAI bundle's fingerprint record after an approved asset change.

Run it from the repo root:

    uv run python scripts/repin_moirai_asset_lock.py

It rewrites ``tests/integrations/moirai-asset-lock.json`` from the bundle as it
stands on disk and prints what moved. It is deliberately a separate, explicit
command rather than something the gate does for itself: the record only means
anything if a person changed it inside a reviewed change (the ``go.sum``
property). A gate that re-pinned itself would report every silent edit as green.

The digest and relation helpers are loaded from the gate module itself, so the
value written here and the value asserted there cannot drift apart.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = REPO_ROOT / "tests" / "integrations" / "test_moirai_asset_lock.py"


def _load_gate_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_moirai_asset_lock_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the gate module at {GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    gate = _load_gate_module()
    digest, file_count = gate.tree_digest(gate.ASSET_ROOT)
    from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets

    record = {
        "_meta": {
            "what": (
                "Content fingerprint of the MoirAI integration asset bundle, which this "
                "repository owns. agent-harness keeps a provenance record of these same "
                "values; the two must name the same asset_version and the same digest."
            ),
            "regenerate": "uv run python scripts/repin_moirai_asset_lock.py",
            "digest": (
                "sha256 over every file, ordered by POSIX relative path string, content "
                "normalized to LF, each path and body NUL-terminated"
            ),
        },
        "asset_version": PackagedMoiraiAssets().asset_version,
        "tree_digest": digest,
        "file_count": file_count,
        "role_skills": gate.role_skill_relation(),
    }

    lock_path = gate.LOCK_PATH
    previous = (
        json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    )
    lock_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for key in ("asset_version", "tree_digest", "file_count"):
        before = previous.get(key)
        after = record[key]
        if before != after:
            print(f"{key}: {before!r} -> {after!r}")
    if previous.get("role_skills") != record["role_skills"]:
        print("role_skills: changed")
    print(f"wrote {lock_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
