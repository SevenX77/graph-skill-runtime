# Canvas validity from runtime compile diagnostics

Date: 2026-10-14. Decision: the runtime is the single authority for gSkill validity and its messages; the canvas opens on any selectable skill root, shows the runtime's compile diagnostics verbatim in a prominent notice when the graph is invalid, and redraws the graph when a later save makes it valid. Native observation on both hosts is pending.

## Goal and authority

This decision serves the stable goal `shared-graph-ui-feasibility`, named at [`VALIDATION.md`](../../src/graph_skill_toolkit/VALIDATION.md) line 3. The companion decision [Live graph transport per host](live-graph-transport-2026-10-14.md) makes the canvas reflect gSkill file changes in real time on both hosts.

Terms used throughout:

- The runtime is the Python package `graph_skill_runtime`, which owns compilation and execution of gSkills.
- A compile diagnostic is one structured finding from runtime compilation, with schema `gskill.compile-diagnostic.v1`.
- The canvas is the plugin page that draws a gSkill graph.
- The live source is the plugin backend module that watches a skill root and emits graph events.
- MCP (Model Context Protocol) is how a host talks to the plugin's server process.
- A long poll is a request the server holds open until new data exists or a time limit passes.

The user ruled on 2026-10-14, quoted verbatim with an English gloss:

- “我同意你的修改方案，但是 错误提示应该使用runtime里面的compile的报错功能，而不是在plugin里面重新做一套” — "I agree with your change plan, but the error messages should use the runtime's compile error reporting, not a second set rebuilt inside the plugin."

The approved change plan: `show_graph` opens the canvas whenever the directory holds `SKILL.md` and `graph.yaml`, including while the graph is invalid; the page shows the error, keeps watching and redraws once the file is valid; the agent-facing text says the graph is invalid and why. A prominent notice above the graph area lists the causes and states that the graph below is the last valid version.

The user rules goal, principle and effect and owns native observation; the coding agent owns every implementation decision here.

## Current facts

Verified on 2026-10-14. Paths are relative to [`src/graph_skill_toolkit/`](../../src/graph_skill_toolkit/) unless absolute.

1. The plugin authors its own validity messages today. [`application/graph/source/files.mjs`](../../src/graph_skill_toolkit/application/graph/source/files.mjs) `loadSkill` throws, for example, "Phase X must contain exactly one type file." (line 45). [`application/graph/projection/graph.mjs`](../../src/graph_skill_toolkit/application/graph/projection/graph.mjs) `projectGraph` throws "Invalid dependencies or output flag for comment." (line 10) and "Graph contains a dependency cycle." (line 20). Line 1 of that file states: "Presentation projection only. Runtime compilation owns full gSkill validity." [`ARCHITECTURE.md`](../../src/graph_skill_toolkit/ARCHITECTURE.md) line 7 states that the runtime owns compilation and the toolkit's graph reader projects topology for display.
2. [`server/main.mjs`](../../src/graph_skill_toolkit/server/main.mjs) `show_graph` calls `readGraphPresentation(skill_root)` (line 61). When that call throws, the tool returns `isError` with "Cannot display Graph Skill: <message>" (line 82) and opens no canvas, in both hosts. On 2026-10-14 a Claude Code `show_graph` on `D:/coding/graph-skill-runtime/examples/hello-world`, whose `graph.yaml` had phase `comment` depending on the unregistered phase `measure`, failed with no canvas. A Codex canvas opened on the same root while valid showed "Invalid dependencies or output flag for comment." in its header after the edit and kept the last valid graph.
3. The live source [`application/graph/live_source/index.mjs`](../../src/graph_skill_toolkit/application/graph/live_source/index.mjs) reads a root on filesystem events (changes to `graph.yaml` and existence changes under `SKILL.md`, `phases/` and `subgraphs/`, with a 75 ms debounce) and on a 1 s reconciliation timer (line 6). It emits `{type:"snapshot",data}` or `{type:"error",message}` when the result changes (lines 24-25). The page renders an error as one line of small status text ([`ui/workbench/index.tsx`](../../src/graph_skill_toolkit/ui/workbench/index.tsx) line 90).
4. The runtime command `gskill compile --no-cache <skill_root>` prints a `gskill.compile-result.v1` JSON object `{status:"passed"|"failed", skill_id, diagnostics:[...]}` and exits 0 on `passed` and 2 on `failed`. Each diagnostic carries `code` (for example `[F-v3-graph-depends-unknown]`), `severity`, `message` (for example "phase 'comment' depends_on unknown phase 'measure'"), `source_path` (relative to the skill root, for example `graph.yaml`), `line`, `field_path`, `graph_id` and `phase_id`. Measured on 2026-10-14 against a broken copy of the example: three fatal diagnostics in about 2.9 s wall time, interpreter start included. A YAML syntax error yields a diagnostic carrying the parser message and line.
5. The installed toolkit bundles the runtime. `~/.local/share/graph-skill/install.json` records `release`; the launcher [`bin/graph-skill.mjs`](../../src/graph_skill_toolkit/bin/graph-skill.mjs) lines 157-160 run `<state>/versions/<release>/runtimes/python/python.exe` (`bin/python3` off Windows) with `-I -B -X utf8 -m graph_skill_runtime <command>`. In test mode the canvas MCP server runs from the worktree's `dist/server.mjs`, and that `install.json` still names the bundled runtime.

## Decision

1. The runtime is the single authority for gSkill validity and its messages. The canvas shows the runtime's compile diagnostics verbatim: code, message, `source_path:line` and field path. Every validity message the plugin displays comes from the runtime.
2. On each watcher event and reconciliation tick, the live source computes a cheap fingerprint of a selected root (path, size and modification time of every file, skipping `.gskill` and dot-entries, with a bounded entry count) and runs the pipeline only when the fingerprint changed:
   - Selection checks: the path is absolute and `SKILL.md` and `graph.yaml` exist. A failed check yields an error event.
   - Runtime compile with `--no-cache`. A `failed` status yields an invalid event carrying the diagnostics.
   - On `passed`, the plugin projects the topology for drawing and emits a snapshot.
   A projection failure on a graph the runtime accepted, or an unreachable runtime, yields an error event that names that cause.
3. The live source emits three event kinds: `snapshot {data:{graph, skillRoot}}`, `invalid {skillRoot, diagnostics}` and `error {message}`. Both page transports, SSE (Server-Sent Events, a one-way HTTP stream) for Claude Code and the `watch_graph` long poll for Codex, carry all three. The page's `GraphConnection` port gains an `invalid` callback.
4. Runtime access is a port with one adapter. The compile port is `compile(root) -> {status, diagnostics}`. The runtime adapter spawns the bundled runtime without a shell, under a bounded timeout, and parses the JSON result. It derives the command from the installation record by the launcher's rule, and an explicit environment variable overrides that command for tests and development.
5. `show_graph` opens the canvas whenever the selection checks pass. Its structured content carries `graph` (`null` when no valid graph exists yet) and `compile: {status, diagnostics}`. Its text gives the agent the node count when valid, or states that the graph is currently invalid with each diagnostic's code, message and location. `inspect_graph` returns the same state. Both tools reuse the live source's current result for the root; the live source keeps a root briefly after its last listener leaves, so the page subscription after `show_graph` reuses the same compile.
6. The page shows a prominent invalid-graph notice above the graph area. The notice holds a heading stating that the runtime reported N problems, the diagnostics list, and a line stating either that the graph below is the last valid version or that no valid version exists yet. A later snapshot clears the notice and draws the new graph.
7. Tests cover: compile adapter parsing (passed, failed, malformed output, timeout, missing runtime) against a fake runtime; fingerprint gating and invalid/snapshot/error transitions in the live source; `invalid` delivery by both page clients; the workbench notice; a real stdio `show_graph` on an invalid root that opens the canvas and reports diagnostics, after which a valid save produces a snapshot over `watch_graph` with no further `show_graph`. One opt-in test runs the real installed runtime when present and is recorded as a blind spot when absent.
8. Delivery runs `npm run build`, `npm test`, `npm run typecheck`, `claude plugin validate dist/claude-mod` and `node bin/graph-skill.mjs mode test`. `ARCHITECTURE.md` updates its live-source and validity paragraphs. No commit is part of this step.

## Design choices and rationale

- **Single authority.** Two validators drift apart in rules and wording. The runtime already reports complete, located diagnostics and decides whether a skill compiles and runs.
- **Fingerprint gating.** A runtime compile costs seconds because of interpreter start. A metadata-only fingerprint keeps the 1 s reconciliation cheap, catches phase-file edits the watcher filter skips, and opens no file that an editor's atomic save could collide with.
- **Canvas on an invalid graph.** Recovery from an invalid file to a valid one is a file change the page must reflect, so opening the canvas while invalid completes the companion decision's live requirement.
- **Port and adapter.** The compile port lets backend tests run without Python; the adapter keeps process spawning, timeout and parsing in one module.

## Alternatives considered

- **Keep the plugin's own checks and add runtime diagnostics beside them.** Rejected: this creates two sources of truth with different wording, contrary to the user's ruling.
- **Call the runtime through its MCP server (`gskill mcp`) as a long-lived child process.** Deferred: it saves interpreter start per change but adds a second long-lived process to own. The per-change command is simpler at current skill sizes and is revisited if compile latency matters.
- **Draw a best-effort graph from an invalid file.** Rejected: it presents topology the runtime rejects as if it were real. The notice above the last valid graph keeps the display truthful.

## Acceptance criteria

| Criterion | Evidence | Stop condition |
| --- | --- | --- |
| The tests listed in the decision pass. | Unit and real stdio test results. | Any failure. |
| Source gates pass. | `npm test` with zero failures; `npm run typecheck`; `npm run build`. The intermittent case in `tests/backend/live.test.mjs` is tracked separately. | Any failure outside that tracked case. |
| The Claude Mod validates and both hosts use the new build. | `claude plugin validate dist/claude-mod` passes; `mode status` reports `configured` after `mode test`. | A validator error, a `mode test` refusal or a reported problem. |
| Native Claude Code observation (pending, next Claude Code session). | `show_graph` on `examples/hello-world` with a broken `graph.yaml` opens the canvas with the notice listing the runtime diagnostics; fixing the file redraws the graph with no further `show_graph`. | No canvas, a notice whose text differs from the runtime diagnostics, or a canvas that stays stale after the fix. |
| Native Codex observation (pending, next Codex session). | On an open canvas, the same invalid-to-valid sequence shows the notice and then the redrawn graph. | A missing notice, plugin-authored validity text, or a canvas that stays stale after the fix. |

## Validation scope

Source and real stdio tests (the host-to-server standard streams) with a fake runtime establish the contracts. The opt-in real-runtime test establishes the adapter against the bundled runtime on this machine only. Native observation on both hosts is pending. No release, publication or commit is part of this decision.

## Revision log

- 2026-10-14: Created. Records the user's ruling that validity messages come from runtime compilation, the fingerprint-gated compile pipeline in the live source, the invalid event, the compile port and runtime adapter, and the invalid-graph notice.
