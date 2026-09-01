# Identification and version

A business gSkill is an explicit user-owned directory with all of these root facts:

- `SKILL.md` is the sole host Agent Skills entry and contains the string metadata entry `gskill: gskill.graph.v1` under `metadata`.
- `graph.yaml` is the root machine topology and declares `schema_version: gskill.graph.v1`.
- `phases/` contains the root graph's registered phase directories.

Use the explicit directory supplied by the user or caller. If the supplied path is inside a candidate bundle, select the nearest ancestor that satisfies the root facts, then compile that root. Do not scan the machine or register a directory globally.

A root `SKILL.md` without the marker is an ordinary Agent Skill or an invalid gSkill candidate; it is not accepted as a business gSkill. An internal `AGENT.md` is a runtime phase contract and never a discovery root. The kit Skills `gskill` and `create-gskill` are operator instructions, not business gSkills, so they do not carry the business marker.

The package release and portable syntax have separate identifiers:

- Distribution releases use normal package versions such as `1.0.0a1`.
- Portable source uses the exact syntax literal `gskill.graph.v1` in both the root marker and graph schema.
- Their major versions must match: runtime `1.x` consumes syntax `v1`.
- Patch and alpha package releases do not by themselves change the syntax literal.

Reject a missing or different root marker, a graph schema mismatch, or a runtime/syntax major mismatch. Do not guess a version, sniff an older format, or add a compatibility alias. An explicit converter may replace a legacy format; ordinary compile and run do not.
