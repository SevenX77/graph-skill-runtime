# Graph Skill toolkit architecture

<a id="shared-view-and-host-delivery"></a>

The Graph Skill toolkit is a local application that shows Graph Skills on a shared canvas inside two agent hosts, Codex and Claude Code, and installs itself through an explicit installer. A Graph Skill, or gSkill, is a user-owned directory containing `SKILL.md`, `graph.yaml` and phase definitions. The toolkit runs as one plugin process on the same physical filesystem as the selected gSkill. That process reads, compiles, projects and watches the gSkill, and streams each change to the canvas page that displays it.

This document is the toolkit's application map. It owns the module tree, the composition of the one plugin process, the loopback HTTP listener and the owner of each route on it, the local graph-data path, the authorization of graph data, the process-level placement of local capabilities, lifecycle and cleanup, and the build outputs. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md) owns host connection, identity, authority and the per-host route mapping for the 17 host interfaces. [Hostpane's guide](https://github.com/SevenX77/hostpane/blob/main/README.md) owns how to build a plugin on Hostpane and the full reference for its host interfaces and local capabilities.

The following terms are used throughout:

- **MCP** (Model Context Protocol) is the channel through which a host calls a plugin's tools and reads its resources. The toolkit's plugin process is an MCP server that the host starts and talks to over standard input and output.
- An **MCP App** is an MCP resource containing an HTML page that the host renders in a sandboxed frame. Codex displays the canvas as an MCP App.
- A **Claude Mod** is plugin code loaded into Claude Code's own session. It reads session facts, runs host tools and relays host events for the toolkit's pages.
- **Loopback** is the local network address of the same computer, `127.0.0.1`. A loopback listener accepts connections only from programs on that computer.
- **SSE** (Server-Sent Events) is an HTTP response that stays open and delivers successive data messages.
- A **long poll** is a request the server holds open until new data exists or a time limit passes.
- A **bearer credential** is a random token whose possession authorizes a defined scope of requests.
- **Hostpane** is the toolkit's host-integration layer, a separately versioned package in the private GitHub repository [`SevenX77/hostpane`](https://github.com/SevenX77/hostpane): the page-side host adapter, the server-side process and presentation helpers, the Claude Mod hooks, the local capabilities and the page-trigger runner. Hostpane's own code calls this layer the Plugin Base, which is why its Mod entry is named `registerPluginBase` and its page snapshot element is `plugin-base-snapshot`.
- A **commit pin** is a dependency declaration naming one exact 40-hexadecimal git commit, so every install reads the same bytes. The toolkit's [`package.json`](package.json) pins Hostpane as `"hostpane": "git+https://github.com/SevenX77/hostpane.git#1d656b42227fc68203807b93fa57383a6a8f6d0e"`; a Hostpane change reaches the toolkit only when that pin is updated.
- A **Port** is a host-neutral contract that an adapter implements through a particular system.
- A **business app** is one unit of plugin functionality built on Hostpane. The toolkit has two: the Graph Skill canvas and the Plugin Interface Lab.

The toolkit source sits at `src/graph_skill_toolkit/` beside `src/graph_skill_runtime/`, the separately packaged Python runtime. The runtime owns compilation and execution, and it is the single authority for gSkill validity and its messages. A compile diagnostic is one structured finding from the runtime command `compile --no-cache <root>`, carrying a code, severity, message, source path, line and field path. The toolkit draws only graphs the runtime accepts: its graph reader projects the root topology and phase kinds of an accepted graph for display. For a graph the runtime rejects, the toolkit shows the runtime's compile diagnostics verbatim. [The canvas diagnostics decision record](../../docs/design/canvas-runtime-diagnostics-2026-10-14.md) records this ownership, [the Plugin Base decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md) records the division into a host-integration layer, business apps and composition root, and [the Hostpane extraction decision](../../docs/design/hostpane-extraction-2026-11-07.md) records why that layer is the separate package Hostpane and how the toolkit depends on it.

## Current source map

```text
src/graph_skill_toolkit/
  composition/
    server.mjs                     the one plugin process and its list of business apps
    triggers.mjs                   the toolkit's page-trigger declaration: page tools, rule files, source folder
    after_tool.mjs                 the PostToolUse hook entry, Hostpane's runTriggerHook with that declaration
    claude_mod/{.claude-plugin/plugin.json,hooks/hooks.json,hooks/register.js}
                                   the one Claude Mod, presenting every app's page
  apps/graph_canvas/               the Graph Skill canvas app
    server/app.mjs                 show_graph, inspect_graph, watch_graph and the canvas resource
    app/{main.tsx,composition.mjs} page entry and pairing of host adapter with graph transport
    application/source/            skill-root selection, fingerprint and accepted-graph loading
    application/projection/        drawable topology from an accepted graph
    application/demo/              the labeled rootless demonstration graph
    application/service/           readGraphState: selection, compile, projection
    application/live_source/       file observation, reconciliation and change events per root
    application/client/            page-side SSE and long-poll graph connections
    backend/graph/                 graph credentials and the /graph/events SSE route
    backend/relay/                 per-root revision counter for watch_graph long polls
    backend/runtime/               compile port adapter that runs the Python runtime
    ports/graph/index.ts           the GraphConnection contract
    ui/{template,workbench,canvas,diagnostics,host_status}/
                                   page template, layout, drawing, invalid-graph notice, host status
    claude_mod/{page.js,payload.js}
                                   the canvas page as the Claude Mod presents it
    triggers.json                  the canvas's page-trigger rule graph-skill.root
  apps/interface_lab/              the Plugin Interface Lab app (developer tool)
    server/app.mjs                 open_interface_lab, lab_echo, lab_triggers and the lab resource
    server/state.mjs               lab state directory location and preparation
    server/triggers.mjs            trigger probe, lab openings that named a firing, read-only trigger views
    triggers.json                  the lab's probe rule interface-lab.probe
    app/main.tsx, ui/{index.tsx,template/lab.html}
                                   lab page entry, UI and template
    ui/triggers.tsx                the 触发 (Triggers) mode's three views
    application/{guide.mjs,runner.mjs}
                                   per-operation guidance and call runner
    application/result_status/     captured host identity and display label for each lab call
    application/connection_status/ one reading of the latest call for its record and its interface signal
    claude_mod/page.js             the lab page as the Claude Mod presents it
  skills/{graph-skill,graph-skill-canvas,plugin-interface-lab}/
                                   host instruction assets
  plugin.json, mcp.json, .claude-plugin/plugin.json, hooks/hooks.json
                                   plugin manifests: MCP server entry and page-trigger hook
  installer/{download,archive,discovery,hosts,ownership,locking,runtime_layout,
             runtime_payload,install,entry,bundle,verify_bundle,mode}/
                                   release acquisition, host projection, state ownership, source selection
  scripts/{build,preview,check_codex,pack_installer}/
                                   build, local preview host, Codex connection check, installer packaging
  bin/graph-skill.mjs              global command dispatch
  npm/                             lightweight npm entry
  tests/{backend,graph,installation,integration,interface_lab,support}/
                                   tests grouped by the boundary they exercise; integration
                                   tests run the built dist/server.mjs over real stdio
```

The toolkit consists of business apps (`apps/graph_canvas`, `apps/interface_lab`), the composition root (`composition/`), the installer, build and support scripts, host instruction assets and tests. It depends on Hostpane, installed under `node_modules/hostpane` from the commit pin, for the host-integration layer.

Toolkit code reaches Hostpane only through the five package exports `hostpane/page`, `hostpane/page/types`, `hostpane/server`, `hostpane/claude-mod` and `hostpane/triggers` (Node only); for example [the composition root](composition/server.mjs) imports `servePlugin` from `hostpane/server`, and [the hook entry](composition/after_tool.mjs) imports `runTriggerHook` from `hostpane/triggers`. [Hostpane's closure rule](https://github.com/SevenX77/hostpane/blob/main/README.md#closure-rule) owns the entry boundary. [The toolkit boundary test](tests/graph/hostpane-boundary.test.mjs) enforces the toolkit side: production code imports only those five specifiers, and `package.json` pins Hostpane by a 40-hexadecimal commit. [Hostpane's closure test](https://github.com/SevenX77/hostpane/blob/main/tests/base/closure.test.mjs) enforces the package side.

The canvas page's [entry](apps/graph_canvas/app/main.tsx) calls [the page composition root](apps/graph_canvas/app/composition.mjs), which builds a host adapter from Hostpane's page entry `hostpane/page` and a `GraphConnection` from [the graph client](apps/graph_canvas/application/client/index.mjs). `GraphConnection`, defined in [the graph port](apps/graph_canvas/ports/graph/index.ts), covers startup callbacks, selected-root changes and disposal for graph data. The [workbench](apps/graph_canvas/ui/workbench/index.tsx) composes the two independent connections. It renders the graph from `ui/canvas/`, the invalid-graph notice from [`ui/diagnostics/`](apps/graph_canvas/ui/diagnostics/index.tsx) above the graph area when the runtime rejects the selected skill, and live host identity from `ui/host_status/`. The common canvas HTML template is [`ui/template/canvas.html`](apps/graph_canvas/ui/template/canvas.html); [Hostpane's publisher](https://github.com/SevenX77/hostpane/blob/main/src/template/publisher.mjs) fills its snapshot slot for both host projections.

## Plugin process and composition

The toolkit runs exactly one plugin process per host MCP connection. [The composition root](composition/server.mjs) names that process `graph-skill-canvas`, so Claude Code exposes its tools as `mcp__graph-skill-canvas__<tool>`. It always serves the Graph Skill canvas app. It adds the Plugin Interface Lab app only when the environment variable `GRAPH_SKILL_INTERFACE_LAB` equals `1`; the installer sets that variable in source test mode only.

[`servePlugin`](https://github.com/SevenX77/hostpane/blob/main/src/server/serve.mjs), imported from `hostpane/server`, builds the process in two scopes:

1. **Once per process.** It creates one [loopback HTTP listener](https://github.com/SevenX77/hostpane/blob/main/src/backend/http/index.mjs), one [Claude host bridge](https://github.com/SevenX77/hostpane/blob/main/src/adapters/claude/bridge/server.mjs) and one set of [local capabilities](https://github.com/SevenX77/hostpane/blob/main/src/local/node/index.mjs), all mounted on that listener. It then calls each app factory once with `{ http, hostBridge, serverInfo }`. Each factory returns an owner `{ register(server, { local }), close() }`. The canvas factory creates the runtime compiler, the live graph source, the graph backend, the graph relay and its preview configuration at this scope.
2. **Once per MCP session.** It creates one MCP server and one local capability connection with its own bearer credential, granted roots and event queue. It calls every owner's `register`, which registers that app's tools and resources and returns the page-callable tools the app lists. It then registers the page-only local capability tools `local_call` and `local_events` and one [`list_page_tools`](https://github.com/SevenX77/hostpane/blob/main/src/server/page_tools.mjs) tool listing every app's page-callable tools plus itself.

The registered MCP tools and their visibility are:

- Canvas: `show_graph` (model-visible; opens the canvas), `inspect_graph` (model- and page-visible; read-only graph read), `watch_graph` (page-only; long poll for graph changes).
- Interface Lab, when enabled: `open_interface_lab` (model-visible; opens the lab; its optional inputs `route`, a lab route such as `trigger/test`, and `trigger_firing`, the id of the page-trigger firing that asked for the call, select the opening view and record the arrival), `lab_echo` (model- and page-visible; side-effect-free target for `tools.call`), `lab_triggers` (model- and page-visible; the trigger views' actions `state`, `prepare` and `evaluate`: the rules in effect, the latest firings, the probe and the lab openings that named a firing; probe preparation; and a dry run that writes no state).
- Hostpane: `list_page_tools` (page-only; read-only), `local_call` and `local_events` (page-only; the Codex route to local capabilities).

The canvas lists `inspect_graph` and `watch_graph` as page-callable tools; the lab lists `lab_echo` and `lab_triggers`. A page-only tool carries visibility `["app"]`, so the host never offers it to the model.

The Claude side has one Mod per installed toolkit. [Its registration](composition/claude_mod/hooks/register.js) calls `registerPluginBase` from `hostpane/claude-mod` with the Mod's own plugin name `graph-skill-canvas-mod`, the `name` in [its manifest](composition/claude_mod/.claude-plugin/plugin.json), and both page definitions: [the canvas page](apps/graph_canvas/claude_mod/page.js) for `show_graph` and [the lab page](apps/interface_lab/claude_mod/page.js) for `open_interface_lab`. For each page tool, the Mod's hooks supply the actual session root and confirmed session identity, request HTML presentation and guide the Browser-pane preview sequence; each page also registers a slash command that returns its latest HTML link.

## Loopback listener and route owners

[The listener](https://github.com/SevenX77/hostpane/blob/main/src/backend/http/index.mjs) binds `127.0.0.1` on an operating-system-assigned port when the process starts. It owns sockets, Host-header validation and shutdown: a request whose `Host` header differs from the listener's own origin receives `403`, an unmatched path receives `404`, and every response carries `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Each route owner mounts its own paths and retains its own credentials, origin policy and lifecycle.

| Path | Methods | Owner | Credential and origin policy |
| --- | --- | --- | --- |
| `/`, `/view/<random>` | GET | [Claude host bridge](https://github.com/SevenX77/hostpane/blob/main/src/adapters/claude/bridge/server.mjs) | Serves a published page's HTML with a strict Content Security Policy (`connect-src 'self'`, `frame-ancestors 'none'`); refuses cross-site navigation. |
| `/capabilities`, `/action`, `/result`, `/events` | GET or POST | Claude host bridge | Page bearer credential; same-origin requests only. |
| `/poll`, `/disconnect`, `/result`, `/events` | POST | Claude host bridge | Mod bearer credential; same-origin requests only. |
| `/local/call`, `/local/events` | POST, GET | [Local capabilities](https://github.com/SevenX77/hostpane/blob/main/src/local/node/index.mjs) | Per-session local credential; cross-origin requests refused. |
| `/graph/events` | GET, OPTIONS | [Graph backend](apps/graph_canvas/backend/graph/index.mjs) | Graph credential limited to selected roots; authenticated cross-origin reads permitted. |

The Claude host bridge exists for HTML presentation. A page view is created when a page tool runs with HTML presentation; the view holds two distinct bearer credentials, one for the page and one for the Mod, and neither token appears in a URL or a log. The page posts host actions and reads their results and host events; the Mod polls for actions, posts results and posts host events. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md) owns the meaning of those actions and events.

## Local graph data and authorization

Graph data never passes through a host interface. The canvas app's server code reads, compiles and watches the selected gSkill with Node.js directly, because that work is the canvas's own business logic in the plugin process. The page receives the results over a graph transport that the canvas app owns.

Each MCP session receives one graph connection from [the graph backend](apps/graph_canvas/backend/graph/index.mjs), holding a random graph bearer credential. Possession of that credential authorizes reads of the roots selected for it and nothing else; it carries no host-action authority. `show_graph` reads and validates the explicit root, then adds both the requested path and its canonical filesystem path to that credential's selected roots. An explicitly requested rootless demonstration selects `null`. `/graph/events` accepts only a root already selected for the presented credential. Graph credentials govern graph reads; the bridge's page and Mod credentials govern host operations on their separate routes; local credentials govern local capabilities.

**Graph-credential lifetime.** The connection returned by `createConnection()` has `close()`, which revokes its credential and ends its streams. The canvas creates it during MCP-session registration. The current registration and process runner provide no MCP-session-end call to that `close()`, so the credential remains valid until process shutdown clears the backend. Stdio serves one session per process. A page stream closing releases its subscription; it leaves the credential in the backend. The [decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md#open-items) tracks session-end revocation as an open lifecycle item.

The page learns its graph connection from its startup data. Every page HTML carries one inert JSON snapshot in `<script id="plugin-base-snapshot" type="application/json">`. The canvas snapshot carries `graphBackend.url` and `graphBackend.token`. Claude's HTTP page also carries its selected root in the snapshot; a Codex page obtains its selected root from the `show_graph` tool input or result that the host delivers to it.

The two hosts reach the graph data by two transports, chosen by [the page composition root](apps/graph_canvas/app/composition.mjs):

- **Claude HTTP page: SSE.** The [stream client](apps/graph_canvas/application/client/index.mjs) opens `/graph/events?root=<root>` with the graph credential and receives each graph event as one SSE message. The backend sends a heartbeat comment every 15 seconds and destroys a stream whose unsent output exceeds 8 MiB.
- **Codex MCP App page: `watch_graph` long poll.** Codex Desktop `26.1007.9446.0` admits only `https:` and `wss:` origins into an MCP App page's Content Security Policy, so its sandboxed page cannot open the loopback route. The [relay client](apps/graph_canvas/application/client/index.mjs) calls the page-only `watch_graph` tool through the page's MCP connection with the last revision it received. The [graph relay](apps/graph_canvas/backend/relay/index.mjs) keeps one revision counter per root and answers at once when the root's revision differs, otherwise on the next change, or with an empty result when the time limit passes (20 seconds by default, at most 25 seconds). A relay root with no waiter retires after 60 seconds. [The live-graph transport decision record](../../docs/design/live-graph-transport-2026-10-14.md) records the Content Security Policy finding and this transport.

Both transports read one shared [live source](apps/graph_canvas/application/live_source/index.mjs) per root, so a root is watched and compiled once however many pages display it.

The graph route's browser-access policy is cross-origin resource sharing, or CORS: it answers preflight requests and permits authenticated cross-origin `GET` from clients outside the listener's origin. The Claude host bridge and the local capability routes are same-origin only: their page is served from the listener's own origin. The canvas MCP resource declares the actual loopback origin in `_meta.ui.csp.connectDomains`. A Content Security Policy, or CSP, controls which network requests the host's browser permits a page to make. The [MCP Apps CSP and CORS documentation](https://apps.extensions.modelcontextprotocol.io/api/documents/csp-and-cors.html) defines these separate controls, including localhost connections.

Codex's resource URI is `ui://<namespace>/<name>-<sha256>.html`, where the hash covers the built HTML plus the startup snapshot, including the graph credential ([Hostpane's resource module](https://github.com/SevenX77/hostpane/blob/main/src/adapters/codex/presentation/resource/index.mjs)). A restarted process produces new credentials and therefore a new resource identity, so a newly retrieved page receives the current connection. Resource identity, selected graph identity and host session identity each have their own owner.

## Save-to-render flow and lifecycle

1. [The graph service](apps/graph_canvas/application/service/index.mjs) reads the selected root through [`application/source/files.mjs`](apps/graph_canvas/application/source/files.mjs) and prepares drawable data through [`application/projection/graph.mjs`](apps/graph_canvas/application/projection/graph.mjs). [`application/demo/`](apps/graph_canvas/application/demo/graph.mjs) supplies the labeled rootless example.
2. [The live source](apps/graph_canvas/application/live_source/index.mjs) owns one observation entry per subscribed root. It runs a recursive filesystem watcher on the root that reacts to `SKILL.md`, `graph.yaml`, `phases/` and `subgraphs/`, debounces notifications for 75 milliseconds, and reconciles the root once per second. Reconciliation covers missed events, phase-file edits the watcher filter skips and filesystems where a recursive watcher is unavailable. Each watcher notification and reconciliation tick first computes the root's fingerprint, a change detector built by [`skillFingerprint`](apps/graph_canvas/application/source/files.mjs) from the path, size and modification time of every file under the root. The fingerprint reads file metadata only, skips dot entries, `node_modules` and `__pycache__`, and is bounded to 10,000 entries. The live source reads the graph only when the fingerprint differs from the last one it read.
3. Each read runs [`readGraphState`](apps/graph_canvas/application/service/index.mjs). It applies the selection checks (an absolute path to a directory holding `SKILL.md` and `graph.yaml`), then compiles the root through the compile port, `compile(root) -> {status, diagnostics}`. The [runtime adapter](apps/graph_canvas/backend/runtime/index.mjs) implements that port: it spawns the runtime shell-free with `compile --no-cache <root>`, bounds the run to 30 seconds and 4 MiB of output, treats exit 0 as `passed` and exit 2 as `failed`, and rejects any other exit or a result outside the `gskill.compile-result.v1` contract. Its command is the JSON argument array in the `GRAPH_SKILL_RUNTIME` environment variable when set, otherwise the bundled Python named by the `release` in `~/.local/share/graph-skill/install.json`, run with `-I -B -X utf8 -m graph_skill_runtime`. The read yields one of three events:
   - `snapshot {data: {graph, skillRoot}}` when the runtime accepts the skill; the graph service projects root topology and phase kinds for drawing.
   - `invalid {skillRoot, diagnostics}` when the runtime rejects the skill; the event carries the runtime's compile diagnostics unchanged.
   - `error {message}` when a selection check fails, the runtime cannot be reached or answers outside its contract, or the canvas cannot draw a graph the runtime accepted; the message names that cause.

   The live source emits an event only when it differs from the root's last event, so a Markdown save that leaves the compile result and projection unchanged retains the existing snapshot. An existing page retains its startup data and its last valid graph across invalid and error events. On an invalid event the page shows the invalid-graph notice above that graph, and a later valid save produces a current snapshot through the same connection. [`show_graph`](apps/graph_canvas/server/app.mjs) opens the canvas for a snapshot or an invalid event; for an invalid event its structured content carries `graph: null` and `compile: {status, diagnostics}`, and its text lists each diagnostic's code, message and location. `inspect_graph` returns the same state for a root selected in the same session, and `watch_graph` carries all three event kinds.
4. The graph backend writes those events to subscribed SSE responses, and the graph relay numbers them per root for `watch_graph` long polls. The page's graph client selects the root, receives each event over its transport and passes snapshots to the workbench. The workbench validates drawable data and preserves a selected node while that node still exists.

Saving a file completes this path through the canvas app's file observation, its graph transport and rendering. The host adapter delivers launch selection and native operations. Its capability refresh updates host identity and operation availability; graph freshness comes from the independent graph transport. A page with valid graph startup data and a selected root keeps receiving graph data while host actions are unavailable.

The page's graph client cancels its current request when the selected root changes or the page is disposed. It reconnects after a lost stream or failed long poll after 750 milliseconds and ignores callbacks from superseded requests. The relay client retries its first failure after a selection silently, because the page may ask before the host finishes the `show_graph` call that selects the root. Backend stream closure releases its subscription and heartbeat. The live source keeps a root for a 30-second retention window after its final subscriber leaves, then retires the root's watcher, timers and cached event. `show_graph` and `inspect_graph` read the root's current event through the live source's `current(root)`, so a page that subscribes within the window reuses that tool call's compile result.

Process cleanup runs once, triggered by standard-input end or closure, `SIGINT` or `SIGTERM` in [`servePlugin`](https://github.com/SevenX77/hostpane/blob/main/src/server/serve.mjs). It proceeds in this order:

1. Every app owner closes. The canvas closes its graph relay, then its graph backend, which clears every graph credential, ends every graph stream and closes the live source with all its watchers and timers; it then removes the exact temporary preview entries it merged into a project's `.claude/launch.json`. The lab removes its own preview entries.
2. The local capabilities close every page connection, removing its credential, stopping its file watches and releasing its waiting event requests.
3. The Claude host bridge settles every outstanding action receipt: an action already delivered to the Mod is reported `pending` with an unknown outcome, and an undelivered action is reported `error`. It then clears its credentials and pages.
4. The listener closes and drops every open connection. On a signal, the MCP standard-input/output transport also closes.

## Local capabilities in the process

`servePlugin` creates one local-capability executor in the plugin's Node.js process and one connection per MCP session. Each app's `register` receives that same session connection. The canvas adds each selected skill root to its grants; the lab adds its state directory. All pages in the session therefore use the combined grants. The architecture's isolation unit is the MCP session. [Hostpane's local capability reference](https://github.com/SevenX77/hostpane/blob/main/README.md#local-capability-reference) owns file-scope checks, operation arguments, limits, evidence and platform commands.

The page snapshot declares a local route. Claude uses authenticated loopback HTTP, and Codex uses page-only MCP tools. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md#local-capability-transports) owns these transports. The canvas's graph reading and watching stays in the server app's business logic through Node.js directly.

The page local client's `dispose()` clears its listeners. The server connection owns watches and credentials until `stop()`/`close()` or process cleanup; page-client disposal alone leaves server watches active. Process cleanup closes every local connection. The [manual procedure](MANUAL-TESTS.md#settlement-and-reporting) includes explicit subscription and watch settlement.

## Host operations and presentation

The page reaches its host through Hostpane's host adapter. Startup data chooses a transport; a connected identity and current capabilities determine the driver and whether each call may proceed. Codex uses the official `@modelcontextprotocol/ext-apps` `App` and `PostMessageTransport` for its host channel; Claude uses the authenticated same-origin HTTP bridge and the Mod running in the host. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md) specifies connection authority, identity and host routes. [Hostpane's host interface reference](https://github.com/SevenX77/hostpane/blob/main/README.md#host-interface-reference) specifies operation arguments and limits.

`show_graph` selects the root, returns graph diagnostics and provides the host-specific presentation. In Codex the presentation is the MCP App view attached to the tool result; [Hostpane's Codex session module](https://github.com/SevenX77/hostpane/blob/main/src/adapters/codex/presentation/session/index.mjs) reuses one view per root. In Claude Code the presentation is the owned loopback HTTP page shown in the Browser pane: [Hostpane's preview configuration](https://github.com/SevenX77/hostpane/blob/main/src/adapters/claude/presentation/preview_configuration/index.mjs) merges one temporary attach entry for the listener's origin into the session project's `.claude/launch.json`, and the Mod's guidance drives `preview_start`, navigation and tab selection. `inspect_graph` performs an explicit read of a root already selected with `show_graph` in the same session. The generic `views.*` host interfaces are a separate function from this graph display flow.

The Plugin Interface Lab is a developer page served only in source test mode. `open_interface_lab` opens it as an MCP App in Codex and as a loopback HTTP page in Claude Code; the developer chooses each operation to run and compares its evidence with the actual effect, and its 触发 (Triggers) mode explains and tests page triggers. [PROTOTYPE.md](PROTOTYPE.md#plugin-interface-lab-page) owns the lab's visible behavior and state locations. [MANUAL-TESTS.md](MANUAL-TESTS.md) owns its native procedure.

### Page triggers

A page trigger is Hostpane's third interface kind, acting in the direction host activity → page: after a host tool call that changes or uses files a page presents, the toolkit's PostToolUse hook returns guidance asking the agent to call that page's tool. [Hostpane's page-trigger reference](https://github.com/SevenX77/hostpane/blob/main/README.md#page-triggers) owns the rule format, the firing reasons, the ignore list, the state and the guidance text; this section owns the toolkit's declaration and rules.

**The hook entry.** [`composition/after_tool.mjs`](composition/after_tool.mjs), bundled to `dist/after-tool.mjs`, runs Hostpane's `runTriggerHook` with `toolkitTriggersAt(<folder of the bundle>)`. The toolkit installer registers it as the PostToolUse command in `~/.claude/settings.json` for Claude Code and in `~/.codex/hooks.json` for Codex. [`composition/triggers.mjs`](composition/triggers.mjs) builds the declaration for that folder: the plugin name `graph-skill-canvas`, the page tools, the rule files, the ignore list `open_skill_folder` and `open_in_codex`, and the source folder. The composition root passes the same declaration to the lab app, so the lab shows the rules the hook uses.

**The canvas rule.** [`apps/graph_canvas/triggers.json`](apps/graph_canvas/triggers.json) holds the rule `graph-skill.root`:

```json
{
  "id": "graph-skill.root",
  "label": "Graph Skill 画布",
  "scope": { "kind": "root", "markers": ["SKILL.md", "graph.yaml"] },
  "use": { "tools": "^mcp__gskill__", "pathKeys": ["skill_root", "skill_path"], "commands": ["gskill"] },
  "pages": [{ "tool": "show_graph", "pathArguments": { "skill_root": "." } }],
  "note": "Follow the graph-skill-canvas skill."
}
```

A Graph Skill root is the nearest folder holding both `SKILL.md` and `graph.yaml`. An `Edit` of `examples/hello-world/graph.yaml` therefore asks for `show_graph` with `skill_root` set to the absolute path of `examples/hello-world`; an `mcp__gskill__compile` call naming that root, or a shell command starting `gskill` inside it, asks for the same call without a file change. Reading or listing a skill's files fires nothing. The business `SKILL.md` remains user-owned and is reachable on request through the host's file tools.

**The lab's probe rule.** [`apps/interface_lab/triggers.json`](apps/interface_lab/triggers.json) holds `interface-lab.probe`, whose root is a folder holding `TRIGGER-PROBE.md` and whose page call is `open_interface_lab` with `{ "route": "trigger/test" }` and `trigger_firing` set to the firing's id. The rule and the page tool `open_interface_lab` belong to the declaration only when `interface-lab.html` lies beside the bundle, which is true of a source build and false of the installed release. The lab's end-to-end trigger test asks the agent to edit the probe file `probe.txt` in that folder; [PROTOTYPE.md](PROTOTYPE.md#trigger-mode) describes it.

**The rebuild step.** When the folder above the bundle holds the toolkit's `package.json` (name `graph-skill-toolkit`, with a `build` script), the declaration's source is that folder with the command `npm run build`. A firing whose root or files lie inside it, or whose root contains it, makes the guidance ask the agent to run `npm run build` there first. An installed release has no source folder and no rebuild step.

**The repository's project rules.** This repository declares, in `.hostpane/triggers.json` at its root, which of its files the toolkit's pages present. Each rule has the `paths` scope, relative to the repository root:

| Rule | Files | Page calls |
| --- | --- | --- |
| `interface-lab.source` (Interface Lab 源码) | `src/graph_skill_toolkit/apps/interface_lab/**` | `open_interface_lab {}` |
| `graph-canvas.source` (画布源码) | `src/graph_skill_toolkit/apps/graph_canvas/**` | `show_graph` with `skill_root` set to `examples/hello-world` |
| `toolkit.shared` (两个页面共用的部分) | `src/graph_skill_toolkit/composition/**`, `src/graph_skill_toolkit/scripts/build/**`, `src/graph_skill_toolkit/package.json`, `vendor/ui-ux-template/core/**` | `open_interface_lab {}` and `show_graph` with `skill_root` set to `examples/hello-world` |

The root of these rules is the repository root, which contains the toolkit source folder, so each of their firings in a source build carries the rebuild step. A Hostpane change reaches the pages by moving the commit pin in `src/graph_skill_toolkit/package.json`, which fires `toolkit.shared`. In a build without the lab, `open_interface_lab` is no page tool, so the rules `interface-lab.source` and `toolkit.shared` are invalid in that build and skipped. The hook reports nothing about them; `evaluateTriggers` lists them in its `projectProblems`, which only the lab's 规则与记录 view shows, so a build without the lab has no place where an agent or developer sees them.

**Where firings are logged.** The hook appends each firing to `firings.jsonl` in Hostpane's trigger state directory for `graph-skill-canvas`: `%LOCALAPPDATA%\hostpane\triggers\graph-skill-canvas` on Windows, `~/Library/Application Support/hostpane/triggers/graph-skill-canvas` on macOS, and otherwise `$XDG_STATE_HOME/hostpane/triggers/graph-skill-canvas` or `~/.local/state/hostpane/triggers/graph-skill-canvas`. The lab's 规则与记录 (Rules and log) view shows the latest 20.

## Build outputs

[The build script](scripts/build/main.mjs) (`npm run build`) uses esbuild to produce every runtime file under `dist/`:

- `dist/server.mjs`: the plugin process, bundled from [`composition/server.mjs`](composition/server.mjs) for Node.js 22, including both business apps and the Hostpane modules they import.
- `dist/canvas.html`: the canvas page, one self-contained HTML file with its script bundle inlined into [the canvas template](apps/graph_canvas/ui/template/canvas.html).
- `dist/interface-lab.html`: the lab page, built the same way from [the lab template](apps/interface_lab/ui/template/lab.html).
- `dist/claude-mod/`: the Claude Mod, with `hooks/register.js` bundled from [the Mod registration](composition/claude_mod/hooks/register.js) and its `hooks.json` and `.claude-plugin/plugin.json` copied from `composition/claude_mod/`.
- `dist/after-tool.mjs`: the page-trigger hook, bundled from [`composition/after_tool.mjs`](composition/after_tool.mjs) with the rule files and the Hostpane trigger modules it imports.
- `dist/installer.mjs`: the npm installer entry, bundled for Node.js 18.

Each enabled app reads its page HTML beside the bundled server through Hostpane's `createPageFile`, once at module load and again on each page open whose file has a different size or modification time. A rebuilt page therefore shows on its next open without restarting the server; a change to server code takes effect in a new server process. The canvas requires `dist/canvas.html`; enabling the lab also requires `dist/interface-lab.html` there. Source builds produce both files; the installed release bundle contains the canvas page and enables the canvas app. The plugin manifests [`mcp.json`](mcp.json) and [`hooks/hooks.json`](hooks/hooks.json) point hosts at `dist/server.mjs` and `dist/after-tool.mjs`.

## Installation and source selection

The installer is separate from the pages and the plugin process. `installer/download/`, `archive/`, `discovery/`, `hosts/`, `ownership/`, `locking/`, `runtime_layout/`, `runtime_payload/`, `install/`, `entry/`, `bundle/` and `verify_bundle/` own release acquisition, host projection, state ownership and archive assembly. [Bundle assembly](installer/bundle/__init__.py) packs the release payload: `dist/server.mjs`, `dist/after-tool.mjs`, `dist/canvas.html`, `dist/installer.mjs`, the built `claude-mod/` files and the `graph-skill` and `graph-skill-canvas` Skills.

The [mode selector](installer/mode/__init__.py) changes which toolkit payload the installed user profiles reference. [Command dispatch](bin/graph-skill.mjs) builds a selected source for test mode and launches the mode entry with the installed private Python runtime. [Host projections](installer/hosts/__init__.py) render the plugin server, page-trigger hook, Skills and Claude Mod paths for either payload. In source test mode only, the projections also set `GRAPH_SKILL_INTERFACE_LAB=1` in both hosts' MCP server entries and install the `plugin-interface-lab` Skill; installed release mode serves neither. [The installation planner](installer/install/__init__.py) verifies the immutable release and managed resources, and the selector records `source_mode`, the test root and hashes of the built assets, the source command and the Skills' Markdown in the installation manifest. The command applies configuration and manifest changes under the installer lock, and a repeated selection with matching hashes and owned resources returns `unchanged` without writing. The installed release supplies private Node.js and Python and the command launchers. A source path, a built payload, a configured host profile and a loaded host process are separate identities; selection and source tests do not establish a host session's behavior, and a host loads a selected server and Mod only after it reloads.

## Design and acceptance references

The [Plugin Base decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md) owns the rationale, user rulings, acceptance criteria and open design items of the division into host-integration layer, business apps and composition root. [The Hostpane extraction decision](../../docs/design/hostpane-extraction-2026-11-07.md) owns the package boundary, the commit pin and the division of tests and documents between the toolkit and Hostpane. Hostpane's own gates are recorded in [its validation ledger](https://github.com/SevenX77/hostpane/blob/main/docs/VALIDATION.md). [VALIDATION.md](VALIDATION.md#hostpane-extraction-candidate-2026-11-07) owns measured source, build and installation checks, beginning with the candidate that depends on Hostpane. [MANUAL-TESTS.md](MANUAL-TESTS.md) owns observation of the loaded candidate in both hosts. A selected source, a built payload, a configured profile and a loaded host process are separate evidence identities.
