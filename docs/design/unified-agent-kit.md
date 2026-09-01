---
doc: unified-agent-kit
role: design
status: drafted
updated: 2026-08-29
---

# Unified provider-neutral Agent kit

## 1. Purpose and current status

The unified Agent kit gives a coding Agent one provider-neutral contract for creating and operating user-owned graph workflows through Graph Skill Runtime. A business gSkill is an explicitly supplied directory whose root carries `metadata.gskill: gskill.graph.v1`; it is not registered globally by package installation or host configuration.

This document describes the verified `graph-skill-runtime` `1.0.0a1` implementation and its portable syntax `gskill.graph.v1`. Runtime and syntax majors must match. The kit is packaged as read-only source assets. There is no unified-kit setup or install command, and no destination is selected by installing the Python package.

Studio and Gateway plugins are future adapter-boundary work, not implemented release features.

## 2. Public surface and ownership

The kit contains exactly two public Agent Skills:

- `gskill` operates an existing explicit root marked `gskill.graph.v1`.
- `create-gskill` handles natural-language requests to create, scaffold, convert, brainstorm, design, or structurally redesign a graph workflow or gSkill.

An ordinary request to create a non-graph Agent Skill selects neither. Implicit selection relies primarily on the two frontmatter descriptions; users need not know Skill names or commands.

The current host owns authorization, host-native child creation, and the final user-facing verdict. The project owner owns business source. The runtime owns typed compilation, immutable requests, durable execution state, traces, and result validation. Optional MoirAI assistance may be routed internally when installed; it does not add a third public kit Skill and users do not choose internal roles.

## 3. Canonical packaged assets

The package owns one provider-neutral instruction section, ten indexed rules, and two complete Skill trees:

```text
agent_kit/assets/
├── AGENTS.md
├── rules/
│   ├── 00-index.md
│   ├── 01-identification-and-version.md
│   ├── 02-entrypoints.md
│   ├── 03-skill-routing.md
│   ├── 04-authoring.md
│   ├── 05-agent-handoff.md
│   ├── 06-configuration-and-state.md
│   ├── 07-diagnostics-and-repair.md
│   ├── 08-execution-and-evidence.md
│   └── 09-safety-and-boundaries.md
└── skills/
    ├── gskill/
    │   ├── SKILL.md
    │   └── references/
    └── create-gskill/
        ├── SKILL.md
        └── references/
```

Rule `00-index.md` maps questions to one detailed owner. Rule `02-entrypoints.md` is the exhaustive Agent-facing CLI reference copied into both Skills. Rule `05-agent-handoff.md` is the only authoritative occurrence of the exact native-child prompt. Rule `08-execution-and-evidence.md` owns trace-to-dialogue behavior and streaming limits.

The provider-neutral packaged `AGENTS.md` does not name host providers. Host placement belongs to the configuration guide and host documentation.

## 4. Read-only configuration guide

```text
python -m graph_skill_runtime guide agent-configuration
```

The command returns structured JSON containing the canonical AGENTS section, standalone `rules/<name>` assets, both complete Skill/reference trees, and current placement choices. It performs zero writes and is not an installer.

Configuration requires an owner decision for:

1. host or hosts;
2. user/global scope or one project;
3. manual editing or explicit authorization for the current Agent to edit;
4. a rules-tree destination and exact instruction and Skill destinations.

Before writing, the Agent inspects the selected existing files, presents an additive plan with every destination and conflict, and obtains approval. The plan copies the standalone rules tree to the owner-selected destination, copies the two complete Skill trees to the chosen Skill scope, and additively merges an instruction section that points to the chosen rules index. Existing `AGENTS.md` and `CLAUDE.md` files are never replaced.

Verified placement choices are:

| Host | User instructions | Project instructions | User Skills | Project Skills |
| --- | --- | --- | --- | --- |
| Codex | `$CODEX_HOME/AGENTS.md`, normally `~/.codex/AGENTS.md` | `<repo>/AGENTS.md` | `~/.agents/skills` | `<repo>/.agents/skills` |
| Claude Code | `~/.claude/CLAUDE.md` | `./CLAUDE.md` or `./.claude/CLAUDE.md` | `~/.claude/skills` | `.claude/skills` |

Codex merges instruction files from repository root to the current working directory. Claude Code reads `CLAUDE.md`, not `AGENTS.md`; a user may deliberately place `@AGENTS.md` in `CLAUDE.md` to import it. Other hosts use their documented locations.

## 5. Natural-language creation flow

A vague request such as “帮我创建一个gskill，这个技能的目的是……” automatically selects `create-gskill`. Before mutation, the Agent asks only for missing high-impact prerequisites:

- intended outcome and activation;
- typed root inputs and outputs with examples;
- destination and scope;
- external side effects, permissions, and allowed resources;
- acceptance evidence;
- material phase or delegation needs.

Facts already supplied are not requested again. If graph workflow versus ordinary Agent Skill is unclear, the Agent asks that distinction.

Once prerequisites and write authorization are complete, the Agent may create the filesystem boundary with:

```text
python -m graph_skill_runtime create NAME --path EXISTING_PARENT --description TEXT
```

The command creates only an absent `EXISTING_PARENT/NAME` scaffold. It does not perform domain design. The Agent refines typed contracts and topology, compiles the complete root, repairs the aggregated diagnostic set at authoritative owners, and recompiles.

## 6. Existing-gSkill operation flow

The `gskill` Skill follows this observable sequence:

1. identify the explicit root marker and verify runtime/syntax major compatibility;
2. compile and preserve all independently knowable diagnostics;
3. repair fatal diagnostics at their source owner;
4. resolve configuration or inspect topology when needed;
5. predict, run, or evaluate an existing golden as requested;
6. perform host-native handoff at each `agent_required` boundary;
7. issue a verdict from structured results, traces, outputs, and artifacts.

Agents prefer the `gskill` MCP server. When MCP is absent, disconnected, or lacks an operation, the fallback is exactly `python -m graph_skill_runtime ...` using the installed interpreter. The distribution intentionally has no `[project.scripts]`, `console_scripts`, package-owned `gskill.exe`, or `bin/gskill` launcher.

The MCP surface contains exactly `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`. Authoring, guide, migration, and integration commands do not extend MCP.

## 7. Host-native Agent handoff

The default executor is `host-native`. When `run` returns `status="agent_required"`, the payload contains a complete `AgentTask` and opaque checkpoint reference. This is a successful durable intermediate boundary.

Authorization to execute a successfully compiled gSkill with supported Agent phases includes the handoff required by that run. At each serial `agent_required` boundary, the current host creates exactly one fresh native clean-context child for the returned task without asking again for subagent authorization. The parent graph is already durably paused; this child is a required business-execution step, not optional parallel delegation for a development task. General restrictions on optional development delegation or parallel subagents do not apply to this mandatory boundary.

The included authority is limited to the returned `AgentTask`, the canonical prompt, the task's declared paths, tools, network policy, capabilities, and deadline, one JSON output valid against `task.output_schema`, and submission through `submit_agent_result`. It does not authorize an extra or parallel child, optional MoirAI delegation, subagents created by the child, or access beyond the user's authorization and enforceable host policy. The parent wraps the output in an `AgentResult` and submits it through MCP `submit_agent_result` or the module CLI `submit` command. A later serial `agent_required` repeats the same bounded procedure with another fresh child.

The exact child prompt is owned only by packaged rule `05-agent-handoff.md`; this design intentionally does not duplicate it. `resume` observes or reopens a wait and may carry a supported non-Agent human response. It never submits or substitutes for an Agent result.

The run blocks only when the user explicitly prohibited a native child for this specific gSkill run or the host cannot create the required child or enforce the task contract. A general “no new parallel subagent for this development task” instruction is not such a prohibition. An unavoidable host policy remains binding; the host reports that capability gap instead of claiming an override. It does not invent output or call a vendor CLI while describing it as the current host's native child.

## 8. Configuration, trace, and evidence

Configuration precedence is invocation, project `<skill_root>/gskill.toml`, operating-system user configuration, portable defaults, then built-in defaults. The default executor is `host-native`. CLI-vendor options are accepted only for the explicit `cli` executor, and `--vendor` is required there. Business JSON inputs must be non-secret; secrets use references and bindings.

`predict` produces deterministic or heuristic shape evidence and writes request/trace state. It does not prove live Agent capability or output quality. `run` executes. Both persist `<state_root>/runs/<run_id>/trace.jsonl`, and `RunResult` returns `trace_path`.

At each returned boundary, the current Agent may narrate concise observed progress: compile result, phase or wait, native-child handoff, failure, outputs, and completion. CLI and MCP calls are blocking between those boundaries. Version 1 has no public live-event subscription or `trace` CLI command, so continuous token-by-token or event-by-event live streaming is not implemented. Raw JSONL and secrets are not dumped into dialogue.

Golden evaluation accepts only an existing baseline. It never creates, captures, promotes, or updates one. A pass requires causal evidence after the requested action; a command invocation, prediction, trace existence, or self-report alone is insufficient.

## 9. Separate optional MoirAI integration

MoirAI is an optional host projection managed separately through `integrations detect/install/uninstall moirai`. Detection and dry-run are read-only. Apply requires explicit authorization and manifest-owned preflight. These commands do not install the unified kit and do not register a business gSkill.

The integration can provide internal brainstorming, domain, graph-design, prompt-design, repair, research, and evaluation routing. User prompts remain outcome-oriented; users never have to ask for internal role names.

## 10. Acceptance criteria

The design is satisfied when:

1. package installation, import, MCP startup, detection, and guide execution make no host/project configuration writes;
2. the guide returns the AGENTS section, standalone rule assets, and exactly two complete Skill/reference trees without selecting a destination;
3. natural-language graph creation selects `create-gskill`, while ordinary Skill creation does not;
4. existing marked roots select `gskill` and follow compile-first routing;
5. every fallback syntax begins `python -m graph_skill_runtime`, and no current contract assumes a package-owned launcher;
6. MCP exposes exactly eight runtime tools and no setup, authoring, guide, migration, or integration tool;
7. every approved configuration plan is additive, names exact destinations, includes an owner-selected rules tree, and preserves existing instruction files;
8. every `agent_required` boundary creates one fresh native child and submits through `submit_agent_result`, never `resume`;
9. the exact child prompt occurs only in rule 05;
10. trace narration is limited to observed returned boundaries and makes no live-streaming claim;
11. Studio and Gateway remain future adapter boundaries rather than implemented plugins.
