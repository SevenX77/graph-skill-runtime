# Deterministic prediction

Prediction resolves the request and uses deterministic or heuristic stubs to expose a planned run shape. It does not invoke a real model.

Use the `predict` tool belonging to the `gskill` MCP server, or:

```text
gskill predict SKILL_ROOT
gskill predict SKILL_ROOT --inputs-json JSON
```

Prediction can help verify configuration resolution, graph traversal expectations, and the shape of a `RunResult(mode="predict")`. It may create the immutable run request snapshot as part of application ordering, but it does not persist declared artifact outputs.

Prediction does not prove:

- that an Agent model can produce valid or useful output;
- that host-native capabilities are available;
- that a vendor CLI is installed, authenticated, or operational;
- that selected artifacts were materialized;
- that a golden baseline passes.

Use `run` for execution evidence and golden evaluation for an existing baseline. Label conclusions from prediction as expectations or hypotheses until a later stage observes them.
