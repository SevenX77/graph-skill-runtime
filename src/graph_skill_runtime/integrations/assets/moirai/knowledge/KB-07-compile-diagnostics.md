# Compile diagnostics and repair

Compilation is the single aggregated diagnostic exit for a business gSkill. Run it before prediction, execution, or evaluation.

Use the `compile` tool belonging to the `gskill` MCP server, or the installed CLI fallback:

```text
python -m graph_skill_runtime compile SKILL_ROOT
```

One pass inventories and parses the bundle, validates graph and phase schemas, checks DAG and call-graph structure, traces I/O, resolves resources and actions/tools, and validates artifact declarations. The result contains the complete set of independently knowable diagnostics, not only the first error.

Repair loop:

1. Preserve every diagnostic field: code, severity, message, source path, line or field when available, and graph/phase identity.
2. Group symptoms by violated invariant.
3. Fix the earliest authoritative owner: inventory, `graph.yaml`, phase document, resource declaration, implementation, or request.
4. Address every independent defect from the same stage.
5. Compile again and compare the full set.

Fatal diagnostics mean the bundle is not executable. Warnings and information remain evidence and should be reviewed, not discarded. Never create a second validation rule in a host prompt or UI to work around the compiler; repair or extend the owning runtime contract.
