# Installed Graph Skill CLI

The installed command is {{GSKILL_COMMAND}}. It explicitly selects the toolkit's private Python interpreter and runs its installed `graph_skill_runtime` module with `-I -B -X utf8`. Those options isolate module search from ambient Python settings, suppress bytecode writes and select UTF-8 mode. This exact interpreter binding keeps host calls independent of PATH and of the host's current Python environment. Preserve the rendered command's quoting and options, then add runtime arguments after it. Replace uppercase argument placeholders with verified values.

On Windows, use PowerShell and prefix every quoted command below with its call operator, `&`. For example, `& {{GSKILL_COMMAND}} --version`. On macOS and Linux, invoke the rendered command directly from a POSIX shell: `{{GSKILL_COMMAND}} --version`. The command already quotes its components; it needs no additional outer quotes. The JSON argument examples use literal single quoting supported by these shells. Other shell interfaces require their own argument encoding.

Runtime operations emit UTF-8 JSON on standard output by default. Help, version output and argument-parser errors have their usual command-line forms. Preserve standard error and the process exit code when reporting a failure. JSON argument options accept a JSON value as one argument, rather than a file path. Use a proper argument array where the host provides one; otherwise use the active shell's literal quoting rules. Keep business inputs free of literal secrets.

## Commands and effects

| Purpose | Command | Result and state effect |
| --- | --- | --- |
| Compile a trusted skill | `{{GSKILL_COMMAND}} compile "SKILL_ROOT"` | `CompileResult`, including complete diagnostics; compilation may load business Python and write its cache. Add `--no-cache` to disable cache use. |
| Resolve invocation | `{{GSKILL_COMMAND}} config resolve "SKILL_ROOT"` | Effective immutable request, absolute roots and configuration origins. |
| Predict | `{{GSKILL_COMMAND}} predict "SKILL_ROOT"` | Deterministic stub prediction; writes local run state. |
| Run | `{{GSKILL_COMMAND}} run "SKILL_ROOT"` | Executes the selected skill, persists a request and returns its current status. |
| Inspect graph calls | `{{GSKILL_COMMAND}} inspect "SKILL_ROOT" --call-graph` | Graph identities, call edges and diagnostics; inspection compiles without the global compile cache. |
| Reopen a durable run | `{{GSKILL_COMMAND}} resume "SKILL_ROOT" "RUN_ID" --state-root "STATE_ROOT" --checkpoint-ref "CHECKPOINT_REF"` | Reads the current durable Agent wait or terminal result. The checkpoint option can be omitted when the runtime can resolve the current wait. |
| Submit Agent output | `{{GSKILL_COMMAND}} submit "RUN_ID" --state-root "STATE_ROOT" --checkpoint-ref "CHECKPOINT_REF" --result-json 'AGENT_RESULT_JSON'` | Validates task identity and output, then continues the same run. |
| Evaluate a baseline | `{{GSKILL_COMMAND}} golden "SKILL_ROOT" "BASELINE_ID" --state-root "STATE_ROOT"` | Evaluates an existing golden baseline and returns `passed` or `failed` with details. Use the actual baseline and authorized evaluation scope. |

The portable specification at [the installed reference](<{{PORTABLE_SPEC}}>) owns file grammar. The runtime owns each result's schema and diagnostics. For command options available in this installed version, use `{{GSKILL_COMMAND}} COMMAND --help`, with the PowerShell prefix above when applicable.

## Invocation and state

`config resolve`, `predict` and `run` share these options:

| Option | Meaning |
| --- | --- |
| `--run-id ID` | Explicit run identity. Use a new identity for a new request; an existing snapshot cannot be overwritten with different content. |
| `--preset ID` | Named business preset from project or explicitly supplied portable configuration. |
| `--state-dir PATH` | Invocation-level state-directory choice. Read the resolved absolute `state_root` from the result. |
| `--inputs-json JSON_OBJECT` | Non-secret business input object passed as one argument. |
| `--executor host-native` | Select host-native Agent handoff explicitly. |
| `--executor cli --vendor VENDOR` | Select direct vendor-process execution explicitly. |
| `--executor embedded` | Select the embedded executor, subject to its installed optional dependencies and verified capabilities. |

Direct vendor-process execution additionally accepts `--agent-profile`, `--model`, `--executable` and `--timeout-seconds`; each requires `--executor cli`. Vendors are `claude`, `codex`, `copilot`, `cursor`, `gemini` and `opencode`. Agent profiles apply only to Copilot, Gemini and OpenCode. Adapter availability and actual vendor operation are separate evidence. An executable is a PATH basename or an absolute path. The default per-Agent timeout is 600 seconds, with accepted values greater than zero and at most 86,400 seconds.

Configuration precedence is invocation, project `gskill.toml`, operating-system user configuration, portable defaults, then built-in defaults. Built-in execution uses `host-native` with SQLite checkpoints. For an existing run, reuse `request.profile.skill_root`, `request.profile.state_root`, `run_id` and the returned checkpoint reference. Resume and submit use `--state-root`; new invocation resolution uses `--state-dir`.

## Result interpretation

Compilation returns `status: passed` or `status: failed`, with `diagnostics`. Read every diagnostic's code, severity, source path and available location before deciding what to repair. Inspection can return diagnostics alongside its topology, so its exit status alone establishes no complete semantic validity.

Run results use `completed`, `failed`, `paused` or `agent_required`. Exit code zero includes waiting states. Exit code two indicates a returned failure/conflict or a false `passed` result; command parsing can also fail before a runtime result exists. Structured errors use `kind: runtime_error`, with a stable `code`, `message` and available details. Keep parser errors, runtime errors, business failures and unavailable host capabilities distinct.

For `agent_required`, use `agent_required.task` as the exact work contract and `agent_required.checkpoint_ref` as the submission reference. The public reference has the form `gskill-handoff-v1:<task-id>`. Host-native Agent handoff currently supports serial Agent waits in a root directed acyclic graph, a graph whose dependency edges contain no cycles. Agent phases in registry subgraphs, graph iteration containing Agent work, Agent phase iteration and incomparable parallel Agent branches are rejected before execution. Standalone human/breakpoint continuation remains outside the completed handoff scope, even though the parser exposes `--human-response-json` on `resume`.

## Agent result submission

Read the phase output schema before preparing the result. A completed result has this shape; replace the identity and output with the actual returned work:

```json
{
  "schema_version": "gskill.agent-result.v1",
  "kind": "agent_result",
  "task_id": "ACTUAL_TASK_ID",
  "status": "completed",
  "output": {},
  "executor_id": "ACTUAL_HOST_WORKER_ID",
  "provenance": {}
}
```

An empty output object is valid only when the task schema permits it. The `executor_id` identifies the actual worker. Use a JSON serializer to form the single `--result-json` argument. A failed or cancelled result has that corresponding status and a structured `error` with a valid runtime error code and message. Preserve genuine worker evidence in non-secret provenance.

The runtime validates the task identity and output schema. An invalid schema leaves the task available for a valid replacement result. An exact duplicate submission returns its cached causal result; a different result for a consumed task conflicts. The next returned result, including any further Agent task, determines the next action.

## Installation and display

The toolkit lifecycle command is {{TOOLKIT_COMMAND}}. It selects the private Node.js runtime, which executes the toolkit entry point. Its `status` operation reports owned installation state. Apply the same PowerShell call operator or direct POSIX invocation described above. The global `graph-skill` command also exposes install, update, status and uninstall; global `gskill` and `graph-skill <runtime-command> [arguments]` forward runtime arguments into the installed environment. For example, `graph-skill inspect "SKILL_ROOT" --call-graph` forwards the inspection command. Installation changes require the user's selected lifecycle action. First installation and upgrade from `0.1.0` use the matching new archive's extracted installer. Host configuration changes remain the lifecycle owner's responsibility.

Runtime calls use the installed CLI. After the related operation, use the available canvas `show_graph` tool normally with the same verified absolute business root. This preserves the host's app presentation path. The canvas result provides presentation evidence; compilation, execution and native panel behavior retain their own acceptance conditions.
