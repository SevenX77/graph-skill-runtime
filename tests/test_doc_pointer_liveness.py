"""Documentation pointers written by this repository must resolve to live documents.

The error catalog is reached in two hops: `ErrorPayload.doc_link` points at
`docs/skill-spec/11-error-code-spec.md`, and that catalog's "Owning spec"
column points at the section of a current contract that defines the legal
state each code guards. Both hops are published contract — a third-party
consumer follows them — so both must land on a document that is still
maintained (`living`) or sealed by an owner hash lock (`FROZEN`), at an anchor
that actually renders. Pointing either hop at a `superseded`/`retired`/
`drafted` document hands the consumer an explanation the project has disowned.

Every other documentation pointer in runtime source, scripts, and tools is
developer navigation. It does not have to be contract, but it must still name
a file that exists here. A pointer that resolves to nothing is not a weaker
reference; it is a false one, and it lends borrowed authority to whatever it
sits next to.

Both failure modes were live. The error registry declared 88 per-code pointers
into `docs/mvp1/**`, the superseded pre-extraction document set, while
`_with_catalog_metadata` unconditionally overwrote every one with the declared
SSOT — stale *and* discarded. Thirteen "Owning spec" cells pointed at a
superseded converter contract, at `docs/mvp1/**`, or at a bare source file
with no anchor at all. And sixteen citations across eleven source files named
pre-extraction Kiro spec artifacts (`PHASE2_DESIGN.md`, `PHASE3_DESIGN.md`,
`design.md`, `tasks.md`, `research.md`, `plan.md`, `deferred-items.md`,
`.kiro/specs/.../design.md`) or origin-repository documents that were never
carried over. Nothing mechanical could see any of it.

Extraction uses `ast` rather than a line regex, because two of those citations
were broken across lines — one inside a docstring, one across two `#` comment
lines — and no line-oriented scan could see either half as a path.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ERROR_REGISTRY_SOURCE = REPO_ROOT / "src" / "graph_skill_runtime" / "core" / "error_registry.py"
SKILL_SPEC_DIR = REPO_ROOT / "docs" / "skill-spec"
ERROR_CATALOG = SKILL_SPEC_DIR / "11-error-code-spec.md"
SOURCE_TREES = ("src", "scripts", "tools")

# The closed set a published contract pointer may land in. `living` = still
# maintained against the current implementation; `FROZEN` = audited,
# owner-stamped, and hash-locked. `drafted`, `audited-ready`, `superseded` and
# `retired` are all excluded: the first two are unfinished, the last two are
# explicitly disowned.
CONTRACT_DOC_STATUSES = frozenset({"living", "FROZEN"})


# The fixed text a row carries INSTEAD of a link when the code is registered
# in §10. A gap cell must equal it exactly — not merely contain it — because a
# cell that may carry anything else may carry a pointer, and a pointer in a
# cell that declares "no owner" is the contradiction this whole check exists
# to catch.
GAP_CELL_MARKER = "—（§10）"

# The label a §10 entry uses to introduce the files that emit its code, and
# the paths that follow, relative to the runtime package. Files, not line
# numbers: a line range is stale the moment anything above it moves, and the
# first version of this section proved it — two entries named ranges that had
# already drifted and omitted whole emitting modules. The set is derived from
# source and asserted against the entry, so it cannot drift again.
GAP_EMITTER_LABEL = "发出文件："
RUNTIME_PACKAGE = REPO_ROOT / "src" / "graph_skill_runtime"

# Exemption applies to BARE names only — a token with no directory in it. A
# token that carries a path (`docs/skill-spec/11-error-code-spec.md`) states
# where the document is and can therefore always be checked; nothing about it
# is ambiguous, so nothing exempts it. A bare name (`AGENT.md`) does not say
# where it lives, because it is not a citation at all: it is a file name the
# runtime resolves against a directory chosen later.
#
# A bare name is exempt ONLY when this code DEFINES it — a string literal
# exactly equal to the token, inside the value of an assignment or a parameter
# default, anywhere in the same trees this check scans. That covers the
# portable-format names (`loader.py` maps `"LOGIC.md"`/`"SUBGRAPH.md"`/
# `"AGENT.md"` to phase kinds and builds `skill_root / "SKILL.md"`), the example
# names a tool description quotes, and the archive-member names the release
# acceptance script asserts on.
#
# The exemption condition is exactly that: a literal definition exists in the
# scanned source. It is a convention that needs a human reviewer, not a proof.
# Deriving it beats a hand-written list only in where the bypass shows up —
# silencing a dead name requires adding a line of otherwise-unused constant to
# production source, which lands in the diff where review can see it, rather
# than one more name in a test-local list nobody rereads.
_DEFINED_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.\-]+\.md")


# A path-like token ending in `.md`, with an optional `#anchor`. The trailing
# boundary rejects a Python module path such as `...tools.md_to_json`, which an
# unbounded `\.md` would tokenize as `...tools.md`. Anchors contain CJK, so the
# anchor class is defined by its delimiters rather than by an ASCII whitelist.
_DOC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.\-/])"
    r"([A-Za-z0-9_.\-][A-Za-z0-9_.\-/]*\.md)(?![A-Za-z0-9_])"
    r"(?:#([^\s\"'`)\],]+))?"
)
# A path continued after a line break: the break follows a `/`, so rejoining is
# unambiguous. Both real cases in this repository have that shape.
_PATH_CONTINUATION_PATTERN = re.compile(r"/[ \t]*\n[ \t]*")
_MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^)\s]+)\)")
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.*)$")
_ANCHOR_STRIP_PATTERN = re.compile(r"[^\w\- ]", re.UNICODE)
_CATALOG_ROW_PATTERN = re.compile(r"^\| `(\[F-v3-[^`]+\])` \|")
_ERROR_CODE_PATTERN = re.compile(r"\[F-v3-[a-z0-9-]+\]")
_BACKTICKED_PATTERN = re.compile(r"`([^`]+)`")
# §10 registers a gap as a bullet, deliberately NOT as a `| `[F-v3-…]` |`
# table row: that row shape is the code table itself, and §1 allows each
# code exactly one such row in the whole document.
_GAP_ENTRY_PATTERN = re.compile(r"^- \*\*`(\[F-v3-[^`]+\])`\*\*")


def _heading_anchor(heading: str) -> str:
    """Slugify a markdown heading the way GitHub renders its anchor."""
    return _ANCHOR_STRIP_PATTERN.sub("", heading.strip().lower()).replace(" ", "-")


def _heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HEADING_PATTERN.match(line)
        if match:
            anchors.add(_heading_anchor(match.group(1)))
    return anchors


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


def _iter_prose(source: str) -> Iterator[str]:
    """Every string literal and comment block in one Python source file.

    String literals come from `ast`, so implicitly concatenated fragments and
    multi-line docstrings each arrive as ONE value — which is what lets a path
    broken across lines be seen whole. Comments are not in the AST, so they are
    read from the token stream and consecutive comment lines are joined into a
    block for the same reason.
    """
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value

    block: list[str] = []
    previous_line: int | None = None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if previous_line is not None and token.start[0] != previous_line + 1:
            yield "\n".join(block)
            block = []
        block.append(token.string.lstrip("#").strip())
        previous_line = token.start[0]
    if block:
        yield "\n".join(block)


def _defined_file_names(source_paths: list[Path]) -> frozenset[str]:
    """Bare markdown file names this code defines as data.

    A name qualifies when a string literal exactly equal to it appears inside
    the value of an assignment (including inside a collection or a path
    expression) or as a parameter default. Prose is not a definition, so a
    citation does not exempt itself by being written.
    """
    names: set[str] = set()
    for source_path in source_paths:
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
                values: list[ast.expr] = [node.value] if node.value is not None else []
            elif isinstance(node, ast.arguments):
                values = [
                    default
                    for default in [*node.defaults, *node.kw_defaults]
                    if default is not None
                ]
            else:
                continue
            for value in values:
                for inner in ast.walk(value):
                    if (
                        isinstance(inner, ast.Constant)
                        and isinstance(inner.value, str)
                        and _DEFINED_NAME_PATTERN.fullmatch(inner.value)
                    ):
                        names.add(inner.value)
    return frozenset(names)


def _iter_doc_tokens(source: str, defined_names: frozenset[str]) -> Iterator[tuple[str, str | None]]:
    for prose in _iter_prose(source):
        joined = _PATH_CONTINUATION_PATTERN.sub("/", prose)
        for match in _DOC_TOKEN_PATTERN.finditer(joined):
            token = match.group(1)
            if "/" not in token and token in defined_names:
                continue
            yield token, match.group(2)


def _resolve_doc(*, repo_root: Path, source_path: Path, pointer: str) -> Path | None:
    """A citation resolves against the repository root or its own directory."""
    for candidate in (repo_root / pointer, source_path.parent / pointer):
        if candidate.is_file():
            return candidate
    return None


def _contract_status_violation(
    target: Path, pointer: str, allowed: frozenset[str] = CONTRACT_DOC_STATUSES
) -> str | None:
    status = _frontmatter_status(target)
    if status in allowed:
        return None
    return (
        f"{pointer}: status {status!r} is not one of {sorted(allowed)}; "
        "a published contract pointer must name a maintained or hash-locked document"
    )


def _collect_source_violations(
    *,
    repo_root: Path,
    source_paths: list[Path],
    require_contract_status: bool,
    definition_paths: list[Path] | None = None,
) -> list[str]:
    """Check `source_paths`, resolving exemptions against `definition_paths`.

    The two differ when only part of the tree is under inspection: a name
    defined in one module is still a defined name when cited from another, so
    the definition scope stays the whole scanned tree.
    """
    violations: list[str] = []
    defined_names = _defined_file_names(sorted(definition_paths or source_paths))
    for source_path in sorted(source_paths):
        source = source_path.read_text(encoding="utf-8")
        for pointer, anchor in _iter_doc_tokens(source, defined_names):
            location = f"{source_path.relative_to(repo_root).as_posix()} -> {pointer}"
            target = _resolve_doc(
                repo_root=repo_root, source_path=source_path, pointer=pointer
            )
            if target is None:
                violations.append(f"{location}: no such document in this repository")
                continue
            if require_contract_status:
                violation = _contract_status_violation(target, pointer)
                if violation is not None:
                    violations.append(
                        f"{source_path.relative_to(repo_root).as_posix()} -> {violation}"
                    )
                    continue
            if anchor and anchor not in _heading_anchors(target):
                violations.append(f"{location}#{anchor}: no heading renders that anchor")
    return sorted(set(violations))


def _collect_markdown_violations(*, docs: list[Path]) -> list[str]:
    violations: list[str] = []
    for doc in sorted(docs):
        for match in _MARKDOWN_LINK_PATTERN.finditer(doc.read_text(encoding="utf-8")):
            link = match.group(1)
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            relative_path, _, anchor = link.partition("#")
            target = (doc.parent / relative_path).resolve() if relative_path else doc
            location = f"{doc.name} -> {link}"
            if not target.is_file():
                violations.append(f"{location}: no such document")
                continue
            if anchor and anchor not in _heading_anchors(target):
                violations.append(f"{location}: no heading renders that anchor")
    return sorted(set(violations))


def _catalog_owning_specs(catalog: Path) -> dict[str, str]:
    """Every registered code's "Owning spec" cell, in catalog order."""
    owning: dict[str, str] = {}
    for line in catalog.read_text(encoding="utf-8").splitlines():
        match = _CATALOG_ROW_PATTERN.match(line)
        if match is None:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        owning[match.group(1)] = cells[-1]
    return owning


def _catalog_registered_gaps(catalog: Path) -> dict[str, str]:
    """Codes the catalog declares as having no owning section yet (§10).

    An entry is its bullet plus any lines it wraps onto, joined back into one
    string, so a list that runs past the margin still parses.
    """
    gaps: dict[str, str] = {}
    in_section = False
    current: str | None = None
    for line in catalog.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.startswith("## 10.")
            current = None
            continue
        if not in_section:
            continue
        match = _GAP_ENTRY_PATTERN.match(line)
        if match is not None:
            current = match.group(1)
            gaps[current] = line[match.end() :].strip(" —-")
            continue
        if current is not None and line.startswith(("  ", "	")):
            gaps[current] += " " + line.strip()
            continue
        current = None
    return gaps


def _gap_entry_emitters(entry: str) -> set[str] | None:
    """The files a §10 entry declares as emitting its code, or None if unstated."""
    label_at = entry.find(GAP_EMITTER_LABEL)
    if label_at < 0:
        return None
    return set(_BACKTICKED_PATTERN.findall(entry[label_at + len(GAP_EMITTER_LABEL) :]))


def _error_code_aliases(registry_source: Path) -> dict[str, str]:
    """Module-level names in the registry that stand for exactly one code.

    There are none today: every emitter writes its code literally. The map is
    computed rather than assumed empty because the two failure directions are
    not symmetric. A file that stops naming its code literally disappears from
    the derived set and turns the entry red, which is safe. A NEW file that
    reaches the code only through a constant would be invisible to a
    literal-only scan and would agree with an entry that also omits it — green,
    and wrong.
    """
    aliases: dict[str, str] = {}
    for node in ast.parse(registry_source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if not _ERROR_CODE_PATTERN.fullmatch(value.value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                aliases[target.id] = value.value
    return aliases


def _local_code_names(tree: ast.Module, registry_aliases: dict[str, str]) -> dict[str, str]:
    """Names standing for an error code inside ONE module, as that module sees them.

    A registry constant does not keep its registry name on the way in. Three
    shapes rebind it, and a scan that only knows the registry's own spelling
    misses all three:

    * `from ...error_registry import CODE as _CODE` — the import's `asname`;
    * `import ...error_registry as registry` then `registry.CODE` — attribute
      access, matched below by attribute name rather than by the module alias,
      so any spelling of the module reference works;
    * `_CODE = CODE` — a plain rebinding after either of the above.

    The rebinding is followed exactly ONE level, resolved against a snapshot
    taken before any rebinding is recorded, so the depth cannot creep with
    source ordering. One level is enough for the question actually being
    asked. A longer chain has to start somewhere, and that somewhere is an
    import in this same file — `_B = _A` cannot exist without the `_A = CODE`
    above it — so the FILE is named by the first hop however many hops follow.
    Depth would only matter to a checker trying to name the emitting
    expression, and this one names the emitting file.
    """
    imported = dict(registry_aliases)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").rsplit(".", 1)[-1] == (
            "error_registry"
        ):
            for alias in node.names:
                if alias.name in registry_aliases:
                    imported[alias.asname or alias.name] = registry_aliases[alias.name]

    local = dict(imported)
    for node in ast.walk(tree):
        for target, code in _rebound_code_names(node, imported):
            local[target] = code
    return local


def _rebound_code_names(
    node: ast.AST, imported: dict[str, str]
) -> Iterator[tuple[str, str]]:
    """`_CODE = CODE` rebindings, resolved against the pre-rebinding snapshot."""
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    else:
        return
    value = node.value
    if not isinstance(value, ast.Name) or value.id not in imported:
        return
    for target in targets:
        if isinstance(target, ast.Name):
            yield target.id, imported[value.id]


def _emitting_files_by_code(
    *, package_root: Path = RUNTIME_PACKAGE, registry_source: Path = ERROR_REGISTRY_SOURCE
) -> dict[str, set[str]]:
    """Every runtime file that names each error code, keyed by code.

    The registry itself is excluded on purpose: it declares the vocabulary, so
    it names all 99 codes and emits none of them.
    """
    registry_aliases = _error_code_aliases(registry_source)
    emitters: dict[str, set[str]] = {}
    for path in sorted(package_root.rglob("*.py")):
        if path == registry_source:
            continue
        relative = path.relative_to(package_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = _local_code_names(tree, registry_aliases)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for code in _ERROR_CODE_PATTERN.findall(node.value):
                    emitters.setdefault(code, set()).add(relative)
            elif isinstance(node, ast.Name) and node.id in names:
                emitters.setdefault(names[node.id], set()).add(relative)
            elif isinstance(node, ast.Attribute) and node.attr in registry_aliases:
                emitters.setdefault(registry_aliases[node.attr], set()).add(relative)
    return emitters


def _owning_link_violations(code: str, link: str, catalog: Path) -> list[str]:
    """Every way one "Owning spec" link can fail to name a live contract section."""
    if "://" in link or link.startswith("mailto:"):
        return [
            f"{code} -> {link}: an owning spec must be a document in this repository, "
            "not an external address"
        ]
    relative_path, _, anchor = link.partition("#")
    target = (catalog.parent / relative_path).resolve()
    if target.parent != catalog.parent.resolve():
        return [
            f"{code} -> {link}: outside docs/skill-spec; an owning spec must be a "
            "current contract in this directory"
        ]
    if target == catalog.resolve():
        return [
            f"{code} -> {link}: points at this catalog; §1 gives the catalog the code "
            "semantics and the owning spec the rules of the checked object"
        ]
    if not target.is_file():
        return [f"{code} -> {link}: no such document"]
    status_violation = _contract_status_violation(target, link)
    if status_violation is not None:
        return [f"{code} -> {status_violation}"]
    if not anchor:
        return [f"{code} -> {link}: names a document but no section anchor"]
    if anchor not in _heading_anchors(target):
        return [f"{code} -> {link}: no heading renders that anchor"]
    return []


def _classify_owning_cell(
    code: str, cell: str, *, registered: set[str], catalog: Path
) -> tuple[list[str], str | None]:
    """Judge one row, returning its violations and which set it joins, if any.

    The gap branch tests the WHOLE cell for equality with the marker. Testing
    for the marker's presence and then inspecting the links found alongside it
    means every link shape the link check does not recognise — an external URL
    above all — rides along in a cell that claims to name no owner.
    """
    cell = cell.strip()
    if cell == GAP_CELL_MARKER:
        if code in registered:
            return [], "gap"
        return [
            f"{code}: carries the §10 marker but §10 does not register it; the marker "
            "is a pointer to that entry, not a way to leave the cell blank"
        ], None
    if code in registered:
        return [
            f"{code}: registered in §10 but its cell is {cell!r}; a registered gap's "
            f"cell must be exactly {GAP_CELL_MARKER!r}, with nothing else in it"
        ], None

    links = _MARKDOWN_LINK_PATTERN.findall(cell)
    if not links:
        return [f"{code}: names no owning section and is not registered in §10"], None
    if GAP_CELL_MARKER in cell:
        return [f"{code}: carries the §10 marker and a link at the same time"], None

    violations = [
        violation for link in links for violation in _owning_link_violations(code, link, catalog)
    ]
    return violations, None if violations else "owned"


def _collect_owning_spec_violations(*, catalog: Path) -> tuple[list[str], set[str], set[str]]:
    """Judge every catalog row against three mutually exclusive outcomes.

    A row either names an owner or declares that none exists — never both,
    never neither:

    * **owned** — the cell links into `docs/skill-spec/`, at a document whose
      status is in the closed set, at an anchor that renders, and not at this
      catalog itself (§1 separates code semantics from the contract that owns
      the checked object, so the catalog cannot own its own rules);
    * **gap** — the cell carries the `—（§10）` marker and NO link at all, and
      the code is registered in §10.

    Anything else is a violation. Dropping unrecognised links and calling the
    row "unowned" — the earlier shape — let a registered gap point back at a
    superseded document and stay green, because nothing rejected the link
    itself.
    """
    violations: list[str] = []
    owned: set[str] = set()
    gaps: set[str] = set()
    registered = set(_catalog_registered_gaps(catalog))

    for code, cell in _catalog_owning_specs(catalog).items():
        row_violations, outcome = _classify_owning_cell(
            code, cell, registered=registered, catalog=catalog
        )
        violations.extend(row_violations)
        if outcome == "owned":
            owned.add(code)
        elif outcome == "gap":
            gaps.add(code)

    return sorted(set(violations)), owned, gaps


def _python_sources(repo_root: Path) -> list[Path]:
    return [path for tree in SOURCE_TREES for path in (repo_root / tree).rglob("*.py")]


def test_error_registry_documentation_pointers_target_contract_documents() -> None:
    violations = _collect_source_violations(
        repo_root=REPO_ROOT,
        source_paths=[ERROR_REGISTRY_SOURCE],
        require_contract_status=True,
        definition_paths=_python_sources(REPO_ROOT),
    )

    assert not violations, (
        "The error registry may only name documents that are `living` or `FROZEN`; "
        "point the catalog pointer at the error-code SSOT instead:\n" + "\n".join(violations)
    )


def test_registered_error_codes_expose_a_contract_doc_link() -> None:
    from graph_skill_runtime.core.error_registry import ERROR_REGISTRY

    violations: list[str] = []
    for code, metadata in sorted(ERROR_REGISTRY.items()):
        pointer, _, anchor = metadata.doc_link.partition("#")
        target = REPO_ROOT / pointer
        if not target.is_file():
            violations.append(f"{code} -> {pointer}: no such document in this repository")
            continue
        status_violation = _contract_status_violation(target, pointer)
        if status_violation is not None:
            violations.append(f"{code} -> {status_violation}")
            continue
        if anchor and anchor not in _heading_anchors(target):
            violations.append(f"{code} -> {pointer}#{anchor}: no heading renders that anchor")

    assert not violations, "Registered error codes expose a dead doc_link:\n" + "\n".join(violations)


def test_error_catalog_owning_specs_resolve_to_a_contract_section() -> None:
    """The second hop is contract too: every code must name a real section.

    A code that has no owning section anywhere in `docs/skill-spec` is a
    specification gap, not a licence to point somewhere dead. §10 registers
    those explicitly, with the marker instead of a link, and the next test
    pins the two sets to the whole registry.
    """
    violations, _owned, _gaps = _collect_owning_spec_violations(catalog=ERROR_CATALOG)

    assert not violations, (
        "Error-catalog `Owning spec` cells must either link to a living/FROZEN "
        "docs/skill-spec section or carry the §10 marker with no link:\n"
        + "\n".join(violations)
    )


def test_owned_and_registered_gap_codes_partition_the_registry() -> None:
    """Owner and gap are exclusive and together cover every registered code."""
    from graph_skill_runtime.core.error_registry import ERROR_REGISTRY

    _violations, owned, gaps = _collect_owning_spec_violations(catalog=ERROR_CATALOG)
    registered_codes = set(ERROR_REGISTRY)

    assert owned & gaps == set(), f"a code cannot be both owned and a gap: {sorted(owned & gaps)}"
    assert owned | gaps == registered_codes, (
        "every registered code must either name an owning section or be registered "
        f"as a gap: missing={sorted(registered_codes - (owned | gaps))}, "
        f"unknown={sorted((owned | gaps) - registered_codes)}"
    )


def test_gap_entries_list_exactly_the_files_that_emit_the_code() -> None:
    """§10's "emitting files" are derived from source, not transcribed.

    Hand-copied coordinates were the defect this replaces: two entries named
    line ranges that had already drifted and omitted whole emitting modules —
    `exit_control.py`'s nudge-budget path, and five of the six files that emit
    `[F-v3-runtime-state-mapping-failed]`. A reader following a gap entry to
    find out what the missing contract has to cover was being handed a partial
    map. The equality is asserted in both directions, so an entry can neither
    omit a file nor keep one that no longer emits.
    """
    entries = _catalog_registered_gaps(ERROR_CATALOG)
    emitters = _emitting_files_by_code()

    violations: list[str] = []
    for code, entry in sorted(entries.items()):
        declared = _gap_entry_emitters(entry)
        if declared is None:
            violations.append(f"{code}: entry states no {GAP_EMITTER_LABEL!r}")
            continue
        derived = emitters.get(code, set())
        if not derived:
            violations.append(
                f"{code}: no file under src/graph_skill_runtime emits it, so there is "
                "nothing for a gap entry to point at"
            )
            continue
        if declared != derived:
            violations.append(
                f"{code}: entry lists {sorted(declared)}, source emits {sorted(derived)}"
            )

    assert not violations, (
        "§10 entries must list exactly the files that emit their code:\n" + "\n".join(violations)
    )


def test_gap_entry_emitter_check_reports_omissions_and_stale_files(tmp_path: Path) -> None:
    """Both directions of the equality fire, and a missing label is not silence."""
    entry = "— 缺：运行期契约尚未成文。发出文件：`runtime/state.py`、`io/artifact_manifest.py`。"

    assert _gap_entry_emitters(entry) == {"runtime/state.py", "io/artifact_manifest.py"}
    assert _gap_entry_emitters("— 缺：运行期契约尚未成文。") is None

    catalog = tmp_path / "11-error-code-spec.md"
    catalog.write_text(
        "---\nstatus: living\n---\n\n"
        "## 10. Gaps\n\n"
        "- **`[F-v3-wrapped]`** — 缺：契约未成文。发出文件：`a.py`、\n"
        "  `b.py`。\n"
        "- **`[F-v3-plain]`** — 缺：契约未成文。发出文件：`c.py`。\n",
        encoding="utf-8",
    )
    parsed = _catalog_registered_gaps(catalog)

    assert set(parsed) == {"[F-v3-wrapped]", "[F-v3-plain]"}
    # A list that wraps onto the next line is still one entry.
    assert _gap_entry_emitters(parsed["[F-v3-wrapped]"]) == {"a.py", "b.py"}
    assert _gap_entry_emitters(parsed["[F-v3-plain]"]) == {"c.py"}


def test_emitting_files_exclude_the_registry_and_follow_code_aliases(tmp_path: Path) -> None:
    """The derivation reads emission sites, not the declaration of the vocabulary."""
    aliases = _error_code_aliases(ERROR_REGISTRY_SOURCE)
    emitters = _emitting_files_by_code()

    # Today no module-level name in the registry stands for a single code, so
    # every emitter is found by its literal. If that changes, the map is what
    # keeps a constant-using emitter visible.
    assert aliases == {} or all(_ERROR_CODE_PATTERN.fullmatch(code) for code in aliases.values())
    assert not any(
        "error_registry.py" in files for files in emitters.values()
    ), "the registry declares all 99 codes and emits none of them"
    assert emitters["[F-v3-agent-exit-control-failed]"] == {"middleware/exit_control.py"}


def test_emitting_files_follow_registry_aliases_through_every_rebinding(tmp_path: Path) -> None:
    """A constant does not keep its registry name on the way into a module.

    The literal-only scan this replaces saw none of these shapes. A new file
    emitting through `import ... as _CODE` was invisible to the derivation,
    and an entry written by the same author would omit it too — the two sides
    agreeing on an incomplete answer, which is the one failure mode a
    both-directions equality cannot catch by itself.
    """
    package = tmp_path / "pkg"
    package.mkdir()
    registry = package / "error_registry.py"
    registry.write_text('ERROR_CODE_X = "[F-v3-x]"\nOTHER = "not a code"\n', encoding="utf-8")

    (package / "literal.py").write_text('DETAIL = "[F-v3-x] boom"\n', encoding="utf-8")
    (package / "asname.py").write_text(
        "from pkg.error_registry import ERROR_CODE_X as _CODE\n\n\n"
        "def emit() -> str:\n    return _CODE\n",
        encoding="utf-8",
    )
    (package / "module_alias.py").write_text(
        "import pkg.error_registry as registry\n\n\n"
        "def emit() -> str:\n    return registry.ERROR_CODE_X\n",
        encoding="utf-8",
    )
    (package / "rebound.py").write_text(
        "from pkg.error_registry import ERROR_CODE_X as _CODE\n\n"
        "_LOCAL = _CODE\n\n\n"
        "def emit() -> str:\n    return _LOCAL\n",
        encoding="utf-8",
    )
    (package / "two_hops.py").write_text(
        "from pkg.error_registry import ERROR_CODE_X as _CODE\n\n"
        "_ONE = _CODE\n_TWO = _ONE\n\n\n"
        "def emit() -> str:\n    return _TWO\n",
        encoding="utf-8",
    )
    (package / "unrelated.py").write_text('MESSAGE = "nothing to do with codes"\n', encoding="utf-8")

    emitters = _emitting_files_by_code(package_root=package, registry_source=registry)

    # `two_hops.py` is found even though the second hop is not followed: the
    # chain begins at an import in that same file, so the first hop names it.
    assert emitters["[F-v3-x]"] == {
        "literal.py",
        "asname.py",
        "module_alias.py",
        "rebound.py",
        "two_hops.py",
    }
    assert "unrelated.py" not in emitters.get("[F-v3-x]", set())
    assert "error_registry.py" not in emitters.get("[F-v3-x]", set())
    # A registry constant whose value is not a code binds nothing.
    assert _error_code_aliases(registry) == {"ERROR_CODE_X": "[F-v3-x]"}


def test_runtime_source_documentation_pointers_resolve() -> None:
    violations = _collect_source_violations(
        repo_root=REPO_ROOT,
        source_paths=_python_sources(REPO_ROOT),
        require_contract_status=False,
    )

    assert not violations, (
        "Source code cites documents this repository does not have:\n" + "\n".join(violations)
    )


def test_skill_spec_cross_references_resolve() -> None:
    violations = _collect_markdown_violations(docs=list(SKILL_SPEC_DIR.glob("*.md")))

    assert not violations, (
        "Skill-spec documents cross-reference sections that do not exist:\n" + "\n".join(violations)
    )


def test_pointer_check_reports_missing_files_archived_status_and_dead_anchors(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs" / "skill-spec"
    docs_root.mkdir(parents=True)
    (docs_root / "live.md").write_text(
        "---\nstatus: living\n---\n\n## 1. 使用规则\n", encoding="utf-8"
    )
    (docs_root / "archived.md").write_text(
        "---\nstatus: superseded（被 portable v1 取代）\n---\n\n# Archived\n", encoding="utf-8"
    )

    source_path = tmp_path / "src" / "registry.py"
    source_path.parent.mkdir()
    source_path.write_text(
        "A = 'docs/skill-spec/live.md#1-使用规则'\n"
        "B = 'docs/skill-spec/live.md#9-不存在的小节'\n"
        "C = 'docs/skill-spec/archived.md'\n"
        "D = 'docs/skill-spec/absent.md'\n",
        encoding="utf-8",
    )

    contract_violations = _collect_source_violations(
        repo_root=tmp_path,
        source_paths=[source_path],
        require_contract_status=True,
    )

    assert any("absent.md" in violation and "no such document" in violation for violation in contract_violations)
    assert any("archived.md" in violation and "superseded" in violation for violation in contract_violations)
    assert any("9-不存在的小节" in violation for violation in contract_violations)
    assert not any("live.md#1-使用规则" in violation for violation in contract_violations)

    navigation_violations = _collect_source_violations(
        repo_root=tmp_path,
        source_paths=[source_path],
        require_contract_status=False,
    )

    assert not any("archived.md" in violation for violation in navigation_violations)
    assert any("absent.md" in violation for violation in navigation_violations)


def test_pointer_check_sees_paths_broken_across_lines_and_bare_relative_names(
    tmp_path: Path,
) -> None:
    """The two shapes a line-oriented regex could not see.

    Both were real: a docstring path split after a `/`, and a citation written
    as a bare filename with no directory at all.
    """
    source_path = tmp_path / "src" / "residue.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        '"""Module.\n'
        "\n"
        "This is the read-side half of the encoding rule (``docs/development/\n"
        'CROSS_PLATFORM.md``).\n'
        '"""\n'
        "\n"
        "# Phase 3 M7 follow-up: see the sibling design record\n"
        "# PHASE3_DESIGN.md v4 §3.5 step 3 for why.\n"
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CROSS_PLATFORM.md").write_text("# policy\n", encoding="utf-8")

    violations = _collect_source_violations(
        repo_root=tmp_path, source_paths=[source_path], require_contract_status=False
    )

    assert any(
        "docs/development/CROSS_PLATFORM.md" in violation and "no such document" in violation
        for violation in violations
    ), violations
    assert any("PHASE3_DESIGN.md" in violation for violation in violations), violations

    # The same tokens resolve once the citations name documents that exist:
    # the repo-root policy file, and a sibling file next to the source.
    source_path.write_text(
        '"""Module.\n'
        "\n"
        "This is the read-side half of the encoding rule (``docs/\n"
        'CROSS_PLATFORM.md``).\n'
        '"""\n'
        "\n"
        "# See PHASE3_DESIGN.md for why.\n"
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (source_path.parent / "PHASE3_DESIGN.md").write_text("# design\n", encoding="utf-8")

    assert (
        _collect_source_violations(
            repo_root=tmp_path, source_paths=[source_path], require_contract_status=False
        )
        == []
    )


def test_a_bare_name_is_exempt_only_where_the_code_defines_it(tmp_path: Path) -> None:
    """A bare name is exempt exactly when the scanned source defines it.

    That is a convention a reviewer enforces, not a proof: someone determined
    to silence a dead name can add an otherwise-unused constant for it. What
    the derived form buys is where that shows up — a line of production source
    in the diff, rather than one more name appended to a test-local list. Here
    `report.md`, `AGENT.md` and `agent-task.md` are exempt because the code
    defines them (a constant, a mapping key, a parameter default), while
    `deferred-items.md` appears only inside prose and stays red.
    """
    src_root = tmp_path / "src"
    src_root.mkdir()
    definitions = src_root / "names.py"
    definitions.write_text(
        'RUN_REPORT_NAME = "report.md"\n'
        'PHASE_FILES = {"AGENT.md": "agent"}\n'
        'def write(name: str = "agent-task.md") -> str:\n'
        "    return name\n",
        encoding="utf-8",
    )
    citations = src_root / "cites.py"
    citations.write_text(
        '"""Parsed by ``graph_skill_runtime.tools.md_to_json.parse_md``.\n'
        "\n"
        "Each run writes ``report.md``; a phase file is named ``AGENT.md``\n"
        "and the prompt lands in ``agent-task.md``.\n"
        "\n"
        "Remaining work is tracked in ``deferred-items.md``.\n"
        '"""\n',
        encoding="utf-8",
    )
    sources = [definitions, citations]

    assert _defined_file_names(sources) == frozenset(
        {"report.md", "AGENT.md", "agent-task.md"}
    )

    violations = _collect_source_violations(
        repo_root=tmp_path,
        source_paths=[citations],
        require_contract_status=False,
        definition_paths=sources,
    )

    assert [
        violation for violation in violations if "deferred-items.md" in violation
    ], violations
    assert not [
        violation
        for violation in violations
        if any(name in violation for name in ("report.md", "AGENT.md", "agent-task.md"))
    ], violations
    # `graph_skill_runtime.tools.md_to_json` is a module path, not a document:
    # the token boundary refuses to read `.md_to_json` as a `.md` file name.
    assert not [violation for violation in violations if "md_to_json" in violation]

    # Silencing the dead name takes a definition site — which is the intended
    # correction when the name really is runtime data, and a visible one-line
    # addition to production source when it is not.
    definitions.write_text(
        definitions.read_text(encoding="utf-8") + 'DEFERRED_ITEMS = "deferred-items.md"\n',
        encoding="utf-8",
    )

    assert (
        _collect_source_violations(
            repo_root=tmp_path,
            source_paths=[citations],
            require_contract_status=False,
            definition_paths=sources,
        )
        == []
    )


def test_markdown_cross_reference_check_reports_missing_targets_and_anchors(tmp_path: Path) -> None:
    docs_root = tmp_path / "skill-spec"
    docs_root.mkdir()
    (docs_root / "target.md").write_text("# Target\n\n## 2. 唯一目录布局\n", encoding="utf-8")
    index = docs_root / "index.md"
    index.write_text(
        "[good](./target.md#2-唯一目录布局)\n"
        "[dead anchor](./target.md#5-phase-文件)\n"
        "[dead file](./gone.md)\n"
        "[external](https://example.invalid/spec.md#x)\n",
        encoding="utf-8",
    )

    violations = _collect_markdown_violations(docs=[index])

    assert any("gone.md" in violation and "no such document" in violation for violation in violations)
    assert any("5-phase-文件" in violation for violation in violations)
    assert not any("2-唯一目录布局" in violation for violation in violations)
    assert not any("example.invalid" in violation for violation in violations)


def test_owning_spec_rows_are_owned_or_registered_gaps_and_nothing_else(tmp_path: Path) -> None:
    """Three-way exclusive: a live link, or the bare §10 marker, never both, never neither.

    The earlier shape checked only the links it recognised and silently called
    every other row "unowned". That left two holes wide enough to drive the
    original defect through: a code registered in §10 could keep a link to a
    disowned document, and a cell could carry an external URL alongside the
    marker, because the link scan filtered `http`/`mailto` out before looking.
    A gap cell is now judged by equality with the marker, so anything at all
    beside it is red.
    """
    docs_root = tmp_path / "docs" / "skill-spec"
    docs_root.mkdir(parents=True)
    (docs_root / "01-contract.md").write_text(
        "---\nstatus: FROZEN\n---\n\n## 5. Phase 文件\n\n### 5.2 `AGENT.md`\n",
        encoding="utf-8",
    )
    (docs_root / "00-old.md").write_text(
        "---\nstatus: superseded\n---\n\n## 4. Old\n", encoding="utf-8"
    )
    (docs_root / "09-unsealed.md").write_text(
        "---\nstatus: audited-ready\n---\n\n## 2. Draft\n", encoding="utf-8"
    )
    disowned = tmp_path / "docs" / "mvp1"
    disowned.mkdir(parents=True)
    (disowned / "runtime.md").write_text(
        "---\nstatus: drafted\n---\n\n## 3. Runtime\n", encoding="utf-8"
    )

    catalog = docs_root / "11-error-code-spec.md"
    catalog.write_text(
        "---\nstatus: living\n---\n\n"
        "## 2. Codes\n\n"
        "| Code | Level | Stage | Owning spec |\n| --- | --- | --- | --- |\n"
        "| `[F-v3-good]` | FATAL | 编译期 | [C](./01-contract.md#52-agentmd) |\n"
        "| `[F-v3-archived]` | FATAL | 编译期 | [Old](./00-old.md#4-old) |\n"
        "| `[F-v3-unsealed]` | FATAL | 编译期 | [D](./09-unsealed.md#2-draft) |\n"
        "| `[F-v3-dead-anchor]` | FATAL | 编译期 | [C](./01-contract.md#99-nope) |\n"
        "| `[F-v3-no-anchor]` | FATAL | 编译期 | [C](./01-contract.md) |\n"
        "| `[F-v3-outside]` | FATAL | 运行期 | [R](../mvp1/runtime.md#3-runtime) |\n"
        f"| `[F-v3-gap]` | FATAL | 运行期 | {GAP_CELL_MARKER} |\n"
        "| `[F-v3-gap-with-link]` | FATAL | 运行期 | [R](../mvp1/runtime.md#3-runtime) |\n"
        f"| `[F-v3-gap-with-url]` | FATAL | 运行期 | {GAP_CELL_MARKER} "
        "[上游](https://example.invalid/runtime#exit) |\n"
        f"| `[F-v3-marked-and-linked]` | FATAL | 运行期 | {GAP_CELL_MARKER} "
        "[C](./01-contract.md#52-agentmd) |\n"
        f"| `[F-v3-marked-unregistered]` | FATAL | 运行期 | {GAP_CELL_MARKER} |\n\n"
        "## 10. Gaps\n\n"
        "- **`[F-v3-gap]`** — 缺：运行期契约尚未成文。发出文件：`runtime/x.py`。\n"
        "- **`[F-v3-gap-with-link]`** — 缺：同上。发出文件：`runtime/y.py`。\n"
        "- **`[F-v3-gap-with-url]`** — 缺：同上。发出文件：`runtime/z.py`。\n",
        encoding="utf-8",
    )

    violations, owned, gaps = _collect_owning_spec_violations(catalog=catalog)

    def failed(code: str) -> list[str]:
        return [violation for violation in violations if code in violation]

    assert owned == {"[F-v3-good]"}, owned
    assert gaps == {"[F-v3-gap]"}, gaps
    assert owned & gaps == set()

    assert [v for v in failed("[F-v3-archived]") if "superseded" in v], violations
    assert [v for v in failed("[F-v3-dead-anchor]") if "anchor" in v], violations
    assert [v for v in failed("[F-v3-no-anchor]") if "no section anchor" in v], violations
    assert [v for v in failed("[F-v3-outside]") if "outside docs/skill-spec" in v], violations
    assert not failed("[F-v3-good]"), violations
    assert not failed("[F-v3-gap]"), violations

    # The `audited-ready` allowance is pinned to ONE file name, not to the
    # status word: another audited-but-unsealed document cannot own a code.
    assert [v for v in failed("[F-v3-unsealed]") if "audited-ready" in v], violations

    # Mutation 1: a code registered as a gap that points back at a disowned
    # document. Its row is identical to `[F-v3-outside]`'s except for the §10
    # registration, and both must be red — registration is not a licence to
    # keep a link.
    assert [
        v for v in failed("[F-v3-gap-with-link]") if "must be exactly" in v
    ], violations

    # Mutation 2 (the filter hole): the marker plus an external URL. The link
    # scan used to drop `https://` links before judging, so this cell passed as
    # a clean gap while pointing the reader at an upstream document.
    assert [v for v in failed("[F-v3-gap-with-url]") if "must be exactly" in v], violations

    # Mutation 3: a cell that hedges with marker AND an in-repo link, and a
    # cell that claims the marker without ever registering the gap.
    assert [
        v
        for v in failed("[F-v3-marked-and-linked]")
        if "marker and a link at the same time" in v
    ], violations
    assert [
        v for v in failed("[F-v3-marked-unregistered]") if "does not register it" in v
    ], violations

    assert set(_catalog_registered_gaps(catalog)) == {
        "[F-v3-gap]",
        "[F-v3-gap-with-link]",
        "[F-v3-gap-with-url]",
    }
