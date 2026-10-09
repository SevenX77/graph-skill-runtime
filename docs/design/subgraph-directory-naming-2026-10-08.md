---
doc: subgraph-directory-naming-2026-10-08
role: decision-record
status: adopted
updated: 2026-10-08
---

# Reusable-subgraph directory naming

## Decision and scope

The portable gSkill format stores reusable subgraph definitions in one flat
`subgraphs/<graph_id>/` directory registry. A registry is the set of reusable
definitions that the compiler finds beneath the skill root. Directory diagrams
label `subgraphs/` with `# reusable subgraph definitions`.

The root `graph.yaml` defines the entry graph. Each reusable definition owns its
own `graph.yaml` and `phases/`. A phase's `SUBGRAPH.md` is a call site: its `graph`
field selects a definition by `graph_id`. Several call sites can share the same
definition. Graph ids remain unique across the bundle, and explicit references
continue to determine the calling relationships. The
[portable format contract](../skill-spec/01-PORTABLE-GSKILL-V1.md) owns these
requirements and their field definitions.

An existing portable bundle adopts this layout by moving its root `graphs/`
directory to `subgraphs/` and updating the affected file and resource links to
use the new directory prefix. Graph ids and references expressed as graph ids
retain their values. Runtime discovery and the explicit Studio converter use the
current directory name.
Compilation resolves reusable definitions exclusively through `subgraphs/`.
This change operates on repository source; user-owned bundles and installed host
projections remain under their owners' explicit update authority.

## Authority and rationale

The product owner's 2026-10-08 request was: “改成subgraphs/ 在后面加上标注，说明这里面是放子图的”
(“Rename it to subgraphs/ and add an annotation explaining that it contains
subgraphs”). The source is the user message in Codex chat
`01a11a98-1d29-7ef2-bd06-1b0716760323`, transcribed in the task's retained source
record. It fixes the directory spelling and the explanatory annotation.

At baseline commit `205b34d34b9354deae5fe1f095f2ba62180a9c52`,
[`v1-alignment.md`, sections 5.1–5.2](./v1-alignment.md#5-subgraph-registry-与调用图)
justified flat reusable definitions, explicit references, and shared callers.
Those reasons govern storage and call semantics. The owner's naming choice
makes the directory's reusable-subgraph purpose visible while preserving that
design. The dated Phase 2 evidence retains its historical `graphs/` spelling.

The selected implementation updates the contract, loader, topology projection,
converter, tests, traceability and canonical MoirAI guidance together. Feasibility
confidence is `0.96`: these owners and their version mechanisms are identified,
and targeted behavior is directly testable. A newly found path consumer or a
required semantic change would require reassessment. A diagram-only alternative
has suitability confidence `0.20`: the pre-edit loader and projection resolve
`graphs/`, so following a renamed normative diagram would fail. These values are
engineering judgments under the stated evidence, rather than statistical success
probabilities.

## Dependent identities

The [compiler rule identity](../../src/graph_skill_runtime/core/compiler.py) moves
to version `2`. A cache records a prior compilation result; including the rule
identity in its key forces this directory contract to be checked again. Serialized
cache collections keep their existing `graphs` key because that key represents
compiled graphs.

The [canonical MoirAI manifest](../../src/graph_skill_runtime/integrations/assets/moirai/integration.json)
uses asset version `1.1.1` for the changed authoring instructions. Its
[content lock](../../tests/integrations/moirai-asset-lock.json) identifies the new
bytes, following the [asset lock's version rule](../../tests/integrations/test_moirai_asset_lock.py).
The portable contract receives an appended
[seal record](../../tests/contract-seals.yaml); earlier seals retain the approved
historical bytes. The local branch is `codex/rename-subgraph-directory`, pending
a separately authorized pull request.

## Validation scope

On 2026-10-08, the local targeted suite reported `29 passed` with this command:

```text
uv run pytest tests/core/test_portable_gskill_v1.py tests/core/test_d84_subgraph_path_semantics.py tests/migration/test_studio_v030.py tests/core/test_cache_key_covers_the_compiler_identity.py tests/e2e/test_execution_runtime_v030.py --tb=short -q
```

The suite covers directory discovery, shared graph references, topology
projection, converter destinations, cache behavior and child execution.
The directory and cache regressions are in
[`test_portable_gskill_v1.py`](../../tests/core/test_portable_gskill_v1.py);
projection and converter coverage are in
[`test_d84_subgraph_path_semantics.py`](../../tests/core/test_d84_subgraph_path_semantics.py)
and [`test_studio_v030.py`](../../tests/migration/test_studio_v030.py).
Changing only the compiler rule identity back to `1` reproduced the cache
regression: the old successful result was replayed. That counterexample supports
the rule-identity increment independently of the directory edits.

The complete `uv run pytest --tb=short -q` suite reported `1814 passed, 1 skipped`
in `98.81s`. Both test runs used `PYTHONUTF8=1` and a task-owned temporary
directory through `PYTEST_DEBUG_TEMPROOT`. The task-owned directory resolved an
initial permission error in the system pytest temporary directory before test
setup. Ruff passed; strict mypy checked 149 source files successfully; import
boundaries reported nine contracts kept and zero broken; the contract manifest
validator exited `0`. The document seal and MoirAI content lock passed in the
complete suite. `uv build --no-sources` produced both the wheel and source
distribution.

`uv run pip-audit` exited `1` and reported 26 advisory findings across the existing
locked packages `langgraph-sdk 0.4.3`, `pyjwt 2.13.0`, `urllib3 2.7.0` and
`virtualenv 21.7.5`; its table repeats four `virtualenv` findings. It skipped the
unpublished local runtime package. Dependency declarations and lockfile versions
are unchanged by this directory change. The required dependency audit therefore
remains a failing gate, and release readiness remains unverified.

These observations establish the local directory naming behavior and current
documentation consistency. Remote cross-platform acceptance, installed-package
acceptance and real-host discovery for the new bytes remain unverified. The
[2026-09-02 acceptance of asset version `1.1.0`](./moirai-asset-single-owner-2026-09-01.md)
continues to describe its own candidate. The task makes its evidence available
for local review; a pull request, release and registry publication each require
separate owner authorization.
