---
name: moirai-eval-judgement
description: Judge a graph skill against explicit criteria using prediction, execution, trace, artifact, and existing golden evidence.
---

# MoirAI evaluation judgement

Use this skill when the user needs a pass-or-rework decision backed by runtime evidence.

1. Convert the request into observable acceptance criteria and identify required inputs, state, artifacts, and existing golden baseline.
2. Compile first. Use topology inspection when graph shape is part of the claim.
3. Use deterministic [prediction](references/KB-08-predict.md) to examine planned flow, never as proof of model quality or persisted output.
4. Use [run, trace, and checkpoint evidence](references/KB-09-run-trace-checkpoint.md) for actual execution. Resolve any `agent_required` state through the current host's native protocol before claiming completion.
5. Inspect [artifacts](references/KB-14-artifacts-persistence.md) only when the run requested and materialized them.
6. Apply [golden evaluation](references/KB-10-golden.md) only to an existing baseline. Failed, stale, missing, malformed, or unevaluated cases do not pass.

Return criterion, action, expected result, observed result, evidence location, and verdict for each item. Finish with one overall `pass`, `rework`, or `blocked` decision and the smallest justified next step.

Attribute every `rework`: route structural defects to design (`moirai-clotho`) and contract or implementation defects to authoritative repair (`moirai-lachesis`), and say which must move first when both apply. A `blocked` decision names the exact missing baseline, input, state, artifact request, or host capability. Never return an unattributed judgement such as "the output looks weak", and never collapse several independent root causes into one paragraph — each gets its own line, its own evidence, and its own owner.

The shared discipline in [working discipline](references/KB-15-working-discipline.md) governs the escalation order and the evidence rules this verdict rests on.
