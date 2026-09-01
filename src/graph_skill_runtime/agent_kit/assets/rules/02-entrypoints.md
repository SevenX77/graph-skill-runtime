# Runtime entrypoints

Python programs use the public `graph_skill_runtime` SDK. Coding Agents prefer the structured tools of the stdio MCP server named `gskill`. If MCP is absent, disconnected, or lacks an operation, the only CLI fallback is the installed interpreter running a module command whose syntax begins exactly `python -m graph_skill_runtime`.

Graph Skill Runtime is a dependency and SDK package. Install it into the owning Python environment through that environment's normal dependency workflow, such as `python -m pip install /path/to/WHEEL`, project `uv add /path/to/WHEEL`, or `uv pip install --python /path/to/python /path/to/WHEEL`. The package is not published, so do not invent a registry install command. `uv tool install` is not the installation form: uv tools are for packages that expose commands, while this distribution intentionally defines no `[project.scripts]` or `console_scripts` entry and installs no package-owned `gskill.exe` or `bin/gskill` launcher. On Windows the selected interpreter is normally `python.exe`; that executable belongs to Python, not to Graph Skill Runtime. Do not use a bare `gskill`, `uv run`, or a source checkout in current-use instructions.

## MCP runtime surface

The MCP server exposes exactly eight runtime tools:

| Tool | Purpose and routing |
| --- | --- |
| `compile` | Compile one explicit root and return the full current diagnostic set. Use before `predict`, `run`, or `evaluate_golden`. |
| `resolve_run` | Resolve an immutable request and field provenance without executing. |
| `predict` | Produce deterministic or heuristic run-shape evidence; it is not live execution proof. |
| `run` | Execute the compiled graph with the resolved executor. |
| `resume` | Observe or reopen a durable wait or terminal response. It does not submit an Agent result. |
| `submit_agent_result` | Submit the typed result for an `agent_required` wait and continue the same run. |
| `inspect` | Read compiled graph inventory and optional call edges. |
| `evaluate_golden` | Evaluate an existing baseline; it never creates, promotes, or updates one. |

Use these minimal MCP argument envelopes. The outer tool argument name—`request` or `invocation`—is part of the contract and must not be guessed or interchanged:

```text
compile: {"request":{"skill_root":"SKILL_ROOT","cache":false}}
resolve_run: {"invocation":{"skill_root":"SKILL_ROOT","inputs":{}}}
predict: {"request":{"invocation":{"skill_root":"SKILL_ROOT","inputs":{}},"strategy":"heuristic"}}
run: {"invocation":{"skill_root":"SKILL_ROOT","inputs":{}}}
resume: {"request":{"run_id":"RUN_ID","skill_root":"SKILL_ROOT","state_root":"STATE_ROOT","checkpoint_ref":"REF"}}
submit_agent_result: {"request":{"run_id":"RUN_ID","state_root":"STATE_ROOT","checkpoint_ref":"REF","result":{"task_id":"TASK_ID","status":"completed","output":{},"executor_id":"HOST_NATIVE","provenance":{}}}}
inspect: {"request":{"skill_root":"SKILL_ROOT","include_call_graph":true}}
evaluate_golden: {"request":{"skill_root":"SKILL_ROOT","state_root":"STATE_ROOT","baseline_id":"BASELINE_ID"}}
```

Defaults supply schema and kind discriminators, so the minimal envelopes omit them. In a real `submit_agent_result` call, replace every example token with the returned run, `AgentTask.task_id`, state-root, and `checkpoint_ref` values; never submit the literal placeholders. Optional invocation fields and configuration choices remain governed by [configuration and state](06-configuration-and-state.md) and the public tool schemas.

There are no MCP authoring, setup, guide, migration, or integration-install tools. Those operations belong only to the module CLI where listed below.

## Module CLI contract

All one-shot commands emit structured JSON. Consume status, diagnostics, error codes, identifiers, paths, and result fields rather than parsing message prose. The CLI exits `0` for success and durable waits such as `agent_required`; it exits `2` for a failed, conflicting, invalid, or `passed=false` result. Argument-parser usage errors are also nonzero. The `mcp` command is the long-running stdio server rather than a one-shot JSON action.

### Version

```text
python -m graph_skill_runtime --version
```

Prints exactly `python -m graph_skill_runtime gskill.graph.v1 (graph-skill-runtime 1.0.0a1)`.

### Compile

```text
python -m graph_skill_runtime compile SKILL_ROOT [--no-cache]
```

Use for the mandatory complete-bundle check and after every repair. `SKILL_ROOT` is the explicit marked root. `--no-cache` prevents use or update of the compile cache for that call. Preserve the complete diagnostic array; a `passed=false` result is not permission to continue to execution.

### Resolve configuration

```text
python -m graph_skill_runtime config resolve SKILL_ROOT [--run-id ID] [--preset ID] [--state-dir PATH] [--executor host-native|cli|embedded] [--vendor claude|codex|copilot|cursor|gemini|opencode] [--agent-profile ID] [--model ID] [--executable PATH_OR_NAME] [--timeout-seconds NUMBER] [--inputs-json JSON_OBJECT]
```

Use to inspect the immutable request and field-level provenance without execution. `--inputs-json` is a JSON object containing non-secret business input. Executor rules are defined under “Invocation options.”

### Predict

```text
python -m graph_skill_runtime predict SKILL_ROOT [--run-id ID] [--preset ID] [--state-dir PATH] [--executor host-native|cli|embedded] [--vendor claude|codex|copilot|cursor|gemini|opencode] [--agent-profile ID] [--model ID] [--executable PATH_OR_NAME] [--timeout-seconds NUMBER] [--inputs-json JSON_OBJECT]
```

Use after successful compilation when traversal or configuration shape evidence is useful. Prediction writes request and trace state, but it does not prove live Agent capability, output quality, or execution success.

### Run

```text
python -m graph_skill_runtime run SKILL_ROOT [--run-id ID] [--preset ID] [--state-dir PATH] [--executor host-native|cli|embedded] [--vendor claude|codex|copilot|cursor|gemini|opencode] [--agent-profile ID] [--model ID] [--executable PATH_OR_NAME] [--timeout-seconds NUMBER] [--inputs-json JSON_OBJECT]
```

Use after successful compilation for execution evidence. Handle `completed`, `failed`, `paused`, and `agent_required` from structured output. A `completed` status still requires output and artifact verification.

### Invocation options

`config resolve`, `predict`, and `run` share the options above. `--run-id` selects a stable request/run identity; `--preset` selects a named non-secret project or portable preset; `--state-dir` overrides the state root for this invocation; `--inputs-json` supplies a non-secret business JSON object.

The default executor is `host-native`. `--vendor` is required when `--executor cli` is selected. `--vendor`, `--agent-profile`, `--model`, `--executable`, and `--timeout-seconds` are valid only with `--executor cli`. `--agent-profile` is vendor-native only for Copilot, Gemini, and OpenCode. Treat `--executable` as an executable name or path, and require a positive valid `--timeout-seconds` value. Do not silently choose a configured fallback executor.

### Resume

```text
python -m graph_skill_runtime resume SKILL_ROOT RUN_ID --state-root STATE_ROOT [--checkpoint-ref REF] [--human-response-json JSON_OBJECT]
```

Use to observe or reopen an existing wait or terminal response. `SKILL_ROOT`, `RUN_ID`, and `STATE_ROOT` identify the original durable run. `--checkpoint-ref` selects an opaque wait reference. `--human-response-json` supplies a non-Agent human response for a supported human wait. Resume never accepts or substitutes for an `AgentResult`; use `submit` for `agent_required`.

### Submit an Agent result

```text
python -m graph_skill_runtime submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json AGENT_RESULT_JSON
```

Use only for output from the native child created for an `agent_required` boundary. `--result-json` must be the complete typed `AgentResult`, not only the business output. The runtime validates run/task identity and the completed output schema before continuing the same run. Never edit checkpoint or handoff storage directly.

### Inspect

```text
python -m graph_skill_runtime inspect SKILL_ROOT [--call-graph]
```

Use for a read-only topology and inventory view after compilation. `--call-graph` includes graph call edges. Inspection does not execute. Internal compilation needed for inspection remains runtime-owned state behavior; use a separate `compile --no-cache` when a no-cache compile result is required.

### Evaluate an existing golden baseline

```text
python -m graph_skill_runtime golden SKILL_ROOT BASELINE_ID --state-root STATE_ROOT
```

Use after successful compilation to evaluate `BASELINE_ID` already stored under `STATE_ROOT`. This command never creates, captures, promotes, or updates a baseline. A missing baseline is a blocked or failed evaluation, not a request to synthesize one.

### Migrate a legacy Studio skill

```text
python -m graph_skill_runtime migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]
```

Use only for an explicitly authorized one-shot legacy conversion. `SOURCE` remains unchanged, `DESTINATION` must be absent, `--runtime-config` identifies an optional legacy configuration input, and `--preset-id` names the migrated preset. When omitted, the default preset is migrated. Ordinary compile and run never sniff or accept the legacy format.

### Detect optional host integrations

```text
python -m graph_skill_runtime integrations detect
```

Returns read-only evidence about supported hosts visible to the current environment. Detection neither authorizes nor performs installation.

### Install or uninstall the optional MoirAI projection

```text
python -m graph_skill_runtime integrations install moirai --targets HOSTS_OR_detected --scope user|project [--project-root PATH] [--dry-run]
python -m graph_skill_runtime integrations uninstall moirai --targets HOSTS_OR_detected --scope user|project [--project-root PATH] [--dry-run]
```

Explicit supported host values are `claude`, `codex`, `copilot`, `cursor`, `gemini`, and `opencode`. `detected` cannot be mixed with explicit host names. Project scope defaults `--project-root` to the current directory; pass it explicitly when the intended project is elsewhere. `--dry-run` returns the exact plan without mutation. Apply mutates only after explicit authorization and preflight. Install and uninstall manage optional MoirAI host projections, not the unified Agent kit and not a user business gSkill.

### Start MCP stdio

```text
python -m graph_skill_runtime mcp
```

This long-running process is configured by a host as the `gskill` stdio MCP server. It is not an ordinary one-shot user action. Starting it does not edit host configuration or register business gSkills.

### Read the Agent configuration guide

```text
python -m graph_skill_runtime guide agent-configuration
```

Returns read-only JSON containing the canonical provider-neutral AGENTS section, the standalone `rules/<name>` assets, the exact two complete Skill/reference trees, and current documented placement choices. It performs zero writes. Use it to prepare an owner-approved plan that selects a rules-tree destination, copies the two Skill trees, and additively merges an instruction section pointing to the chosen rules index. It is guidance, never an installer, and it selects no destination.

### Create a scaffold

```text
python -m graph_skill_runtime create NAME --path EXISTING_PARENT --description TEXT
```

Creates only an absent `EXISTING_PARENT/NAME` scaffold. `NAME` is the new directory/name, `--path` must be an existing parent, and `--description` supplies discovery guidance. The scaffold is not a complete domain design: refine typed inputs, outputs, phases, permissions, side effects, and evidence, then compile it. There is no force, overwrite, or adopt behavior.

## Operation ordering

Compile before `predict`, `run`, or `golden`. Use `config resolve` to explain configuration without execution; use `predict` for shape evidence; use `run` for execution. Use `submit` only for `agent_required`; use `resume` to observe/reopen or for a supported non-Agent human response. Use `inspect` for topology. Keep integration projection, authoring, migration, configuration guidance, and business execution as distinct operations.
