---
name: graph-skill
description: Author, read, validate, execute, and inspect portable Graph Skills that contain SKILL.md and graph.yaml, using the installed runtime and shared graph canvas.
---

# Graph Skill

Use this Skill for work on a portable Graph Skill: a user-owned directory whose root `SKILL.md` describes its use and whose `graph.yaml` declares its executable graph. The installed runtime command is {{GSKILL_COMMAND}}. On Windows, invoke this quoted command from PowerShell with `&` before it; on macOS or Linux, invoke it directly from a POSIX shell. Use the host's file and shell tools for source work and runtime calls. The installed toolkit command, {{TOOLKIT_COMMAND}}, follows the same shell convention and owns installation status and lifecycle.

These rendered commands select the toolkit's private runtimes by absolute path. Preserve the Python command's `-I -B -X utf8` options for isolated module search, suppressed bytecode writes and UTF-8 mode. A missing or broken installed command calls for reporting the installation failure through its lifecycle owner; use the packaged interpreter binding when running this toolkit.

Read [the CLI reference](references/cli.md) before a runtime call. Read the installed [portable specification](<{{PORTABLE_SPEC}}>) before authoring or changing graph declarations. These instructions operate on an explicit business skill root; they create no discovery registry for business skills.

## Select and edit the source

Resolve the user's selected directory to an absolute path with host file tools. Verify its root `SKILL.md` and `graph.yaml`. For a new skill, use the requested destination and author those files there. Read the current files and applicable project instructions before changing them.

Keep graph identity, dependencies, input/output schemas and root artifact declarations in `graph.yaml`. Each `phases/<phase_id>/` directory contains exactly one type file: `LOGIC.md`, `AGENT.md` or `SUBGRAPH.md`. Reusable graphs live in the one flat `subgraphs/<graph_id>/graph.yaml` registry within that business skill. Only the business root has the discoverable `SKILL.md`. Follow the portable specification for the complete grammar and phase resources.

Make source edits through the host's normal file tools. Use native file and diff views to explain or review changes. When the user requests reading or explanation, inspect source directly; compilation and inspection can load declared Python code and require a trusted selected skill.

## Choose the runtime operation

Use the installed CLI and consume its structured JSON result. Select `compile` for complete diagnostics, `config resolve` for the effective request and configuration origins, `predict` for a deterministic stub prediction, `run` for authorized execution, `inspect --call-graph` for graph identities and calls, and `golden` for an existing named baseline. Use `resume` and `submit` for an existing durable run as described below. Preserve the run ID, resolved state root, checkpoint reference and trace location from actual results.

Calling the runtime from a shell uses its normal application boundary. The default executor remains `host-native`, which delegates Agent phases to the current host. `--executor cli` is a separate explicit choice that runs vendor CLI processes; use it only when the task calls for that execution mode. Configuration may override defaults, so inspect the resolved request when execution settings matter.

Read all returned diagnostics and the semantic status. An exit code of zero can accompany an `agent_required` or `paused` run. Prediction uses stubs and establishes only its reported scope. A compiler success, a displayed graph and a completed business run each establish different results.

## Complete a host-native Agent phase

For `status: agent_required`, read `agent_required.task` and preserve its `checkpoint_ref`. The task contains the phase instructions, input, output schema, resource handles and paths, allowed tools and paths, network policy, deadline and required capabilities. Check that the host can honor those boundaries before launching the work.

Create a fresh native subagent with no inherited conversation history. Give it the complete task and only the permitted resources and instructions it needs. The subagent performs the delegated phase and returns an `AgentResult` matching the task identity and output schema. The host owns this subagent's lifecycle and cancellation. If the host cannot create the required clean-context worker or enforce a required capability boundary, preserve the durable wait and report the missing capability.

Submit the actual result with the CLI `submit` command. Consume the returned run result and repeat only if it requests another Agent phase. `resume` reads the current wait or terminal result; it supplies no Agent output. Keep failed, cancelled and completed phase results distinct, and report a business run as complete only when its final result and required artifacts support that conclusion.

## Show the current graph

After authoring, reading, compiling, predicting, running, inspecting, resuming, submitting or evaluating the selected skill, call the available `graph-skill-canvas` server's `show_graph` through the host's normal tool interface. Pass the verified absolute business root as `skill_root`. The host may namespace the tool name.

Treat this instruction, the canvas Skill and a hook reminder as one display request for the same operation and root. Display and folder-opening actions do not trigger another display. Respect the user's explicit choice to narrow or disable follow-up. If the root is unverifiable or the tool is unavailable, state that limitation. Use the demonstration only when the user requests it.

The canvas presents the root graph; the runtime owns semantic validation and execution. Folder opening and source editing remain host operations. A successful `show_graph` response establishes a tool result; the host determines panel placement and focus.
