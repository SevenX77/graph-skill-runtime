---
name: hello-world
description: Use this graph skill when you need a minimal deterministic greeting or want to verify a Graph Skill Runtime installation.
---

# Hello World

Treat this directory as the explicit skill root.

1. Prefer the `gskill` MCP server's `compile` or `run` tool.
2. If MCP is unavailable, call the installed `gskill` console command with this
   directory path.
3. Pass an optional string input named `name` and consume the structured result.

Do not invoke the runtime through `python -m`; the installed `gskill` command is
the stable process fallback.
