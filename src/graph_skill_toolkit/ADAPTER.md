# Host Port and adapters

<a id="current-baseline-adopted-architecture-direction-2026-10-12"></a>
<a id="current-baseline-host-capability-interfaces-2026-10-12"></a>
<a id="contract"></a>
<a id="interface-contract"></a>

The Plugin Base connects plugin pages to Claude Code Desktop and Codex Desktop through one host-neutral Port. A **Port** is the page-facing contract; an **adapter** implements that contract through one host's native features. This document owns connection, identity, authority, transport, event delivery and the per-host route mapping. [Plugin Base usage](plugin_base/README.md) owns plugin construction and the full argument, result and evidence reference for the 17 host interfaces and 5 local capabilities. [ARCHITECTURE.md](ARCHITECTURE.md) owns the application map, process composition, route ownership and lifecycle.

## Terms

- **MCP (Model Context Protocol)** is the protocol through which the host calls the plugin server's tools and reads its resources. The toolkit uses standard input and output, or stdio, for this connection.
- **MCP App** is the extension that displays a plugin's HTML resource in a host-owned frame and carries page-to-host messages. Codex uses this channel.
- **Claude Mod** is hook code loaded inside a Claude Code session. It reads session facts and calls native host APIs for the page.
- **Browser pane** is the Claude Code Desktop panel that displays web pages in tabs.
- **Loopback** is the address `127.0.0.1`, which refers to the same machine. The plugin process opens one HTTP listener there on an operating-system-assigned port.
- **Host bridge** is the authenticated channel on that listener between a Claude page and its Mod.
- **Facade** is the page-side object returned by `createHostAdapter()`. It owns one host connection and checks operation authority.
- **Originating server** is the MCP server that presented the page. Codex page tool calls stay within that server.
- **Capability** is one interface's current declaration: state, detail, scope, constraints and limits. Its state is `available`, `unavailable` or `unknown`.

## Adapter module map

All paths in this table are inside the Plugin Base. Its four public entries and closure rule are specified in [Plugin Base usage](plugin_base/README.md#entry-files).

| Responsibility | Source |
| --- | --- |
| Port types, catalog and argument/result validation | [ports/host/](plugin_base/ports/host/) |
| One shared definition and two host implementations per interface | [host_interfaces/](plugin_base/host_interfaces/) |
| Factory and local-client attachment | [adapters/factory/index.mjs](plugin_base/adapters/factory/index.mjs) |
| Connection lifecycle, identity pinning and dispatch gate | [adapters/facade/index.mjs](plugin_base/adapters/facade/index.mjs) |
| Transport discovery and live host recognition | [adapters/detection/index.mjs](plugin_base/adapters/detection/index.mjs) |
| Launch facts and their comparison with the connection | [adapters/launch/index.mjs](plugin_base/adapters/launch/index.mjs) |
| Codex channel and operation dispatch | [adapters/codex/connection/](plugin_base/adapters/codex/connection/), [driver/](plugin_base/adapters/codex/driver/) |
| Claude page channel, dispatch and bridge | [adapters/claude/connection/](plugin_base/adapters/claude/connection/), [driver/](plugin_base/adapters/claude/driver/), [bridge/](plugin_base/adapters/claude/bridge/) |
| Claude hooks and native execution | [adapters/claude/mod/hooks/base.js](plugin_base/adapters/claude/mod/hooks/base.js), [operations/](plugin_base/adapters/claude/mod/operations/) |

## Connection and detection

The server publishes startup data in the page's inert JSON snapshot, whose element id is `plugin-base-snapshot`. The snapshot selects a transport and provides launch facts for comparison. Its format and construction belong to [Plugin Base usage](plugin_base/README.md#the-page-document-and-its-bootstrap-snapshot).

`createHostAdapter({ appInfo })` treats a missing or `null` snapshot as a standalone page and returns `null`. Malformed JSON, a non-object snapshot or a snapshot containing an error produces a visibly failing connection. A snapshot with `hostInfo.transport: "mcp-app"` selects the Codex channel and requires a parent frame. `http-bridge` selects the Claude channel. A parent frame alone supplies no host identity.

At tool invocation, `launchHostInfo()` records the calling MCP client. `codex-mcp-client` or `chatgpt`, with an absent or `codex_desktop` client type, identifies a Codex launch. `claude-code` identifies a Claude launch. For HTML presentation the Claude Mod supplies the native session identity from the live session.

Live recognition uses connection evidence:

- Codex requires MCP App initialization reporting `chatgpt` with an absent or `codex_desktop` client type.
- Claude requires a current Mod heartbeat and the identity `Claude Code`, source `claude-mod-session`, version, session id and client type `claude_code`.

Other evidence yields an unknown host with unknown capabilities. The facade compares transport, host id and any recorded session id with the live connection. Name, version and client type are also compared when the records have the same identity source. Different identity sources identify different software layers, such as an MCP engine and a desktop shell. A mismatch yields an unknown host and a diagnostic asking the user to reopen the page in the current session.

## Identity, authority and facade behavior

The [facade](plugin_base/adapters/facade/index.mjs) owns one connection from creation to disposal. It connects once and exposes the states `new`, `connecting`, `connected`, `failed` and `disposed`. Disposal closes the host connection and disposes the local page client.

The facade selects a host driver only after live identity confirmation on the matching transport. It pins host id, transport, name, version, client type and session id. A changed identity prevents further host dispatch. Before each operation, it refreshes identity and capability, validates and snapshots the arguments, and dispatches only an `available` operation. `unavailable` and `unknown` return `unsupported` with `data.capabilityState`. The [usage contract](plugin_base/README.md#results-and-evidence) defines argument bounds and result semantics.

A capability is `available` when the confirmed connection declares the required features. It is `unavailable` when a required feature is absent, and `unknown` when an equivalent native route has not been confirmed. An omitted declaration becomes `unknown`. These states describe the current adapter and connection. They leave future host capabilities open to independent verification.

The Codex driver refreshes declarations before execution. The Claude bridge checks the Mod's latest declaration, and the Mod checks its live session and tool inventory before native execution. Native permissions remain with the host. Launch data, editable samples and possession of a graph credential each supply their own limited facts; host execution requires the full connection gate.

## Receipt handling

[Plugin Base usage](plugin_base/README.md#results-and-evidence) owns the six result statuses and the four evidence slots. The facade supplies evidence on every `invoke` result. Empty receipt or observation slots state the available evidence boundary.

A failure after dispatch is `pending` unless it proves either refusal or absence of dispatch. The adapters retain the original request identity and avoid automatic replay:

- Claude exposes `adapter.getResult(requestId)` for querying an existing bridge receipt. A failed lookup preserves the uncertain original action.
- Codex treats explicit rejection and JSON-RPC errors `-32600`, `-32601` and `-32602` as proof that the update was refused. Other post-dispatch failures remain `pending`.
- A connection closed after dispatch leaves the effect uncertain and requires host observation.

## Codex transport

The [Codex connection](plugin_base/adapters/codex/connection/index.mjs) uses the official `@modelcontextprotocol/ext-apps` `App` and `PostMessageTransport`. This library owns handshake, message framing, request correlation, schema validation and teardown. `appInfo` supplies the page's name and version.

The host delivers the presenting tool's input and result to the page. A tool error fails connection with its message. If startup data does not arrive within 12 seconds after handshake, the connection reports the missing data and asks the user to reopen the page. Identity comes from `App.getHostVersion()`; capabilities and environment come from `App.getHostCapabilities()` and `App.getHostContext()`.

The driver calls declared native features: `openai/files`, `openai/message`, `sendMessage`, `updateModelContext`, `callServerTool` and `requestDisplayMode`. Page tool calls use `App.callServerTool` on the originating server. `list_page_tools` lists the apps' declared page-callable tools and itself. In this toolkit the list contains `inspect_graph`, `watch_graph`, `list_page_tools` and, when the lab is enabled, `lab_echo`. The local transport tools are registered separately with page-only visibility.

## Claude transport

**Page connection.** The [connection](plugin_base/adapters/claude/connection/index.mjs) validates the bridge descriptor. Its URL is `http://127.0.0.1:<port>/` with no credentials, query or fragment, and its token has 32–256 URL-safe characters. Its origin must match the page. Requests carry bearer authorization, omit cookies, disable caching and refuse redirects. HTTP responses 400, 401, 403, 404 and 429 mean `rejected`.

**Bridge.** The [bridge](plugin_base/adapters/claude/bridge/server.mjs) creates a published view path and distinct browser and Mod credentials. Bearer credentials stay in headers and snapshot data. A view is connected while its confirmed Mod heartbeat is less than five seconds old. The bridge deduplicates request ids, refuses a reused id with different content, holds at most 32 unsettled actions per view and retains up to 256 results. It returns `pending` with the request id after 20 seconds without an answer. A session-identity change, session end or process closure settles delivered actions as uncertain and undelivered actions as unsent errors. [ARCHITECTURE.md](ARCHITECTURE.md#loopback-listener-and-route-owners) owns the routes and their network policies.

**Mod.** [registerPluginBase](plugin_base/adapters/claude/mod/hooks/base.js) starts one-second heartbeats at session start. Each heartbeat reads identity and tools, posts declarations, receives queued actions and executes them once. Before native execution it checks that session id and generation remain unchanged. A failed result posting is retried; the native operation is executed once. A result exceeding 60,000 bytes retains its status and message while its data is omitted. The `tools.list` implementation detects this bound and returns an explicit error for an oversized list. Session end emits `session.ended`, disconnects bridges and clears session state.

The Mod supplies current session facts to presenting tools and adds ordered Browser-pane guidance to their results. [Plugin Base usage](plugin_base/README.md#registering-the-page-with-the-claude-mod) specifies page registration. [PROTOTYPE.md](PROTOTYPE.md#host-presentation) owns the visible presentation sequence and hidden-pane limit.

## Event delivery

`adapter.events.subscribe(listener, types?)` registers a listener and returns its unsubscribe function. Events are `{ type, at, data? }`. The facade copies events for listeners and isolates a failing listener. The [event reference](plugin_base/README.md#events) owns event fields and the host-specific data shapes.

Claude's Mod gathers `tool.completed`, main-agent `turn.completed`, `session.ended` and `context.attached` from its hooks. Each heartbeat posts queued events to the bridge through `POST /events`. The page starts long-polling `GET /events?after=N` at its first subscriber. Each bridge view retains the most recent 500 events. Relay delay is about one second, and the declared boundary excludes replay of events produced while the page is closed.

Codex converts MCP App notifications into `tool.completed`, `host.contextChanged` and `page.teardown`. Its `tool.completed` describes the presenting tool result. Turn-completion and session-end notifications have no confirmed MCP App route.

## Interface mapping

This table owns routes and per-host behavior. [The full operation reference](plugin_base/README.md#host-interface-reference) owns argument definitions, return fields, limits and examples. Availability also depends on the current connection gate.

| Interface | Codex route and behavior | Claude route and behavior |
| --- | --- | --- |
| `host.getInfo` | Facade; confirmed MCP App identity. | Facade; confirmed Mod session identity. |
| `host.getCapabilities` | Facade; current declarations. | Facade; current declarations. |
| `host.getContext` | MCP App host context: theme, locale and display modes; workspace roots unavailable. | Mod session APIs: project root, working directory and model; theme and locale unavailable. |
| `events.subscribe` | Facade listeners over MCP App notifications. | Facade listeners over Mod events and bridge long polls. |
| `files.openFile` | `openai/files/open`; accepted request; line navigation unsupported. | Native file-pane tool; accepted request with optional line. |
| `files.revealDirectory` | `unknown`; host file-browser directory route unconfirmed. | `unknown`; host file-browser directory route unconfirmed. |
| `composer.writeDraft` | `openai/message` draft extension; append only. | Mod `prompt.fill`; append or replace. |
| `conversation.submitMessage` | `sendMessage`; current session model and effort only. Other selection sources return `unsupported` without sending. | Mod `prompt.submit`; current or specified settings. A specified value applies to one main-agent turn through `turn.step`; default selection is unsupported. |
| `context.update` | `updateModelContext` using declared modalities; receipt-only confirmation of a whole snapshot. | Per-page stored snapshot attached by the next prompt-submission hook; `context.attached` reports attached blocks. |
| `tools.list` | `list_page_tools` on the originating server. | Session tool inventory with native and MCP entries. |
| `tools.call` | `App.callServerTool` on the originating server. | Permission-checked Mod `tool.call` for a listed session tool. |
| `skills.list` | `unknown`; native Skill inventory unconfirmed. | `session.usage` summary; complete names only. |
| `skills.invoke` | `unknown`; native Skill activation unconfirmed. | Native `Skill` tool; activation receipt and business outcome assessed separately. |
| `views.open` | `unknown`; owned reusable view handles unconfirmed. | Browser tools open or reuse this page's own web tab. |
| `views.list` | `unknown`; host view inventory unconfirmed. | Browser inventory filtered to this page's own views. |
| `views.close` | `unknown`; owned view closure unconfirmed. | Browser tools close this page's owned tab and read back inventory. |
| `views.requestDisplayMode` | `App.requestDisplayMode` for host-declared modes; resources advertise fullscreen. | `unknown`; equivalent container-mode route unconfirmed. |

Claude's specified model/effort correlation matches submitted text to `turn.start`, then applies the override to that turn's main-agent steps. `turn.completed.override.applied` carries applied values and the values the session would have used. The [decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md#open-items) owns the unresolved correlation and host-default questions.

## Local capability transports

The five local capabilities execute in the plugin's Node process. The [local reference](plugin_base/README.md#local-capability-reference) owns their file scope, arguments, evidence and platform commands. Their page route is selected by the snapshot's `local` field:

- Claude receives `{ transport: "http", url, token }` and calls `/local/call` and `/local/events` on the page's loopback origin with bearer authorization.
- Codex receives `{ transport: "mcp-tools" }` and calls the originating server's `local_call` and `local_events`. Both tools declare visibility `["app"]`, which keeps them hidden from the model. Codex Desktop 26.1007 admits only `https` and `wss` page connections, so the MCP channel carries these calls.

An absent usable route makes `adapter.local.available` false. [ARCHITECTURE.md](ARCHITECTURE.md#local-capabilities-in-the-process) owns the shared session connection and its grants.

## Verification boundary

The routes above describe source-checked behavior and capability declarations. [VALIDATION.md](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) owns dated command results and their scope. Native acceptance of all 22 operations on both hosts is pending. [MANUAL-TESTS.md](MANUAL-TESTS.md) gives the Interface Lab procedure for collecting candidate-bound effects and comparison records.
