# Graph Skill Runtime

Graph Skill Runtime is an independent Python repository for compiling and running document-driven graph skills. The repository is currently in **Phase 0**: it preserves and characterizes the extracted engine under its existing identity while the standalone v1 contract remains a drafted target.

## Current package and drafted target

The two contract lines must not be mixed:

| Surface | Current Phase 0 implementation | Drafted standalone target |
| --- | --- | --- |
| Python distribution | `graph-agent` 0.3.1 | `graph-skill-runtime` |
| Python import | `graph_agent` | `graph_skill_runtime` |
| Command line | Legacy `python -m graph_agent`; no console script | `gskill` |
| Skill root | `GRAPH.md` | Agent Skills entry `SKILL.md` plus `graph.yaml` |
| Agent phase file | `SKILL.md` | `AGENT.md` |
| Nested graph layout | Root `subgraph/` hierarchy | Flat `graphs/<graph_id>/` registry |
| Contract status | Implemented and characterized | `drafted`; not implemented or published |

The repository name does not make the target package, import, command, or file format available. Until an explicit cutover replaces the current line, callers must use `graph-agent`, import `graph_agent`, and follow the current [`GRAPH.md` format contract](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md).

The project is pre-release and has no external compatibility commitment. A future cutover will replace the old contract in one coordinated change after implementation and migration verification; the runtime will not keep permanent dual readers, legacy aliases, or version-guessing branches.

## What the runtime owns

The current engine compiles a user-provided skill directory into a typed graph and can execute, predict, checkpoint, resume, trace, and evaluate it. It owns:

- aggregated compile diagnostics;
- `LOGIC`, `AGENT`, and `SUBGRAPH` phase execution;
- typed blackboard state, declared inputs and outputs, and iteration;
- checkpoints and resume;
- typed callback events, traces, artifacts, and structured errors;
- prediction and golden-baseline evaluation;
- local skill resolution and compiled artifacts.

This repository is the runtime boundary. It does not own an HTTP API, Studio UI or filesystem behavior, Gateway credential and route truth, or a host application's global configuration. Host-specific integration belongs behind explicit adapters rather than inside the runtime domain.

## User-owned graph skills

A business graph skill (gSkill) is user-owned project content. The caller supplies its path explicitly; installing or importing the runtime does not discover, register, copy, or modify business skills.

The wheel contains runtime code and may contain engine-owned implementation resources. Those resources are not user business skills. Neither the current `graph-agent` wheel nor the drafted future wheel is a registry or delivery channel for a user's gSkills.

## Requirements and local installation

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)

This is a single-package `uv` project. From the repository root, create or update the local environment with development dependencies:

```bash
uv sync --extra dev
```

For runtime dependencies only:

```bash
uv sync
```

The target `graph-skill-runtime` distribution is not published. Do not install that name to use this checkout. The commands above install the current local `graph-agent` project into `.venv`.

## Use the current SDK

Pass the skill root directory to the SDK. `workspace_dir` must be an absolute path for `run_skill`, `predict_skill`, and `resume_skill`.

```python
from pathlib import Path

from graph_agent import compile_skill, run_skill

skill_root = Path("/absolute/path/to/my-skill").resolve()
workspace_dir = (skill_root / ".workspace").resolve()

compile_result = compile_skill(skill_root)

# This is sufficient only when the executed path has no AGENT phase.
run_result = run_skill(
    skill_root,
    workspace_dir=workspace_dir,
    user_name="Developer",
)
```

An executed `AGENT` phase requires model execution supplied explicitly by the host through the current `llm_provider` or `model_resolver` seam. The runtime does not infer a provider, credentials, role map, or model route from an implicit application configuration.

The package currently exposes exactly 24 names through [`graph_agent.__all__`](src/graph_agent/__init__.py):

- execution and prediction: `run_skill`, `predict_skill`, `resume_skill`, `evaluate_golden_baseline`, `RunResult`, `PathDiff`, and `PhaseRecord`;
- artifact execution: `compile_artifact`, `run_artifact`, and `predict_artifact`;
- compilation and serialization: `compile_skill`, `CompileResult`, `SkillManifest`, and `serialize_skill`;
- assembly and state: `assemble_graph`, `CompiledSkill`, `CompiledStateGraph`, and `BlackboardState`;
- resolution: `LocalWorkspaceResolver`;
- errors: `GraphAgentError`, `GraphCompileError`, `GraphExecutionError`, `ModelProviderError`, and `ResourceNotFoundError`.

Internal modules are not additional top-level SDK commitments.

## Current command-line entry

The package has no `[project.scripts]` entry. Its legacy argparse module can be inspected with:

```bash
uv run python -m graph_agent --help
```

This module entry is a legacy surface, not the drafted `gskill` command contract. Automation that needs the current stable boundary should use the exported Python API and pin the repository revision.

## Development and verification

Run the complete local gate set from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build
uv run pip-audit
```

The Phase 0 local characterization result is 1,601 passed and 1 skipped. Ruff, strict mypy over 118 source files, and the contract-manifest validator are green. `uv build` produces `graph_agent-0.3.1` wheel and source distributions. `pip-audit` reports no known vulnerability in resolved third-party dependencies; it skips the local `graph-agent` project because that distribution has no PyPI entry.

CI is configured for Python 3.11, 3.12, and 3.13 on Linux, with Windows and macOS smoke jobs, plus CodeQL, Scorecard, and Dependabot configuration. Phase 0 has not made its first remote push, so configured workflows and repository settings are not evidence that remote CI or branch protection has run successfully.

## Documentation map

- [Current FROZEN skill-format contract](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md)
- [Current engine MVP1 design](docs/mvp1/INDEX.md)
- [Standalone design index and contract-line distinction](docs/design/README.md)
- [Pre-extraction baseline](docs/design/baseline.md)
- [Drafted standalone v1 target](docs/design/v1-alignment.md)
- [Cross-platform policy](docs/CROSS_PLATFORM.md)
- [Contributor and agent rules](AGENTS.md)

The current implementation line is authoritative for behavior that exists today. The drafted target is authoritative only for the intended future design.

## License

Apache-2.0. See [LICENSE](LICENSE).
