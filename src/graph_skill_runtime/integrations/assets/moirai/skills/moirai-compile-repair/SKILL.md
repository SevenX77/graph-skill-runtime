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

Read [skill anatomy](references/KB-01-skill-anatomy.md) to identify owners and [compile diagnostics](references/KB-07-compile-diagnostics.md) for the repair loop.

Return root cause, files or fields changed, before/after diagnostic evidence, and unresolved failures. Do not run a failing bundle merely to gather later-stage symptoms.
