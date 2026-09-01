---
name: moirai-domain-analysis
description: Define graph-skill domain concepts, invariants, and typed input/output boundaries before topology design.
---

# MoirAI domain analysis

Use this skill to turn a business request into a stable vocabulary and explicit data contract.

1. Identify the business outcome, actors, source facts, decisions, and persisted outputs.
2. Define each important term once. Separate facts supplied by the caller from values inferred or created by the workflow.
3. Specify root inputs and outputs as explicit, comprehensible object-shaped JSON Schemas.
4. Trace every required output to an input, deterministic transformation, explicit judgment, or external result.
5. Record invariants and failure cases at the boundary where they can be validated.
6. Mark unresolved business choices; do not encode them as vague strings or implicit defaults.

Read every supplied document, file, and message completely before proposing anything. An analysis started on partial material is rewritten, not refined.

Organize the result in these sections so the next stage can consume it without rereading the sources:

- **Entities** — the domain nouns and concepts, each with the fields or attributes that identify it.
- **Workflows** — the step sequences, conditional branches, and decision points as the domain actually performs them.
- **Rules** — constraints, validation requirements, boundaries, and prerequisites, each stated where it can be checked.
- **Glossary** — each term defined exactly once, with the caller-supplied facts separated from values the workflow infers or creates.
- **Root I/O and trace** — the explicit object-shaped root input and output schemas, plus one guaranteed source for every required output.
- **Unresolved** — gaps and contradictions in the material. Ask; do not close them with an assumption.

When the domain is complex enough that a blind spot is likely, seek one independent viewpoint using whatever capability the current host exposes and authorizes. The runtime provides no analysis or search tool of its own. If no such capability is available, complete the analysis and state plainly that it had no external cross-check, rather than implying one occurred.

Read [skill anatomy](references/KB-01-skill-anatomy.md) for ownership and [I/O dataflow](references/KB-02-io-dataflow.md) for field-level flow rules; [working discipline](references/KB-15-working-discipline.md) governs evidence and reporting.

Return a glossary, root I/O schema, invariant list, source-to-output trace, and open decisions. Topology design should start only after these boundaries are reviewable. Do not return a long prose summary in place of the structured sections, and do not invent a domain parameter to fill a gap in the material.
