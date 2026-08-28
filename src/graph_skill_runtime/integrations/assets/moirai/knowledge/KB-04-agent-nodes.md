# Runtime Agent nodes

Use `AGENT.md` for a phase whose output requires bounded judgment. It is an internal runtime node, not a host Agent Skill and not a replacement for the root `SKILL.md`.

The phase declares object-shaped input/output schemas plus optional role, tools, context access, subagent, subgraph, reference, example, validator, iteration, and overwrite settings. Its Markdown body has exactly one `<role>` and one `<goal>`, followed by zero or more structured `<step>`, `<protocol>`, and `<example>` elements.

Design checklist:

- Give the phase one decision responsibility and only the inputs it needs.
- Make the output schema precise enough for downstream phases to consume without interpreting prose.
- Declare every reference and example with a stable id, skill-relative path, and summary.
- Declare only required tools and capabilities. A file existing under `tools/` does not mount it automatically.
- Use `context_access` only for the explicit `working_memory` or `artifact` capabilities.
- Define what to do when evidence is insufficient; never instruct the executor to invent a value.

Role selection is explicit. With `use_graph_llm_role: false`, the phase role precedes graph role and host fallback. With `true`, graph role precedes host fallback and the phase role is not selected for that run.

The default host-native executor currently supports serially addressable Agent waits in the root DAG. Agent phases in registry subgraphs, graph-level iteration, Agent phase iteration, and incomparable parallel branches fail fast. Design around this current boundary or report that Phase 3b support is required; do not rely on silent fallback.
