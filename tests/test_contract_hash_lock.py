"""Byte lock over the documents this repository has sealed.

A `FROZEN` document is sealed by two carriers that must agree: the human-read
`status:` word in its frontmatter, and the SHA-256 digest recorded here. The
status word alone is a claim; only the digest makes silent drift impossible.
That is why `docs/skill-spec/01-PORTABLE-GSKILL-V1.md` stayed `audited-ready`
for as long as it did — the semantics were audited, but no machine held the
bytes.

Locking is not a prohibition on change. It forces every byte of change to be
an explicit, recorded decision: re-pin the digest in the same pull request
that edits the document, and say above the line what changed and on what
ruling or evidence. The failure message below prints the exact command that
produces the new digest.
"""

from __future__ import annotations

import hashlib
import string
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXEMPTIONS_PATH = Path(__file__).with_name("contract-exemptions.yaml")
SKILL_SPEC_DIR = REPO_ROOT / "docs" / "skill-spec"


def _repin_command(relative_path: str) -> str:
    """The exact shell command that prints the digest this table wants.

    Quoting is single-quotes-only inside a double-quoted ``-c`` argument, and
    the CR/LF normalization is spelled with ``chr()`` rather than escapes, so
    the printed line can be pasted into a shell unchanged.
    """
    return (
        're-pin with: uv run python -c "import hashlib,pathlib;'
        f"p=pathlib.Path('{relative_path}');"
        "print(hashlib.sha256(p.read_text(encoding='utf-8')"
        ".replace(chr(13)+chr(10),chr(10)).replace(chr(13),chr(10))"
        ".encode('utf-8')).hexdigest())\""
    )


EXPECTED_CONTRACT_HASHES = {
    "docs/mvp0/skill-spec/00-FORMAT-GROUND-TRUTH.md": "083f158bdb4c6ae3bea7b5b66ce1d57e1897a668c81dac757a2ddb2bf067af0e",
    "docs/mvp0/skill-spec/01-physical-layout.md": "9478f81d9d8552227c82c440f6b047dc587652fcaa21200b0f38e3a93dcd8cc4",
    "docs/mvp0/skill-spec/02-graph-md-spec.md": "d9202117a473cf055a58bcff29e454e7551a1438d1cecdd90ccac50e28646b6c",
    "docs/mvp0/skill-spec/03-logic-md-spec.md": "f979921e9076b14a499d5dff257c7728afbe741b4e1d2ab642bed3fb0a369298",
    "docs/mvp0/skill-spec/04-subgraph-md-spec.md": "2440be9949793cb5717ed1cb29712896c174fa71e8c1bfc48b41099a4ac33f3e",
    "docs/mvp0/skill-spec/05-agent-md-spec.md": "51541ec8a805313c840c518130fe4ccf3615507614c0acf256f68102602f5b05",
    "docs/mvp0/skill-spec/06-cognitive-template-spec.md": "8e7a942df4bef5f7c95812ec4a0886ee140a55c33ce49ff1b2328158d9203090",
    "docs/mvp0/skill-spec/07-mention-syntax-spec.md": "ed8802373a1169fc0e4482f458e164d4153687b8a9123ca41da4d0284eadcc8d",
    "docs/mvp0/skill-spec/08-resource-mechanisms-spec.md": "b52777065d6eb5a90a4e7be99d492b4e45f36317de80428dbb48499d59c6ad3b",
    "docs/mvp0/skill-spec/09-builtin-modules-spec.md": "dac431f0a28d11448ea72193814ad4cb1c4cdb36cc1e09cc6fb9dfb7c11413d1",
    "docs/mvp0/skill-spec/10-skill-resolver-protocol-spec.md": "9cc8f9a3df095623b67c74a353838c63825fae678e77a94593a18716cded660c",
    # Re-pinned 2026-08-19 (an-error-code-either-fires-or-leaves): the eleven
    # adjudicated-out zero-emitter codes left the table (decision doc
    # .kiro/specs/decision-2026-08-19-an-error-code-either-fires-or-leaves.md;
    # pre-release, no-backward-compat, registry + mvp1 table updated in the
    # same PR — same pattern as the 2026-08-15 event-family re-pin below).
    "docs/mvp0/skill-spec/11-error-code-spec.md": "5bcb4f70d864ae7d392fe1d4c357d0269c0b88424cc726c7f5a7762d7c024509",
    "docs/mvp0/skill-spec/12-compile-runtime-flow-spec.md": "0c632cbc7edbad3e741bf4a3676d08e68852ea2311f10624503d20f84d598223",
    "docs/mvp0/skill-spec/README.md": "dc16c4c4caade48e027700f91ce666779b07f9a053ed3b8bda9f957fa6053b30",
    # Re-pinned 2026-08-15 (PR E, legacy execution family removal): the
    # CallbackEvent union dropped the ten zero-emitter event classes
    # (ValidationPass/ValidationFail/Retry/RetryExhausted/ModelResolved/
    # FinishTask/AmbiguityReport/Heartbeat/ThreadCleanedUp/InternalError)
    # and the stale LLMFallbackEvent entry that never existed in code
    # (decision doc §5; pre-release, no-backward-compat, all consumers
    # updated in the same PR).
    "docs/mvp0/public-api-contract.md": "68075217ba4c57feff2a5dce9b4d4e506d2a52095a4b2e891f0558baa60cd243",
    "docs/mvp0/feature-compliance-checklist.md": "77ea3efd4c6dfed5a09f496a82a1ba7ff3d2832ad1dc92ba9ac1f5cb759dc5c7",
    # Re-pinned at the portable gSkill v1 cutover: the contract map can now
    # bind features to the implemented 01-PORTABLE-GSKILL-V1 sections instead
    # of the superseded v0.3 format document.
    "spec/round28-manifest-schema.yaml": "de27d0d2909f907fcd94ccfa14a282ca19f52fb8207e5f99a1eafb80fa72db81",
    # Sealed 2026-09-01 (F-T3): the current portable format contract moves
    # `audited-ready` -> `FROZEN`. Unlike every other entry above, this is not
    # an archive — it is the live contract the production reader implements,
    # and sealing it is the gate for handing single ownership of the engine to
    # this repository. It could only be sealed once the revisions that were
    # queued ahead of it had landed: D-T1 (#14) corrected §5.2's role-selection
    # chain to the 2026-08-31 user ruling, and D-T3 (#18) confirmed the
    # registry no longer depends on any section of this document. Change it
    # through the two paths its own preamble documents, never by removing this
    # line.
    "docs/skill-spec/01-PORTABLE-GSKILL-V1.md": "fa2f7f21fc9c4aa58c766fe3959ad7ee3039e064649a36b1a5695582f77154f1",
}


def _sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frontmatter_status(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("status:"):
            value = line.removeprefix("status:").strip()
            return value.split("（", 1)[0].split("(", 1)[0].strip()
    return None


def _load_hash_exemptions(
    exemptions_path: Path = EXEMPTIONS_PATH,
) -> set[tuple[str, str]]:
    """Approved (file, sha256) pairs.

    An exemption pins ONE approved set of bytes, not a file. Keying it by path
    alone — the shape this file used to have — would have turned every
    exemption into a permanent unlock: the named document could then drift
    again, and again, with the lock silent. The sibling engine-doc lock
    already pinned exact digests; the two mechanisms now agree.
    """
    data = yaml.safe_load(exemptions_path.read_text(encoding="utf-8")) or {}
    exemptions = data.get("exemptions", [])
    assert isinstance(exemptions, list), "contract exemptions must be a list"

    approved: set[tuple[str, str]] = set()
    for index, exemption in enumerate(exemptions):
        assert isinstance(exemption, dict), f"exemption #{index} must be a mapping"

        relative_path = exemption.get("file")
        if relative_path is None:
            continue

        approved_hash = exemption.get("sha256")
        assert isinstance(relative_path, str) and relative_path, (
            f"hash exemption #{index} must name the file it approves"
        )
        assert (
            isinstance(approved_hash, str)
            and len(approved_hash) == 64
            and all(character in string.hexdigits for character in approved_hash)
        ), f"hash exemption #{index} must pin one exact SHA-256 hex digest"
        assert exemption.get("reason"), f"hash exemption #{index} must include reason"
        assert exemption.get("pr"), f"hash exemption #{index} must include pr"
        assert exemption.get("pm_approval"), f"hash exemption #{index} must include pm_approval"

        approved.add((relative_path, approved_hash))
    return approved


def _collect_hash_drift(
    *,
    repo_root: Path,
    expected_hashes: Mapping[str, str],
    approved: set[tuple[str, str]],
) -> list[str]:
    drifted: list[str] = []
    for relative_path, expected_hash in expected_hashes.items():
        actual_hash = _sha256(repo_root / relative_path)
        if actual_hash != expected_hash and (relative_path, actual_hash) not in approved:
            drifted.append(
                f"{relative_path}: expected {expected_hash}, got {actual_hash}; "
                f"{_repin_command(relative_path)}"
            )
    return drifted


def test_contract_hashes_match_frozen_baseline_or_pm_exemption() -> None:
    drifted = _collect_hash_drift(
        repo_root=REPO_ROOT,
        expected_hashes=EXPECTED_CONTRACT_HASHES,
        approved=_load_hash_exemptions(),
    )

    assert not drifted, "Unapproved contract hash drift:\n" + "\n".join(drifted)


def test_every_frozen_skill_spec_document_is_hash_locked() -> None:
    """The two carriers of `FROZEN` must agree in both directions.

    A document whose frontmatter claims `FROZEN` without a digest here is an
    unbacked claim; a digest here for a document that no longer declares
    `FROZEN` is a lock nobody reads.

    Scoped to `docs/skill-spec/` on purpose. `docs/feature-compliance-checklist.md`
    also declares `FROZEN`, but it is a GENERATED view of `spec/features.yaml`
    and is guarded by regeneration equality in
    `tests/test_feature_traceability_matrix.py` — a stronger check than a byte
    digest, and one that survives every legitimate feature addition. Byte-locking
    a generated file would make each such addition require a re-pin for no added
    assurance.
    """
    locked = {
        relative_path
        for relative_path in EXPECTED_CONTRACT_HASHES
        if relative_path.startswith("docs/skill-spec/")
    }
    declared = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted(SKILL_SPEC_DIR.glob("*.md"))
        if _frontmatter_status(path) == "FROZEN"
    }

    assert locked == declared, (
        "docs/skill-spec FROZEN documents and the hash table must match exactly: "
        f"claimed but unlocked={sorted(declared - locked)}, "
        f"locked but not claiming FROZEN={sorted(locked - declared)}"
    )


def test_exemption_must_pin_one_exact_digest_with_owner_approval(tmp_path: Path) -> None:
    exemptions_path = tmp_path / "contract-exemptions.yaml"
    exemptions_path.write_text(
        'version: "1"\n'
        "exemptions:\n"
        '  - file: "docs/skill-spec/01-PORTABLE-GSKILL-V1.md"\n'
        '    sha256: "' + "1" * 64 + '"\n'
        '    reason: "Approved drift."\n'
        '    pr: "PR-1"\n',
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="pm_approval"):
        _load_hash_exemptions(exemptions_path)


def test_exemption_approves_only_the_exact_bytes_it_pinned(tmp_path: Path) -> None:
    document = tmp_path / "contract.md"
    document.write_text("sealed\n", encoding="utf-8")
    sealed_hash = _sha256(document)

    document.write_text("approved drift\n", encoding="utf-8")
    approved_hash = _sha256(document)
    expected = {"contract.md": sealed_hash}

    assert (
        _collect_hash_drift(
            repo_root=tmp_path,
            expected_hashes=expected,
            approved={("contract.md", approved_hash)},
        )
        == []
    )

    document.write_text("second, unapproved drift\n", encoding="utf-8")
    drifted = _collect_hash_drift(
        repo_root=tmp_path,
        expected_hashes=expected,
        approved={("contract.md", approved_hash)},
    )

    assert len(drifted) == 1
    assert "re-pin with" in drifted[0]
