# Run, trace, and checkpoint evidence

`run` resolves configuration, writes an immutable request snapshot, compiles the explicit business gSkill, and executes with the selected executor. The default state root is `<skill_root>/.gskill` unless configuration resolves another absolute path.

Use the `run` tool belonging to the `gskill` MCP server, or:

```text
gskill run SKILL_ROOT
gskill run SKILL_ROOT --inputs-json JSON
```

A `RunResult` can be `completed`, `failed`, `paused`, or `agent_required`. Inspect the full result: run id, mode, request, outputs, diagnostics, error, Agent task, and trace reference when present. A command being issued does not establish completion.

For host-native Agent work, `agent_required` is a successful durable wait. Graph checkpoint state and the separate Agent handoff record already exist. The current host executes the task and submits an `AgentResult`; it must not edit private SQLite state.

`resume` is an observation/reopen operation for the durable wait or terminal response:

```text
gskill resume SKILL_ROOT RUN_ID --state-root STATE_ROOT --checkpoint-ref REF
```

It does not submit Agent output. Submission uses:

```text
gskill submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json JSON
```

Checkpoint state is segmented by namespace so concurrent scopes cannot collide. Two segments compose, in this order: an active iteration contributes `iter<index>`, and an Agent phase's inner loop contributes `agent:<phase_id>`. So the values you can actually observe are the empty namespace (the graph's own execution scope), `iter<index>` (one iteration item), `agent:<phase_id>` (an Agent phase with no iteration active), and `iter<index>.agent:<phase_id>` (an Agent phase inside an iteration item). A wait or a resumed state always belongs to exactly one namespace; read the whole value, not its prefix, before concluding which unit paused — `agent:draft` and `iter2.agent:draft` are different lanes of the same phase.

There is no public `trace` CLI command. Use the returned trace reference and public runtime events as evidence. Relate trace, request snapshot, checkpoint, handoff, and artifact observations by the same run identity; none of those stores substitutes for another.
