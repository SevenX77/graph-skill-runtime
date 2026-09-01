# Agent execution and submission

The default executor is `host-native`. For a supported Agent phase in the root DAG, `run` can return `RunResult(status="agent_required")` with a complete `AgentTask` and opaque `checkpoint_ref`.

The current host must then:

1. confirm it can enforce the task's required capabilities and policy;
2. create a fresh native clean-context subagent;
3. give that subagent the complete `AgentTask` without relying on conversation history;
4. receive exactly one JSON value satisfying `task.output_schema`;
5. wrap it as `AgentResult` with the same `task_id`, terminal status, executor identity, and non-secret provenance;
6. call the `submit_agent_result` tool belonging to the `gskill` MCP server, or use `python -m graph_skill_runtime submit`.

`resume` only observes the current durable wait or terminal response. It does not accept or apply Agent output.

If the current host cannot create a clean native child or enforce required capabilities, stop and report the gap. Do not fabricate output and do not shell out to a vendor CLI merely to pretend that process is the current host's native subagent.

An explicitly resolved `executor=cli` is a separate alternative. It launches one fresh vendor-native top-level process per task; that process is not a child of the current host conversation. Direct adapters exist for Claude, Codex, GitHub Copilot, Cursor, Gemini, and OpenCode. Current real operational evidence supports only Codex CLI `0.144.1` on Windows `10.0.26200` x64 with Python `3.11.15`; adapter code and fake tests do not expand that support claim.

Both host-native and CLI currently reject registry-subgraph Agent phases, graph iteration containing Agent, Agent phase iteration, and Agent phases on incomparable parallel branches. These are Phase 3b limitations and fail fast without implicit fallback.
