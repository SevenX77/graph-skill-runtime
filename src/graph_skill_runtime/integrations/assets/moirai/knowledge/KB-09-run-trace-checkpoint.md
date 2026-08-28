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

There is no public `trace` CLI command. Use the returned trace reference and public runtime events as evidence. Relate trace, request snapshot, checkpoint, handoff, and artifact observations by the same run identity; none of those stores substitutes for another.
