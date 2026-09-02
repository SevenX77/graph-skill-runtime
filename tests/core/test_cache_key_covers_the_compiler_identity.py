"""A compile cache entry may only be replayed by the rules that minted it.

The cache key covers the skill files and the package version. Neither one moves
when a compile RULE changes meaning: the source tree is untouched, and the
package version is pinned through pre-release (every rule change so far shipped
under `0.1.0a1`). So an entry minted before a rule existed stayed reachable, and
`cache=True` replayed a stale "this skill compiles" verdict for a skill the new
rules reject — the cache answering a question it was never asked.

Found on the 2026-08-31 llm_role ruling: making the check unconditional stops
any NEW cache entry from recording a role-less success, but says nothing about
entries already on disk from before the upgrade.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from graph_skill_runtime.core.cache import compute_cache_key, get_cache_dir, save_to_cache
from graph_skill_runtime.core.compiler import CACHE_SCHEMA_VERSION, compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError

_EMPTY_SCHEMA = json.dumps({"type": "object", "properties": {}})


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _skill(root: Path, *, llm_role: str | None) -> None:
    _write(
        root / "SKILL.md",
        "---\nname: cache-identity\ndescription: Exercise the compile cache key.\n---\n",
    )
    _write(
        root / "graph.yaml",
        "schema_version: gskill.graph.v1\ngraph_id: root\ndescription: Cache identity graph.\n"
        f"io:\n  inputs:\n    {_EMPTY_SCHEMA}\n  outputs:\n    {_EMPTY_SCHEMA}\n"
        "phases:\n  - id: main\n    depends_on: [input]\n    output: true\n",
    )
    role_line = f"llm_role: {llm_role}\n" if llm_role is not None else ""
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"---\nname: main\n{role_line}"
        f"io:\n  inputs:\n    {_EMPTY_SCHEMA}\n  outputs:\n    {_EMPTY_SCHEMA}\n---\n"
        "<role>Cache</role>\n<goal>Exercise the cache key.</goal>\n",
    )


def _pre_bump_cache_key(root: Path) -> str:
    """The key exactly as the runtime computed it before the version was added.

    Spelled out here rather than imported, because the point is to stand in for
    a build of the runtime this test cannot import: an entry on disk from
    before the bump.
    """
    from graph_skill_runtime.core.cache import (
        _get_graph_skill_runtime_version,
        _skill_file_metadata,
    )

    resolved = root.resolve()
    payload = {
        "format": "portable-v1",
        "root": str(resolved),
        "python": list(sys.version_info[:3]),
        "package": _get_graph_skill_runtime_version(),
        "files": _skill_file_metadata(resolved),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.fixture
def isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # The real cache lives in the developer's home directory; a test must never
    # read or write that one.
    cache_dir = tmp_path / "cache-home"
    cache_dir.mkdir()
    monkeypatch.setattr("graph_skill_runtime.core.cache.get_cache_dir", lambda: cache_dir)
    return cache_dir


def test_cache_key_covers_the_rule_version_not_only_the_files(tmp_path: Path) -> None:
    root = tmp_path / "cache-identity"
    _skill(root, llm_role="analyst")

    same_files_new_rules = compute_cache_key(root, schema_version=CACHE_SCHEMA_VERSION + 1)
    same_files_same_rules = compute_cache_key(root, schema_version=CACHE_SCHEMA_VERSION)

    assert same_files_new_rules != same_files_same_rules
    assert compute_cache_key(root, schema_version=CACHE_SCHEMA_VERSION) == same_files_same_rules


def test_an_entry_minted_before_the_rule_existed_is_not_replayed(
    tmp_path: Path, isolated_cache_dir: Path
) -> None:
    # Stage exactly the situation an upgrade produces: a real, loadable success
    # snapshot sitting at the key the OLD runtime would have computed for this
    # very tree — a tree the new rules reject.
    root = tmp_path / "cache-identity"
    _skill(root, llm_role="analyst")
    healthy = compile_skill(root, cache=False)

    _skill(root, llm_role=None)

    # Control arm first, or this test could pass for the wrong reason: a
    # snapshot that simply fails to rehydrate is ignored whatever key it sits
    # under, and the real assertion below would prove nothing. Staged at the
    # CURRENT key, this exact snapshot IS replayed — and replaying it is
    # precisely the stale verdict the version exists to fence off.
    current_key = compute_cache_key(root, schema_version=CACHE_SCHEMA_VERSION)
    save_to_cache(current_key, healthy)
    assert compile_skill(root, cache=True) is not None, "fixture entry must be replayable"
    (isolated_cache_dir / f"{current_key}.json").unlink()

    stale_key = _pre_bump_cache_key(root)
    assert stale_key != current_key
    save_to_cache(stale_key, healthy)
    assert (isolated_cache_dir / f"{stale_key}.json").is_file(), "fixture must stage a real entry"

    with pytest.raises(SkillLoadError) as caught:
        compile_skill(root, cache=True)

    codes = {str(issue.rule_id) for issue in caught.value.compile_result.issues}
    assert "[F-v3-agent-llm-role-missing]" in codes, codes


def test_a_current_entry_is_still_reused(tmp_path: Path, isolated_cache_dir: Path) -> None:
    # The version is a correctness fence, not a way to disable caching: a
    # healthy skill compiled under the current rules still comes back from disk.
    root = tmp_path / "cache-identity"
    _skill(root, llm_role="analyst")

    compile_skill(root, cache=True)
    entries = list(isolated_cache_dir.glob("*.json"))

    assert [path.name for path in entries] == [
        f"{compute_cache_key(root, schema_version=CACHE_SCHEMA_VERSION)}.json"
    ]
    assert compile_skill(root, cache=True) is not None


def test_get_cache_dir_is_the_only_place_the_cache_location_is_decided() -> None:
    # The isolation fixture above patches exactly one function; that is only
    # sound while every reader and writer goes through it.
    source = Path(get_cache_dir.__code__.co_filename).read_text(encoding="utf-8")

    assert source.count("Path.home()") == 1
