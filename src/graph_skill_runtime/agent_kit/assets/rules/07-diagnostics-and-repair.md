# Diagnostics and repair

Compilation is the single aggregated diagnostic exit for a business gSkill. Run MCP `compile` or `python -m graph_skill_runtime compile SKILL_ROOT` before prediction, execution, or golden evaluation.

One pass inventories and parses the complete bundle, validates closed schemas, checks graph and call topology, traces typed dataflow, resolves resources and implementations, and validates artifact declarations. It reports every independently knowable defect from that pass rather than stopping at the first error.

For each diagnostic, preserve its code, severity, message, source path, field or line when available, and graph/phase identity. Repair by invariant:

1. Group related symptoms without discarding independent diagnostics.
2. Identify the earliest authoritative owner: root marker, file inventory, `graph.yaml`, phase document, resource declaration, implementation, runtime configuration, or request.
3. Correct that owner and every independent defect exposed at the same stage.
4. Compile the complete explicit root again and compare the full diagnostic set.
5. Continue until no fatal diagnostic remains; review warnings and informational evidence rather than hiding them.

Do not create a host-only validator, duplicate topology, compatibility shim, format-sniffing branch, silent fallback, or message-text parser to bypass the compiler. If the authoritative runtime contract is wrong, change that contract and its evidence; if the business source is wrong, repair the owning source.
