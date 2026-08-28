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

Read [skill anatomy](references/KB-01-skill-anatomy.md) for ownership and [I/O dataflow](references/KB-02-io-dataflow.md) for field-level flow rules.

Return a glossary, root I/O schema, invariant list, source-to-output trace, and open decisions. Topology design should start only after these boundaries are reviewable.
