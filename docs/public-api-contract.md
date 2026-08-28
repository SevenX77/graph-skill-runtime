# Public API Contract

This document records the implemented top-level Python contract for `graph-skill-runtime` `0.1.0a1`. Phase 2 changed the accepted business-skill format without changing the 58-symbol Phase 1 facade. The executable symbol source is [`graph_skill_runtime.__all__`](../src/graph_skill_runtime/__init__.py); this document must contain exactly one strict `## <symbol>` heading for each of those 58 names. The distribution has not been published to PyPI.

## 1. Contract-wide rules

Every public Pydantic model is defined in [`domain/models.py`](../src/graph_skill_runtime/domain/models.py), forbids unknown fields, is frozen after construction, and carries a literal `schema_version` plus a literal `kind`. Nested JSON dictionaries and lists are also frozen, so a caller cannot mutate a validated request through a child collection. Invalid fields, values, discriminators, or cross-field combinations fail model construction with Pydantic validation errors.

The public facade uses JSON-compatible typed contracts instead of unbounded `Any` configuration. Executor and checkpoint-store unions discriminate on `kind`. Identifiers use `^[A-Za-z][A-Za-z0-9_.-]*$` where the model declares an identifier field.

Literal values stored under structurally secret-shaped keys are rejected from persistent input and override objects. Secret values are represented by `SecretReference` and `SecretBinding`; the runtime cannot determine whether every arbitrary business string is confidential.

The eight SDK functions in [`sdk.py`](../src/graph_skill_runtime/sdk.py), the `gskill` CLI, and the eight same-named MCP tools delegate to one [`RuntimeApplication`](../src/graph_skill_runtime/application/service.py). Each SDK call accepts an optional `application=` dependency. If omitted, it calls `create_application()`; no global application singleton is used.

## 2. Phase boundary

The current engine adapter accepts only an explicit business-skill root defined by the [portable format contract](skill-spec/01-PORTABLE-GSKILL-V1.md): root `SKILL.md`, `graph.yaml`, phase `LOGIC.md` / `AGENT.md` / `SUBGRAPH.md`, and an optional flat `graphs/<graph_id>/` registry. Production SDK, CLI, MCP, compile, inspect, predict, and run paths do not fall back to v0.3. Legacy parsing is confined to the explicit `gskill migrate studio-skill` converter. The default executor is `host-native`, but its durable adapter is not implemented: `run` persists the resolved request and returns `GSKILL_EXECUTOR_UNAVAILABLE`. Only explicit `embedded` execution reaches the engine. Durable `resume` and `submit_agent_result` return `GSKILL_NOT_IMPLEMENTED` until Phase 3.

The Port types below define provider-neutral boundaries. Their presence does not imply that Phase 1 ships a default adapter for every Port.

## AgentExecutor

- **Responsibility**: protocol for executing one `AgentTask` without owning graph checkpoint state.
- **Interface**: read-only `executor_id: str`; `execute(task: AgentTask) -> AgentResult`.
- **Failure semantics**: an implementation reports terminal task failure in `AgentResult`; transport or adapter exceptions are implementation-boundary failures. No host-native or vendor CLI implementation ships in Phase 1.

## AgentRequired

- **Responsibility**: versioned pause payload saying a durable agent task is ready for an external host; defining the payload does not mean Phase 1 emits it.
- **Fields**: `task: AgentTask`, non-empty `checkpoint_ref`, and `submit_methods`, defaulting to `("mcp", "cli")`.
- **Failure semantics**: invalid task or empty checkpoint reference fails validation. Phase 1 returns executor-unavailable before producing this payload because durable handoff is Phase 3 work.

## AgentResult

- **Responsibility**: terminal result returned by an agent executor.
- **Fields**: non-empty `task_id`, `status` (`completed`, `failed`, or `cancelled`), optional JSON `output`, optional `RuntimeErrorPayload`, non-empty `executor_id`, and JSON `provenance`.
- **Failure semantics**: `completed` requires `output`; `failed` and `cancelled` require `error`. Mismatched terminal payloads fail validation.

## AgentTask

- **Responsibility**: least-authority, provider-neutral unit of work for one agent phase.
- **Fields**: task/run identity, `PhaseAddress`, instructions, JSON inputs and output schema, allowed tools and paths, network policy, optional deadline, and required capabilities.
- **Failure semantics**: empty identities or instructions, invalid identifiers, an invalid network discriminator, or non-JSON payloads fail validation. Phase 1 does not yet dispatch this model through host-native handoff.

## ArtifactRequest

- **Responsibility**: select one declared artifact for a run and optionally name its destination.
- **Fields**: identifier-shaped `artifact_id` and optional `destination` string.
- **Failure semantics**: an invalid artifact identifier fails validation. Phase 1 does not treat this request as permission to redefine artifact declarations.

## ArtifactStore

- **Responsibility**: protocol for materializing declared bytes and returning a stable reference.
- **Interface**: `write(run_id: str, artifact_id: str, content: bytes) -> str`.
- **Failure semantics**: storage, ownership, and collision failures belong to the adapter; Phase 1's default composition does not inject an `ArtifactStore`.

## CheckpointStore

- **Responsibility**: protocol that durably owns graph-state generations, separate from agent process/session supervision.
- **Interface**: `save(run_id: str, generation: int, state: JsonObject) -> str` and `load(checkpoint_ref: str) -> JsonObject`.
- **Failure semantics**: missing, stale, or conflicting generations must fail in the adapter. The public Port does not make Phase 3 durable typed resume complete.

## CliExecutorConfig

- **Responsibility**: select a future vendor CLI executor without embedding provider objects in the public API.
- **Fields**: `kind="cli"`, vendor (`claude`, `codex`, `copilot`, `cursor`, `gemini`, or `opencode`), optional `agent_profile`, and optional `model_override`.
- **Failure semantics**: an unsupported vendor or unknown field fails validation. Phase 1 has no executable probe, argv builder, or vendor process adapter; a resolved CLI run returns `GSKILL_EXECUTOR_UNAVAILABLE`.

## CompareCandidate

- **Responsibility**: identify one model comparison candidate for a graph-local phase.
- **Fields**: `PhaseAddress`, identifier-shaped `candidate_id`, and optional `model_override`.
- **Failure semantics**: invalid addresses or identifiers fail validation. Capability and model availability checks belong to the executing adapter.

## CompileDiagnostic

- **Responsibility**: transport-neutral projection of one compile issue.
- **Fields**: non-empty `code`, severity (`fatal`, `warning`, or `info`), non-empty message, optional source path, positive line, field path, graph/phase identity, and conflicting phase.
- **Failure semantics**: invalid severity, blank required text, or a line below one fails validation. A fatal diagnostic determines failed `CompileResult` status.

## CompileRequest

- **Responsibility**: request compilation of an explicitly supplied skill root.
- **Fields**: non-empty `skill_root` and `cache`, defaulting to `True`.
- **Failure semantics**: model validation rejects a blank root. The default engine adapter reports compile/parser/loader failures as a failed `CompileResult` with fatal diagnostics.

## CompileResult

- **Responsibility**: complete structured outcome of one compile pass.
- **Fields**: status (`passed` or `failed`), optional `skill_id`, and an immutable tuple of `CompileDiagnostic`; `passed` is a derived convenience property.
- **Failure semantics**: `failed` requires at least one fatal diagnostic, and `passed` forbids fatal diagnostics. An inconsistent result fails validation.

## ConfigResolution

- **Responsibility**: return the normalized machine profile and the exact replayable run request produced by one resolution.
- **Fields**: `profile: ResolvedRuntimeProfile` and `request: RunRequest`; the request embeds the same resolved profile.
- **Failure semantics**: malformed nested contracts fail validation. Resolution failures occur before this model exists and are reported by `ConfigResolver`.

## ConfigResolver

- **Responsibility**: own the single configuration precedence implementation and field provenance.
- **Interface**: `ConfigResolver(user_config_path: Path | None = None)` and `resolve(invocation, *, portable_runtime=None, portable_defaults=None) -> ConfigResolution`; `user_config_path` exposes the resolved machine-config path without creating it.
- **Inputs and outputs**: precedence is invocation > project `<skill_root>/gskill.toml` > OS user config > portable values > built-in defaults. Project or portable sources may own a `RunPreset`; user config may own only a machine `RuntimeProfile` overlay. Output roots are absolute.
- **Failure semantics**: invalid TOML/schema, an unknown requested preset, or a non-directory root raises `ConfigurationError` with `GSKILL_CONFIG_INVALID`; filesystem resolution can also raise an OS error. It never silently guesses a preset or writes configuration.

## ConfigSource

- **Responsibility**: enumerate the provenance layer for a resolved value.
- **Values**: `default`, `portable`, `user`, `project`, `preset`, and `invocation`.
- **Failure semantics**: unknown enum values fail validation. `preset` identifies business values selected from project configuration, while `project` identifies the runtime overlay.

## ConfigurationError

- **Responsibility**: boundary exception for rejected configuration before runtime execution.
- **Interface**: constructed from one `RuntimeErrorPayload`, retained as `.payload`; its exception message is `payload.message`.
- **Failure semantics**: the default resolver uses code `GSKILL_CONFIG_INVALID`. The CLI serializes this payload and exits nonzero; the Python SDK exposes the exception to its caller.

## EmbeddedExecutorConfig

- **Responsibility**: explicitly select the extracted embedded engine path.
- **Fields**: `kind="embedded"`, optional identifier-shaped `provider`, optional `model`, and optional `credential: SecretReference`.
- **Failure semantics**: invalid provider identifiers or inline credential shapes fail validation. Provider clients live in the optional `embedded` extra; current evidence proves a real portable `LOGIC` path, not general provider-backed AGENT parity.

## EventSink

- **Responsibility**: protocol for receiving ordered public `RuntimeEvent` envelopes.
- **Interface**: `emit(event: RuntimeEvent) -> None`.
- **Failure semantics**: ordering, durability, and sink I/O failures belong to the adapter. The default Phase 1 composition does not inject an `EventSink` or claim full host-native lifecycle emission.

## GoldenEvaluationRequest

- **Responsibility**: request evaluation of one stored golden baseline for an explicit skill and state root.
- **Fields**: non-empty `skill_root`, non-empty `state_root`, and identifier-shaped `baseline_id`.
- **Failure semantics**: invalid fields fail validation; inaccessible paths or engine evaluation failures become a failed `GoldenEvaluationResult` in the default adapter.

## GoldenEvaluationResult

- **Responsibility**: structured golden-evaluation outcome.
- **Fields**: status (`passed` or `failed`), `baseline_id`, JSON `details`, and optional `RuntimeErrorPayload`.
- **Failure semantics**: the current adapter returns `GSKILL_RUN_FAILED` when evaluation raises or reports failure. This model does not require every failed result to carry an error, so producers remain responsible for a complete diagnostic.

## HostNativeExecutorConfig

- **Responsibility**: select cooperative execution by the current host; it is the default `RuntimeProfile.executor` discriminator.
- **Fields**: only `schema_version` and `kind="host-native"`.
- **Failure semantics**: the contract validates today, but the Phase 1 adapter is unavailable. `run` saves the request snapshot and returns `GSKILL_EXECUTOR_UNAVAILABLE` without silently falling back.

## InputBinding

- **Responsibility**: bind a JSON value to one named input on a `PhaseAddress`.
- **Fields**: address, identifier-shaped field name, and JSON `value`.
- **Failure semantics**: invalid addresses/identifiers/non-JSON values fail validation; structurally secret-shaped literal keys inside the value are rejected and must be represented with secret-reference contracts.

## InspectRequest

- **Responsibility**: request compiled topology information for an explicit skill root.
- **Fields**: non-empty `skill_root` and `include_call_graph`, defaulting to `False`.
- **Failure semantics**: a blank root fails validation. The current adapter returns compile diagnostics instead of raising normal compile failures; when requested, inspection projects the flat-registry call graph from the same explicit graph references used by compilation.

## InspectResult

- **Responsibility**: return inspected skill identity, graph identifiers, call edges, and compile diagnostics.
- **Fields**: optional `skill_id`, immutable `graphs`, immutable `(caller, callee)` `call_edges`, and immutable diagnostics.
- **Failure semantics**: malformed tuples or diagnostics fail validation. `CurrentEngineAdapter` reports the root and registry graph ids, explicit call edges, and compile diagnostics from the portable bundle; it does not maintain a second topology source.

## MemoryCheckpointStoreConfig

- **Responsibility**: select an in-memory checkpoint-store configuration.
- **Fields**: only `schema_version` and `kind="memory"`.
- **Failure semantics**: unknown fields fail validation. This configuration value does not itself provide persistence or make durable Phase 3 resume available.

## NodeOverride

- **Responsibility**: carry a typed per-phase timeout and JSON parameter override.
- **Fields**: `PhaseAddress`, optional positive `timeout_seconds`, and JSON `custom_params`.
- **Failure semantics**: non-positive timeouts and invalid addresses fail validation. Structurally secret-shaped literal keys in `custom_params` are rejected; use secret-reference contracts instead.

## PermissionPolicy

- **Responsibility**: describe the run's requested network and filesystem policy without binding the public API to one host.
- **Fields**: `network` (`deny`, `host-policy`, or `allow`, default `host-policy`) and `filesystem` (`declared-only` or `skill-and-state`, default `skill-and-state`).
- **Failure semantics**: unknown policy values fail validation. Phase 1 snapshots this policy but has no host-native adapter that enforces it.

## PhaseAddress

- **Responsibility**: stable graph-local address used by bindings, overrides, diagnostics, and handoff contracts.
- **Fields**: identifier-shaped `graph_id` and `phase_id`; `.value` renders `<graph_id>/<phase_id>`.
- **Failure semantics**: malformed identifiers fail validation. The address model does not prove that the referenced graph or phase exists; compilation owns that check.

## PredictRequest

- **Responsibility**: pair one unresolved `RunInvocation` with a supported prediction strategy.
- **Fields**: `invocation` and `strategy="heuristic"`.
- **Failure semantics**: an unknown strategy or invalid invocation fails validation. The application resolves and snapshots the invocation before delegating to the engine predictor.

## ResolvedRuntimeProfile

- **Responsibility**: immutable normalized machine profile plus path and provenance snapshot for one run.
- **Fields**: complete `RuntimeProfile`, absolute string `skill_root`, absolute string `state_root`, and immutable `field_origins`.
- **Failure semantics**: relative roots fail validation. Path existence and directory checks occur in `ConfigResolver`, before this model is returned.

## ResumeRequest

- **Responsibility**: typed request to resume a named run from explicit skill/state roots and optional checkpoint or human response.
- **Fields**: non-empty `run_id`, `skill_root`, and `state_root`; optional `checkpoint_ref`; optional JSON `human_response`.
- **Failure semantics**: invalid fields fail validation. `CurrentEngineAdapter.resume` returns a failed `RunResult` with `GSKILL_NOT_IMPLEMENTED`; Phase 1 does not yet reload and advance a durable typed checkpoint.

## RunInvocation

- **Responsibility**: represent exactly what one caller supplied before precedence resolution.
- **Fields**: skill root, optional run/preset identity, partial `RuntimeProfileOverlay`, and optional inputs, secret bindings, phase bindings, breakpoints, node overrides, compare candidates, and artifact requests.
- **Input semantics**: `None` means inherit the selected preset/default; an explicit empty collection clears that category. The resolver generates a UUID when `run_id` is absent.
- **Failure semantics**: invalid nested contracts and structurally secret-shaped literal keys in `inputs` fail validation. Root existence, configuration, and preset selection fail later in `ConfigResolver`.

## RunPreset

- **Responsibility**: reusable, named business defaults separated from machine configuration.
- **Fields**: identifier-shaped `preset_id`; JSON inputs; secret references; bindings; breakpoints; node overrides; compare candidates; and artifact requests.
- **Ownership**: named presets may come from project `gskill.toml` or an explicitly supplied portable default. OS user config cannot own them.
- **Failure semantics**: invalid nested values or structurally secret-shaped literal keys in `inputs` fail validation. A preset may persist secret references, never secret values.

## RunRequest

- **Responsibility**: exact replayable execution snapshot produced by configuration resolution.
- **Fields**: non-empty `run_id`, optional `preset_id`, `ResolvedRuntimeProfile`, resolved business values, and immutable `value_origins`.
- **Snapshot semantics**: it contains absolute skill/state roots through its profile. The default local store writes it to `<state_root>/runs/<run_id>/request.json` before prediction or execution.
- **Failure semantics**: malformed nested contracts fail validation. Resolved requests should come from `ConfigResolver`, whose invocation/preset boundaries reject structurally secret-shaped literal values; the snapshot stores only `SecretBinding` references for secrets.

## RunResult

- **Responsibility**: common structured result for run, predict, and resume modes.
- **Fields**: status (`completed`, `failed`, `paused`, or `agent_required`), run identity, mode, optional request, JSON outputs, optional trace path, optional error, optional `AgentRequired`, and compile diagnostics.
- **Failure semantics**: `failed` requires `error`; `agent_required` requires an `AgentRequired` payload, and every other status forbids that payload. Inconsistent combinations fail validation.

## RunSnapshotStore

- **Responsibility**: Port that persists and reloads the exact immutable `RunRequest` before execution begins.
- **Interface**: `save(request: RunRequest) -> str` and `load(state_root: Path, run_id: str) -> RunRequest`.
- **Failure semantics**: the default `LocalRunSnapshotStore` validates a one-segment run id, atomically creates `request.json`, treats identical content as idempotent, rejects different content for an existing run id, and wraps unreadable/invalid snapshots as `ValueError`.

## RuntimeApplication

- **Responsibility**: single transport-independent owner of use-case ordering.
- **Construction**: requires explicit `ConfigResolver`, `RuntimeEngine`, and `RunSnapshotStore` dependencies.
- **Interface**: `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `evaluate_golden`, `inspect`, and `load_run_request`. `predict` and `run` resolve and save the request before calling or selecting an engine path.
- **Failure semantics**: non-embedded `run` returns `GSKILL_EXECUTOR_UNAVAILABLE` after snapshot persistence. `submit_agent_result` returns `GSKILL_NOT_IMPLEMENTED`. Dependency exceptions otherwise retain their native boundary unless a called adapter returns a structured result.

## RuntimeEngine

- **Responsibility**: provider-neutral Port behind `RuntimeApplication` for current engine capabilities.
- **Interface**: `compile(CompileRequest)`, `predict(RunRequest)`, `run(RunRequest)`, `resume(ResumeRequest)`, `evaluate_golden(GoldenEvaluationRequest)`, and `inspect(InspectRequest)`, each returning its typed result.
- **Failure semantics**: adapters should project expected domain failures into typed results. The current `CurrentEngineAdapter` implements portable compile/predict/run/golden/inspect and a structured not-implemented resume.

## RuntimeErrorCode

- **Responsibility**: stable application-boundary error catalog shared by transports.
- **Values**: `GSKILL_CONFIG_INVALID`, `GSKILL_COMPILE_FAILED`, `GSKILL_EXECUTOR_UNAVAILABLE`, `GSKILL_INTERNAL_ERROR`, `GSKILL_INVALID_REQUEST`, `GSKILL_NOT_IMPLEMENTED`, `GSKILL_RUN_FAILED`, and `GSKILL_SNAPSHOT_NOT_FOUND`.
- **Failure semantics**: an unknown code fails enum/model validation. Not every declared code is emitted by every Phase 1 adapter.

## RuntimeErrorPayload

- **Responsibility**: provider-neutral structured failure body.
- **Fields**: `RuntimeErrorCode`, non-empty message, `retryable` flag, optional phase and source path, and JSON details.
- **Failure semantics**: invalid code, blank message, non-JSON details, or unknown fields fail validation. Callers should branch on `code`, not parse message text.

## RuntimeEvent

- **Responsibility**: versioned public transport envelope around one observable event.
- **Fields**: `event_type` is a closed 38-value Literal: `agent_exit_decision`, `agent_loop_iteration`, `ambiguity_logged`, `artifact_saved`, `blackboard_reduce`, `builtin_subagent_enter`, `builtin_subagent_exit`, `builtin_subagent_fallback`, `compaction`, `dead_end_pruned`, `edge_end`, `edge_start`, `finish_task_verdict`, `input_dispatch`, `input_file_injected`, `interrupted`, `llm_call`, `llm_call_settings`, `llm_delta`, `llm_route_decision`, `loop_detected`, `nudge`, `parallel_map_group_ended`, `parallel_map_group_started`, `phase_end`, `phase_start`, `predict_chain_start`, `prompt_captured`, `protocol_violation`, `resumed`, `run_ended`, `run_started`, `runtime_input_injected`, `tool_call`, `tool_call_started`, `tool_error_handled`, `tool_history_repaired`, or `working_memory_update`. The remaining fields are non-empty `run_id`, non-negative `sequence`, non-empty timestamp, and JSON payload.
- **Failure semantics**: any event type outside that catalog, an invalid identity, a negative sequence, or a non-JSON payload fails validation. The [public API contract test](../tests/test_public_api_contract.py) proves this catalog is exactly equal to every concrete `CallbackEvent` discriminator in `callbacks/events.py`; a complete host-native event lifecycle still belongs to Phase 3.

## RuntimeProfile

- **Responsibility**: complete machine/runtime choices, deliberately excluding business run values.
- **Fields**: primary executor (default host-native), checkpoint store (default SQLite), optional state directory, permission policy, required capabilities, and fallback executor declarations.
- **Failure semantics**: a fallback cannot repeat the primary executor kind, and fallback kinds cannot repeat each other. Phase 1 records fallback declarations but does not silently execute them.

## RuntimeProfileOverlay

- **Responsibility**: partial machine/runtime values contributed by one precedence layer.
- **Fields**: optional executor, checkpoint store, state directory, permissions, required capabilities, and fallback executors.
- **Failure semantics**: a blank `state_dir`, invalid discriminated union, or malformed nested contract fails validation. `None` leaves a lower-precedence value unchanged.

## SecretBinding

- **Responsibility**: bind a business input name to a secret reference without persisting the secret value.
- **Fields**: identifier-shaped `input_name` and `reference: SecretReference`.
- **Failure semantics**: invalid identifiers or references fail validation. Resolution and snapshots preserve the reference, not a fetched value.

## SecretReference

- **Responsibility**: point to a secret owned by an environment, host, or operating-system keychain.
- **Fields**: source (`environment`, `host`, or `keychain`) and a 1-to-256-character name.
- **Failure semantics**: unknown sources and blank or overlong names fail validation. The contract does not read or resolve the secret by itself.

## SkillSource

- **Responsibility**: storage-neutral Port for reading an explicitly supplied skill-relative text file.
- **Interface**: `read_text(skill_root: Path, relative_path: str) -> str`.
- **Failure semantics**: missing files, invalid paths, encoding, and containment enforcement belong to the adapter. It is not a global business-skill discovery API.

## SqliteCheckpointStoreConfig

- **Responsibility**: select a SQLite checkpoint-store configuration.
- **Fields**: `kind="sqlite"` and filename, defaulting to `checkpoints.sqlite3`.
- **Failure semantics**: the filename must be a single path segment and cannot contain `/` or `\\`. This config value does not itself implement Phase 3 durable typed resume.

## SubmitAgentResultRequest

- **Responsibility**: typed request to submit one terminal `AgentResult` against a durable checkpoint.
- **Fields**: non-empty `run_id`, `state_root`, and `checkpoint_ref`, plus `result: AgentResult`.
- **Failure semantics**: invalid fields or result combinations fail validation. `RuntimeApplication.submit_agent_result` currently returns `GSKILL_NOT_IMPLEMENTED`; identity, generation, and idempotency transitions are Phase 3 work.

## ValueOrigin

- **Responsibility**: record the exact precedence source for one resolved field.
- **Fields**: non-empty field path, `ConfigSource`, and optional source path.
- **Failure semantics**: blank fields or unknown source values fail validation. A missing `source_path` is valid for invocation, portable, and built-in sources that have no file.

## compile

- **Responsibility**: thin Python facade for `RuntimeApplication.compile`.
- **Signature**: `compile(request: CompileRequest, *, application: RuntimeApplication | None = None) -> CompileResult`.
- **Failure semantics**: the default current-engine adapter converts compile exceptions into a failed result with fatal diagnostics. Invalid requests fail during `CompileRequest` construction.

## create_application

- **Responsibility**: explicit composition root for SDK, CLI, and MCP dependencies.
- **Signature**: `create_application(*, user_config_path: Path | None = None, engine: RuntimeEngine | None = None, snapshot_store: RunSnapshotStore | None = None) -> RuntimeApplication`.
- **Output**: a new application using `ConfigResolver`, `CurrentEngineAdapter`, and `LocalRunSnapshotStore` for omitted dependencies.
- **Failure semantics**: it creates no global singleton and writes no host or project configuration. Dependency-construction errors propagate to the caller.

## evaluate_golden

- **Responsibility**: thin Python facade for one golden-baseline evaluation.
- **Signature**: `evaluate_golden(request: GoldenEvaluationRequest, *, application: RuntimeApplication | None = None) -> GoldenEvaluationResult`.
- **Failure semantics**: the default adapter returns a failed result with `GSKILL_RUN_FAILED` when engine evaluation raises or reports failure.

## inspect

- **Responsibility**: thin Python facade for compiled topology inspection.
- **Signature**: `inspect(request: InspectRequest, *, application: RuntimeApplication | None = None) -> InspectResult`.
- **Failure semantics**: the default adapter projects compile failures into `InspectResult.diagnostics` and, when requested, projects call edges from the compiled portable bundle.

## predict

- **Responsibility**: resolve and snapshot a `PredictRequest.invocation`, then delegate the immutable request to the engine predictor.
- **Signature**: `predict(request: PredictRequest, *, application: RuntimeApplication | None = None) -> RunResult`.
- **Failure semantics**: configuration, snapshot-collision, and unexpected engine exceptions propagate at the Python boundary; successful engine projection uses `RunResult(mode="predict")`.

## resolve_run

- **Responsibility**: expose the single configuration resolver without executing a skill.
- **Signature**: `resolve_run(invocation: RunInvocation, *, portable_runtime: RuntimeProfileOverlay | None = None, portable_defaults: RunPreset | None = None, application: RuntimeApplication | None = None) -> ConfigResolution`.
- **Failure semantics**: invalid configuration or preset selection raises `ConfigurationError`; missing/inaccessible paths can raise OS errors. Resolution itself does not persist the returned request.

## resume

- **Responsibility**: thin Python facade for typed run resumption.
- **Signature**: `resume(request: ResumeRequest, *, application: RuntimeApplication | None = None) -> RunResult`.
- **Failure semantics**: the default Phase 1 engine returns `RunResult(status="failed", mode="resume")` with `GSKILL_NOT_IMPLEMENTED`. It must not be described as durable resume until Phase 3.

## run

- **Responsibility**: resolve one invocation, persist its immutable request, and select the explicitly resolved executor path.
- **Signature**: `run(invocation: RunInvocation, *, application: RuntimeApplication | None = None) -> RunResult`.
- **Failure semantics**: host-native and CLI selections return `GSKILL_EXECUTOR_UNAVAILABLE` after snapshot persistence. Only explicit embedded selection calls the current engine. Configuration and snapshot-collision errors propagate at the Python boundary; no implicit fallback occurs.

## submit_agent_result

- **Responsibility**: thin Python facade for the typed durable agent-result submission use case.
- **Signature**: `submit_agent_result(request: SubmitAgentResultRequest, *, application: RuntimeApplication | None = None) -> RunResult`.
- **Failure semantics**: Phase 1 always returns a failed resume-mode result with `GSKILL_NOT_IMPLEMENTED`. Durable checkpoint validation and idempotent state transition are Phase 3 responsibilities.
