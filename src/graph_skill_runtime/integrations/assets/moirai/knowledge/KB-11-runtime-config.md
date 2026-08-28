# Runtime configuration ownership

Graph Skill Runtime resolves each value from highest to lowest precedence:

1. the current invocation;
2. project `<skill_root>/gskill.toml`;
3. operating-system user configuration;
4. explicit portable integration defaults;
5. built-in defaults.

The machine `RuntimeProfile` owns executor, checkpoint store, state directory, permissions, required capabilities, and fallback declarations. Operating-system user config may own only that machine profile.

`RunPreset` owns reusable non-secret business defaults such as inputs, bindings, breakpoints, node overrides, comparison candidates, and artifact requests. A named preset comes only from project configuration or explicitly supplied portable defaults. The current invocation owns one call's overrides.

Resolution produces an immutable `RunRequest` with absolute skill and state roots and field-level provenance. The default state root is `<skill_root>/.gskill`. Use `gskill config resolve SKILL_ROOT` when a human-readable CLI workflow needs to inspect the resolved request without executing it.

Secrets are references and bindings, never persisted literal values. Keep credentials in the environment, current host, or operating-system keychain and use `SecretReference` / `SecretBinding` in durable contracts. Host UI state, MoirAI install manifests, and business topology have different owners and do not belong in runtime configuration.

Fallback declarations are snapshotted but never silently selected. `host-native` remains the default; `cli` or `embedded` requires explicit resolution.
