---
name: moirai-agent-prompt-design
description: Design a narrow runtime AGENT.md task with sufficient context, permissions, and a machine-checkable output schema.
---

# MoirAI Agent prompt design

Use this skill for a phase that genuinely requires judgment rather than a deterministic action.

1. Define the phase responsibility and the decision it alone owns.
2. Supply only declared inputs and necessary references or examples.
3. Write one `<role>`, one `<goal>`, ordered `<step>` elements, and explicit `<protocol>` constraints.
4. Define a Draft 2020-12 object output schema that is sufficient for downstream phases and rejects ambiguous completion.
5. Declare tools, context access, subagents, subgraphs, paths, network policy, and capabilities only when required.
6. State what the executor must do when evidence or capability is missing.

Read [Agent nodes](references/KB-04-agent-nodes.md) for authoring structure and [Agent execution](references/KB-12-agent-execution.md) for host-native and explicit CLI boundaries.

Return the proposed `AGENT.md` contract, input/output rationale, permission set, and failure conditions. A phase `AGENT.md` is runtime-internal and must never be projected as a host Agent Skill.
