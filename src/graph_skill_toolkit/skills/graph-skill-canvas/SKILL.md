---
name: graph-skill-canvas
description: Keep the current graph canvas open after portable Graph Skill work, using the shared canvas tool.
---

# Graph Skill canvas

After authoring, reading, compiling, predicting, running, inspecting, resuming, submitting an Agent result or evaluating a portable Graph Skill, display its current graph on the shared canvas. The canvas is the only view this presentation opens, selects and verifies. Reuse the existing canvas view, preserve other user pages, and leave the canvas active. Follow explicit user instructions that narrow or disable this behavior.

Use the host Agent's file or shell tools to resolve and verify the absolute business root containing `SKILL.md` and `graph.yaml`. Supply that root to the available `graph-skill-canvas` server's `show_graph` tool through the normal host tool interface; the host may namespace its name. A missing or unverifiable root requires a limitation report. Omit `skill_root` only for an explicitly requested labeled demonstration, which has no business root.

- **Codex:** Call `show_graph` once for the verified root as the final presentation. The MCP App view attached to that result is the canvas. Observe the final state before claiming the canvas is active, and report a hidden canvas, wrong active view or lost/duplicate view as a presentation failure.
- **Claude Code:** Call `show_graph`, then follow the project Mod's ordered preview guidance. The Mod supplies the live host operation sequence: record the existing tab inventory, attach the returned preview configuration by name, navigate only the returned HTTP tab to the canvas URL, select that tab, and verify the final state after selection completes. The host exposes no agent-callable way to reveal a hidden Browser pane; when the pane stays hidden, the canvas is ready but not visible, so ask the user to open it manually with the preview card's Open button or the Browser toggle, and open no file or other page to reveal it. Preserve observations and stop dependent steps if identity is ambiguous, an operation is refused or the required view remains hidden.

Treat a hook follow-up and this rule as one display request per operation and root. Preview, navigation and canvas-control calls are presentation steps and must not recursively trigger another display. Page loading itself must not change host focus. Verify the displayed root and graph before claiming the current graph is visible. Business files stay reachable through the canvas's host-interface controls and the host's ordinary file tools when the user asks for them.

`show_graph` presents the root graph. Use the installed runtime CLI, {{GSKILL_COMMAND}}, for compilation, execution and other runtime operations, following the `graph-skill` Skill and its CLI reference. Prefix that quoted command with `&` in Windows PowerShell; invoke it directly in a macOS or Linux POSIX shell. A shell invocation preserves the runtime's host-native executor default; direct vendor execution requires a separate explicit executor choice. Keep code changes and folder browsing with the host's native tools. The host owns panel visibility and focus; successful tool delivery alone does not establish either.
