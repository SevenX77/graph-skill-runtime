# Deterministic prediction

Prediction resolves the request and uses deterministic or heuristic stubs to expose a planned run shape. It does not invoke a real model.

Use the `predict` tool belonging to the `gskill` MCP server, or:

```text
gskill predict SKILL_ROOT
gskill predict SKILL_ROOT --inputs-json JSON
```

Prediction can help verify configuration resolution, graph traversal expectations, and the shape of a `RunResult(mode="predict")`. It may create the immutable run request snapshot as part of application ordering, but it does not persist declared artifact outputs.

## What the public prediction surface substitutes

The public predict request declares exactly one strategy, `heuristic`: an Agent phase's output is a stub generated from that phase's `io.outputs` schema. The CLI and MCP surfaces expose no mock-injection parameter, so `gskill predict` and the `predict` tool always take this path. The engine also implements golden-case replay and per-phase override strategies, but those are internal to an embedding host and are not part of the public prediction contract — do not plan around them, and do not reach into runtime-internal Python to obtain them.

A schema-driven stub satisfies the declared shape by construction. That is exactly why a green prediction says nothing about content: the stub agrees with the schema no matter how wrong the real judgment would be, and the same placeholder data is substituted for every phase.

Prediction does not prove:

- that an Agent model can produce valid or useful output;
- that host-native capabilities are available;
- that a vendor CLI is installed, authenticated, or operational;
- that selected artifacts were materialized;
- that a golden baseline passes.

Use `run` for execution evidence and golden evaluation for an existing baseline. Label conclusions from prediction as expectations or hypotheses until a later stage observes them. Never record a predicted output as a golden baseline or as an expected value inside one; only observed execution output is a measurement.
