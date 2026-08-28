---
role: compliance-view
status: FROZEN
source: spec/features.yaml
---
<!-- DO NOT EDIT: Golden principle contract baseline. Generated from spec/features.yaml; change the manifest and regenerate this view. -->

# Feature Compliance Checklist

This FROZEN view follows the feature source of truth in manifest order. Each item records the feature description, review boundary, source anchors, every core implementation path, primary contract counts, and its canonical first targeted pytest node id. A feature may additionally enumerate its complete targeted-test set when exact evidence coverage is part of the feature contract.

## Manifest Features

### F-typed-runtime-facade: Expose one versioned, closed, immutable contract surface and typed Python facade for every standalone runtime use case.

- **Boundary**: public-method - graph_skill_runtime.__all__, SDK transport parity, and public-api contract
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/__init__.py`, `src/graph_skill_runtime/domain/models.py`, `src/graph_skill_runtime/sdk.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/test_public_api_contract.py::test_top_level_all_remains_the_declared_symbol_surface]`

### F-runtime-config-resolution: Resolve portable defaults, user machine profile, project profile, named preset, and invocation overrides into one provenance-bearing run request.

- **Boundary**: externally-observable-behavior - four-layer config resolver contract
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/application/config.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_config_resolver.py::test_four_layers_resolve_to_one_absolute_replayable_snapshot]`

### F-run-snapshot-persistence: Persist each resolved run request exactly once as an atomic, replayable local snapshot.

- **Boundary**: lifecycle-behavior - immutable local run snapshot store
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/snapshots.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_config_resolver.py::test_run_request_and_persisted_snapshot_are_immutable]`

### F-runtime-application-service: Own compile, resolution, prediction, execution, resume, agent-result submission, inspection, and golden evaluation behind provider-neutral ports.

- **Boundary**: lifecycle-behavior - one RuntimeApplication use-case exit
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/application/service.py`, `src/graph_skill_runtime/composition.py`, `src/graph_skill_runtime/ports/runtime.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_transport_parity.py::test_default_host_native_run_delegates_to_engine_and_keeps_request_snapshot]`

### F-runtime-cli-adapter: Project the application service through the gskill console command using structured JSON results.

- **Boundary**: public-method - gskill console entry point and transport parity
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/__main__.py`, `src/graph_skill_runtime/adapters/cli.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_transport_parity.py::test_sdk_cli_and_mcp_compile_are_projections_of_one_application_service]`

### F-runtime-mcp-adapter: Expose the same eight application use cases as typed MCP tools without duplicating runtime rules.

- **Boundary**: public-method - gskill MCP tool inventory and transport parity
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/mcp.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_transport_parity.py::test_mcp_exposes_the_same_eight_application_use_cases]`

### F-current-engine-adapter: Adapt the characterized extracted compiler, predictor, runner, inspection, and golden evaluator to the standalone typed application contract.

- **Boundary**: lifecycle-behavior - CurrentEngineAdapter contract tests
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/engine.py`, `src/graph_skill_runtime/adapters/result_mapping.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/application/test_current_engine_adapter.py::test_current_engine_adapter_compiles_and_runs_an_explicit_embedded_logic_skill]`

### F-host-native-agent-handoff: Persist a root Agent phase task before exposing it, validate a host-native result, and resume the same graph run exactly once across process boundaries.

- **Boundary**: lifecycle-behavior - durable AgentTask and AgentResult integration tests
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/agent_handoffs.py`, `src/graph_skill_runtime/adapters/host_native.py`, `src/graph_skill_runtime/adapters/host_native_runtime.py`, `src/graph_skill_runtime/adapters/engine.py`
- **Primary contracts**: 0 error codes, 4 events
- **Targeted tests**:
  - `tests/application/test_host_native_handoff.py::test_host_native_task_survives_process_boundary_and_resumes_same_run`
  - `tests/application/test_host_native_handoff.py::test_sequential_agent_phases_create_one_durable_task_at_a_time`
  - `tests/application/test_host_native_handoff.py::test_invalid_agent_output_does_not_consume_the_task`
  - `tests/application/test_host_native_handoff.py::test_cancelled_agent_result_fails_the_run_without_executing_the_phase`
  - `tests/application/test_host_native_handoff.py::test_agent_result_rejects_a_checkpoint_for_a_tampered_run_snapshot`
  - `tests/application/test_host_native_handoff.py::test_retry_recovers_when_graph_committed_before_handoff_response`
  - `tests/application/test_host_native_handoff.py::test_run_recovers_when_graph_paused_before_handoff_row_was_written`
  - `tests/application/test_host_native_handoff.py::test_host_native_agent_requires_a_durable_checkpoint_store`
  - `tests/application/test_host_native_handoff.py::test_parallel_agent_wait_point_fails_instead_of_falling_back_to_embedded`
  - `tests/application/test_host_native_handoff.py::test_agent_result_cannot_persist_secret_shaped_output_or_provenance`
  - `tests/application/test_host_native_handoff.py::test_cli_treats_agent_required_as_a_successful_two_step_protocol`
  - `tests/application/test_host_native_handoff.py::test_mcp_projects_the_same_host_native_submit_protocol`
- `[Covered By: tests/application/test_host_native_handoff.py::test_host_native_task_survives_process_boundary_and_resumes_same_run]`

### F-agent-cli-executors: Execute supported root-DAG Agent phases through capability-probed vendor CLI processes, validate the same provider-neutral AgentTask and AgentResult contracts, and resume the durable graph run only after schema-valid output.

- **Boundary**: lifecycle-behavior - vendor adapter contracts, process-tree tests, and durable CLI retry integration
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/cli.py`, `src/graph_skill_runtime/adapters/engine.py`, `src/graph_skill_runtime/adapters/host_native.py`, `src/graph_skill_runtime/adapters/host_native_runtime.py`, `src/graph_skill_runtime/adapters/process.py`, `src/graph_skill_runtime/adapters/vendor_cli/executor.py`, `src/graph_skill_runtime/adapters/vendor_cli/runtime.py`, `src/graph_skill_runtime/adapters/vendor_cli/vendors.py`, `src/graph_skill_runtime/adapters/windows_job.py`, `src/graph_skill_runtime/callbacks/events.py`, `src/graph_skill_runtime/domain/models.py`, `src/graph_skill_runtime/ports/process.py`
- **Primary contracts**: 0 error codes, 2 events
- **Targeted tests**:
  - `tests/adapters/test_vendor_cli_executor.py::test_each_vendor_probes_builds_a_fresh_session_and_parses_one_agent_result`
  - `tests/adapters/test_process_runner.py::test_timeout_terminates_the_whole_process_tree`
  - `tests/application/test_cli_runtime.py::test_cli_runtime_closes_one_agent_wait_with_causal_events`
  - `tests/application/test_cli_runtime.py::test_cli_runtime_rejects_unbridged_agent_capabilities_before_handoff`
  - `tests/application/test_cli_runtime.py::test_cli_failure_preserves_same_durable_task_for_retry`
- `[Covered By: tests/adapters/test_vendor_cli_executor.py::test_each_vendor_probes_builds_a_fresh_session_and_parses_one_agent_result]`

### F-md-frontmatter-parsing: Parse markdown frontmatter and body into stable skill metadata and diagnostics.

- **Boundary**: lifecycle-behavior - skill parser contract
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/parser.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/core/test_parse_skill_file.py::test_parse_markdown_parts_returns_frontmatter_body_and_line_meta]`

### F-graph-skill-loading: Load portable gSkill bundles from disk, validate topology, and build the phase registry.

- **Boundary**: lifecycle-behavior - GRAPH skill spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/loader.py`, `src/graph_skill_runtime/core/manifest.py`
- **Primary contracts**: 22 error codes, 0 events
- `[Covered By: tests/core/test_round14_skill_compilation_cutover.py::test_valid_portable_graph_uses_graph_yaml_as_the_only_phase_registry]`

### F-iterate-runtime: Compile and execute MVP1 iterate batch/loop contracts for node-level and graph-level loops.

- **Boundary**: lifecycle-behavior - iterate runtime contract
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/graph_assembler.py`, `src/graph_skill_runtime/core/loader.py`, `src/graph_skill_runtime/core/manifest.py`
- **Primary contracts**: 2 error codes, 0 events
- `[Covered By: tests/core/test_ws_e1_iterate_runtime_contract_red.py::test_loop_iterate_requires_item_and_accumulator_in_phase_inputs]`

### F-logic-action-execution: Run LOGIC action phases through registered Python actions and validators.

- **Boundary**: lifecycle-behavior - LOGIC skill spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/actions.py`
- **Primary contracts**: 14 error codes, 0 events
- `[Covered By: tests/core/test_context_facade_logic_action.py::test_logic_action_receives_plain_dict_not_context_facade]`

### F-subgraph-delegation: Compile and execute nested subgraphs while preserving parent-child IO boundaries.

- **Boundary**: lifecycle-behavior - SUBGRAPH skill spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/builtin_subagents/reference_reader.py`, `src/graph_skill_runtime/core/subagents.py`
- **Primary contracts**: 6 error codes, 3 events
- `[Covered By: tests/core/test_round14_skill_compilation_cutover.py::test_subgraph_io_input_mismatch_is_allowed_at_compile_time]`

### F-agent-phase-orchestration: Compile AGENT phases into prompt-driven execution with role, goal, tools, and finish contracts.

- **Boundary**: lifecycle-behavior - AGENT skill spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/graph_assembler.py`, `src/graph_skill_runtime/core/loader.py`
- **Primary contracts**: 16 error codes, 1 events
- `[Covered By: tests/fixtures/test_portable_agent_demo_compiles.py::test_portable_agent_demo_compiles_and_renders_template]`

### F-mention-resolution: Resolve @-mentions against tools, references, examples, subagents, and subgraphs before runtime.

- **Boundary**: lifecycle-behavior - mention syntax spec
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/mentions.py`
- **Primary contracts**: 2 error codes, 0 events
- `[Covered By: tests/core/test_round14_skill_compilation_cutover.py::test_missing_mention_target_is_rejected]`

### F-resource-reference-access: Expose reference and example resources through safe builtin reader tools.

- **Boundary**: public-method - resource mechanisms and builtin modules specs
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/tools/builtin/read_example.py`, `src/graph_skill_runtime/tools/builtin/read_reference.py`
- **Primary contracts**: 12 error codes, 0 events
- `[Covered By: tests/tools/test_builtin_resource_tools.py::test_read_reference_returns_declared_current_phase_markdown]`

### F-skill-resolution: Resolve target skills through local workspace registries with deterministic errors for misses and ambiguity.

- **Boundary**: lifecycle-behavior - skill resolver protocol spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/local_workspace_resolver.py`, `src/graph_skill_runtime/core/skill_resolver_protocol.py`
- **Primary contracts**: 6 error codes, 0 events
- `[Covered By: tests/core/test_local_workspace_resolver.py::test_local_workspace_resolver_resolves_direct_directory]`

### F-compile-runtime-flow: Keep compile, template assembly, and runtime workflow boundaries explicit and ordered.

- **Boundary**: lifecycle-behavior - compile-runtime flow spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/compiler.py`
- **Primary contracts**: 2 error codes, 0 events
- `[Covered By: tests/core/test_compile_skill_v030_root_rejection.py::test_compile_skill_rejects_legacy_schema_20_file_path]`

### F-runtime-execution: Run compiled graph skills and return stable workflow results to callers.

- **Boundary**: public-method - graph_skill_runtime.run_skill
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/cognitive/context_facade.py`, `src/graph_skill_runtime/core/edge_transition.py`, `src/graph_skill_runtime/core/result_contracts.py`
- **Primary contracts**: 1 error codes, 12 events
- `[Covered By: tests/core/test_run_skill_entrypoint_root_shape.py::test_run_skill_single_markdown_file_returns_portable_root_error]`

### F-state-blackboard: Map parent, child, and blackboard state without leaking unrelated execution state.

- **Boundary**: lifecycle-behavior - runtime state mapping
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/blackboard_contract.py`, `src/graph_skill_runtime/core/io_manager.py`, `src/graph_skill_runtime/core/run_context.py`, `src/graph_skill_runtime/core/runtime_state.py`
- **Primary contracts**: 1 error codes, 2 events
- `[Covered By: tests/test_round28_invariant_guards.py::test_round28_blackboard_state_has_explicit_mapping_boundary]`

### F-checkpoint-persistence: Persist and restore runtime checkpoints across graph execution boundaries.

- **Boundary**: lifecycle-behavior - checkpointer runtime
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/cache.py`, `src/graph_skill_runtime/core/checkpoint_validity.py`, `src/graph_skill_runtime/core/checkpointer.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/core/test_v030_deltachannel_checkpoint.py::test_sqlite_deltachannel_checkpoint_size]`

### F-callback-event-stream: Emit typed callback events with stable discriminator and schema metadata.

- **Boundary**: externally-observable-behavior - CallbackEvent union
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/callbacks/base.py`, `src/graph_skill_runtime/callbacks/emit.py`, `src/graph_skill_runtime/callbacks/events.py`, `src/graph_skill_runtime/core/event_contracts.py`
- **Primary contracts**: 0 error codes, 1 events
- `[Covered By: tests/callbacks/test_events.py::TestUnionDiscriminator::test_unknown_event_type_rejected]`

### F-callback-tracing: Record execution traces and callback payloads for downstream observability.

- **Boundary**: externally-observable-behavior - TracingCallback contract
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/callbacks/tracing.py`, `src/graph_skill_runtime/tracing/steps.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/callbacks/test_v030_trace_events.py::test_tracing_callback_writes_v030_typed_events]`

### F-error-code-recovery: Attach stable F-v3 error metadata, severity, and recovery hints to failures.

- **Boundary**: externally-observable-behavior - error code spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/error_registry.py`, `src/graph_skill_runtime/core/exceptions.py`
- **Primary contracts**: 0 error codes, 6 events
- `[Covered By: tests/test_round28_invariant_guards.py::test_round28_error_registry_keeps_f_v3_metadata_shape]`

### F-llm-prompt-assembly: Assemble the v0.3 cognitive prompt with the required eight business slots.

- **Boundary**: lifecycle-behavior - cognitive template spec
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/cognitive/critic.py`
- **Primary contracts**: 1 error codes, 2 events
- `[Covered By: tests/test_round28_invariant_guards.py::test_round28_prompt_template_keeps_eight_named_slots]`

### F-llm-execution: Dispatch model calls through configured providers, fallbacks, and predictive gateways.

- **Boundary**: lifecycle-behavior - LLM client manager
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/llm_provider.py`, `src/graph_skill_runtime/models/__init__.py`
- **Primary contracts**: 0 error codes, 6 events
- `[Covered By: tests/models/test_predict_gateway_chat_model.py::test_generate_uses_p0_golden_before_p1_override_and_p2_stub]`

### F-tool-call-binding: Bind tools into LLM phases while preserving finish_task and provider call behavior.

- **Boundary**: lifecycle-behavior - tool binding runtime
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/tools/builtin/cognitive_tools.py`
- **Primary contracts**: 1 error codes, 3 events
- `[Covered By: tests/models/test_predict_gateway_chat_model.py::test_bind_tools_preserves_predict_gateway_and_mock_strategy]`

### F-finish-task-validation: Validate finish_task output schema and reject incomplete agent completion payloads.

- **Boundary**: externally-observable-behavior - finish_task contract
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/cognitive/finish_task.py`, `src/graph_skill_runtime/middleware/exit_control.py`
- **Primary contracts**: 1 error codes, 2 events
- `[Covered By: tests/runtime/test_exit_contract.py::test_v030_exit_contract_is_hardcoded_at_prompt_tail]`

### F-md-patch: Apply markdown patch tools and reasoning patches without corrupting structured output.

- **Boundary**: lifecycle-behavior - md patch tool contract
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/cognitive/md2json.py`, `src/graph_skill_runtime/cognitive/md_patch.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/models/test_reasoning_patch.py::test_apply_reasoning_patch_is_idempotent]`

### F-tool-sandbox-permission: Reject unsafe tool/module operations that escape the allowed execution surface.

- **Boundary**: externally-observable-behavior - module sandbox and purity guard
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/module_sandbox.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/test_round28_invariant_guards.py::test_round28_tool_sandbox_blocks_write_and_escape_shapes]`

### F-tool-sandbox-isolation: Run builtin tools with isolated context access and predictable IO side effects.

- **Boundary**: lifecycle-behavior - tool runtime sandbox
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/tools/builtin/read_file.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/tools/test_read_file.py::TestReadFileBuiltin::test_path_traversal_blocked]`

### F-middleware-ordering: Mount cognitive middleware in the required observation-before-control order.

- **Boundary**: lifecycle-behavior - middleware ordering
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/middleware/__init__.py`, `src/graph_skill_runtime/middleware/factory.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/middleware/test_chain_topology.py::test_the_chain_order_is_the_contract]`

### F-middleware-mounting: Enable and disable runtime middleware based on attended, unattended, and configuration modes.

- **Boundary**: lifecycle-behavior - middleware factory
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/middleware/__init__.py`, `src/graph_skill_runtime/middleware/cognitive_flow.py`, `src/graph_skill_runtime/middleware/compaction.py`, `src/graph_skill_runtime/middleware/execution_control.py`, `src/graph_skill_runtime/middleware/factory.py`, `src/graph_skill_runtime/middleware/invocation_scope.py`, `src/graph_skill_runtime/middleware/loop_detection.py`, `src/graph_skill_runtime/middleware/nudge_policy.py`, `src/graph_skill_runtime/middleware/protocol_validation.py`, `src/graph_skill_runtime/middleware/runtime_input.py`, `src/graph_skill_runtime/middleware/tool_error.py`, `src/graph_skill_runtime/middleware/tool_history.py`
- **Primary contracts**: 0 error codes, 5 events
- `[Covered By: tests/core/test_cognitive_tools_mounting.py::test_cognitive_tools_mounted_unconditionally]`

### F-predict-internal-mocking: Provide deterministic prediction, golden-case mocks, and headless golden evaluation for offline execution and tests.

- **Boundary**: lifecycle-behavior - predict internal gateway
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/_predict_internal/exporter.py`, `src/graph_skill_runtime/core/_predict_internal/golden_eval.py`, `src/graph_skill_runtime/core/_predict_internal/hash.py`
- **Primary contracts**: 1 error codes, 0 events
- `[Covered By: tests/models/test_predict_gateway_chat_model.py::test_generate_sets_mock_metadata_and_zero_usage_without_provider_call]`

### F-serialization-output: Serialize manifests, callback payloads, and graph structures into stable JSON-safe output.

- **Boundary**: public-method - serialization public API
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/callbacks/serialize.py`, `src/graph_skill_runtime/core/graph_serializer.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/callbacks/test_serialize.py::TestPrimitives::test_passthrough]`

### F-graph-assembly: Assemble phase nodes into executable graphs while preserving graph serialization contracts.

- **Boundary**: public-method - graph assembly public API
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/graph_assembler.py`, `src/graph_skill_runtime/core/topology_projection.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/core/test_round14_skill_compilation_cutover.py::test_graph_serializer_fresh_render_emits_only_portable_yaml]`

### F-runtime-compatibility-patches: Apply runtime compatibility patches and compatibility hooks exactly through the central bootstrap path.

- **Boundary**: lifecycle-behavior - bootstrap patches and reasoning compatibility
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/bootstrap.py`, `src/graph_skill_runtime/patches/__init__.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/test_bootstrap.py::test_apply_patches_calls_central_patch_entry_once]`

### F-observability-metrics: Expose logging and metrics callbacks for operational visibility without changing execution semantics.

- **Boundary**: externally-observable-behavior - logging and metrics callbacks
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/callbacks/logging_cb.py`, `src/graph_skill_runtime/callbacks/metrics.py`, `src/graph_skill_runtime/callbacks/token_accounting.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/callbacks/test_events.py::TestSchemaInvariants::test_every_class_stamps_schema_version_1_0[PhaseStartEvent]]`

### F-clarification-flow: Handle ambiguity and clarification workflows consistently in attended and unattended modes.

- **Boundary**: externally-observable-behavior - clarification middleware
- **Sources**: `public-api`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/cognitive/clarification_middleware.py`
- **Primary contracts**: 0 error codes, 2 events
- `[Covered By: tests/middleware/test_beta_clarification_and_runtime_integration.py::test_ask_clarification_unattended_path_returns_conservative_auto_answer]`

### F-parallel-map-tools: Run parallel map and builtin tool providers through stable tool contracts.

- **Boundary**: lifecycle-behavior - parallel map builtin tool
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/tools/builtin/parallel_map.py`
- **Primary contracts**: 0 error codes, 2 events
- `[Covered By: tests/tools/test_parallel_map.py::test_parallel_map_runs_children_in_input_order_and_emits_group_events]`

### F-storage-io: Store, load, and analyze IO artifacts through graph-skill-runtime storage and analyzer helpers.

- **Boundary**: lifecycle-behavior - IO storage helpers
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/artifacts.py`, `src/graph_skill_runtime/core/storage_contracts.py`, `src/graph_skill_runtime/io/artifact_manifest.py`, `src/graph_skill_runtime/io/manager.py`, `src/graph_skill_runtime/io/run_layout.py`
- **Primary contracts**: 0 error codes, 1 events
- `[Covered By: tests/io/test_storage.py::TestStorageManagerBasics::test_save_artifact_writes_str_bytes_and_json]`

### F-portable-gskill-v1: Compile one root Agent Skill entry, graph.yaml topology, flat graph registry, internal phase documents, and root artifact declarations as one portable business gSkill bundle.

- **Boundary**: lifecycle-behavior - portable gSkill v1 bundle contract
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/core/loader.py`, `src/graph_skill_runtime/core/manifest.py`
- **Primary contracts**: 10 error codes, 0 events
- `[Covered By: tests/core/test_portable_gskill_v1.py::test_missing_root_entry_and_graph_are_reported_in_one_compile]`

### F-studio-skill-migration: Convert one legacy Studio v0.3 skill into the portable v1 layout through an explicit, deterministic, no-overwrite CLI operation.

- **Boundary**: externally-observable-behavior - portable gSkill v1 migration contract
- **Sources**: `skill-spec`, `source-file-map`
- **Core paths**: `src/graph_skill_runtime/adapters/cli.py`, `src/graph_skill_runtime/migration/studio_v030.py`
- **Primary contracts**: 0 error codes, 0 events
- `[Covered By: tests/migration/test_studio_v030.py::test_converter_renames_internal_agent_entry_and_emits_one_root_skill]`
