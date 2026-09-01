# Runtime Agent nodes

Use `AGENT.md` for a phase whose output requires bounded judgment. It is an internal runtime node, not a host Agent Skill and not a replacement for the root `SKILL.md`.

The phase declares object-shaped input/output schemas plus optional role, tools, context access, subagent, subgraph, reference, example, validator, iteration, and overwrite settings. Its Markdown body has exactly one `<role>` and one `<goal>`, followed by zero or more structured `<step>`, `<protocol>`, and `<example>` elements.

## Where an authored body actually lands

`system_prompt` is a compiled value, never an authoring field. The compiler composes the final prompt from a fixed cognitive template, the resource registry, and the phase I/O schema; the authored body fills only the business slots.

| Authored in `AGENT.md` | Slot in the compiled prompt | What the author owns there |
| --- | --- | --- |
| body `<role>` | `<role>` | the business persona, one sentence |
| body `<goal>` | `<goal>` | what counts as done, plus one line per input explaining what it is for |
| body `<step id name>` | the suggested-step list inside `<thinking_style>` | ordered procedure; advisory, not binding |
| body `<protocol id>` | the rule list inside `<protocol_citation>` | binding rules the model must cite, for example `[protocol:P1]` |
| body `<example id>` | the inline part of `<examples>` | business-comprehension aids |
| frontmatter `references` | `<knowledge_base>` and the `read_reference` registry | pre-read material and the readable registry |
| frontmatter `examples` | the extended part of `<examples>` and the `read_example` registry | boundary cases fetched on demand |
| frontmatter `io.outputs` | `<exit_contract>` and its `<output_schema>` | the single output-format authority |

The template also injects slots no author writes: thinking style, the ambiguity-feedback loop, protocol-citation mechanics, completion reminders, and the exit contract. Restating any of them in the body is noise at best and a contradiction at worst. Writing `<exit_contract>` in the body is rejected outright.

The completion protocol and the readable-resource tools are framework builtins mounted for every Agent phase — completion, reference reading, example reading, and ambiguity logging. They are not business tools: declaring the completion tool in `tools` is the compile defect `[F-v3-agent-tool-reserved]`.

Design checklist:

- Give the phase one decision responsibility and only the inputs it needs.
- Make the output schema precise enough for downstream phases to consume without interpreting prose.
- Declare every reference and example with a stable id, skill-relative path, and summary.
- Declare only required tools and capabilities. A file existing under `tools/` does not mount it automatically.
- Use `context_access` only for the explicit `working_memory` or `artifact` capabilities.
- Define what to do when evidence is insufficient; never instruct the executor to invent a value.

Role selection is explicit. With `use_graph_llm_role: false`, the phase role precedes graph role and host fallback. With `true`, graph role precedes host fallback and the phase role is not selected for that run.

The default host-native executor currently supports serially addressable Agent waits in the root DAG. Agent phases in registry subgraphs, graph-level iteration, Agent phase iteration, and incomparable parallel branches fail fast. Design around this current boundary or report that Phase 3b support is required; do not rely on silent fallback.
