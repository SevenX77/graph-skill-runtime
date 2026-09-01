# Authoring a business gSkill

Begin with the domain boundary. Before mutation, establish these facts when material to the requested workflow:

- intended user-visible outcome and activation condition;
- typed root inputs and outputs, with representative examples;
- destination and user/global versus project scope;
- external side effects, permissions, allowed paths/tools/network, and other resources;
- acceptance evidence;
- phase boundaries and delegation needs when judgement or reusable subgraphs materially affect the design.

Ask only for missing high-impact facts, and never re-ask information already supplied. A vague create request may require these questions before any write. If the user has supplied a complete contract, proceed within the authorized scope.

Use `python -m graph_skill_runtime create NAME --path EXISTING_PARENT --description TEXT` for the initial filesystem boundary. It creates only an absent `EXISTING_PARENT/NAME`; do not request force, overwrite, or adoption of a partial directory. Replace the scaffold's generic request/result contract with the actual domain design before treating the bundle as complete.

A business gSkill has these source owners:

- Root `SKILL.md` owns host discovery and invocation guidance, including `metadata.gskill: gskill.graph.v1`.
- Root `graph.yaml` owns root identity, typed I/O, phase registry, dependency edges, outputs, and artifact declarations.
- `phases/<phase_id>/` owns one registered root phase and contains exactly one of `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`.
- Reusable graphs live directly under the flat `graphs/<graph_id>/` registry. Each owns its own `graph.yaml` and `phases/`; identifiers are bundle-wide unique.

Every graph and phase uses a Draft 2020-12 object-shaped JSON Schema for inputs and outputs. Each required phase input has one guaranteed source through graph input, an upstream dependency, an explicit runtime binding, or iterator injection. Phase output keys are narrow and sufficient for downstream consumers.

Choose the phase type by responsibility:

- `LOGIC.md` owns deterministic, testable transformation through an explicit ordered action chain.
- `AGENT.md` owns one bounded judgement task with precise typed output, declared resources, tools, and capabilities. It is runtime source, not another host Skill.
- `SUBGRAPH.md` owns an explicit call to a coherent reusable registry graph with typed input and output boundaries.

Explicit graph and call edges own topology; physical nesting does not. Root artifact declarations own what can be materialized, while a run request selects declarations by stable artifact id.

The current host-native wait protocol supports serial Agent phases in the root DAG. An Agent inside a registry subgraph, graph iteration containing Agent, Agent phase iteration, or Agent phases on incomparable parallel branches is unsupported and must fail during preflight. Redesign the topology or report the missing capability; do not add fallback.

Compile the complete bundle after authoring, repair every current fatal diagnostic at its authoritative owner, and recompile. Compilation, not a parallel prompt rule, decides whether the bundle is executable.
