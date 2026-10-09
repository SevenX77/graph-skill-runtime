---
name: graph-skill-canvas
description: Display the current graph after work on a portable Graph Skill, using the shared canvas tool after source operations or installed runtime CLI calls.
---

# Graph Skill canvas

After authoring, reading, compiling, predicting, running, inspecting, resuming, submitting an Agent result or evaluating a portable Graph Skill, call the available `graph-skill-canvas` server's `show_graph` tool through the host's normal tool interface. The host may namespace the tool name. Supply `skill_root` as the verified absolute business skill root containing both `SKILL.md` and `graph.yaml`.

Use the host Agent's file or shell tools to resolve relative, shell, or indirect paths and verify the root. Use file evidence for the selection; never invent a root or graph data. Omit `skill_root` only when the user wants the labeled demonstration. If the selected root cannot be verified or the tool is unavailable, state that limitation instead of substituting the demonstration.

Treat a hook follow-up and this rule as one display request for the same operation and root. Avoid duplicate calls. Canvas display and folder-opening operations must not recursively trigger another display. Follow explicit user instructions that narrow or disable this behavior.

`show_graph` presents the root graph. Use the installed runtime CLI, {{GSKILL_COMMAND}}, for compilation, execution and other runtime operations, following the `graph-skill` Skill and its CLI reference. Prefix that quoted command with `&` in Windows PowerShell; invoke it directly in a macOS or Linux POSIX shell. A shell invocation preserves the runtime's host-native executor default; direct vendor execution requires a separate explicit executor choice. Keep code changes and folder browsing with the host's native tools. The host controls whether its app panel opens or receives focus.
