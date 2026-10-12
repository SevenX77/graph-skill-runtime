# Unified host adapter

## Current baseline

This document owns the launch and browser adapter contract for goal `shared-graph-ui-feasibility`. An adapter connects the shared graph page to operations in its host session. The required result supplies known host information when the canvas opens and uses the current connection's identity and capabilities for later actions. One public browser entry, one immutable `HostInfo` value, one HTML interface and the existing Claude and Codex execution adapters remain the delivery structure. [VALIDATION.md](VALIDATION.md#current-baseline-host-information-at-canvas-launch-2026-10-12) owns current acceptance. [PROTOTYPE.md](PROTOTYPE.md) owns observable controls and presentation effects.

**The launch implementation and both automated protocol/browser paths are attained in their measured cases. Changed-build installation and Desktop effects remain unverified.** The source base is `1a58394de250d29c778452570f33a05c886311fc`, branch `codex/claude-canvas-path`, with working version `0.3.4`. The coordinator owns implementation, verification and integrated acceptance. The independent writer owns this contract and its decision record. This responsibility covers working-source changes. The [0.3.4 delivery report](release/DELIVERY-0.3.4.md) retains its separately completed public-delivery scope.

The latest direct instruction, transcribed in the coordinator's self-contained handoff on 2026-10-12, is: “从agent调用show graph到分叉成codex怎么怎么样、Claude怎么怎么样，中间不应该有一个判断宿主是codex还是Claude吗？还是说这一步本身就不需要，那么就在这一步把宿主信息植入到打开的graph canvas，用于后续反向操作” (“Between the Agent calling show graph and the Codex/Claude branches, should there be a host decision? If that step is already unnecessary, inject host information into the canvas there for later reverse operations”). A reverse operation is a canvas control requesting an action in its host session. The [launch decision](evidence/launch-host-20261012/decision.md) retains the source, previous bytes, alternatives and confidence judgments. The [preceding source and decision](evidence/host-info-20261011/decision.md) retain the effective one-HTML, two-adapter, separate-identification and actual-connection requirements.

## Contract

The public browser factory is [createHostAdapter()](adapters/index.mjs). The application and workbench use that entry and the neutral [host Port](ports/host/index.ts), the common operation interface independent of host protocol. [adapters/launch/](adapters/launch/index.mjs) owns launch metadata capture and startup/live comparison. [adapters/detection/](adapters/detection/index.mjs) owns startup validation, explicit transport selection and pure HostInfo normalization. [adapters/host/](adapters/host/index.mjs) owns the page connection, graph binding and guarded dispatch. The two concrete adapters translate host operations. The canvas server and native presentation owners retain their existing responsibilities.

### Launch information

The launch boundary is the canvas server's `show_graph` handler and HTML resource handler. MCP, the Model Context Protocol, carries the invoking client's metadata, tool calls and results. The launch module reads the current request's `io.modelcontextprotocol/clientInfo` envelope field. If that request has no envelope, the module reads the SDK's initialization-scoped client getter. A present envelope with missing identity yields unknown identity.

The launch module recognizes reported MCP names `codex-mcp-client` or `chatgpt` as Codex when `client_type` is absent or `codex_desktop`, and `claude-code` as Claude. Other reported names remain visible facts with `id=unknown`. These declarations establish product-routing evidence from the connected protocol. Action authority also requires the current operation channel and its capability checks.

The Claude Mod is the plugin executing inside Claude Code. For an actual business root, it checks current preview tools and reads `$.session.root()`, `$.session.id()` and `$.session.version()` before forwarding `show_graph`. It replaces supplied presentation, preview-root and `native_host` values with those live facts when the HTML route is available. Missing native identity removes those supplied claims and leaves the graph result accompanied by a presentation diagnostic. The server accepts a native identity only with reported MCP client `claude-code`, HTML presentation and a valid Claude session/version description. Ordinary callers omit `native_host`.

The common HTML's inert `graph-skill-snapshot` JSON contains `hostInfo`, including the explicit `mcp-app` or `http-bridge` transport. `show_graph` returns the invocation's HostInfo with graph/document data. The MCP HTML resource embeds the resource request's client facts. The Claude HTTP page embeds its invocation's HostInfo alongside the graph and browser bridge descriptor. Both use the same template and executable page. Browser and Mod credentials retain their separate delivery boundaries.

The page selects its channel from that explicit startup value. MCP App delivery additionally requires a parent frame. An unconfigured template remains a standalone read-only demonstration even inside a frame; malformed startup data reports an error. A connection failure supplies no alternative product identity or automatic transport fallback.

### HostInfo and current authority

`HostInfo` is a frozen, safely copied value. Optional unavailable facts use `null`; an unknown version remains unknown.

| Field | Meaning |
| --- | --- |
| `id` | Normalized identity: `codex`, `claude` or `unknown`. |
| `name`, `version`, `clientType`, `sessionId` | Available reported facts, preserving the source's name and version scope. |
| `transport` | Explicit or connected channel: `mcp-app`, `http-bridge` or `none`. |
| `identitySource` | `mcp-client` for launch-client metadata, `mcp-initialize` for UI initialization, `claude-mod-session` for native Mod facts, or `none`. |
| `status`, `reason` | `confirmed` or `unknown`, with the basis for that judgment. |
| `capabilities` | Availability and explanation for each common action. Startup parsing always disables them until live evidence establishes availability. |

Startup confirmation describes reported caller identity. Current capabilities describe what the connected channel can request. These are separate conditions. The facade displays startup facts before connection, retains their binding internally and exposes the current normalized HostInfo after inspection. A client version describes the MCP engine/client; UI initialization can report a different component version. Across sources the launch comparison checks transport, confirmed product and an available startup session identifier. Name, version and client type are compared when both values have the same evidence source.

MCP App initialization returns `hostInfo` and `hostCapabilities`. Current Codex recognition requires name `chatgpt`, with `client_type` absent or `codex_desktop`. A contradictory client type or unrecognized name yields unknown identity with all actions unavailable. A missing launch identity can be completed by sufficient current connection evidence.

Claude's authenticated Mod heartbeat reports name `Claude Code`, source `claude-mod-session`, client type `claude_code`, the actual session ID and known engine version. The Mod declares its statically validated API routes and reads `$.tool.list()` for the fixed inspection capability. The HTTP bridge pins a confirmed native startup session before the first heartbeat, or binds its first confirmed heartbeat when launch session facts are unavailable. A different session cannot take over that view. A new explicit launch for another session retires the old Mod credential, settles its outstanding requests according to delivery state and creates a distinct view. Existing browser receipt inspection remains available while its service is reachable.

The facade checks returned graph-result HostInfo as well as the HTML startup value, so resource reuse preserves invocation identity. Confirmed product/session conflicts disable the page's actions and require reopening in the current session. Once live identity is pinned, later identity changes also disable dispatch. Missing or expired current metadata yields unknown identity and permits read-only recovery for the same binding. No action is automatically replayed.

The workbench refreshes HostInfo every two seconds and each dispatch obtains current capabilities. This is an observation interval. Claude retains the existing one-second heartbeat and five-second freshness window; expiry gates new actions and preserves pending outcomes. The [preceding decision](evidence/host-info-20261011/decision.md#native-mod-capability-decision) retains the interval evidence and native-scheduling limit.

### Actions and lifecycle

All eight actions use `invoke(action, args)`: `open-root`, `open-file`, `fill-prompt`, `send-prompt`, `update-context`, `list-tools`, `call-tool` and `request-skill`. Dispatch requires a connected lifecycle, confirmed current identity, an available capability and an absolute root matching the displayed graph. Context identifies that root, graph and an existing selected node when supplied. The facade validates and copies arguments before asynchronous capability retrieval, then rejects a graph revision that would make them stale.

`call-tool` retains the fixed `inspect_graph` operation. `request-skill` retains reading and summarization of the selected Skill. `open-root` remains the folder-opening operation. The retained `SKILL.md`/canvas presentation sequence stays with each host's presentation owner.

The [shared boundary](ports/host/contract.mjs) validates graph snapshots, action arguments, capabilities and results. Invalid graph data removes action authority. Disposal rejects new dispatch, suppresses late callbacks and closes the owned connection once. Work dispatched before disposal retains an unknown outcome when its effect cannot be established. `connect`, `capabilities`, `invoke`, optional receipt inspection and `dispose` retain their lifecycle roles. The [result contract](PROTOTYPE.md#capability-and-result-meaning) distinguishes `completed`, `accepted`, `pending`, `unsupported`, `rejected` and `error`; a request acknowledgment establishes only its acknowledged effect.

## Acceptance and record identity

Acceptance covers launch delivery, current connection authority, preserved behavior through both host routes and evidence-bound documentation. The [current validation record](VALIDATION.md#current-baseline-host-information-at-canvas-launch-2026-10-12) owns measured outcomes, exact source/build identity and operational gaps. Source tests and real-browser checks with simulated native peers establish their exercised contracts. Changed-build installed loading and actual Desktop effects require separate causal observations in each real host. An unknown host remains a truthful read-only view with host actions unavailable.

The compact Markdown authority is this contract together with the current validation section. Direct file-identity, reference and semantic review apply; the JSON goal checker has no interface for this format. The [launch decision](evidence/launch-host-20261012/decision.md#source-and-record-binding) provides the previous document snapshots and their hashes. Local evidence links are review coordinates that may be absent from public archives. Earlier accepted candidates retain their recorded scope.
