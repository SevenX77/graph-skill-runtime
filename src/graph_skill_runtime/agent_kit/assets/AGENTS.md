# Graph Skill Runtime Agent rules

A business gSkill is a user-owned graph workflow supplied to Graph Skill Runtime by an explicit directory path. Its root `SKILL.md` carries the portable marker `metadata.gskill: gskill.graph.v1`, its `graph.yaml` owns typed topology, and its phase documents own runtime behavior. Compile the complete bundle before prediction, execution, or evaluation.

The current host retains authorization and final ownership. Use only the paths, tools, network access, credentials, and external actions allowed by the user and host policy. Treat structured runtime results and observable artifacts as evidence; a command invocation or advertised capability is not proof of success.

## Select the public Skill

| Requested outcome | Public Skill |
| --- | --- |
| Operate, inspect, configure, predict, run, repair, or evaluate an existing root marked `gskill.graph.v1` | `gskill` |
| Create, scaffold, convert, brainstorm, design, or structurally redesign a graph workflow or gSkill | `create-gskill` |
| Create or edit an ordinary non-graph Agent Skill | Neither; use the host's ordinary Skill workflow. |

Selection is automatic from the request and each Skill's description. Do not require the user to know a command, Skill name, or internal MoirAI role.

## Use runtime entrypoints in order

For Agent work, prefer the structured tools belonging to the MCP server named `gskill`. If MCP is absent, disconnected, or lacks the required operation, use the installed interpreter with exactly `python -m graph_skill_runtime ...` as documented in [rules/02-entrypoints.md](rules/02-entrypoints.md). The distribution intentionally installs no package-owned console launcher.

Compile the explicit root first. Preserve complete diagnostics, statuses, error codes, run identity, checkpoint references, trace paths, and artifact identities. Never parse message prose when a structured field exists.

## Delegate only at the runtime boundary

A user's authorization to execute a successfully compiled gSkill with supported Agent phases includes exactly one fresh host-native clean-context child for each serial `agent_required` boundary returned by that run. The parent does not request subagent authorization again at each wait: the graph is durably paused, and the child is a required business-execution step rather than optional parallel development delegation. A general restriction on optional or parallel development subagents does not block this handoff.

The authorization covers only the returned `AgentTask`, canonical prompt, declared paths/tools/network/capabilities/deadline, one schema-valid output, and `submit_agent_result`. It authorizes no extra or parallel child, optional MoirAI delegation, child-created subagents, or broader permission. Block only if the user explicitly prohibited a native child for this gSkill run or the host cannot create or constrain it; hard host policy remains binding. Follow [rules/05-agent-handoff.md](rules/05-agent-handoff.md). `resume` observes or reopens; it does not submit an Agent result, and the current host retains final ownership.

Optional MoirAI assistance is internal routing for authoring, repair, or evaluation when that integration is installed. The user chooses an outcome and never has to name a specialist role.

## Configuration writes are owner decisions

Package installation, import, MCP startup, detection, and `python -m graph_skill_runtime guide agent-configuration` are read-only for host and project configuration. The runtime does not auto-register user business gSkills and provides no unified-kit setup or install command. The guide supplies standalone rules plus two Skill trees; the owner selects the rules-tree destination and the additive instruction section points to that chosen index.

Before any host-instruction or Skill-tree write, ask the owner to choose the host, user/global or project scope, and manual editing or explicit authorization for the current Agent to edit. Inspect the selected existing files, propose an additive merge or copy plan with exact destinations, and obtain approval. Never replace an existing host instruction file.

## Detailed rules

[rules/00-index.md](rules/00-index.md) maps each question to its single detailed owner.
