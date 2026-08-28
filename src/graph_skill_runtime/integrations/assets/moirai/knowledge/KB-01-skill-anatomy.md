# Portable business gSkill anatomy

A business gSkill is a user-owned directory supplied explicitly to Graph Skill Runtime. Package installation, Python import, MCP startup, host detection, and MoirAI installation do not register or bundle that workflow.

The minimum root is:

```text
<skill-root>/
├── SKILL.md
├── graph.yaml
└── phases/
    └── <phase_id>/
        └── LOGIC.md | AGENT.md | SUBGRAPH.md
```

- Root `SKILL.md` is the sole host Agent Skills discovery entry. Its body explains when and how to invoke the business skill.
- Root `graph.yaml` is the sole machine-readable owner of root topology, root I/O, phase registry, edges, and artifact declarations.
- Every registered phase directory contains exactly one type file: `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`.
- `AGENT.md` is a runtime-internal phase contract. It must not be named or projected as another host `SKILL.md`.
- Reusable graphs live directly at `graphs/<graph_id>/`, each with its own `graph.yaml` and `phases/`. Graph ids are explicit and bundle-wide unique.
- Physical directories own files; explicit graph and call edges own topology. Do not infer parentage from deep nesting.
- Optional `gskill.toml` owns project runtime overrides and named presets. Default runtime state is `.gskill/` beneath the business skill root unless resolution selects another state root.

MoirAI's packaged integration assets are host guidance, roles, and knowledge. They intentionally contain no `graph.yaml` and are not a business gSkill.
