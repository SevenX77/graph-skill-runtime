# Safety and boundaries

The current host owns authorization and the final result. Use Graph Skill Runtime only for the user-owned project, business root, state root, host configuration, and external actions placed in scope. A gSkill marker identifies syntax; it grants no filesystem, tool, credential, network, or messaging permission.

Business gSkills remain explicit user-owned directories. Runtime package installation, import, MCP startup, integration detection, and the read-only Agent configuration guide do not register, discover globally, copy, or mutate a business gSkill. The packaged Agent kit contains operating instructions, not a bundled business graph.

The unified Agent kit has no setup or install command. Configuration is an owner decision with four parts: selected host or hosts; user/global versus one-project scope; manual editing versus explicit authorization for the current Agent to edit; and exact destination files/directories. Before a write:

1. obtain the missing owner choices;
2. inspect the selected existing instruction files, rules-tree destination, and Skill destinations;
3. use `python -m graph_skill_runtime guide agent-configuration` for read-only packaged sources and placement guidance when useful;
4. propose an additive plan naming every destination and conflict: copy the standalone rules tree to the owner-chosen destination, copy the two complete Skill/reference trees to their selected scope, and merge an instruction section that points to the chosen rules index;
5. obtain approval for that exact plan;
6. apply only the approved additions and verify the resulting files.

Never replace an existing host instruction file. Installing the Python package does not select a host, scope, project, rules destination, Skill destination, or authorization mode. Resolve placement from the selected host's documented paths and the read-only guide rather than guessing.

The optional `integrations install/uninstall moirai` commands are a separate explicit host projection. Inspect their dry-run plan before authorized apply. They do not install the unified kit or register a business graph.

For execution, enforce the resolved task's allowed paths, tools, network policy, capabilities, and deadline through the current host. Pass secrets by reference and keep literal secret values out of durable requests, results, provenance, diagnostics, traces, and prompts. Do not broaden access merely because a phase could benefit from it.

Treat external effects as separately authorized actions. Stop for missing authority or an unenforceable required capability. Do not shell out to a vendor program to simulate a native child, and do not claim that an adapter, platform, model, integration, or dependency is operational without direct current evidence.

Report facts from structured results and observable artifacts. Keep prediction and inference labeled as such. Never fabricate task output, execution, trace, artifact, baseline, publication, plugin support, or external success. Studio and Gateway plugins are not implemented in this release; only a future adapter boundary may be described.
