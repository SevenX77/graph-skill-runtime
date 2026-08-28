# Graph Skill Runtime

Graph Skill Runtime is a provider-neutral Python runtime for compiling, predicting, and running document-driven graph skills. The Phase 1 typed runtime foundation and Phase 2 portable gSkill format are implemented in this repository. The distribution is `graph-skill-runtime` version `0.1.0a1`, the import is `graph_skill_runtime`, and the console command is `gskill`.

This is an alpha source release, not a PyPI release. The repository exists at [SevenX77/graph-skill-runtime](https://github.com/SevenX77/graph-skill-runtime); `main` is pull-request-only and has completed a green six-job CI run. The [release workflow](.github/workflows/release.yml) is prepared to verify a GitHub Release tag `v<pyproject version>`, build and inspect the wheel and source distribution, and publish through PyPI Trusted Publishing with OpenID Connect (OIDC). That workflow is release automation, not publication evidence: the PyPI project and trusted publisher still require owner configuration, and no package has been published.

## Current capability boundary

The current checkout provides the Phase 1 typed runtime facade and configuration boundary together with the Phase 2 format cutover:

- exactly 58 top-level symbols defined by [`graph_skill_runtime.__all__`](src/graph_skill_runtime/__init__.py), documented in the [public API contract](docs/public-api-contract.md);
- closed, frozen Pydantic request and result models with `schema_version` and `kind` discriminators;
- immutable nested JSON collections after model construction;
- a closed 38-value `RuntimeEvent.event_type` catalog kept exactly equal to every concrete internal `CallbackEvent` variant by contract test;
- eight Python use-case functions: `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`;
- the `gskill` CLI and eight same-named MCP tools as thin adapters over one `RuntimeApplication`;
- explicit dependency composition through `create_application`, with no process-global application singleton;
- deterministic configuration precedence and provenance-bearing immutable run requests;
- create-once local request snapshots at `<state_root>/runs/<run_id>/request.json`;
- the extracted engine behind `CurrentEngineAdapter`, including a verified compile/run path for an explicit embedded portable `LOGIC` skill;
- one production reader for the portable root `SKILL.md` plus `graph.yaml` format, with a flat graph registry and no legacy fallback;
- an explicit, non-overwriting `gskill migrate studio-skill` converter for legacy v0.3 source.

The current reader accepts one explicit business skill root in the portable format:

```text
my-skill/
├── SKILL.md
├── graph.yaml
├── phases/
│   └── <phase_id>/
│       └── LOGIC.md | AGENT.md | SUBGRAPH.md
└── graphs/
    └── <graph_id>/
        ├── graph.yaml
        └── phases/
            └── <phase_id>/
                └── LOGIC.md | AGENT.md | SUBGRAPH.md
```

The root `SKILL.md` is the only Agent Skills discovery target. `graph.yaml` uses schema version `gskill.graph.v1`; the root Agent Skill name and root graph id are separate identities. Reusable graphs live directly under the single-level `graphs/<graph_id>/` registry, and graph ids are explicit and unique across the bundle. Only the root graph declares artifacts; presets and requests select them by `artifact_id`.

Production compile, predict, run, inspect, SDK, CLI, and MCP paths do not sniff formats or fall back to v0.3. Legacy parsing exists only behind `gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]`. The converter leaves `SOURCE` unchanged, refuses an existing destination, and publishes from a sibling temporary directory through an operating-system-native create-if-absent rename with a deterministic migration report.

The default executor selection is `host-native`, but the current runtime does not include a durable host-native handoff adapter. A default `run` therefore saves the resolved request snapshot and returns a failed `RunResult` with `GSKILL_EXECUTOR_UNAVAILABLE`. `resume` and `submit_agent_result` return structured `GSKILL_NOT_IMPLEMENTED` failures until Phase 3 supplies durable handoff and resume. Vendor CLI executors, MoirAI installation, and Gateway or Studio adapters are also later-phase work.

## User-owned graph skills

A business graph skill, or gSkill, is project content owned by its user. Every SDK, CLI, or MCP invocation receives the skill path explicitly. Installing or importing the runtime does not register, discover globally, copy, or mutate business gSkills.

The repository-level [`examples/hello-world/`](examples/hello-world/) directory is a portable business gSkill that has been compiled and run with the explicit `embedded` executor in the local Phase 2 evidence. It belongs to the source checkout, not the installed package: wheel verification rejects any `graph_skill_runtime/examples/` package content.

The wheel may contain runtime implementation resources. Those resources are not business gSkills and do not make the wheel a skill registry.

## Requirements and local installation

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)

Create the development environment from the repository root:

```bash
uv sync --extra dev
```

Install only base runtime dependencies for this checkout:

```bash
uv sync
```

Provider clients are isolated in the optional `embedded` extra:

```bash
uv sync --extra embedded
```

The `embedded` extra is required only for embedded provider-backed agent execution. It is not part of the base dependency set. An embedded `LOGIC`-only skill can run without a provider call.

## Python SDK

Construct the typed request that matches the use case. This example compiles and then runs a current-format `LOGIC` skill through the explicit embedded executor:

```python
from pathlib import Path

from graph_skill_runtime import (
    CompileRequest,
    EmbeddedExecutorConfig,
    RunInvocation,
    RuntimeProfileOverlay,
    compile,
    run,
)

skill_root = Path("/absolute/path/to/my-skill").resolve()

compile_result = compile(CompileRequest(skill_root=str(skill_root)))
if not compile_result.passed:
    raise RuntimeError(compile_result.diagnostics)

run_result = run(
    RunInvocation(
        skill_root=str(skill_root),
        runtime=RuntimeProfileOverlay(executor=EmbeddedExecutorConfig()),
        inputs={"topic": "typed runtime"},
    )
)
```

Each SDK function accepts an optional `application=` argument for explicit adapter injection. Without it, the function calls `create_application()` and receives a new application service composed from the current engine and local snapshot store.

## Configuration

Runtime configuration resolves from highest to lowest precedence:

1. the current `RunInvocation` or equivalent CLI flags;
2. project configuration at `<skill_root>/gskill.toml`;
3. the operating-system user configuration;
4. portable runtime or business defaults supplied by an integration;
5. built-in defaults.

Project configuration may define both a machine/runtime overlay and named, non-secret business presets:

```toml
schema_version = "gskill.config.v1"

[runtime.executor]
kind = "embedded"

[presets.local.inputs]
topic = "project default"
```

User configuration may contain only the machine-level runtime overlay. `RuntimeProfile` owns executor, checkpoint store, state directory, permissions, required capabilities, and fallback executor declarations. `RunPreset` owns reusable non-secret business defaults. `RunInvocation` owns one call's overrides. Resolution produces a `RunRequest` containing absolute skill and state roots plus field-level provenance.

Literal values under secret-shaped keys such as `api_key`, `access_token`, or `password` are rejected from persistent input contracts. Use `SecretReference` and `SecretBinding` instead. The runtime cannot infer whether an arbitrary business string is confidential, so callers remain responsible for classifying values that do not have a structurally secret-shaped key.

## CLI and MCP

The console command emits structured JSON:

```bash
uv run gskill compile /absolute/path/to/my-skill
uv run gskill config resolve /absolute/path/to/my-skill --run-id example
uv run gskill run /absolute/path/to/my-skill --executor embedded --inputs-json '{"topic":"typed runtime"}'
uv run gskill inspect /absolute/path/to/my-skill
uv run gskill golden /absolute/path/to/my-skill baseline-id --state-root /absolute/path/to/state
```

Start the MCP server over standard input/output with:

```bash
uv run gskill mcp
```

The MCP server exposes exactly `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`. These tools call the same application methods as the Python facade and CLI; they do not implement separate runtime rules.

The CLI includes `resume` and `submit` command shapes so clients can bind the typed contracts now. Their durable behavior remains Phase 3 work and currently returns a structured not-implemented result.

Convert a legacy Studio v0.3 skill only through the explicit migration boundary:

```bash
uv run gskill migrate studio-skill /absolute/path/to/legacy-skill /absolute/path/to/new-portable-skill
```

This command is not a second production reader. Compile and execution accept only the portable destination.

## Development and verification

Run the required local gates from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build
uv run pip-audit
```

`uv build` must produce both a wheel and a source distribution. A local package skip reported by `pip-audit` is not evidence that this repository's own source has been security-audited; the command audits resolved third-party distributions.

## Documentation map

- [Public typed API contract](docs/public-api-contract.md)
- [Current portable gSkill v1 format contract](docs/skill-spec/01-PORTABLE-GSKILL-V1.md)
- [Superseded v0.3 converter and historical evidence](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md)
- [MVP1 design index and Phase 2 ownership map](docs/mvp1/INDEX.md)
- [Design authority and implementation-status map](docs/design/README.md)
- [Drafted standalone v1 target](docs/design/v1-alignment.md)
- [Historical pre-extraction baseline](docs/design/baseline.md)
- [Feature compliance view generated from the feature manifest](docs/feature-compliance-checklist.md)
- [Cross-platform policy](docs/CROSS_PLATFORM.md)
- [Contributor and agent rules](AGENTS.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
