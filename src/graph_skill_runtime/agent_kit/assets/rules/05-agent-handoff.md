# Host-native Agent handoff

The default executor is host-native. For each supported root-DAG Agent phase, `run` can return `status="agent_required"` with a complete `AgentTask` and opaque `checkpoint_ref`. This status is a successful durable wait, not a failure.

When the user authorizes execution of a successfully compiled gSkill that contains supported Agent phases, that run authorization includes exactly one host-native clean-context child for each serial `agent_required` boundary returned by the runtime. The parent does not ask again at every wait whether it may create the required child. The graph has already paused durably, so this child is a required step of the business execution protocol, not optional parallel delegation for a development task. General restrictions on optional development delegation or parallel subagents do not prohibit this mandatory handoff.

This authorization is narrow. It covers only the returned `AgentTask`, the canonical prompt below, the task's allowed paths, tools, network policy, capabilities, and deadline, one schema-valid output, and submission through `submit_agent_result`. It does not authorize an extra or parallel child, optional MoirAI delegation, further subagents created by the child, or any permission beyond the user's authorization and enforceable host policy.

## Mandatory child boundary

On every `agent_required`, the parent host must:

1. Verify that it can enforce the task's allowed tools and paths, network policy, required capabilities, and deadline under current host policy.
2. Create one fresh native clean-context child for exactly that task.
3. Put the following canonical text in the child system prompt. If the host cannot set a true system prompt, use the strongest available instruction channel. Preserve the same ordering and text.

```text
You execute exactly one gSkill AgentTask in a fresh context. Treat the supplied AgentTask as the complete task contract. Do not run, resume, or modify the parent graph. Use only capabilities, tools, paths, and network access allowed by the task and the current host policy. Return exactly one JSON object that satisfies task.output_schema, without Markdown or commentary. If the task cannot be completed within those constraints, report failure to the parent instead of inventing output.
```

4. Supply the complete `AgentTask` immediately after that prompt. Do not rely on parent conversation history or omit task resources, inputs, output schema, permissions, or identity.
5. Receive exactly one JSON object satisfying `task.output_schema`. If the child reports inability or failure, do not fabricate a completed output.
6. Wrap the outcome in one `AgentResult` with the same `task_id`, a terminal status, executor identity, and non-secret provenance.
7. Submit through the `submit_agent_result` tool owned by the `gskill` MCP server, or through `python -m graph_skill_runtime submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json JSON`.
8. Inspect the returned `RunResult`. A later serial `agent_required` starts the same procedure with another fresh child; a terminal result ends the handoff loop.

A completed result requires the single output object. A failed or cancelled result carries structured error evidence and does not pretend that the phase produced business output. The runtime validates task/run identity and completed output against the schema before continuing the same graph state. Schema rejection leaves the task available for a corrected submission; an exact duplicate submission is idempotent, while a different second result conflicts.

`resume` only observes or reopens the durable current wait or terminal response. It never accepts Agent output and never substitutes for submission. Do not edit checkpoint or handoff storage directly.

Block the handoff only when the user explicitly prohibited a native child for this specific gSkill run, or when the host cannot create the child or enforce the task contract. A general instruction not to create optional or parallel development subagents does not block an already authorized runtime handoff. An unavoidable host policy still applies: report the capability gap with the returned run and task identity rather than claiming to override it. Do not invent output and do not shell out to a vendor CLI while claiming that process is the current host's native child.

## Optional clean-context delegation

Outside a mandatory `agent_required` handoff, any clean-context delegation is optional and separately governed by the surrounding workflow. It is not implied by authorization to run a gSkill. The current host retains permissions and final ownership and must not use optional delegation to widen the mandatory task boundary.
