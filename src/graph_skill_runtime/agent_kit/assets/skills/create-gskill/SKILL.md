---
name: create-gskill
description: "Create, scaffold, convert, brainstorm, design, or structurally redesign a gSkill or graph workflow for Graph Skill Runtime, including vague natural-language requests such as creating a gskill for a stated purpose. Do not select for ordinary non-graph Agent Skills."
---

# Create or redesign a gSkill

Select from natural-language intent; the user need not know this Skill or a command. Use [skill and stage routing](references/03-skill-routing.md) to distinguish graph work from ordinary Skills and [identification and version](references/01-identification-and-version.md) for the portable root contract. If graph workflow versus ordinary Agent Skill is unclear, ask that distinction. Before mutation, ask only for missing high-impact outcome, activation, typed input/output examples, destination/scope, side effects and permissions, resources, acceptance evidence, and material phase/delegation needs. Do not re-ask supplied facts.

Use `python -m graph_skill_runtime create NAME --path EXISTING_PARENT --description TEXT` only after the destination write is authorized. It creates an absent scaffold, not a complete domain design. For an explicit legacy conversion, use the one-shot converter in [entrypoints](references/02-entrypoints.md).

Refine the scaffold according to [authoring](references/04-authoring.md), compile the complete root, repair every fatal diagnostic at its owner according to [diagnostics and repair](references/07-diagnostics-and-repair.md), and recompile. Optional specialist assistance may be routed internally when installed, but the user never has to name a role and no third public unified-kit Skill is created.

Apply [safety and boundaries](references/09-safety-and-boundaries.md) to paths, configuration, permissions, secrets, and external effects.
