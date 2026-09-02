# Deterministic LOGIC actions

Use a `LOGIC.md` phase when the same validated inputs should produce the same business transformation without model judgment.

`LOGIC.md` declares a non-empty ordered `actions` list, phase I/O, and optional validator, sequential-overwrite, or iterate settings. Its body contains the same action names as `<action>...</action>` elements in execution order.

```markdown
---
name: normalize source
io:
  inputs:
    type: object
    required: [source]
    properties:
      source: {type: string}
  outputs:
    type: object
    required: [normalized]
    properties:
      normalized: {type: string}
actions: [normalize_source]
---

<action>normalize_source</action>
```

The implementation lives beside the phase at `actions/normalize_source.py` and exports:

```python
def normalize_source(inputs) -> dict:
    return {"normalized": inputs["source"].strip()}
```

The input is a phase-local read-only snapshot. The returned dictionary is the action's write channel, and every returned key belongs to the phase output schema. Keep parsing, normalization, sorting, mapping, and other testable rules here instead of asking an Agent to reproduce them probabilistically.

If an action needs filesystem, network, clock, or another side effect, make that dependency and failure behavior explicit at its boundary. Do not hide an unavailable dependency behind an empty result.

## The validator contract

`validator: true` on any phase — `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md` — runs `validator.py` from that same phase directory immediately after the phase produces its output. It exports:

```python
def validate(output: dict, state_slice: dict, **kwargs) -> None | dict:
    ...
```

Returning `None` accepts the output unchanged. Returning a dict replaces it, and that replacement is checked against the phase's `io.outputs` schema again. Raising, or returning any other type, is a structured phase failure.

A validator owns **shape**: types, enumerations, ranges, index continuity, and mechanical enrichment. It does not own quality. "Is this output good" belongs to a review phase and to golden evaluation, because a validator cannot distinguish a correct judgment from a plausible one. An assertion a schema-driven prediction stub cannot satisfy but a real output can — or the reverse — is a layering defect, not extra strictness: it makes the same phase pass or fail depending on which stage produced the value.
