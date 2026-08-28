---
name: moirai-graph-design
description: Design or review portable graph.yaml topology, phase boundaries, reusable subgraphs, and iteration semantics.
---

# MoirAI graph design

Use this skill after the domain inputs, outputs, and invariants are explicit.

1. Define the root graph boundary and choose stable, bundle-unique graph ids.
2. Split work by responsibility: deterministic action chains use `LOGIC.md`, executor judgment uses `AGENT.md`, and reusable graph calls use `SUBGRAPH.md`.
3. Declare every phase and dependency in `graph.yaml`; treat explicit call edges as topology truth.
4. Trace required phase inputs to root inputs, upstream outputs, bindings, or iterator injection.
5. Place reusable graphs directly under `graphs/<graph_id>/`; never encode parentage through nested folders.
6. Add batch or loop iteration only with explicit item, range, concurrency or accumulation semantics.
7. Compile the complete bundle and address the full diagnostic set before execution.

Use [skill anatomy](references/KB-01-skill-anatomy.md), [I/O dataflow](references/KB-02-io-dataflow.md), [logic actions](references/KB-03-logic-actions.md), [Agent nodes](references/KB-04-agent-nodes.md), [subgraphs](references/KB-05-subgraph.md), and [iteration](references/KB-06-iterate.md) as needed.

Return the graph inventory, phase table, edges, field-level dataflow, subgraph and iterate decisions, and unresolved constraints. Do not add a `graph.yaml` to MoirAI integration assets; topology belongs only to the user's business gSkill.
