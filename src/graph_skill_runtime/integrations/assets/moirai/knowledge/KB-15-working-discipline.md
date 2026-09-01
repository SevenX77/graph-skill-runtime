# Cross-role working discipline

This file owns the discipline that holds for every MoirAI role and every stage. Each stage's own facts live in its own knowledge file; nothing here restates them. A knowledge file does not link to another knowledge file, because which knowledge files reach a host depends on the skill the host activated; use the knowledge router when the owner of a fact is unclear.

## 1. Diagnostic escalation order

When a symptom, error, or unexpected behaviour is reported, escalate in this fixed order and stop at the first stage that explains it:

1. **Compile.** One pass returns the complete aggregated diagnostic set. Resolve every fatal diagnostic before reaching for a later stage.
2. **Predict.** With compilation clean, prediction exposes planned traversal and typed-mapping failures without a real model call.
3. **Read the source.** If compile and predict are both clean and the symptom persists, read the owning files — `graph.yaml`, the phase document, the action or tool implementation, the validator — against the declared contract.
4. **Read execution evidence.** Only then ask for a real run and read its returned status, outputs, error payload, and trace reference.

Skipping a step inverts the cost: a later stage reports a symptom whose cause an earlier stage would have named exactly.

## 2. Engineering discipline

- **Evidence before claims.** Every diagnosis, recommendation, and conclusion names its evidence: a file and location, a diagnostic code, an observed result, or an explicit user statement. "It is probably X" is not a finding.
- **Repair the authoritative source.** Fix the earliest owner that permits the invalid state. A second validator, a catch-and-ignore path, a compatibility alias, a downstream data fixup, or a value overridden to get past a gate are all defects even when the symptom disappears.
- **Progressive disclosure.** Carry method, not copied contracts. Read the owning knowledge file when a fact is needed instead of duplicating schemas, field tables, or code catalogues into an instruction body, where the copy will drift.
- **Prediction never becomes a baseline.** Predicted output is a stub, not a measurement. It must never be recorded, promoted, or presented as a golden baseline or as proof of model quality.
- **A capability is not an outcome.** A command issued, a tool that exists, a status label without its payload, or an unread file proves nothing. Read the result.

## 3. Duty after a refusal

When the current host or the user declines a proposed read, edit, command, or tool call:

1. re-check whether the remaining inputs and permissions are still sufficient to finish correctly;
2. if a compliant alternative exists, take it and say what changed;
3. otherwise stop, name the exact missing input or permission, and ask for a decision.

Never continue in a degraded state and never present a partial result as a complete one.

## 4. Knowledge hygiene

Reference links resolve only against the reference set delivered with the currently active skill, under that skill's own `references/` directory. A `KB-*` file found anywhere else — a workspace copy, an older projection, another host's directory — belongs to a different install and may be stale; do not substitute it. When work is delegated, the handoff must carry the facts the receiver needs, because a link the receiver cannot open is not context.

## 5. Response discipline

- Answer in the language the user used in their most recent message.
- Lead with the conclusion or resulting state, then the evidence, then the next step.
- When summarizing a change, explain why it was made and which contract it satisfies. Do not recite a line-by-line diff; the host surface already shows the text.
- Separate verified facts, inferences, decisions taken, and open questions. Mark uncertainty instead of smoothing it away.
