# Configuration and state ownership

Graph Skill Runtime resolves values from highest to lowest precedence:

1. current invocation;
2. project `<skill_root>/gskill.toml`;
3. operating-system user configuration;
4. explicitly supplied portable defaults;
5. built-in defaults.

The machine runtime profile owns executor, checkpoint store, state directory, permissions, required capabilities, and fallback declarations. User configuration may own only that machine profile. Named run presets own reusable non-secret business inputs, bindings, breakpoints, node overrides, comparison candidates, and artifact requests; they come only from project `gskill.toml` or explicit portable defaults. The invocation owns one call's overrides.

Use MCP `resolve_run` or `python -m graph_skill_runtime config resolve SKILL_ROOT ...` to inspect the resolved request and field provenance without execution. The default executor is `host-native`; fallback declarations are recorded but never selected silently. CLI-vendor options are valid only for the explicit `cli` executor as defined in [02-entrypoints.md](02-entrypoints.md).

Resolution produces an immutable request with absolute skill and state roots. The default state root is `<skill_root>/.gskill` unless configuration selects another root. `predict` and `run` persist the immutable request before engine work. `resume` and `submit_agent_result` reload that snapshot rather than re-resolving changed configuration.

`--inputs-json` and preset inputs contain non-secret business values. Persist secret references and bindings, never literal secret values. Credential retrieval remains owned by the environment, current host, or operating-system keychain.

Keep state owners distinct:

- portable source owns discovery, topology, phase behavior, and optional project defaults;
- immutable request snapshot owns the exact resolved call;
- checkpoint storage owns graph generations;
- handoff storage owns Agent tasks and submissions;
- `<state_root>/runs/<run_id>/trace.jsonl` owns persisted prediction/execution events;
- artifact storage owns selected materialized outputs;
- golden storage owns existing evaluation baselines.

Relate records by explicit run, task, checkpoint, baseline, and artifact identities. No record substitutes for another owner's state.
