---
name: moirai
description: Coordinate graph-skill design, repair, execution, and evidence-based evaluation when a request spans multiple runtime stages.
---

# MoirAI

Use this skill as the coordinating front door for work on an explicit user-owned business gSkill. The MoirAI integration supplies guidance and host profiles; it does not contain or register the user's workflow.

## Start with the contract

1. Identify the requested outcome, the explicit business gSkill root, constraints, and observable acceptance evidence.
2. Separate verified facts, inferences, decisions, and open questions.
3. Compile before prediction or execution. Prefer the tools belonging to the `gskill` MCP server; if they are unavailable, use the installed `gskill` command.
4. Keep the current host responsible for authorization, edits, specialist handoffs, host-native Agent execution, and the final answer.

Read only the detail needed for the current stage:

- For bundle shape and dataflow, read [skill anatomy](references/KB-01-skill-anatomy.md) and [I/O dataflow](references/KB-02-io-dataflow.md).
- For node choices, read [logic actions](references/KB-03-logic-actions.md), [Agent nodes](references/KB-04-agent-nodes.md), [subgraphs](references/KB-05-subgraph.md), and [iteration](references/KB-06-iterate.md).
- For runtime use, read [compile diagnostics](references/KB-07-compile-diagnostics.md), [prediction](references/KB-08-predict.md), [run and checkpoint](references/KB-09-run-trace-checkpoint.md), and [runtime tools](references/KB-13-runtime-tools.md).
- For acceptance, read [golden evaluation](references/KB-10-golden.md) and [artifacts](references/KB-14-artifacts-persistence.md).
- For environment decisions, read [runtime configuration](references/KB-11-runtime-config.md) and [Agent execution](references/KB-12-agent-execution.md).
- Use the [knowledge router](references/KB-00-hub.md) when the correct owner is unclear.

## Route specialist work

If the host exposes the installed specialist profiles, use `moirai-clotho` for domain/topology/prompt design, `moirai-lachesis` for diagnosis and authoritative repair, and `moirai-atropos` for evidence and verdicts. Every handoff must include the objective, scope, relevant files or typed inputs, verified facts, constraints, required output, and acceptance criteria. If no specialist mechanism is available, perform the same work in the current host rather than pretending a delegation occurred.

## Close the loop

Return the result, evidence, remaining uncertainty, and a clear pass, rework, or blocked status. Never treat `predict` as a real model run, `agent_required` as completed work, `resume` as Agent output submission, or a stale golden case as a pass.
