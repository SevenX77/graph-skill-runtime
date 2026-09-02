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

## What belongs in each body element

The compiled prompt places each authored element into a fixed slot and injects the execution discipline around it. [Agent nodes](references/KB-04-agent-nodes.md) owns that slot map and the framework-owned slots you must not restate; this skill covers what content belongs in each element and why.

- **`<role>` — exactly one sentence.** Who the agent is in the business domain. No procedure, no rules, no backstory.
- **`<goal>` — one short block.** What outcome counts as done, plus one line per input saying what that input is for. No steps, no classification criteria, no judgment rules. If you are writing *how*, it belongs in a `<step>`; if you are writing *must* or *never*, it belongs in a `<protocol>`. A `<goal>` that keeps growing is the most common way iterative edits rot a prompt.
- **`<step>` — procedure only.** One action per step, in execution order. A step references a rule instead of restating it: write "classify each span per `[protocol:P1]`", not a second copy of P1. A rule stated in both a step and a protocol will diverge under future edits.
- **`<protocol>` — the single authority for every business rule.** Atomic: one rule, one id, citable. When a rule needs teaching material to be applied correctly — criteria expansions, easy-to-misjudge counter-examples — that material is part of the rule. Keep it inside the protocol or in a declared reference; deleting it changes behaviour.
- **`<example>` — business comprehension only.** Boundary cases, tricky classifications, worked judgments. Never an output-format mould: the compiled prompt explicitly tells the model not to copy example structure, and the format authority is `io.outputs`. An example whose content is "the completed payload must look like this JSON" is a defect, because it competes with the exit contract and the prompt then contradicts itself.

## Output contract and validator layering

`io.outputs` declares the fields the phase itself must author, and the compiled exit contract renders that schema. Steps and examples must agree with it; never instruct the executor to submit a subset or a superset of the declared required fields.

Check that agreement mechanically rather than by eye: write down `io.outputs.required`, write down every output field the body names, and require the two lists to be equal. A body that names one field while `required` declares four is the common shape, and it survives review because each half reads correctly on its own — the contradiction exists only between them, and the model meets it as a rendered contract demanding four fields under a goal that asked for one.

A `validator.py` is for shape only: types, enums, ranges, index continuity, and mechanical enrichment, per the runtime contract in [logic actions](references/KB-03-logic-actions.md). Whether an output is *good* is a question for a review phase and for [golden evaluation](references/KB-10-golden.md), never for the validator. Any validator assertion that a schema-driven prediction stub cannot satisfy but a real output can — or the reverse — is a layering defect, not extra strictness.

Design the phase so its output is evaluable: prefer structured or enumerated fields over free text, and restrict variance with the schema rather than with prose exhortations.

## Iteration loop

Test with real declared input payloads through [prediction](references/KB-08-predict.md), remembering that a stub agrees with the schema by construction and proves nothing about content. Change one instruction or one output key at a time and observe the effect before the next change. Encode a corrected failure into the element that owns it: a misjudgment becomes a protocol refinement or a boundary example, never a patch sentence appended to `<goal>`.

## Anti-patterns

- **Goal stuffing** — steps, criteria, or rule text accumulating in `<goal>`. Symptom: `<goal>` longer than a short paragraph.
- **Format-mould examples** — an `<example>` that exists to show the completed payload's shape.
- **Rule duplication** — one business rule stated in a step and a protocol, or in two protocols.
- **Framework restatement** — thinking discipline, completion mechanics, or the ambiguity loop rewritten in the body.
- **Hand-written exit contract or grouping wrappers** — rejected by the format.
- **Semantic assertions in `validator.py`** — exact counts or quality thresholds on real content.
- **Putting input payload content in the body, pasted or expanded.** The runtime already hands the model the phase's entire declared input slice on every model call ([I/O dataflow](references/KB-02-io-dataflow.md)), so a `{some_input}` reference written into the body is a second full copy of a value the model already has. Expanding a large field also splits the sentence it sits in: the reader, and the model, meets the verb, then thousands of characters of payload, then finally the object it was supposed to act on.
- **Conversational filler** that changes nothing about the output.

Read [Agent execution](references/KB-12-agent-execution.md) for the host-native and explicit CLI boundaries a designed task must live within, and [working discipline](references/KB-15-working-discipline.md) for the evidence rules that govern this work.

Return the proposed `AGENT.md` contract, input/output rationale, permission set, and failure conditions. A phase `AGENT.md` is runtime-internal and must never be projected as a host Agent Skill.
