# Skill and stage routing

Public Skill selection is automatic and relies primarily on each Skill frontmatter `description`:

| User intent | Select |
| --- | --- |
| Operate an existing root explicitly marked `metadata.gskill: gskill.graph.v1`, including compile, inspect, configuration, prediction, execution, Agent handoff, repair, or existing-golden evaluation | `gskill` |
| Create, scaffold, convert, brainstorm, design, or structurally redesign a graph workflow or gSkill | `create-gskill` |
| Create or edit an ordinary non-graph Agent Skill | Neither |

A vague request such as “帮我创建一个gskill，这个技能的目的是……” selects `create-gskill` without requiring the user to know a command or Skill name. If the request could mean either an ordinary Agent Skill or a graph workflow, ask that single distinction before proceeding.

After `gskill` is selected, route by observable state:

1. Identify the explicit marked root and compatible syntax version.
2. Compile it and preserve the full diagnostic set.
3. Repair fatal diagnostics before later operations.
4. Resolve configuration or inspect topology when the request or evidence requires it.
5. Predict only for expected traversal or configuration-shape evidence.
6. Run for execution evidence.
7. On `agent_required`, create the native child and submit its typed result; repeat for each later serial wait.
8. Evaluate an existing golden baseline only after the current bundle compiles.
9. Issue an evidence verdict grounded in returned results and observable artifacts.

The user chooses a business outcome, not a MoirAI role. When MoirAI is installed, `create-gskill` or `gskill` may route internally to brainstorming, domain, graph-design, repair, prompt-design, research, or evaluation assistance. That optional internal routing does not add a third public unified-kit Skill and does not require the user to name Lachesis, Atropos, Clotho, or any other role.
