"""Byte lock over the documents this repository has sealed.

A `FROZEN` document is sealed by two carriers that must agree: the human-read
`status:` word in its frontmatter, and a SHA-256 digest recorded in
`tests/contract-seals.yaml`. The status word alone is a claim; only the
digest makes silent drift impossible. That is why
`docs/skill-spec/01-PORTABLE-GSKILL-V1.md` stayed `audited-ready` for as long
as it did — the semantics were audited, but no machine held the bytes.

**The digest lives in the governance file, not here.** Until F-T3 this module
carried an `EXPECTED_CONTRACT_HASHES` constant, which made re-pinning a code
edit: `.github/CODEOWNERS` covers the governance file but not this one, so an
author could change a sealed document, update the constant, leave the
governance file empty, and pass every gate without an owner ever seeing a
record. That is a route around the state machine, whose only
transition out of `FROZEN` is "改动需 exemption"
(`docs/development/design-doc-standards/01-writing-standard.md` §1.2-§1.3).
Moving the pin into the record file removes the route rather than documenting
it away: there is now exactly ONE way to change a sealed document, and it
produces a reviewable record by construction.

Locking is not a prohibition on change. It forces every byte of change to be
an explicit, recorded decision: append a record naming the new digest, the
reason, the PR and the owner approval, in the same pull request that edits the
document. The failure message below prints the exact command that produces the
new digest.
"""

from __future__ import annotations

import hashlib
import re
import string
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SEALS_PATH = Path(__file__).with_name("contract-seals.yaml")

# The record format this loader understands. A governance file with no version,
# or a version this code was not written against, is not "probably fine" — it is
# a file whose meaning is unknown, and reading it anyway is how a format change
# turns into a silently weakened lock.
SUPPORTED_SEALS_VERSION = "1"

# Exactly the keys a seal record may carry. Strict in both directions: a record
# missing one is incomplete governance, and a record carrying an unknown one is
# either a typo (so a required field is silently absent) or a leftover from the
# path-keyed shape this file used to have, whose records the loader used to skip
# with `continue` — governance that enters the repository and is never read.
_REQUIRED_SEAL_KEYS = frozenset(
    {"exemption_id", "file", "sha256", "reason", "pr", "pm_approval"}
)
_OPTIONAL_SEAL_KEYS = frozenset({"expires_or_cleanup"})
_TOP_LEVEL_KEYS = frozenset({"version", "seals"})
_SEAL_ID_PATTERN = re.compile(r"^EX-[0-9]{4}-[a-z0-9-]+$")
_FRONTMATTER_FENCE = "---"

# The complete list of sealed files that do NOT declare `status: FROZEN`, named
# one by one. "Any file without frontmatter may be sealed" was the earlier rule
# and it is an OPEN category: it lets anything lacking a `status:` line be
# sealed without ever making the human-read claim, which hollows out the second
# direction of the bijection — "sealed but not FROZEN is red" would then be
# unenforceable against exactly the files that never say anything. A closed set
# has to be edited, in a diff, to grow — and the bijection test also requires
# every member to hold a current seal record, so widening the set and filing the
# governance record are the same pull request, reviewed together. Without that
# second direction the allowlist alone would be a green pre-authorisation.
#
# `spec/round28-manifest-schema.yaml` is in it for two reasons, both concrete:
#   * it is a JSON-Schema document, not prose — there is no frontmatter for a
#     human-read `status:` word to live in, and inventing one would change the
#     bytes the schema's own consumers parse;
#   * `tests/test_round28_contract_manifests.py::
#     test_task7_hash_lock_detects_mutated_schema_fixture` mutates that schema
#     and requires THIS module to fail and name it, so dropping its seal would
#     delete a guard that is currently working.
SEALED_WITHOUT_STATUS_CARRIER = frozenset({"spec/round28-manifest-schema.yaml"})


def _repin_command(relative_path: str) -> str:
    """The exact shell command that prints the digest a new record must carry.

    One line, no heredoc: this is the command a Windows maintainer pastes into
    PowerShell, where a bash here-document is a parse error (see
    `docs/CROSS_PLATFORM.md`). Quoting is single-quotes-only inside the
    double-quoted ``-c`` argument, and the CR/LF normalization is spelled with
    ``chr()`` rather than escapes, so the printed line survives being copied
    verbatim into either shell.
    """
    return (
        'uv run python -c "import hashlib,pathlib;'
        f"p=pathlib.Path('{relative_path}');"
        "print(hashlib.sha256(p.read_text(encoding='utf-8')"
        ".replace(chr(13)+chr(10),chr(10)).replace(chr(13),chr(10))"
        ".encode('utf-8')).hexdigest())\""
    )


def _sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frontmatter_status(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return None
    for line in lines[1:]:
        if line.strip() == _FRONTMATTER_FENCE:
            return None
        if line.startswith("status:"):
            value = line.removeprefix("status:").strip()
            return value.split("（", 1)[0].split("(", 1)[0].strip()
    return None


def _assert_seal_shape(seal: object, *, index: int) -> dict[str, Any]:
    """Reject anything this loader could not fully understand, loudly."""
    where = f"seal record #{index}"
    assert isinstance(seal, dict), f"{where} must be a mapping"

    keys = set(seal)
    missing = sorted(_REQUIRED_SEAL_KEYS - keys)
    assert not missing, f"{where} is missing required key(s): {missing}"
    extra = sorted(keys - _REQUIRED_SEAL_KEYS - _OPTIONAL_SEAL_KEYS)
    assert not extra, (
        f"{where} carries unknown key(s) {extra}; allowed keys are "
        f"{sorted(_REQUIRED_SEAL_KEYS)} plus optional {sorted(_OPTIONAL_SEAL_KEYS)}"
    )
    for key in sorted(keys):
        value = seal[key]
        assert isinstance(value, str) and value.strip(), (
            f"{where} field {key!r} must be a non-empty string"
        )

    seal_id = seal["exemption_id"]
    assert _SEAL_ID_PATTERN.fullmatch(seal_id), (
        f"{where} exemption_id {seal_id!r} must match EX-NNNN-<lowercase-slug>"
    )
    digest = seal["sha256"]
    assert len(digest) == 64 and all(character in string.hexdigits for character in digest), (
        f"{where} sha256 must be a 64-character SHA-256 hex digest"
    )
    return seal


def _load_seals(
    seals_path: Path = SEALS_PATH, *, repo_root: Path = REPO_ROOT
) -> list[dict[str, Any]]:
    """Every seal record, in file order, with the schema enforced fail-closed.

    Nothing is skipped. A record this loader cannot understand is a record an
    owner may believe is in force, so an unreadable one raises instead of
    quietly dropping out of the set.
    """
    assert seals_path.exists(), f"seal record file missing: {seals_path}"
    data = yaml.safe_load(seals_path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict), "seal records must be a mapping"

    unknown_top = sorted(set(data) - _TOP_LEVEL_KEYS)
    assert not unknown_top, (
        f"unknown top-level key(s) {unknown_top} in {seals_path.name}; this file holds "
        f"exactly {sorted(_TOP_LEVEL_KEYS)}. Feature-retirement exemptions belong in "
        "tests/contract-exemptions.yaml, whose shape the round-28 schema owns."
    )
    version = data.get("version")
    assert isinstance(version, str) and version.strip(), (
        f"{seals_path.name} must declare a non-empty string `version`"
    )
    assert version == SUPPORTED_SEALS_VERSION, (
        f"{seals_path.name} declares version {version!r}, but this loader reads "
        f"{SUPPORTED_SEALS_VERSION!r}; update the loader in the same change that "
        "changes the format, rather than reading records whose meaning it does not know"
    )
    assert "seals" in data, f"{seals_path.name} must declare a `seals` list"
    seals = data["seals"]
    assert isinstance(seals, list), "`seals` must be a list"

    seen_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, entry in enumerate(seals):
        seal = _assert_seal_shape(entry, index=index)
        seal_id = seal["exemption_id"]
        assert seal_id not in seen_ids, f"seal record #{index} reuses exemption_id {seal_id!r}"
        seen_ids.add(seal_id)

        relative_path = seal["file"]
        candidate = Path(relative_path)
        assert not candidate.is_absolute() and ".." not in candidate.parts, (
            f"seal record #{index} file must be a repository-relative path: {relative_path!r}"
        )
        assert (repo_root / candidate).is_file(), (
            f"seal record #{index} seals {relative_path!r}, which is not a file in this repository"
        )
        records.append(seal)
    return records


def _current_seal_by_file(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The last record for each file — list order is time order."""
    current: dict[str, dict[str, Any]] = {}
    for seal in records:
        current[seal["file"]] = seal
    return current


def _collect_seal_drift(*, repo_root: Path, current: dict[str, dict[str, Any]]) -> list[str]:
    drifted: list[str] = []
    for relative_path, seal in sorted(current.items()):
        actual = _sha256(repo_root / relative_path)
        if actual != seal["sha256"]:
            drifted.append(
                f"{relative_path}: sealed as {seal['sha256']} by {seal['exemption_id']}, "
                f"now {actual}. Append a new seals record (exemption_id, file, sha256, "
                "reason, pr, pm_approval) in the same PR as the edit; read the digest "
                f"with: {_repin_command(relative_path)}"
            )
    return drifted


def _tracked_files(repo_root: Path) -> list[Path]:
    """Every file git tracks, which is the honest definition of "this repository".

    Asking git beats re-deriving the ignore rules: a hand-written exclusion list
    drifts, and the direction it drifts in is silence — a `FROZEN` document in a
    directory the list forgot would simply never be checked. If git cannot
    answer, this raises; a machine without git is a broken checkout, not a
    supported mode.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    return [repo_root / name.decode("utf-8") for name in result.stdout.split(b"\0") if name]


def _declared_frozen_files(repo_root: Path) -> set[str]:
    frozen: set[str] = set()
    for path in _tracked_files(repo_root):
        if not path.is_file():
            continue
        if _frontmatter_status(path) == "FROZEN":
            frozen.add(path.relative_to(repo_root).as_posix())
    return frozen


def _seals_without_a_frozen_claim(repo_root: Path, sealed: set[str]) -> list[str]:
    """Sealed files that neither declare `FROZEN` nor sit in the closed exemption set."""
    return sorted(
        relative_path
        for relative_path in sealed
        if relative_path not in SEALED_WITHOUT_STATUS_CARRIER
        and _frontmatter_status(repo_root / relative_path) != "FROZEN"
    )


def test_sealed_documents_still_hash_to_their_current_seal() -> None:
    drifted = _collect_seal_drift(
        repo_root=REPO_ROOT, current=_current_seal_by_file(_load_seals())
    )

    assert not drifted, "Unrecorded drift in a sealed document:\n" + "\n".join(drifted)


def test_frozen_declarations_and_seal_records_are_the_same_set() -> None:
    """The two carriers of `FROZEN` must agree, repository-wide, both ways.

    A document whose frontmatter claims `FROZEN` without a seal record is an
    unbacked claim; a record for a document that does not claim `FROZEN` is a
    lock contradicting its own subject.

    The only files exempt from the second direction are the ones named in
    `SEALED_WITHOUT_STATUS_CARRIER`, and they are named individually rather
    than described by a property, so the exemption cannot widen by accident.
    Every member of that set must itself hold a current seal record: an entry
    with no record would be an allowlist slot standing open, approved ahead of
    the change it would excuse.
    """
    sealed = set(_current_seal_by_file(_load_seals()))
    declared = _declared_frozen_files(REPO_ROOT)

    unbacked = sorted(declared - sealed)
    assert not unbacked, (
        "these documents declare `status: FROZEN` but have no seal record in "
        f"{SEALS_PATH.name}: {unbacked}"
    )

    unsealed_allowlist = sorted(SEALED_WITHOUT_STATUS_CARRIER - sealed)
    assert not unsealed_allowlist, (
        "every path in SEALED_WITHOUT_STATUS_CARRIER must carry a current seal record; "
        "otherwise a path could be added to the allowlist ahead of the change it would "
        f"excuse, and the gate would stay green with nothing to review: {unsealed_allowlist}"
    )

    contradicting = _seals_without_a_frozen_claim(REPO_ROOT, sealed)
    assert not contradicting, (
        "these files carry a seal record without declaring `status: FROZEN`; declare it, "
        "drop the record, or — only for a machine contract that has no frontmatter at all "
        f"— add the path to SEALED_WITHOUT_STATUS_CARRIER with its reason: {contradicting}"
    )


def _seal_fixture(tmp_path: Path) -> tuple[Path, str]:
    document = tmp_path / "contract.md"
    document.write_text("---\nstatus: FROZEN\n---\n\nsealed\n", encoding="utf-8")
    return document, _sha256(document)


def _good_record(digest: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "exemption_id": "EX-0001-contract",
        "file": "contract.md",
        "sha256": digest,
        "reason": "Approved drift.",
        "pr": "#1",
        "pm_approval": "Owner approved.",
    }
    record.update(overrides)
    return record


def test_seal_schema_rejects_the_path_keyed_shape_and_malformed_records(tmp_path: Path) -> None:
    """Every schema failure is loud. Silence is the defect being removed here."""
    _document, digest = _seal_fixture(tmp_path)
    seals_path = tmp_path / "contract-seals.yaml"

    def write(body: str) -> Path:
        seals_path.write_text(body, encoding="utf-8")
        return seals_path

    def dump(records: list[dict[str, object]]) -> str:
        return yaml.safe_dump({"version": "1", "seals": records}, sort_keys=False)

    # The point of this test: the previous loader dropped a record with no
    # `file` key via `continue`, so a whole governance file written in the old
    # path-keyed shape could enter the repository and be read as empty.
    legacy = (
        'version: "1"\n'
        "exemptions:\n"
        "  - exemption_id: EX-0001-legacy\n"
        '    hashes: ["contract.md"]\n'
        '    reason: "Approved drift."\n'
        '    pr: "#1"\n'
        '    pm_approval: "Owner approved."\n'
    )
    with pytest.raises(AssertionError, match="unknown top-level key"):
        _load_seals(write(legacy), repo_root=tmp_path)

    for key in sorted(_REQUIRED_SEAL_KEYS):
        record = _good_record(digest)
        del record[key]
        with pytest.raises(AssertionError, match="missing required key"):
            _load_seals(write(dump([record])), repo_root=tmp_path)

    with pytest.raises(AssertionError, match="unknown key"):
        _load_seals(write(dump([_good_record(digest, hashes=["contract.md"])])), repo_root=tmp_path)
    with pytest.raises(AssertionError, match="64-character SHA-256"):
        _load_seals(write(dump([_good_record(digest, sha256="deadbeef")])), repo_root=tmp_path)
    with pytest.raises(AssertionError, match="not a file in this repository"):
        _load_seals(
            write(dump([_good_record(digest, file="docs/never-existed.md")])), repo_root=tmp_path
        )
    with pytest.raises(AssertionError, match="EX-NNNN"):
        _load_seals(write(dump([_good_record(digest, exemption_id="EX-1-bad")])), repo_root=tmp_path)
    with pytest.raises(AssertionError, match="reuses exemption_id"):
        _load_seals(write(dump([_good_record(digest), _good_record(digest)])), repo_root=tmp_path)

    accepted = _load_seals(
        write(dump([_good_record(digest, expires_or_cleanup="Superseded by the runtime PR.")])),
        repo_root=tmp_path,
    )
    assert len(accepted) == 1


def test_seal_file_must_declare_a_version_this_loader_reads(tmp_path: Path) -> None:
    """A governance file with no version identity is a file of unknown meaning.

    Accepting it is how a later format change becomes a silently weakened lock:
    the records still parse, the fields still have the old names, and nothing
    says the reader and the writer disagree.
    """
    document = tmp_path / "contract.md"
    document.write_text("---\nstatus: FROZEN\n---\n\nsealed\n", encoding="utf-8")
    seals_path = tmp_path / "contract-seals.yaml"
    record = _good_record(_sha256(document))

    seals_path.write_text(yaml.safe_dump({"seals": [record]}, sort_keys=False), encoding="utf-8")
    with pytest.raises(AssertionError, match="non-empty string `version`"):
        _load_seals(seals_path, repo_root=tmp_path)

    seals_path.write_text(
        yaml.safe_dump({"version": "", "seals": [record]}, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="non-empty string `version`"):
        _load_seals(seals_path, repo_root=tmp_path)

    seals_path.write_text(
        yaml.safe_dump({"version": "2", "seals": [record]}, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="this loader reads"):
        _load_seals(seals_path, repo_root=tmp_path)

    seals_path.write_text(
        yaml.safe_dump(
            {"version": SUPPORTED_SEALS_VERSION, "seals": [record]}, sort_keys=False
        ),
        encoding="utf-8",
    )
    assert len(_load_seals(seals_path, repo_root=tmp_path)) == 1


def test_drift_needs_an_appended_record_and_the_last_record_wins(tmp_path: Path) -> None:
    """One approved digest per edit — and the newest record is the live seal."""
    document, first = _seal_fixture(tmp_path)

    seals: list[dict[str, Any]] = [_good_record(first)]
    assert _collect_seal_drift(repo_root=tmp_path, current=_current_seal_by_file(seals)) == []

    document.write_text("---\nstatus: FROZEN\n---\n\nrevised\n", encoding="utf-8")
    second = _sha256(document)
    drift = _collect_seal_drift(repo_root=tmp_path, current=_current_seal_by_file(seals))
    assert len(drift) == 1
    assert first in drift[0] and second in drift[0]
    assert _repin_command("contract.md") in drift[0]
    # Pastable into PowerShell: one line, no here-document, no redirection.
    assert "<<" not in drift[0] and "\n" not in _repin_command("contract.md")

    seals.append(
        _good_record(
            second,
            exemption_id="EX-0002-contract",
            reason="Revised on the 2026-09-02 ruling.",
            pr="#2",
        )
    )
    assert _collect_seal_drift(repo_root=tmp_path, current=_current_seal_by_file(seals)) == []

    # Reverting the document without withdrawing the record is drift too: the
    # live seal is the LAST record, not any record that ever existed.
    document.write_text("---\nstatus: FROZEN\n---\n\nsealed\n", encoding="utf-8")
    assert _collect_seal_drift(repo_root=tmp_path, current=_current_seal_by_file(seals)) != []


def test_only_the_named_files_may_be_sealed_without_declaring_frozen(tmp_path: Path) -> None:
    """The exemption is a list of paths, not a property a file can acquire.

    Under the earlier rule — "sealed is fine as long as the file declares no
    status" — any file without frontmatter could be sealed while never making
    the human-read claim, so "sealed but not FROZEN is red" could not be
    enforced against precisely the files that say nothing. Growing the
    exemption now requires editing a constant, in a diff.
    """
    (tmp_path / "spec").mkdir()
    schema = tmp_path / "spec" / "round28-manifest-schema.yaml"
    schema.write_text("features:\n  type: object\n", encoding="utf-8")
    silent = tmp_path / "untracked-machine-contract.yaml"
    silent.write_text("kind: something\n", encoding="utf-8")
    claimed = tmp_path / "contract.md"
    claimed.write_text("---\nstatus: FROZEN\n---\n\nsealed\n", encoding="utf-8")
    demoted = tmp_path / "demoted.md"
    demoted.write_text("---\nstatus: superseded\n---\n\nold\n", encoding="utf-8")

    # In the closed set, so sealing it without a `status:` word is allowed.
    assert "spec/round28-manifest-schema.yaml" in SEALED_WITHOUT_STATUS_CARRIER
    assert _seals_without_a_frozen_claim(tmp_path, {"spec/round28-manifest-schema.yaml"}) == []
    assert _seals_without_a_frozen_claim(tmp_path, {"contract.md"}) == []

    # Not in the closed set: having no frontmatter is not an excuse any more.
    assert _seals_without_a_frozen_claim(tmp_path, {"untracked-machine-contract.yaml"}) == [
        "untracked-machine-contract.yaml"
    ]
    # And a file that claims some other status stays red, as before.
    assert _seals_without_a_frozen_claim(tmp_path, {"demoted.md"}) == ["demoted.md"]

    # Reverse direction: a path may sit in the closed set only while it holds a
    # current seal record. Adding one ahead of the change it would excuse is a
    # pre-authorisation nobody reviews, so the live set is checked against the
    # live records.
    sealed_now = set(_current_seal_by_file(_load_seals()))
    assert SEALED_WITHOUT_STATUS_CARRIER <= sealed_now, sorted(
        SEALED_WITHOUT_STATUS_CARRIER - sealed_now
    )
