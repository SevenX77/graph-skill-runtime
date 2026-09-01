# Public runtime tools

Prefer the structured tools belonging to the MCP server named `gskill`. A host may display a prefix, so select the tool by server ownership and final tool name rather than assuming an unprefixed label.

The server exposes exactly eight tools:

| Tool | Purpose |
| --- | --- |
| `compile` | Compile one explicit business gSkill and return all diagnostics from one pass. |
| `resolve_run` | Resolve configuration into the immutable runtime profile and run request. |
| `predict` | Produce a deterministic or heuristic prediction without a real model call. |
| `run` | Execute with the explicitly resolved executor. |
| `resume` | Observe a durable host-native wait or terminal response. |
| `submit_agent_result` | Submit one typed host-native `AgentResult` and continue the same run. |
| `inspect` | Inspect compiled graph inventory and optional call edges. |
| `evaluate_golden` | Evaluate an existing golden baseline. |

When MCP is unavailable, use the installed interpreter's public module CLI, never a bare launcher, `uv run`, or a source checkout:

```text
python -m graph_skill_runtime compile SKILL_ROOT
python -m graph_skill_runtime predict SKILL_ROOT
python -m graph_skill_runtime predict SKILL_ROOT --inputs-json JSON
python -m graph_skill_runtime run SKILL_ROOT
python -m graph_skill_runtime run SKILL_ROOT --inputs-json JSON
python -m graph_skill_runtime inspect SKILL_ROOT --call-graph
python -m graph_skill_runtime golden SKILL_ROOT BASELINE_ID --state-root STATE_ROOT
python -m graph_skill_runtime resume SKILL_ROOT RUN_ID --state-root STATE_ROOT --checkpoint-ref REF
python -m graph_skill_runtime submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json JSON
```

Compile before execution. Preserve structured results and error codes instead of parsing human wording. `resume` does not submit Agent output; `submit` does. There are no public MCP tools named `trace`, `artifacts`, `create_golden`, or `promote_golden`. Integration installation is an explicit CLI/SDK operation, not an MCP runtime tool.
