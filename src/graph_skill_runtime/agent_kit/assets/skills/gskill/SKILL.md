---
name: gskill
description: "Operate an existing graph workflow whose explicit root SKILL.md is marked metadata.gskill: gskill.graph.v1. Select for compile, inspect, configuration, predict, run, resume, Agent handoff, repair, trace evidence, or existing-golden evaluation; select create-gskill for creation or structural redesign."
---

# Operate an existing gSkill

Accept only an explicit compatible root according to [identification and version](references/01-identification-and-version.md). Route internally from observed state according to [skill and stage routing](references/03-skill-routing.md); do not require the user to name a command or internal role.

Prefer the eight tools of the MCP server named `gskill`. If the needed operation is unavailable there, use the installed interpreter exactly as defined in [entrypoints](references/02-entrypoints.md). Compile first, preserve the complete structured diagnostic set, and repair its authoritative owner using [diagnostics and repair](references/07-diagnostics-and-repair.md).

Resolve configuration through [configuration and state](references/06-configuration-and-state.md), then predict, run, resume, inspect, or evaluate an existing golden only for the requested outcome. Apply [execution and evidence](references/08-execution-and-evidence.md) to distinguish shape evidence from execution and to narrate only returned trace boundaries. If a repair changes source structure, follow [authoring](references/04-authoring.md).

On `agent_required`, follow the exact native-child protocol owned by [host-native Agent handoff](references/05-agent-handoff.md); `resume` never submits Agent output. Apply [safety and boundaries](references/09-safety-and-boundaries.md) to every write, capability, secret, and external effect.
