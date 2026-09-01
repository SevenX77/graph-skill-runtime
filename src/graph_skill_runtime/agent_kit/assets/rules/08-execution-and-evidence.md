# Execution, trace, dialogue, and evidence

Compile the same explicit root successfully before prediction, execution, or existing-golden evaluation.

`predict` resolves and snapshots a request, then produces deterministic or heuristic run-shape evidence without proving a live Agent call. It writes request and trace state. Prediction may support an expectation about configuration or traversal; it does not prove Agent capability, output quality, artifact materialization, or execution success.

`run` provides execution evidence. Read the complete `RunResult`:

- `completed` is terminal runtime success; verify requested outputs and artifacts separately.
- `failed` is terminal failure with structured error evidence.
- `paused` is a non-Agent wait and is not completion.
- `agent_required` is a successful durable intermediate boundary; execute and submit the returned task through rule 05.

Both `predict` and `run` persist `<state_root>/runs/<run_id>/trace.jsonl`, and their `RunResult` returns `trace_path`. At each returned boundary, the current Agent may read the structured result and returned trace path, then narrate concise meaningful progress in dialogue: compile outcome, current phase or wait, native-child handoff, failure, produced outputs, and completion. The narration must remain tied to events and fields the Agent actually observed.

Current CLI and MCP calls are blocking between returned boundaries. Version 1 has no public live-event subscription and no `trace` CLI command. It therefore does not provide continuous token-by-token or event-by-event live streaming. Do not dump raw JSONL, expose secrets, flood the dialogue with internal events, or claim unseen progress. `agent_required` is a natural intermediate point at which an accurate progress update is available.

Preserve and relate explicit identities: run id binds the immutable request and result; opaque checkpoint reference identifies the durable wait; task id identifies Agent work; `trace_path` locates event evidence; artifact id identifies a declared output selected by the request. A trace event, checkpoint, or artifact file alone is not terminal success.

Golden evaluation measures only an existing baseline under the selected state root. It does not create, capture, promote, or update one. A valid summary has non-negative `total_cases`, `passed`, `failed`, and `stale`, with total equal to the other three counts. Evaluation passes only when `failed` and `stale` are both zero.

Report one evidence-based verdict:

- **Pass**: the requested observable outcome is present, identities align, no required evidence is missing, and any requested golden evaluation passed.
- **Rework**: current source, configuration, execution, output, or baseline evidence fails a criterion repairable within the authorized scope.
- **Blocked**: required authorization, host capability, dependency, or existing baseline is unavailable after safe in-scope checks; name the missing owner and evidence.

A command invocation, prediction, adapter presence, trace existence, or self-reported status does not by itself prove the requested outcome.
