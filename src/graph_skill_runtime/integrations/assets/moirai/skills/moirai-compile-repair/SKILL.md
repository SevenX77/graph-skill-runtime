---
name: moirai-compile-repair
description: Diagnose a complete gSkill compile result and repair the smallest authoritative source of its failures.
---

# MoirAI compile repair

Use this skill when compilation fails or when topology and schema validity must be established before execution.

1. Obtain one complete compile result for the explicit business gSkill root.
2. Preserve every diagnostic; group related symptoms by violated invariant.
3. Locate the earliest authoritative source: root inventory, `graph.yaml`, phase file, resource registry, action/tool implementation, or request binding.
4. Repair the source contract rather than adding a parallel validator, compatibility alias, catch-and-ignore path, or downstream fixup.
5. Recompile once and compare the complete diagnostic set. Treat remaining diagnostics as independent work, not hidden success.

Work from the diagnostics themselves, never from a summary of them: read the full set with each code, severity, source path, and location. A repair started on a partial or second-hand error list fixes the wrong file.

Match on the diagnostic **code**, not on the message wording. A code is a stable identity registered by the runtime; the human sentence beside it can be reworded. Do not guess what a code means — if its meaning is not established, say so and look it up rather than inventing a remediation.

Group the set before editing anything. The recurring categories are identity mismatch, DAG shape, schema incompatibility, implementation contract, and resource or mention reachability; [compile diagnostics](references/KB-07-compile-diagnostics.md) defines each and what compilation can and cannot establish. Fix one category at a time so a recompile attributes the change.

When a failure appears only at prediction and not at compile, it is a runtime-structural defect, not a compile defect: read [prediction](references/KB-08-predict.md) for what that stage substitutes and what it can therefore expose.

Read [skill anatomy](references/KB-01-skill-anatomy.md) to identify owners and [working discipline](references/KB-15-working-discipline.md) for the escalation order this loop sits inside.

Return root cause, files or fields changed, before/after diagnostic evidence, and unresolved failures. Do not run a failing bundle merely to gather later-stage symptoms, and do not attempt several unrelated categories at once.
