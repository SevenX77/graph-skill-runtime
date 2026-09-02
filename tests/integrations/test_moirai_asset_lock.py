"""The MoirAI bundle's self-fingerprint gate.

This repo owns the MoirAI assets, so this repo is the only place that can prove
what they currently are. A downstream reader (``agent-harness``) keeps a
provenance record of this bundle's digest so a human can see, at review time,
which version it was reading; that record cannot verify itself — it has no copy
of the bundle to hash. Without the gate below, "the authoritative side changed
without being re-pinned turns the build red" was a sentence nobody had encoded.

Shape borrowed from ``go.sum`` and ``package-lock.json``'s ``integrity``: the
content hash is committed, and changing the content requires changing the
recorded hash **in the same reviewed change**, so a silent edit is impossible.
Auto-refresh is deliberately rejected — the whole value of the record is that a
person has to touch it and be seen doing so. The failure text naming its own
remediation command is borrowed from ``agent-harness``'s audited-doc hash lock.

The lock lives under ``tests/`` rather than beside the assets because the bundle
is a closed set: ``integration.json`` declares every member and
``PackagedMoiraiAssets`` rejects any file it does not declare, so a lock file
inside ``assets/moirai/`` would break the package it is meant to protect.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets

ASSET_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "graph_skill_runtime"
    / "integrations"
    / "assets"
    / "moirai"
)
LOCK_PATH = Path(__file__).with_name("moirai-asset-lock.json")
REMEDIATION = (
    "the MoirAI bundle changed; re-pin it in the same change with "
    "`uv run python scripts/repin_moirai_asset_lock.py`. If the digest being replaced "
    "was already published — merged to main, or recorded by a downstream reader — bump "
    "`integration.json.asset_version` too, so one anchor never names two contents"
)


def tree_digest(root: Path) -> tuple[str, int]:
    """Digest a whole directory, identically on every platform and checkout.

    Two hazards this deliberately avoids, because the digest is compared across
    machines and against a record kept in another repository:

    - Ordering by ``Path`` objects is NOT stable across platforms: ``PurePath``
      compares case-insensitively on Windows and case-sensitively on POSIX, so
      ``README.md`` sorts to a different position and the same tree yields two
      digests. The sort key is therefore the POSIX relative-path *string*.
    - Line endings are a property of the checkout, not of the content, so
      content is normalized to LF before hashing.

    The relative path is hashed alongside the bytes, and both are terminated,
    so renaming a file changes the digest and no concatenation of one file's
    tail with the next file's head can be mistaken for a different pair.
    """

    entries = sorted(
        (path.relative_to(root).as_posix(), path) for path in root.rglob("*") if path.is_file()
    )
    digest = hashlib.sha256()
    for relative_posix, path in entries:
        digest.update(relative_posix.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest(), len(entries)


def role_skill_relation() -> dict[str, list[str]]:
    """The role-to-skill mapping, the second fact the downstream reader pins.

    A digest alone cannot answer "does the reader still route the same skills to
    the same role", because the reader's own copy uses different skill ids. The
    relation is pinned separately so that question has a mechanical answer.
    """

    assets = PackagedMoiraiAssets()
    return {role_id: list(assets.role_skill_ids(role_id)) for role_id in assets.role_ids()}


def _load_lock() -> dict[str, object]:
    assert LOCK_PATH.is_file(), (
        f"missing {LOCK_PATH.name}: the MoirAI bundle must carry its own fingerprint record"
    )
    data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "the MoirAI asset lock must be a JSON object"
    return data


def test_bundle_digest_matches_the_committed_lock() -> None:
    """The authoritative bundle equals its recorded fingerprint."""

    lock = _load_lock()
    digest, file_count = tree_digest(ASSET_ROOT)

    assert lock.get("tree_digest") == digest, REMEDIATION
    assert lock.get("file_count") == file_count, REMEDIATION


def test_lock_names_the_asset_version_it_describes() -> None:
    """The version anchor is what makes the downstream provenance record readable.

    ``agent-harness`` records this bundle as ``graph-skill-runtime@<version>#<8
    hex>``. If the content changed while the anchor stayed put, that record
    would name one version and describe another, and a reviewer comparing the
    two repositories would have no way to notice.
    """

    lock = _load_lock()
    assert lock.get("asset_version") == PackagedMoiraiAssets().asset_version, REMEDIATION


def test_role_skill_relation_matches_the_committed_lock() -> None:
    """The role-to-skill routing equals its recorded shape."""

    assert _load_lock().get("role_skills") == role_skill_relation(), REMEDIATION


def test_digest_order_does_not_depend_on_platform_path_comparison(tmp_path: Path) -> None:
    """A mixed-case tree hashes the same on Windows and on POSIX.

    ``README.md`` versus ``agents.md`` is exactly the pair that sorts one way
    under case-insensitive ``PurePath`` comparison and the other way under a
    plain string sort, so the expected digest is constructed explicitly here
    rather than taken from the implementation.
    """

    (tmp_path / "README.md").write_bytes(b"upper")
    (tmp_path / "agents.md").write_bytes(b"lower")

    expected = hashlib.sha256()
    for name, body in (("README.md", b"upper"), ("agents.md", b"lower")):
        expected.update(name.encode("utf-8"))
        expected.update(b"\0")
        expected.update(body)
        expected.update(b"\0")

    assert tree_digest(tmp_path) == (expected.hexdigest(), 2)


def test_digest_ignores_the_checkout_line_ending(tmp_path: Path) -> None:
    """A CRLF checkout of the same content yields the same digest."""

    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    (lf / "a.md").write_bytes(b"one\ntwo\n")
    (crlf / "a.md").write_bytes(b"one\r\ntwo\r\n")

    assert tree_digest(lf) == tree_digest(crlf)
