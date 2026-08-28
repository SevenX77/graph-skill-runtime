# Graph Skill Runtime

Graph Skill Runtime is a provider-neutral Python runtime for compiling, predicting, and running document-driven graph skills. The Phase 1 typed runtime foundation, Phase 2 portable gSkill format, bounded Phase 3 durable host-native handoff, Phase 4 direct vendor CLI executor, Phase 5 MoirAI host integration, and Phase 6 cross-platform package/release-candidate acceptance are accepted in their documented scopes. `graph-skill-runtime` version `0.1.0a1` is one Python distribution installable with `pip` or `uv`; it provides the importable `graph_skill_runtime` SDK, the `gskill` console command, and the `gskill` MCP transport. Phase 3b host-native expansion, first-release naming review, and actual release/registry publication remain incomplete, so the complete v1 design remains drafted.

The repository has accepted an alpha release candidate; it has not published a release. The repository exists at [SevenX77/graph-skill-runtime](https://github.com/SevenX77/graph-skill-runtime) and `main` is pull-request-only. The [release workflow](.github/workflows/release.yml) verifies a GitHub Release tag against `v<pyproject version>`, builds one wheel/source-distribution pair, requires that exact candidate to pass source and installed-package acceptance on Ubuntu, Windows, and macOS, and only then makes the original distributions eligible for PyPI Trusted Publishing through OpenID Connect (OIDC). No release tag was triggered, no GitHub Release was created, nothing was published to PyPI or TestPyPI, and the PyPI project and trusted publisher have not been configured or verified.

## Current capability boundary

The current checkout provides the typed runtime facade and configuration boundary, the portable format cutover, the supported Phase 3 host-native handoff, the bounded Phase 4 direct CLI executor, the accepted Phase 5 host integration, and the accepted Phase 6 package boundary:

- exactly 77 top-level symbols defined by [`graph_skill_runtime.__all__`](src/graph_skill_runtime/__init__.py), documented in the [public API contract](docs/public-api-contract.md);
- closed, frozen Pydantic request and result models with `schema_version` and `kind` discriminators;
- immutable nested JSON collections after model construction;
- a closed 44-value `RuntimeEvent.event_type` catalog kept exactly equal to every concrete internal `CallbackEvent` variant by contract test;
- fourteen top-level Python functions: nine runtime/application entry points (`create_application`, `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`) plus five integration functions (`detect_integration_hosts`, `plan_integration_install`, `install_integration`, `plan_integration_uninstall`, and `uninstall_integration`);
- the `gskill` CLI and exactly eight runtime MCP tools—`compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`—over one `RuntimeApplication`; integration installation is not an MCP tool;
- explicit dependency composition through `create_application`, with no process-global application singleton;
- deterministic configuration precedence and provenance-bearing immutable run requests;
- create-once local request snapshots at `<state_root>/runs/<run_id>/request.json`;
- durable root-DAG Agent waits: a LangGraph SQLite checkpoint, a separate `agent-handoffs.sqlite3` task/result owner, cross-process submission, exact-retry idempotency, and recovery across both the checkpoint-to-task and graph-commit-to-response crash windows;
- a public `AgentResource` contract that lets an Agent task identify declared references and examples without duplicating their filesystem paths in rendered instructions;
- direct `cli` execution for Claude, Codex, GitHub Copilot, Cursor, Gemini, and OpenCode through capability-probed vendor adapters, bounded task materialization, schema-validated output, and causal attempt events;
- shell-free process-tree ownership: Win32 Job Objects on Windows and process groups on POSIX, with a bounded exact-PGID/effective-UID fallback when a POSIX group signal is denied and whole-tree cleanup after success, timeout, cancellation, or parent exit;
- the extracted engine behind `CurrentEngineAdapter`, including a verified compile/run path for an explicit embedded portable `LOGIC` skill;
- one production reader for the portable root `SKILL.md` plus `graph.yaml` format, with a flat graph registry and no legacy fallback;
- an explicit, non-overwriting `gskill migrate studio-skill` converter for legacy v0.3 source;
- one optional MoirAI integration inventory at asset version `1.0.0`: four provider-neutral role instructions, eight Agent Skills, and `KB-00` through `KB-14`, with no business `graph.yaml`;
- explicit `gskill integrations detect/install/uninstall` and equivalent SDK contracts for `claude`, `codex`, `copilot`, `cursor`, `gemini`, and `opencode`, with dry-run planning, all-target conflict preflight, manifest ownership, causally safe rollback, idempotency, and hash-safe uninstall;
- a release-artifact validator that requires exactly one wheel and one source distribution, validates metadata, the pure-wheel/console contract, safe archive paths, required and forbidden package content, and the manifest-closed MoirAI subtree, then binds their sizes and SHA-256 digests to one source commit;
- a package-acceptance runner that verifies those manifest-owned artifact bytes and the expected source commit, installs the candidate through pip-wheel, uv-wheel, and pip-sdist channels, exercises the installed SDK/CLI/MCP/integration/durable-state behavior, and emits versioned acceptance evidence.

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

The default executor is `host-native`. A graph with no Agent phase runs directly. For a supported Agent phase in the root DAG, `run` saves the request, durably checkpoints immediately before that phase, persists a provider-neutral `AgentTask`, and returns `RunResult(status="agent_required")`. If the process stops after the graph checkpoint but before the task row is written, repeating the same run reconstructs the public task from that existing Agent breakpoint without invoking or replaying the already-completed graph prefix. The host must create a fresh clean-context native subagent, give it the task, and submit its typed result; the runtime does not call a model, create the host child itself, or silently fall back to another executor.

The current Agent address is narrow by design. Agent phases in registry subgraphs, graph-level iterate, Agent phase iterate, and incomparable parallel branches fail fast for both `host-native` and `cli`. Host-native Agent handoff requires a SQLite checkpoint store. `resume(checkpoint_ref)` only reads the durable current wait or terminal response; Agent output must use `submit_agent_result`. Ordinary human/breakpoint typed resume is not yet implemented.

The default executor remains `host-native`; only an explicit `executor=cli` enters the direct vendor path. A `LOGIC`-only graph completes without constructing or probing a vendor executor even when its profile selects `cli`. Before creating a handoff task, a CLI run probes the executable, required flags, and any vendor-exposed authentication status, and rejects Agent declarations that require the not-yet-bridged portable tools, subagents, subgraphs, or framework context access. There is no silent `embedded` fallback. Phase 5 is accepted for canonical assets, six renderer formats, explicit safe installation, and the documented discovery evidence below. Phase 6 is accepted for immutable artifact binding and the documented three-platform installed-package behavior. Neither phase completes Phase 3b or adds Gateway or Studio plugins; future product integrations remain behind external Port/Adapter boundaries.

## User-owned graph skills

A business graph skill, or gSkill, is project content owned by its user. Every SDK, CLI, or MCP invocation receives the skill path explicitly. Installing or importing the runtime does not register, discover globally, copy, or mutate business gSkills.

The repository-level [`examples/hello-world/`](examples/hello-world/) directory is a portable business gSkill that has been compiled and run with the explicit `embedded` executor in the local Phase 2 evidence. It belongs to the source checkout, not the installed package: wheel validation rejects `graph_skill_runtime/examples/`, and installed acceptance rejects that namespace and every installed `graph.yaml`. A source distribution may contain this repository-level example and test fixtures as source corpus; installing that source distribution does not install or register them as a business gSkill.

The wheel may contain runtime implementation resources. Those resources are not business gSkills and do not make the wheel a skill registry.

## Optional MoirAI host integration

MoirAI is an optional design, repair, execution, and evaluation front door. Its canonical source bundle contains four role instructions (`moirai`, `moirai-clotho`, `moirai-lachesis`, and `moirai-atropos`), eight Agent Skills, and fifteen focused knowledge files. The six renderers project those assets into each selected host's native skill and agent directories and register the existing `gskill` MCP server. They do not install a business workflow, add a `graph.yaml`, or make MoirAI a core-runtime dependency.

These are installed-user commands and intentionally invoke `gskill` directly. Inspect the read-only PATH evidence, dry-run an explicit target, then apply only when the plan is acceptable:

```text
gskill integrations detect
gskill integrations install moirai --targets codex --scope user --dry-run
gskill integrations install moirai --targets codex --scope user
gskill integrations uninstall moirai --targets codex --scope user --dry-run
gskill integrations uninstall moirai --targets codex --scope user
```

For project scope, name the project and every target explicitly:

```text
gskill integrations install moirai --targets claude,codex --scope project --project-root PROJECT_ROOT --dry-run
gskill integrations install moirai --targets claude,codex --scope project --project-root PROJECT_ROOT
```

`--targets detected` is also accepted, but detection only reports supported executable names found on `PATH`; it neither invokes a host nor authorizes writes until used in an explicit install command. Package installation, import, installer construction, MCP startup, and detection write no host or project state.

The installer preflights every requested target before changing any of them. It never adopts or overwrites an unmanaged file or shared configuration entry, updates only a manifest-owned value, and uninstalls only exact unmodified owned hashes. After an apply failure, rollback restores a path only while that path still exactly equals the after-image written by this operation. If another process changed it, the installer preserves the concurrent content and raises an incomplete-rollback error instead of overwriting it. A modified managed resource is preserved and blocks the whole requested operation. Project manifests live under `PROJECT_ROOT/.gskill/integrations/moirai/`; user-scope manifests live under the runtime user state directory. OpenCode's `.opencode/opencode.json` is shared configuration: the installer merges and owns only `mcp.servers.gskill`, plus its separately projected manifest-owned files. A sibling `opencode.jsonc` causes a fail-closed conflict rather than being rewritten or shadowed.

The canonical role names remain provider-neutral and hyphenated: `moirai`, `moirai-clotho`, `moirai-lachesis`, and `moirai-atropos`. The Codex renderer alone normalizes hyphens to underscores for its safe identifier surface, so it writes paths such as `.codex/agents/moirai_clotho.toml` with `name = "moirai_clotho"`. Other renderers retain the hyphenated names. This adapter-specific projection does not change the canonical inventory.

### Phase 5 acceptance evidence

The source, built artifact, and real-host observations establish different parts of the accepted scope:

- Local source gates passed: Ruff; strict mypy over 149 source files; the contract manifest validator; and pytest with `1715 passed, 1 skipped in 83.51s`. `uv build` produced the `0.1.0a1` source distribution and wheel, and the built-wheel smoke passed. `pip-audit` reported `No known vulnerabilities found` for resolved third-party distributions while skipping the unpublished local `graph-skill-runtime`; that result is neither a source-code security audit nor publication evidence.
- The [renderer snapshot](tests/integrations/snapshots/moirai_renderers.json) locks all six renderers in project and user scope, including native paths, profile metadata, and MCP shape. A snapshot proves deterministic format projection, not operational behavior of six real products.
- The built wheel contained exactly 28 closed MoirAI members: one `integration.json`, four role bodies, eight Agent Skills, and fifteen knowledge files, with no `graph.yaml` and no extra member. A clean Python 3.11 environment installed that wheel, loaded the 4/8/15 inventory through `PackagedMoiraiAssets`, and used the wheel's `gskill` command to project a temporary project.
- On Windows `10.0.26200` x64, Claude Code `2.1.222` discovered all eight project skills in an isolated configuration, listed all four hyphenated MoirAI agents before authentication when given an invalid agent selector, accepted `moirai-clotho` as a valid selected profile, discovered the project `gskill` MCP entry, and started and connected its stdio server with tools, prompts, and resources capabilities. The valid-agent run then stopped at the machine's missing authentication; this proves skill, agent, and MCP discovery/startup, not authenticated Claude model execution.
- In an isolated Codex CLI `0.144.1` project, the host supplied project skill `$moirai`, and project MCP tool `gskill.inspect` successfully returned `skill_id=hello-world`. That session's spawn tool exposed no `agent_type`; its child metadata had `agent_role=null` and did not load custom `developer_instructions`. Codex custom-agent invocation is therefore not verified. This observed limitation does not invalidate the official standalone TOML format or the underscore-normalized renderer snapshot.

Phase 5 acceptance rests on Claude skill/agent/MCP discovery plus the Codex skill/MCP cross-check. It does not claim all six hosts are operational, authenticated model execution through Claude, or Codex custom-agent runtime invocation.

## Phase 6 package acceptance and publication boundary

[`scripts/accept_release_artifacts.py`](scripts/accept_release_artifacts.py) establishes one reproducible pre-publication boundary. `validate` requires the distribution directory to contain exactly one wheel and one `.tar.gz` source distribution. It checks names and versions, `Requires-Python`, the `gskill` console entry, the wheel's `py3-none-any` pure-Python declaration, non-traversing archive paths, explicit wheel-symlink rejection, source-distribution regular-file/directory membership, required package content, and the manifest-owned closed MoirAI asset subtree. The wheel rejects old `graph_agent/` and `graph_skill_runtime/examples/`; the source distribution rejects those namespaces under `src/`. A source distribution may still carry repository-level examples and tests as source corpus, but those files are not installed or registered as a business gSkill. This is a release content contract, not a fixed whitelist of every ordinary runtime source member.

`accept` requires the wheel and source distribution to match the manifest's sizes and SHA-256 values and requires the manifest's source commit to match `--expected-source-commit`. It copies those verified bytes, creates isolated environments, installs pip-wheel, uv-wheel, and pip-sdist channels, and writes `gskill.package-acceptance.v1`. That evidence includes the SHA-256 of the manifest it consumed; independently produced platform evidence with the same manifest digest proves that the platforms accepted the same manifest. There is no separate expected-manifest-hash argument.

Use the exact 40-hex commit represented by the clean candidate in place of `SOURCE_COMMIT`:

```text
uv build --no-sources
uv run --no-project --python 3.11 python scripts/accept_release_artifacts.py validate --dist-dir dist --manifest build/release-artifacts.json --source-commit SOURCE_COMMIT
uv run --no-project --python 3.11 python scripts/accept_release_artifacts.py accept --dist-dir dist --manifest build/release-artifacts.json --expected-source-commit SOURCE_COMMIT --logic-skill examples/hello-world --agent-skill tests/fixtures/demo-echo-agent --evidence build/package-acceptance.json
```

The installed smoke imports `graph_skill_runtime` from the isolated environment's site-packages and verifies that base installation did not pull provider extras or install `graph_skill_runtime/examples/` or any `graph.yaml`. It checks version and console identity, the six-target read-only host-detection inventory, exact enumeration of the eight MCP tools over a real stdio session plus a successful MCP `compile` call, CLI compile/inspect/predict/run, spaces and non-ASCII paths and values, and MoirAI project projection for Claude and Codex through planned → installed → unchanged → uninstalled. Its host-native fixture verifies run → reopened wait → submit → exact duplicate submit → reopened terminal state; both SQLite databases pass integrity and rename/reopen checks, the immutable request and trace exist, Windows releases file handles, and no unexpected host configuration appears outside the owned compile cache.

The Phase 6 implementation checkout passed local Ruff, strict mypy over 149 source files, the contract manifest validator, `1716 passed, 1 skipped`, seven distribution-contract tests, dependency audit with no known resolved-distribution vulnerabilities, and all three Windows package channels on Python `3.11.15` / Windows 10 AMD64. The local-project audit skip is not a source-code security audit. The first remote causal run is recorded in the [cross-platform policy](docs/CROSS_PLATFORM.md): one Actions-built candidate passed the three install channels on Ubuntu, Windows, and macOS with Python `3.11.16`, with identical artifact-manifest identity and the expected compile, run, durable handoff, integration lifecycle, and zero-unexpected-host-state observations on every platform.

This evidence makes the candidate eligible for a later release action; it does not publish it. The release workflow has not been triggered, no GitHub Release exists for this candidate, no registry upload has occurred, and no PyPI/TestPyPI project or trusted-publisher relationship has been exercised. The cross-platform smoke uses the deterministic host-native submission protocol, not real vendor CLIs. Direct vendor operational evidence therefore remains limited to the Windows/Codex combination documented below.

## Source-checkout requirements and development environment

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

Commands in this development section and the later runtime examples use `uv run gskill` because they execute the source checkout's managed environment. After installing the distribution into a user environment, invoke the installed `gskill` command directly, as in the MoirAI section above.

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

## Host-native two-step handoff

Host-native execution is a cooperative two-step protocol. First, start the run with a stable run id and state root:

```bash
uv run gskill run /absolute/path/to/my-skill --run-id host-demo --state-dir /absolute/path/to/state --inputs-json '{"question":"Why?"}'
```

For a supported Agent wait, the JSON result has `status: "agent_required"`; this is a successful CLI outcome with exit code `0`. Read `agent_required.task`, then use the current host's native subagent mechanism to create a new clean context and execute that task. The native subagent returns only an object that satisfies `task.output_schema`. Wrap that object in an `AgentResult` and submit it:

```bash
uv run gskill submit host-demo --state-root /absolute/path/to/state --checkpoint-ref 'gskill-handoff-v1:<task-id>' --result-json '{"schema_version":"gskill.agent-result.v1","kind":"agent_result","task_id":"<task-id>","status":"completed","output":{"answer":"..."},"executor_id":"host-native-subagent","provenance":{"session":"fresh"}}'
```

Replace `<task-id>` and the example `output` with the values required by the returned task. Durable `output` and `provenance` reject literal values under secret-shaped keys. `gskill submit` validates the task identity and output schema, writes a completed phase into the existing graph state, and returns either the next `agent_required` wait or the terminal result for the same `run_id`. A terminal `failed` or `cancelled` result does not execute the Agent phase: it idempotently fails the run and emits `agent_failed`. The equivalent submission entry points are Python `submit_agent_result(...)` and the MCP `submit_agent_result` tool. Direct vendor CLI execution instead starts one fresh vendor-native top-level process session for each task; it is not this native-child protocol.

## Direct vendor CLI execution

Select the CLI path explicitly and provide the business gSkill as usual:

```bash
uv run gskill run /absolute/path/to/my-skill --executor cli --vendor codex --run-id cli-demo --state-dir /absolute/path/to/state --inputs-json '{"question":"Why?"}'
```

The six implemented adapter values are `claude`, `codex`, `copilot`, `cursor`, `gemini`, and `opencode`. Optional CLI projections are `--agent-profile`, `--model`, `--executable`, and `--timeout-seconds`. `--executable` accepts a PATH basename or an absolute path; a relative path containing a separator fails before execution. The timeout defaults to 600 seconds and must be greater than zero and no more than 86,400 seconds.

`--agent-profile` is deliberately narrower than a generic “subagent” switch. Copilot and OpenCode pass it through their documented `--agent` selectors. Gemini prefixes `@<name>` to the task context so its main CLI agent can broker a request to that named subagent. Claude cannot select a custom agent under the required safe mode, Codex `--profile` selects configuration rather than a child agent, and Cursor has no documented direct selector, so those three reject `agent_profile` during configuration validation. If `--model` is omitted, the vendor chooses its own default. GitHub Copilot CLI is an agent product rather than a foundation model named “Copilot”; its current default and selectable models are vendor-managed, so the runtime does not hard-code them ([official CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)).

All six protocol adapters and their fake-process contract tests are implemented. An adapter implementation is not a blanket operating-system or version support claim. The current real-machine evidence is Windows `10.0.26200` x64 with Python `3.11.15`:

| Vendor adapter | Authentication probe | Agent profile | Session persistence provenance | Real operational evidence |
| --- | --- | --- | --- | --- |
| Claude | CLI-exposed and required | Rejected | `disabled` | Claude Code `2.1.222` passed executable/version/help probing but failed its auth probe; no successful run claim |
| Codex | CLI-exposed and required | Rejected | `disabled` | Codex CLI `0.144.1` completed a real gSkill run on this Windows host |
| Copilot | `not-exposed`; login failures surface from execution | Direct `--agent` | `vendor-default` | CLI not installed on the evidence host |
| Cursor | CLI-exposed and required | Rejected | `vendor-default` | CLI not installed on the evidence host |
| Gemini | `not-exposed`; login failures surface from execution | Brokered `@name` request | `vendor-default` | CLI not installed on the evidence host |
| OpenCode | `not-exposed`; login failures surface from execution | Direct `--agent` | `vendor-default` | CLI not installed on the evidence host |

Source-checkout CI on commit [`8928d13`](https://github.com/SevenX77/graph-skill-runtime/commit/8928d13b32c800a2ad303d02e1bd96551f969ab5) passed quality gates, Python 3.11/3.12/3.13 runtime tests, and both Windows and macOS cross-platform smoke jobs in [workflow run 33140732333](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33140732333); the CodeQL check, including Analyze Python, also passed. Phase 6 later added same-candidate installed-package acceptance to the required CI path, but that smoke uses deterministic host-native result submission rather than a real vendor executable. Neither run expands the operational support row beyond Windows/Codex `0.144.1`.

Each Agent task gets a new process and temporary working directory. The runtime passes no resume, continue, or prior session id. Claude and Codex explicitly disable session persistence; the other four may still save session records according to vendor defaults. “Fresh top-level session” therefore means no runtime-requested continuation of a prior task, not a blank vendor user configuration and not a native child of the current host conversation.

The complete business prompt never enters process argv: Claude, Codex, Cursor, and Gemini receive it on UTF-8 stdin; Copilot and OpenCode receive it through a temporary UTF-8 `agent-task.md`. Declared resources are read only when their resolved files fall under `AgentTask.allowed_paths`, then materialized as handle, summary, and content without their original paths. Aggregate resource input is limited to 1 MiB, the final prompt to 2 MiB, the output schema to 1 MiB, combined stdout and stderr to 4 MiB, and the Codex final-response file to 4 MiB. Every successful output is validated with Draft 2020-12 JSON Schema even when a vendor also applies a native schema. Invalid output and nonzero-exit diagnostics retain only an output SHA-256, never the raw rejected payload.

This is not one uniform cross-vendor operating-system sandbox. The runtime uses a fresh temporary working directory, a minimal allowlisted environment, vendor-exposed customization controls, and a prompt that forbids extra filesystem, shell, network, MCP, skill, and subagent tools. Vendor-managed credentials and configuration can still apply, and each CLI has different tool and sandbox strength. On this path, `allowed_paths` authorizes runtime resource materialization; it does not promise that an arbitrary vendor process can read only those paths. See the [cross-platform policy](docs/CROSS_PLATFORM.md) for process-tree ownership and the exact verification boundary.

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

The CLI `submit` command and the same-named SDK/MCP use case implement durable host-native result submission. `resume --checkpoint-ref ...` reads the current handoff wait or terminal response without applying a result. `resume` without a host-native handoff reference, including an ordinary human response, remains a structured `GSKILL_NOT_IMPLEMENTED` result.

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
uv build --no-sources
uv run pip-audit
```

`uv build --no-sources` must produce both a wheel and a source distribution without relying on local `tool.uv.sources` overrides. Run the Phase 6 `validate` and `accept` commands above when establishing package acceptance for a candidate. A local package skip reported by `pip-audit` is not evidence that this repository's own source has been security-audited; the command audits resolved third-party distributions.

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
