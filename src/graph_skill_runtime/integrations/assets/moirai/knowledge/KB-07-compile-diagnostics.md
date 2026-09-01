# Compile diagnostics and repair

Compilation is the single aggregated diagnostic exit for a business gSkill. Run it before prediction, execution, or evaluation.

Use the `compile` tool belonging to the `gskill` MCP server, or the installed CLI fallback:

```text
gskill compile SKILL_ROOT
```

One pass inventories and parses the bundle, validates graph and phase schemas, checks DAG and call-graph structure, traces I/O, resolves resources and actions/tools, and validates artifact declarations. The result contains the complete set of independently knowable diagnostics, not only the first error.

## What compilation can and cannot establish

It can establish: root inventory presence, Agent Skills metadata and its name/directory agreement, graph and phase inventory identity, closed-schema validity of every `graph.yaml` and phase document, phase DAG shape including unknown or duplicate dependencies, unreachable phases, missing or non-terminal outputs and cycles, graph call resolution and call cycles, field-level I/O reachability and sequential-overwrite authorization, resource paths, action and tool resolution and scope, validator presence, body mention reachability, and artifact declarations and requests.

It cannot establish: whether a resolved LLM role is actually reachable at a provider, whether a host can supply a required capability, what a real model will return, whether business logic inside an action is semantically correct, or what values a run will encounter. A clean compile is a structural result, not a quality result.

## Reading a diagnostic

Every diagnostic carries a stable code, a severity, a source path relative to the skill root, a field or line location when one can be determined, the graph and phase identity, and a complete message. The **code** is the stable identity: match on it, and never re-derive meaning from the human wording, which may be reworded. If a document cannot be parsed at all, the compiler keeps checking the other independent files and does not fabricate the secondary conclusions that would have depended on that document — so a parse failure explains missing later diagnostics rather than proving their absence.

Triage a set by category before editing anything:

- **identity mismatch** — a phase or graph id disagreeing with its directory, or a registered phase with no directory (and the reverse);
- **DAG shape** — a cycle, an unreachable phase, a missing terminal output, an unknown or duplicated dependency;
- **schema incompatibility** — a declared downstream input with no guaranteed upstream source, or an unauthorized ancestor overwrite;
- **implementation contract** — an action or tool that does not resolve, a signature that does not match its declaration, a validator that is declared but absent;
- **resource and mention** — a reference, example, tool, subagent, subgraph, or protocol mention with no matching declaration.

Repair loop:

1. Preserve every diagnostic field: code, severity, message, source path, line or field when available, and graph/phase identity.
2. Group symptoms by violated invariant.
3. Fix the earliest authoritative owner: inventory, `graph.yaml`, phase document, resource declaration, implementation, or request.
4. Address every independent defect from the same stage.
5. Compile again and compare the full set.

Fatal diagnostics mean the bundle is not executable. Warnings and information remain evidence and should be reviewed, not discarded. Never create a second validation rule in a host prompt or UI to work around the compiler; repair or extend the owning runtime contract.
