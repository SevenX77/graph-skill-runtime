# Existing golden baseline evaluation

Golden evaluation measures the current business gSkill against an existing baseline under:

```text
<state_root>/golden/<baseline_id>/
```

The baseline includes `baseline.json` and its cases. Graph Skill Runtime exposes evaluation only; there is no public create, capture, promote, or update operation.

Use the `evaluate_golden` tool belonging to the `gskill` MCP server, or:

```text
python -m graph_skill_runtime golden SKILL_ROOT BASELINE_ID --state-root STATE_ROOT
```

The engine report must contain an internally consistent `summary` with non-negative integer fields `total_cases`, `passed`, `failed`, and `stale`, where:

```text
total_cases = passed + failed + stale
```

`GoldenEvaluationResult.status` is `passed` only when the summary is valid and both `failed` and `stale` are zero. A stale case is not a pass. A failed or stale report returns failed with a `RuntimeErrorPayload`; a malformed report or evaluation exception also returns failed with a `RuntimeErrorPayload`.

Report the baseline id, summary counts, case evidence when available, and a pass-or-rework verdict. Missing or outdated baselines require an explicit external baseline workflow; do not invent a promotion operation.
