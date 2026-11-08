---
name: plugin-interface-lab
description: Open the Plugin Interface Lab, the developer page that exercises every Plugin Base host interface and local capability on the current host and shows their evidence. Use when the user asks to test, check or compare plugin interfaces.
---

# Plugin Interface Lab

The Plugin Interface Lab is a developer page. It lists the 17 Plugin Base host interfaces and the 5 local capabilities, tells the developer what each one should do on Claude Code and on Codex, runs the one the developer chooses, and shows four parts of evidence for every call: what was sent, what the host returned, what was observed and which host limits applied. The developer records whether the observed effect matches the expectation; the page writes those records to its own state directory. Its 触发 (Triggers) mode explains and tests page triggers, the plugin hook that asks you to open a page after a tool call changed or used the files that page presents.

Open the lab with the `open_interface_lab` tool of the `graph-skill-canvas` server through the normal host tool interface; the host may namespace its name. The tool only opens the page. Every interface call is started by the developer on the page, never by this Skill.

- **Codex:** Call `open_interface_lab` once. The MCP App view attached to that result is the lab. Observe the final state before claiming the lab is visible.
- **Claude Code:** Call `open_interface_lab`, then follow the project Mod's ordered preview guidance: record the existing tab inventory, attach the returned preview configuration by name, navigate only the returned HTTP tab to the lab URL, select that tab, and verify the final state after selection completes. When the Browser pane is hidden, show it once with the host's pane tool and read the tab inventory again. When the pane still stays hidden, the lab is ready but not visible: ask the user to open it with the preview card's Open button or the Browser toggle, and open no file or other page to reveal it.

When the lab sends a message that asks the model to repeat its page context, answer with the exact text of the context block that starts with "Plugin page context", or with the stated "not received" sentence when no such block is present. Call no tool for that answer.

When the lab's page-trigger test asks you to edit its probe file `probe.txt`, make exactly that edit with the host's file-writing tool (Edit in Claude Code, apply_patch in Codex) and change nothing else. The plugin's hook then returns page-trigger guidance; follow it once by calling `open_interface_lab` with exactly the `route` and `trigger_firing` it names, and present the lab as above.

When this Skill is invoked with an input that starts with `echo`, the invocation is the lab's `skills.invoke` test: reply with one sentence, `Interface Lab skill invoked: ` followed by the input, and do nothing else.
