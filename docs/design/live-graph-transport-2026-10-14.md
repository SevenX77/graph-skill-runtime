# Live graph transport per host

Date: 2026-10-14. Decision: the plugin backend owns graph reading, watching and change delivery for every host; each host adapter picks the transport its page is allowed to use; the Claude Mod passes `claude plugin validate` again. Native observation on both hosts is pending.

## Goal and authority

This decision serves the stable goal `shared-graph-ui-feasibility`, baseline at [`VALIDATION.md`](../../src/graph_skill_toolkit/VALIDATION.md) line 5. The canvas is the plugin's shared HTML page that draws a Graph Skill, a user-owned folder holding `SKILL.md` and `graph.yaml`.

The user set the requirement in Codex session `01a134b6-5743-74a0-bc3f-5c5b3ffd8bc8` (2026-10-13/14, stored under `C:/Users/test/.codex/sessions/2026/10/13/`), quoted verbatim with an English gloss:

- 2026-10-13T23:03Z: “页面必须实施反应gskill文件的变化，而不是等宿主来刷新页面，所以他需要能够实时读取本地gskill的文件” — "The page must reflect gSkill file changes in real time, without waiting for the host to refresh it, so it needs to read the local gSkill files in real time."
- 2026-10-13T23:10Z: “这个plugin本身他就不仅仅是一个页面，她是一个完整的app，只是嵌入在agent宿主里面，方便agent使用。所以他本来就需要完整的前后端” — "The plugin is a complete app embedded in the agent host for the agent's convenience, so it needs a full frontend and backend."
- 2026-10-13T23:12Z: “按照这个思路实施，保持模块化、高内聚低耦合” — "Implement along these lines; keep it modular, highly cohesive and loosely coupled."

In a Claude Code session on 2026-10-14, the user extended the requirement to both hosts:

- “这个需求是我提的，要实现，解决问题，Claude也需要这样实现” — "This requirement is mine; implement it and solve the problem; Claude needs the same implementation."

The user rules goal, principle and effect and owns native observation; the coding agent owns every implementation decision here.

## Current facts

Verified on 2026-10-14. Paths are relative to [`src/graph_skill_toolkit/`](../../src/graph_skill_toolkit/) unless absolute.

Terms: MCP (Model Context Protocol) is how a host talks to the plugin's server process. An MCP App is an HTML page that a Codex tool result attaches, run by Codex inside an isolated sandbox frame. CSP (Content Security Policy) is the browser rule list that decides which addresses a page may contact. SSE (Server-Sent Events) is a one-way HTTP stream from server to page. A long poll is a request the server holds open until new data exists or a time limit passes. The Mod is Claude Code's event plugin, loaded from `dist/claude-mod`.

1. The plugin backend is the canvas MCP server process [`server/main.mjs`](../../src/graph_skill_toolkit/server/main.mjs). It owns one loopback HTTP listener (`backend/http`) and the live graph source [`application/graph/live_source/index.mjs`](../../src/graph_skill_toolkit/application/graph/live_source/index.mjs). The live source runs one filesystem watch per subscribed root with a 75 ms debounce and a 1 s reconciliation, and it emits `{type:"snapshot",data}` or `{type:"error",message}` only when content changes. [`backend/graph/index.mjs`](../../src/graph_skill_toolkit/backend/graph/index.mjs) serves that source as SSE on `/graph/events` with a per-connection bearer token.
2. The page [`ui/workbench/index.tsx`](../../src/graph_skill_toolkit/ui/workbench/index.tsx) takes graph data only from a `GraphConnection`, defined in [`ports/graph/index.ts`](../../src/graph_skill_toolkit/ports/graph/index.ts) as `connect({receive, fail})`, `selectRoot(root)` and `dispose()`. Host tool results only select the root (lines 50-53). [`app/main.tsx`](../../src/graph_skill_toolkit/app/main.tsx) builds that connection with `createPageGraphConnection` in [`application/graph/client/index.mjs`](../../src/graph_skill_toolkit/application/graph/client/index.mjs), which reads the backend URL and token from the page snapshot and opens SSE.
3. Codex observation, 2026-10-14, session `01a13a18-9174-7242-b1a5-c3d45b8093fe`: `show_graph` on `examples/hello-world` returned 5 nodes, and the MCP App page showed “本地画布连接失败：Failed to fetch” ("local canvas connection failed: Failed to fetch") with no graph. A command-line request to the same backend port returned the expected 401 with correct CORS and private-network headers, which shows the listener works.
4. Codex Desktop `26.1007.9446.0` (`C:\Program Files\WindowsApps\OpenAI.Codex_26.1007.9446.0_x64__2p2nqsd0c76g0\app\resources\app.asar`, member `/webview/assets/resource-a537fc5fab33.js`) passes MCP App `connectDomains` through function `se`. That function keeps only `https:` and `wss:` origins, plus `http://localhost` when the build flag `oe()` is true; in this build `oe()` returns `false`. The page's declared `http://127.0.0.1:<port>` is therefore removed from its CSP, and the sandbox blocks every page request to the local backend. The page's browser engine treats a self-signed `https://127.0.0.1` certificate as untrusted. The MCP Apps channel (`app.callServerTool`, used at [`host_interfaces/tools/call/codex.mjs`](../../src/graph_skill_toolkit/host_interfaces/tools/call/codex.mjs) line 6) is the page's route out of the sandbox: Codex relays the call to this plugin's own MCP server process.
5. In Claude Code the same loopback listener serves the canvas page, so its SSE request is same-origin and reaches the backend. The user's 2026-10-14 Claude screenshot shows the graph loaded through that path.
6. With Claude Code `2.1.295`, `claude plugin validate dist/claude-mod` fails with `dist/claude-mod/hooks/register.js:581: $ itself is passed as an argument …`. The source is [`adapters/claude/mod/operations/registry.mjs`](../../src/graph_skill_toolkit/adapters/claude/mod/operations/registry.mjs), where `nativeCapabilities(tools, $)` calls `operation.capability(tools, $)`. The engine refuses the Mod, so no Mod hook runs, no bridge heartbeat reaches the page, and the page shows “宿主连接未就绪或心跳已过期” ("host connection not ready or heartbeat expired"). The committed version at HEAD `a450fda8`, built in isolation, passes the same validation; its helpers take `$` as their first parameter.

## Decision

1. The plugin backend owns graph reading, watching and change delivery for every host. One live source per root serves all transports.
2. Each host adapter picks the transport its page is allowed to use:
   - The Claude Code page uses SSE on the backend's `/graph/events`, same origin, as today.
   - The Codex MCP App page uses long poll over the MCP Apps channel. The backend exposes an app-only MCP tool, `watch_graph`, marked `_meta.ui.visibility: ["app"]`, hidden from the model and attaching no canvas. Its input is `skill_root` (a root already selected by `show_graph` on that MCP connection), an optional `after_revision` (integer ≥ 0) and an optional `timeout_ms` (bounded, default about 25 000). It returns at once when the root's revision differs from `after_revision`; otherwise it returns when the next change arrives or the time limit passes. Its result is `{ revision, event }`, where `event` is the live source's snapshot or error event, or `null` on timeout.
   - A new backend module, for example `backend/relay/`, owns per-root revision counting and waiters on top of the live source, and it retires an idle root subscription.
   - A new client, for example `createRelayGraphConnection` in `application/graph/client/`, implements `GraphConnection`. It calls `watch_graph` in a loop with the last revision, delivers snapshots to `receive` and errors to `fail`, retries after a short delay on transport failure, and stops on `dispose` or a root change.
   - The browser composition (`adapters/factory` plus `app/main.tsx`) builds one MCP connection for a Codex page and gives that same connection to both the host adapter and the relay client.
3. The Claude Mod passes `claude plugin validate`: every helper that needs the engine handle receives `$` in the form the validator accepts, and the operations registry dispatch follows that form. The Mod's behaviour stays the same.
4. Tests cover backend relay waiting, revision, timeout and idle retirement; `watch_graph` over real stdio, including refusal for an unselected root and an update after a `graph.yaml` save with no new `show_graph`; the relay client loop, retry and dispose; composition that gives Codex pages the relay and Claude pages SSE; and Mod validation.
5. Delivery runs `npm run build`, `npm test`, `npm run typecheck`, `claude plugin validate dist/claude-mod`, then `node bin/graph-skill.mjs mode test`, so both hosts start the new build next session. No commit.

## Design choices and rationale

- **Backend ownership.** The user's requirement describes the plugin as a full app with its own frontend and backend. Reading, watching and change detection live in the backend. In Codex, the host relay carries bytes between the plugin's own page and the plugin's own process.
- **Long poll on a request/response channel.** A held call that returns on the next change gives change-driven delivery: the page sees a change as soon as the backend's watcher reports it, with one open request at a time.
- **Transport chosen per host.** The page depends on `GraphConnection`, and both transports read the same live source. Only composition knows which transport a host permits, which keeps each adapter cohesive.

## Alternatives considered

- **Serve the backend over trusted HTTPS on loopback.** Rejected: it requires installing a certificate into the user's trust store, a system security change outside this plugin's authority.
- **Poll `inspect_graph` on a fixed interval.** Rejected: it delivers changes up to one interval late and re-reads the graph on every tick, while long poll reuses the live source's change events.
- **Route Claude Code through the MCP relay as well.** Rejected: the Claude Code page has a direct same-origin path, and an extra hop adds latency with no constraint that requires it.

## Acceptance criteria

| Criterion | Evidence | Stop condition |
| --- | --- | --- |
| Relay unit and stdio tests pass, including a save-without-`show_graph` update over `watch_graph`. | Backend relay and `watch_graph` stdio tests. | Any failure. |
| Source gates pass. | `npm test` with zero failures; `npm run typecheck`; `npm run build`. The intermittent case in `tests/backend/live.test.mjs` is tracked separately. | Any failure outside that tracked case. |
| The Claude Mod validates. | `claude plugin validate dist/claude-mod` passes. | A validator error. |
| Both hosts are wired to the new build. | `mode status` reports `configured` after `mode test`. | A `mode test` refusal or a reported problem. |
| Native Codex observation (pending, next Codex session). | `show_graph` on `examples/hello-world` shows the graph; editing `graph.yaml` updates the open canvas with no new `show_graph`; restoring the bytes updates it back. | A connection failure message, a missing graph, or a canvas that stays stale after a save. |
| Native Claude Code observation (pending, next Claude Code session). | The canvas shows the graph and updates on a `graph.yaml` save; the page's host status shows a connected host, and the host buttons respond. | A stale canvas, a "heartbeat expired" status, or unresponsive host buttons. |

## Validation scope

Source, simulated-host and real stdio tests (the host-to-server standard streams) establish the transport contracts. Codex sandbox behaviour and Claude Mod loading need native observation in fresh sessions; both are pending. No release, publication or commit is part of this decision.

## Revision log

- 2026-10-14: Created. Records the per-host transport decision, the Codex sandbox CSP finding, the long-poll `watch_graph` design and the Claude Mod validation repair.
