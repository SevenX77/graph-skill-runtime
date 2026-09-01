---
name: hello-world
description: Use this graph skill when you need a minimal deterministic greeting or want to verify a Graph Skill Runtime installation.
metadata:
  gskill: gskill.graph.v1
---

# Hello World

Treat this directory as the explicit skill root.

1. Prefer the `gskill` MCP server's `compile` or `run` tool.
2. If MCP is unavailable or lacks the required operation, use the installed
   interpreter with `python -m graph_skill_runtime` and this directory path.
3. Pass an optional string input named `name` and consume the structured result.
