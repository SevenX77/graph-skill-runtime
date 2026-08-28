---
name: moirai-brainstorming
description: Explore competing graph-skill workflow designs before a domain model or topology has been chosen.
---

# MoirAI brainstorming

Use this skill before implementation when the desired outcome is known but the domain boundary, node split, or reuse strategy is still open.

1. State the user outcome and acceptance evidence without choosing a graph shape yet.
2. List actors, business concepts, inputs, outputs, invariants, side effects, and uncertainties.
3. Produce two or three materially different workflow options. For each, identify what is deterministic, what needs judgment, what can be reused, and what evidence could falsify it.
4. Compare the options on typed dataflow clarity, failure isolation, testability, and operational cost.
5. Recommend one option only when its assumptions are explicit; otherwise return the decision that remains open.

Use [skill anatomy](references/KB-01-skill-anatomy.md) for the portable bundle boundary and [I/O dataflow](references/KB-02-io-dataflow.md) for typed contracts. Consult [Agent nodes](references/KB-04-agent-nodes.md) before assigning judgment to an Agent phase and [subgraphs](references/KB-05-subgraph.md) before extracting reuse.

Return a concise option comparison, recommendation, rejected alternatives, and unresolved evidence. Do not create deep graph directories, hide topology in prose, or turn every uncertain step into an Agent.
