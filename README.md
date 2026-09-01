# Graph Skill Runtime

Graph Skill Runtime is a provider-neutral Python runtime for compiling, predicting, and executing document-driven graph workflows. The current distribution target is `graph-skill-runtime` `1.0.0a1`; portable source uses the exact syntax marker `gskill.graph.v1`, and runtime and syntax majors must match.

The package is not published to PyPI or TestPyPI. Historical release-candidate evidence and current working-tree evidence are scoped in [the v1 alignment record](docs/design/v1-alignment.md); neither is registry publication.

## Current product boundary

The runtime provides:

- the typed `graph_skill_runtime` Python facade;
- an installed-interpreter module CLI;
- one stdio MCP server named `gskill` with exactly eight runtime tools: `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`;
- a portable gSkill v1 reader and explicit one-shot legacy Studio converter;
- default host-native execution with durable Agent handoff;
- an explicitly selected direct vendor CLI executor;
- optional, explicitly installed MoirAI host projections;
- a read-only provider-neutral Agent kit containing exactly two public Skills, `gskill` and `create-gskill`.

Studio and Gateway plugins are not implemented in this release. Their only current design status is a future Port/Adapter boundary.

## Installation and command identity

Graph Skill Runtime is a dependency and SDK package. Install it into the owning Python 3.11-or-newer environment through that environment's normal dependency workflow. The package is not published, so local installation examples must name an actual locally built wheel or source path rather than a registry package name:

```text
python -m pip install /path/to/graph_skill_runtime-1.0.0a1-py3-none-any.whl
uv add /path/to/graph_skill_runtime-1.0.0a1-py3-none-any.whl
uv pip install --python /path/to/python /path/to/graph_skill_runtime-1.0.0a1-py3-none-any.whl
```

Choose the form owned by the environment or project; these examples are alternatives, not a sequence. `uv tool install` is not the installation form for this package because uv tools install packages that expose commands, while Graph Skill Runtime intentionally exposes none. Installation, import, MCP startup, host detection, and Agent configuration guidance make no host/project configuration changes and do not register user business gSkills.

The distribution intentionally defines no `[project.scripts]` or `console_scripts` entry. It installs no package-owned `gskill.exe` or `bin/gskill` launcher. Use the installed interpreter:

```text
python -m graph_skill_runtime --version
```

The exact version line is:

```text
python -m graph_skill_runtime gskill.graph.v1 (graph-skill-runtime 1.0.0a1)
```

On Windows the interpreter is normally `python.exe`; that executable belongs to Python, not to this package.

## Portable business gSkill

A business gSkill is a user-owned directory supplied explicitly on every operation. Its root contains:

- `SKILL.md` with `metadata.gskill: gskill.graph.v1`;
- `graph.yaml` with `schema_version: gskill.graph.v1`;
- registered phase directories containing exactly one of `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`.

Reusable graphs live in a flat `graphs/<graph_id>/` registry. The runtime neither scans the machine for business graphs nor registers them globally. Current compile, inspect, predict, and run paths do not guess or fall back to a legacy format. See the [portable format contract](docs/skill-spec/01-PORTABLE-GSKILL-V1.md).

## Agent-facing operation flow

Coding Agents prefer the `gskill` MCP tools when available. If MCP is absent, disconnected, or lacks the needed operation, they use the installed interpreter with `python -m graph_skill_runtime ...`.

The normal flow is:

1. identify the explicit marked root and compatible major;
2. compile and preserve the full aggregated diagnostic set;
3. repair fatal diagnostics and recompile;
4. resolve configuration or inspect topology when needed;
5. predict, run, or evaluate an existing golden as requested;
6. perform native child handoff at each `agent_required` boundary;
7. verify outputs, traces, artifacts, and requested acceptance evidence.

The exhaustive Agent-facing command and option contract is [packaged rule 02](src/graph_skill_runtime/agent_kit/assets/rules/02-entrypoints.md).

## Common module CLI forms

```text
python -m graph_skill_runtime compile SKILL_ROOT [--no-cache]
python -m graph_skill_runtime config resolve SKILL_ROOT [INVOCATION_OPTIONS]
python -m graph_skill_runtime predict SKILL_ROOT [INVOCATION_OPTIONS]
python -m graph_skill_runtime run SKILL_ROOT [INVOCATION_OPTIONS]
python -m graph_skill_runtime resume SKILL_ROOT RUN_ID --state-root STATE_ROOT [--checkpoint-ref REF] [--human-response-json JSON_OBJECT]
python -m graph_skill_runtime submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json AGENT_RESULT_JSON
python -m graph_skill_runtime inspect SKILL_ROOT [--call-graph]
python -m graph_skill_runtime golden SKILL_ROOT BASELINE_ID --state-root STATE_ROOT
python -m graph_skill_runtime migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]
python -m graph_skill_runtime integrations detect
python -m graph_skill_runtime integrations install moirai --targets HOSTS_OR_detected --scope user|project [--project-root PATH] [--dry-run]
python -m graph_skill_runtime integrations uninstall moirai --targets HOSTS_OR_detected --scope user|project [--project-root PATH] [--dry-run]
python -m graph_skill_runtime guide agent-configuration
python -m graph_skill_runtime create NAME --path EXISTING_PARENT --description TEXT
python -m graph_skill_runtime mcp
```

All one-shot commands emit structured JSON. Exit code `0` means success or a durable wait such as `agent_required`; exit code `2` means a failed, conflicting, invalid, or `passed=false` structured result. Argument-parser usage errors are nonzero. Consume structured fields instead of parsing message prose.

Compile before predict, run, or golden evaluation. Prediction writes request and trace state but provides deterministic or heuristic shape evidence, not proof of live Agent capability or output quality. Golden evaluation accepts only an existing baseline.

## Configuration and state

Configuration precedence is invocation, project `<skill_root>/gskill.toml`, operating-system user configuration, portable defaults, then built-in defaults. The default executor is `host-native`. An explicit `cli` executor requires `--vendor`; CLI-only vendor options are invalid with other executors. Business `--inputs-json` values must be non-secret.

The default state root is `<skill_root>/.gskill` unless overridden. Predict and run persist the immutable request and `<state_root>/runs/<run_id>/trace.jsonl`; `RunResult` returns `trace_path`. Checkpoints, Agent handoffs, traces, artifacts, and golden baselines remain separate state owners.

## Host-native handoff

Authorizing execution of a successfully compiled gSkill with supported Agent phases also authorizes the required handoff for that run. At each serial `agent_required` boundary, the current host creates exactly one fresh native clean-context child for the returned `AgentTask`; it does not ask again for subagent permission at every wait. Because the parent graph is durably paused, this is a required business-execution step, not optional parallel delegation for development work. A general restriction on optional or parallel development subagents does not block the handoff.

The handoff authorization is limited to the returned task, canonical prompt, declared paths/tools/network/capabilities/deadline, one schema-valid output, and `submit_agent_result`. It does not authorize extra or parallel children, optional MoirAI delegation, child-created subagents, or broader access. The run blocks only if the user explicitly prohibited a native child for this run or the host cannot create or constrain one; an unavoidable host policy cannot be overridden. The parent validates the output, wraps an `AgentResult`, and submits it through MCP `submit_agent_result` or the module CLI `submit` command. `resume` observes or reopens the wait; it does not submit Agent output, and the current host retains final ownership.

The exact child prompt is owned only by [packaged rule 05](src/graph_skill_runtime/agent_kit/assets/rules/05-agent-handoff.md).

At returned boundaries, an Agent may summarize observed compile results, phase/wait state, native-child handoff, failures, outputs, and completion. Current module CLI and MCP calls block between returned boundaries. There is no public live event subscription or `trace` command, so continuous token-by-token or event-by-event streaming is not implemented.

## Configure the provider-neutral Agent kit

The unified kit has no setup or install command. Read its packaged sources and placement choices without writing:

```text
python -m graph_skill_runtime guide agent-configuration
```

The JSON result includes the canonical AGENTS section, standalone rules, and the two complete Skill/reference trees. The owner chooses:

- host or hosts;
- user/global scope or one project;
- manual editing or explicit authorization for the current Agent to edit;
- the rules-tree destination and exact instruction and Skill destinations.

Before a write, inspect selected existing files, propose an additive merge/copy plan naming every destination, and obtain approval. Copy the standalone rules tree to the owner-chosen location, copy the two Skill trees to the selected scope, and point the merged instruction section to that rules index. Never replace an existing `AGENTS.md` or `CLAUDE.md`.

Codex user instructions use `$CODEX_HOME/AGENTS.md` (normally `~/.codex/AGENTS.md`), project instructions use `<repo>/AGENTS.md`, user Skills use `~/.agents/skills`, and project Skills use `<repo>/.agents/skills`. Codex merges instruction files from repository root to current working directory.

Claude Code reads `CLAUDE.md`, not `AGENTS.md`: user instructions use `~/.claude/CLAUDE.md`, project instructions use `./CLAUDE.md` or `./.claude/CLAUDE.md`, user Skills use `~/.claude/skills`, and project Skills use `.claude/skills`. A user may deliberately import `@AGENTS.md` from a `CLAUDE.md`. For another host, use its documented paths.

Implicit routing uses the Skill descriptions. A vague request to create a gSkill selects `create-gskill` and asks only for missing high-impact domain and authorization facts before mutation. Ordinary non-graph Agent Skill creation selects neither. Existing marked-root operation selects `gskill`.

## Optional MoirAI projection

MoirAI is separate from the unified kit. `integrations detect` is read-only. Install and uninstall support `claude`, `codex`, `copilot`, `cursor`, `gemini`, and `opencode`; `detected` cannot be mixed with explicit hosts. `--dry-run` returns the exact plan, while apply mutates only after explicit authorization. These commands project optional host assistance and do not install a business graph or unified-kit configuration.

## Development checkout

Repository development uses `uv`; these are contributor commands, not installed-user CLI syntax:

```text
uv sync --extra dev
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build --no-sources
```

## Documentation map

- [Public typed API contract](docs/public-api-contract.md)
- [Portable gSkill v1 format](docs/skill-spec/01-PORTABLE-GSKILL-V1.md)
- [Unified Agent-kit design](docs/design/unified-agent-kit.md)
- [Design authority and status map](docs/design/README.md)
- [Drafted v1 alignment and revision record](docs/design/v1-alignment.md)
- [Cross-platform policy](docs/CROSS_PLATFORM.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
