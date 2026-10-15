# Plugin Base

The Plugin Base is the shared foundation for plugin pages: web pages that a plugin shows inside Claude Code Desktop or Codex Desktop and that interact with the conversation in which they are shown. A plugin built on the Plugin Base consists of three parts:

- a **plugin server**: one Node process that the host starts as an MCP server and that serves one or more page apps;
- a **page**: a self-contained HTML document that runs in the host and calls host interfaces and local capabilities through one page object;
- a **Claude Mod registration**: the hook module that lets Claude Code present the page and carry its host operations.

This document owns plugin construction and the argument, effect, host behavior, limit and evidence reference for all 22 operations. [The adapter architecture](../ADAPTER.md) owns connection authority and transport behavior. [The application map](../ARCHITECTURE.md) owns process composition and lifecycle. [Page behavior](../PROTOTYPE.md) owns the Interface Lab display, and [the manual procedure](../MANUAL-TESTS.md) owns native observation. [The validation ledger](../VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) records the measured source checks and the pending native acceptance.

## Terms

- **Host**: the desktop application in which the page is shown. The Plugin Base implements adapters for Claude Code Desktop (called **Claude** below) and Codex Desktop (called **Codex** below). Their declared behavior is source-checked; native acceptance for the current candidate is pending.
- **MCP** (Model Context Protocol): the protocol through which a host starts a tool server and calls its tools. The plugin server is an MCP server over standard input and output (stdio).
- **MCP App**: the MCP extension in which a tool result names a `ui://` HTML resource that the host renders as an embedded page. Codex shows plugin pages as MCP Apps.
- **Claude Mod**: a Claude Code plugin module that registers hooks on Claude Code events (session start, prompt submission, tool calls, turn steps) and calls Claude Code's own APIs through the `$` object passed to each hook. Claude shows plugin pages through a Mod.
- **Browser pane**: the Claude Code Desktop panel that displays web pages in tabs. Claude shows plugin pages as tabs in the Browser pane.
- **Loopback**: the local network address `127.0.0.1`, reachable only from the same machine. The plugin server serves Claude pages and local capability requests on one loopback HTTP listener with an operating-system-assigned port.
- **Bridge** (host bridge): the authenticated loopback channel between a Claude page and the Claude Mod. The page posts operations to the bridge; the Mod polls the bridge once per second, executes the operations with Claude Code APIs, returns their results and posts host events.
- **Host interface**: one of 17 operations a page asks the host to perform, such as writing a draft into the message composer. Each host interface has one identifier, for example `composer.writeDraft`.
- **Local capability**: one of 5 operations the plugin's own Node process performs on the local machine for its page, such as reading a file. The plugin process owns their effects. A Codex page reaches that process through host-carried MCP tool calls; a Claude page uses local HTTP.
- **Capability**: the per-host declaration of one host interface: its state (`available`, `unavailable` or `unknown`), a detail text, and optionally a scope, constraints and limits.
- **Evidence**: four result slots for the payload record, raw receipt, read-back observation and applicable limits. The result reference defines populated and empty slots.
- **Effort**: the reasoning-effort setting of a model turn, one of `low`, `medium`, `high`, `xhigh`, `max`.
- **viewId**: the identifier a page receives for a Browser tab it opened with `views.open`; it names only tabs that page owns.

## What the Plugin Base owns

The Plugin Base owns four things:

1. **Host interfaces for both hosts.** Each of the 17 host interfaces has one shared definition (identifier, label, sample arguments, field list, argument validation) and one implementation per host. The catalog in [ports/host/catalog.mjs](ports/host/catalog.mjs) lists them in order; each lives in `host_interfaces/<group>/<name>/` with `index.mjs` (shared definition), `claude.mjs` and `codex.mjs` (capability and execution).
2. **Local capabilities.** The 5 local capabilities in [local/](local/) execute in the plugin server process, check the roots granted to the session local connection for file operations, and reach the page through loopback HTTP on Claude and through page-only MCP tools on Codex.
3. **Page presentation in both hosts.** The Plugin Base produces the MCP App resource for Codex and the loopback page, preview configuration and bridge for Claude, and the Claude Mod hooks that present the page.
4. **Evidence on every call.** Results from `adapter.invoke` and local calls carry evidence using the four slots defined in [ports/host/index.ts](ports/host/index.ts). The result reference below explains empty slots and convenience methods.

### Closure rule

The Plugin Base is closed in both directions:

- Code outside `plugin_base/` imports only the four entry files listed below.
- Code inside `plugin_base/` imports only its own files, third-party packages and Node built-in modules.

[../tests/plugin_base/closure.test.mjs](../tests/plugin_base/closure.test.mjs) enforces both directions over every production source file of the toolkit.

## Entry files

### Page entry: [page/index.mjs](page/index.mjs)

Everything a plugin page may import at run time.

| Export | Purpose |
| --- | --- |
| `createHostAdapter({ appInfo })` | Creates the page's one `HostAdapter` from the bootstrap snapshot in the document; returns `null` for a document whose snapshot is `null`. |
| `discoverConnection({ snapshotText, framed })` | Reads the bootstrap snapshot text and returns the connection channel (`mcp-app` or `http-bridge`), the snapshot and the launch host information; `createHostAdapter` calls it. |
| `createMcpConnection({ window, originatingServer, appInfo })` | Creates the Codex MCP App connection; `createHostAdapter` calls it. |
| `INTERFACES` | The 17 host interfaces in catalog order, each `{ id, label, sample }`. |
| `HOST_ACTIONS` | The 17 host interface identifiers in catalog order. |
| `SNAPSHOT_ELEMENT_ID` | `"plugin-base-snapshot"`, the id of the script element that holds the bootstrap snapshot. |
| `LOCAL_DEFINITIONS` | The 5 local capabilities, each `{ id, label, fields, sample, validate }`. |
| `LOCAL_ACTIONS` | The 5 local capability identifiers. |

### Page type entry: [page/types.ts](page/types.ts)

Type declarations only. It re-exports every type of [ports/host/index.ts](ports/host/index.ts), including `HostAdapter`, `HostResult`, `HostResultStatus`, `CallEvidence`, `HostEvent`, `HostEventType`, `HostCapability`, `HostCapabilities`, `HostInfo`, `Selection`, `ToolReference`, `ViewResource`, `LocalClient`, `LocalAction`, `LocalFileChange` and `LocalWatchResult`. Import it with `import type`.

### Server entry: [server/index.mjs](server/index.mjs)

Everything a plugin server process may import.

| Export | Purpose |
| --- | --- |
| `servePlugin({ serverInfo, apps })` | Runs the plugin server: one stdio MCP server with shared loopback listener, Claude bridge and local capabilities, serving every app. |
| `createLocalHttpServer()` | Creates the loopback HTTP listener (`127.0.0.1`, operating-system-assigned port) with `mount`, `open`, `close` and `origin`; `servePlugin` creates one. |
| `createHostBridge({ http })` | Creates the Claude bridge on that listener; its `createView(key, hostInfo)` and `publish(key, html)` serve a Claude page; `servePlugin` creates one. |
| `createPreviewConfiguration({ namePrefix })` | Owns the Claude preview entries in `<project>/.claude/launch.json`: `ensure(projectRoot, origin)` writes or reuses one URL entry and returns `{ name, projectRoot }`; `close()` removes the entries it wrote. |
| `pageResourceUri(namespace, name, html)` | Returns `ui://<namespace>/<name>-<sha256 of html>.html`, so each distinct page document has its own Codex resource URI. |
| `codexResourceMetadata` | The `openai/ui` resource metadata that advertises the fullscreen display mode to Codex. |
| `createCodexPageSessions()` | Creates per-MCP-session Codex widget session keys: `metadata(key)` returns `{ "openai/widgetSessionId": id }` and `existingMetadata(key)` returns it only when one exists. |
| `launchHostInfo({ clientInfo, presentation, nativeHost })` | Builds the launch host information that the page snapshot must carry, from the MCP client information and, on Claude, the Mod-supplied native session identity. |
| `requestClientInfo(server, context)` | Reads the MCP client information of the current tool or resource request. |
| `snapshotHtml(html, payload)` | Writes `payload` as JSON into the page's snapshot slot; throws when the slot is missing or duplicated. |
| `SNAPSHOT_SLOT` | The exact slot markup a page template must contain once: `<script id="plugin-base-snapshot" type="application/json">null</script>`. |
| `registerPageToolList(server, tools)` | Registers the page-only `list_page_tools` tool that Codex `tools.list` reads; `servePlugin` calls it. |
| `createLocalCapabilities({ http })` | Creates the local capability executor; `servePlugin` creates one. |
| `registerLocalCapabilityTools(server, connection)` | Registers the page-only `local_call` and `local_events` tools; `servePlugin` calls it. |

A plugin server built with `servePlugin` uses `snapshotHtml`, `pageResourceUri`, `codexResourceMetadata`, `createCodexPageSessions`, `createPreviewConfiguration`, `launchHostInfo` and `requestClientInfo` directly. The remaining exports are the parts `servePlugin` composes.

### Claude Mod entry: [claude_mod/index.js](claude_mod/index.js)

| Export | Purpose |
| --- | --- |
| `registerPluginBase(on, { pages })` | Registers the Plugin Base hooks once per Mod and presents every listed page; defined in [adapters/claude/mod/hooks/base.js](adapters/claude/mod/hooks/base.js). |

## Building a plugin

The Interface Lab is a complete worked example: server app [../apps/interface_lab/server/app.mjs](../apps/interface_lab/server/app.mjs), page [../apps/interface_lab/app/main.tsx](../apps/interface_lab/app/main.tsx), Mod page definition [../apps/interface_lab/claude_mod/page.js](../apps/interface_lab/claude_mod/page.js), and the composition files [../composition/server.mjs](../composition/server.mjs) and [../composition/claude_mod/hooks/register.js](../composition/claude_mod/hooks/register.js).

### The plugin server: `servePlugin` and app factories

The plugin server's entry module calls `servePlugin` once:

```js
import { servePlugin } from "../plugin_base/server/index.mjs";
import { myPageApp } from "../apps/my_page/server/app.mjs";

await servePlugin({ serverInfo: Object.freeze({ name: "my-plugin", version: "1.0.0" }), apps: [myPageApp] });
```

`servePlugin` ([server/serve.mjs](server/serve.mjs)) does the following:

1. It creates one loopback HTTP listener, one Claude bridge and the local capabilities.
2. It calls each app factory once per process with `{ http, hostBridge, serverInfo }`.
3. For each MCP session, it creates an MCP server, creates one local capability connection, and calls every app's `register(server, { local })`.
4. It then registers the page-only tools `local_call`, `local_events` and `list_page_tools`.
5. When standard input ends or closes, or on `SIGINT` or `SIGTERM`, it closes every app, the local capabilities, the bridge and the listener.

An app factory returns an owner object:

- `register(server, { local })` runs once per MCP session. It registers the app's tools and resources on `server` and returns the page-callable tools as `[{ name, description }]`; these are the tools Codex `tools.list` reports. `local` is that session's local capability connection: `local.allow(root)` grants that session connection one directory tree and `local.descriptor` holds the loopback `{ url, token }` a Claude page uses.
- `close()` runs once at process exit.

On Claude, MCP tool names take the form `mcp__<serverInfo.name>__<tool>`.

### The page document and its bootstrap snapshot

A page is a self-contained HTML document whose template contains `SNAPSHOT_SLOT` exactly once. The server fills the slot with `snapshotHtml(html, payload)`, which writes one inert JSON object into `<script id="plugin-base-snapshot" type="application/json">` ([template/publisher.mjs](template/publisher.mjs)). The snapshot carries:

- `hostInfo`: the launch host information from `launchHostInfo`;
- `serverInfo`: the plugin server's `{ name, version }`, which identifies the originating server on Codex;
- `local`: the page's route to local capabilities, `{ "transport": "http", "url", "token" }` for a Claude loopback page and `{ "transport": "mcp-tools" }` for a Codex MCP App page;
- `hostBridge` (Claude only): the page's bridge credential `{ url, token }`;
- any business data the app adds.

Codex MCP App pages use page-only MCP tools for local capabilities because the Codex page content security policy admits only `https` and `wss` connections, which excludes `http://127.0.0.1`.

### Presenting the page in Codex

Codex shows the page as an MCP App. The app registers one resource and one presenting tool whose metadata names that resource:

```js
const codexSessions = createCodexPageSessions();
const bootstrap = { serverInfo, page: PAGE_KEY, local: { transport: "mcp-tools" } };
const resourceUri = pageResourceUri("my-plugin", "page", snapshotHtml(html, bootstrap));
const ui = { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: false };

registerAppResource(server, "My page", resourceUri, { _meta: { ui, ...codexResourceMetadata } }, async (_uri, context) => ({
  contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, _meta: { ui, ...codexResourceMetadata },
    text: snapshotHtml(html, { ...bootstrap, hostInfo: launchHostInfo({ clientInfo: requestClientInfo(server.server, context) }) }) }],
}));
```

The presenting tool, registered with `registerAppTool` from `@modelcontextprotocol/ext-apps/server`, declares `_meta: { ui: { resourceUri, visibility: ["model"] } }`. Its successful result carries `structuredContent` with the business data and the invocation's `hostInfo`, plus `_meta: codexSessions.metadata(PAGE_KEY)`; an error result carries `_meta: codexSessions.existingMetadata(PAGE_KEY)`. The page receives that `structuredContent` through its `receive` callback.

A page-callable tool, such as the Interface Lab's `lab_echo`, declares `_meta: { ui: { visibility: ["model", "app"] } }` and appears in the list `register` returns.

### Presenting the page in Claude

Claude shows the page as a loopback HTTP page in a Browser pane tab. The Claude Mod calls the presenting tool with `presentation: "html"`, `preview_project_root` (the Claude session's project root) and `native_host` (the Claude session identity), so the presenting tool's input schema accepts these three optional fields. For an HTML presentation the tool does the following:

```js
const previewConfiguration = createPreviewConfiguration({ namePrefix: "my-page" }); // once per app factory; close() in owner.close

const hostInfo = launchHostInfo({ clientInfo: requestClientInfo(server.server, context), presentation, nativeHost: native_host });
const bridge = await hostBridge.createView(PAGE_KEY, hostInfo);
const document = snapshotHtml(html, { ...bootstrap, ...payload, hostInfo,
  hostBridge: bridge.browser, local: { transport: "http", ...local.descriptor } });
const preview = await previewConfiguration.ensure(preview_project_root, bridge.browser.url);
const httpPresentation = { kind: "http", url: hostBridge.publish(PAGE_KEY, document), preview, bridge: bridge.mod };
return { content: [{ type: "text", text: "Ready." }], structuredContent: { ...payload, presentation: httpPresentation } };
```

- `hostBridge.createView(key, hostInfo)` returns `{ browser, mod, url }`: `browser` is the page's bridge credential and `mod` is the Mod's credential `{ url, token, key }`.
- `hostBridge.publish(key, html)` serves the document at `http://127.0.0.1:<port>/view/<token>` and returns that URL.
- `previewConfiguration.ensure(projectRoot, origin)` writes or reuses one URL attach entry named `<namePrefix>-<uuid>` in `<projectRoot>/.claude/launch.json` and returns `{ name, projectRoot }`.
- The returned `presentation` object `{ kind: "http", url, preview, bridge }` is what the Claude Mod reads to register the bridge and guide the agent to open the page.

### Granting local roots

Local capabilities that touch files check directories granted to the session's connection. The app grants them in `register`, for example `await local.allow(stateDirectory)`. Each MCP session has its own connection, credential and granted roots. All apps and pages in that session share this connection and its combined grants; the scope is the MCP session. [The application map](../ARCHITECTURE.md#local-capabilities-in-the-process) describes its lifecycle.

### Registering the page with the Claude Mod

The Mod's hook module calls `registerPluginBase` once with every page of the plugin:

```js
import { registerPluginBase } from '../../../plugin_base/claude_mod/index.js';
import { myPage } from '../../../apps/my_page/claude_mod/page.js';

export function register(on) {
  registerPluginBase(on, { pages: [myPage] });
}
```

The Mod's `hooks/hooks.json` names that module: `{"modules":["./register.js"]}`. Each page definition has these fields:

- `tool`: the presenting tool's full Claude name, `mcp__<server>__<tool>`;
- `label`: the page name shown to the user and the agent;
- `command` (optional): `{ name, description }` of a slash command that returns the latest page link;
- `accepts` (optional): a predicate over the tool input; the Mod presents the page only when it returns true;
- `readPayload(result)`: reads the tool's `structuredContent` (with its `presentation` object) from the tool result as the Mod sees it.

With the page registered, the Mod does the following:

1. At session start it registers each page's command and starts polling every registered bridge once per second.
2. When the presenting tool is called and the Browser pane tools `preview_start` and `navigate` exist, it sets `presentation`, `preview_project_root` and `native_host` from the live session, overwriting caller values.
3. After the tool returns, it registers the page's bridge and appends preview guidance to the tool result, which tells the agent how to open the page in the Browser pane.
4. On each poll it sends the session identity and capabilities to the bridge, executes the page's queued Claude host operations, and relays host events.
5. At session end it emits `session.ended` and disconnects every bridge.

### The page: adapter, connection and calls

```ts
import { createHostAdapter } from "../../../plugin_base/page/index.mjs";
import type { HostEvent } from "../../../plugin_base/page/types";

const adapter = createHostAdapter({ appInfo: { name: "My page", version: "1.0.0" } });
if (adapter) {
  await adapter.connect({ receive: payload => render(payload), fail: error => showError(error) });
  const capabilities = await adapter.capabilities();
  const unsubscribe = adapter.events.subscribe((event: HostEvent) => log(event), ["tool.completed"]);
  const result = await adapter.composer.writeDraft({ text: "Hello", mode: "append" });
  const file = await adapter.local.files.read({ path: "/granted/dir/notes.txt" });
}
```

- `createHostAdapter({ appInfo })` reads the snapshot and selects the channel. It returns `null` when the snapshot is `null`, which marks a standalone document. A malformed snapshot yields an adapter whose `connect` fails with the reason.
- `adapter.connect({ receive, fail })` runs once per adapter. On Claude, `receive` is called with the snapshot. On Codex, `receive` is called with `{ toolInput }` for the presenting tool's arguments and with the presenting tool result's `structuredContent`; a tool error result calls `fail`. After connection the adapter confirms the host identity; operations select the Claude or Codex implementation only from a confirmed identity.
- `adapter.capabilities()` returns the current capability of every host interface.
- Host interfaces are called as `adapter.<namespace>.<name>(args)` or `adapter.invoke(id, args)`. `adapter.host.getInfo()` returns the `HostInfo` object directly and `adapter.host.getCapabilities()` returns the capabilities directly.
- `adapter.events.subscribe(listener, types?)` receives host events and returns the unsubscribe function.
- `adapter.local` is the local capability client.
- `adapter.hostInfo`, `adapter.hostId`, `adapter.hostName` and `adapter.state` (`new`, `connecting`, `connected`, `failed`, `disposed`) describe the connection.
- `adapter.getResult(requestId)` exists on Claude; it looks up a `pending` result by its `requestId` without sending the operation again.
- `adapter.dispose()` closes the connection and the local client.

## Results and evidence

`adapter.invoke(id, args)`, the operation methods that delegate to it, and local calls resolve to a `HostResult`. The convenience methods `adapter.host.getInfo()` and `adapter.host.getCapabilities()` return data directly. `adapter.events.subscribe(listener, types?)` returns an unsubscribe function; the Interface Lab wraps this subscription in its own evidenced result. Use `adapter.invoke("host.getInfo", {})` or `adapter.invoke("host.getCapabilities", {})` when a result envelope is required:

```ts
{ status, message, data?, requestId?, evidence: { sent, receipt, observed, limits } }
```

| Status | Meaning |
| --- | --- |
| `completed` | The operation's defined effect is established, such as reading data or storing context. Visible focus, a model reply and a business result each need their own observation. |
| `accepted` | The host accepted the request; the effect is observed separately. |
| `pending` | The request was dispatched and its outcome is unknown; check the host before sending it again. Claude pending results carry a `requestId` for `adapter.getResult`. |
| `unsupported` | The current host cannot perform the operation as requested. A capability whose state is `unavailable` or `unknown` yields this status with `data.capabilityState`. |
| `rejected` | The host, the scope rule or the target refused the request. |
| `error` | The operation failed or its arguments were invalid. |

The four evidence slots are defined by `CallEvidence` in [ports/host/index.ts](ports/host/index.ts). The [contract validator](ports/host/contract.mjs) accepts optional evidence and optional fields; it validates the evidence object and its limits when present. The [facade](adapters/facade/index.mjs) adds `sent` and `limits` to every `invoke` result, and the local client adds them to local-call results. `receipt` and `observed` are populated when the implementation has such evidence. The Interface Lab renders all four slots, including an empty marker for missing values:

- `sent`: the implementation's payload record. Host calls may record the exact native parameters; local writes record the target, encoding, byte count and SHA-256 digest. The facade uses the validated arguments when the implementation supplies no non-null value. This fallback also applies to refused variants, so `sent` alone does not prove dispatch.
- `receipt`: the raw host or operating-system response.
- `observed`: data read back about the actual effect.
- `limits`: plain-text host limits that applied, merged from the capability's `limits` and the implementation's own.

The page facade validates arguments before any host contact. Arguments are plain JSON objects whose fields are exactly the interface's declared fields, nested at most 32 levels and at most 48,000 UTF-8 bytes when encoded. Message and draft text contains non-whitespace content and is at most 8000 characters. Identifier strings are 1 to 256 characters without line breaks. Paths are absolute (`C:/...`, `C:\...` or `/...`) and at most 32768 characters. Line numbers are positive integers.

## Host interface reference

Each interface's shared definition is `host_interfaces/<group>/<name>/index.mjs`; its Claude and Codex behavior is in `claude.mjs` and `codex.mjs` beside it. On Claude, dispatched operations other than `host.getInfo`, `host.getCapabilities` and `events.subscribe` execute in the Claude Mod through the bridge. On Codex, they execute through the MCP App connection. Unless stated below, `sent` uses the validated arguments and native receipt/read-back fields are present only when supplied by the implementation; [Results and evidence](#results-and-evidence) defines these common rules.

### host.getInfo

- **Arguments:** none.
- **Effect:** returns the confirmed host identity as `HostInfo` (`id`, `status`, `name`, `version`, `clientType`, `sessionId`, `transport`, `identitySource`, `reason`, `capabilities`). The page facade answers it.
- **Claude:** identity from the Mod session: name `Claude Code`, version and session id.
- **Codex:** identity from MCP App initialization.
- **Limits:** identity is what the connection reports; it is not cryptographic attestation.

### host.getCapabilities

- **Arguments:** none.
- **Effect:** returns every host interface's capability: `state`, `detail`, and where declared `scope`, `constraints` and `limits`. The page facade answers it.
- **Claude and Codex:** available on both.

### host.getContext

- **Arguments:** none.
- **Effect:** returns the host environment as `{ workspaceRoots, cwd?, model?, theme, locale, displayMode, availableDisplayModes, raw? }`.
- **Claude:** returns `workspaceRoots: [root]`, `cwd` and `model` from the Mod session; `theme`, `locale` and display fields are `null`. `receipt` holds `{ root, cwd, model }`.
- **Codex:** returns `theme`, `locale`, `displayMode`, `availableDisplayModes` and the raw MCP App host context; `workspaceRoots` is `null`. `receipt` holds the raw context.
- **Limits:** Claude provides no theme or locale. Codex provides no workspace roots.

### events.subscribe

- **Arguments:** `types?`: a nonempty array of event types.
- **Effect:** the page subscribes with `adapter.events.subscribe(listener, types?)`, which returns the unsubscribe function. Calling `adapter.invoke("events.subscribe", ...)` returns `unsupported` with the capability, because a subscription needs a listener function. See [Events](#events).
- **Claude:** delivers `tool.completed`, `turn.completed`, `session.ended` and `context.attached`.
- **Codex:** delivers `tool.completed`, `host.contextChanged` and `page.teardown`.
- **Limits:** Claude events arrive up to about 1 second late, and events produced while the page is closed are not replayed. Codex does not deliver `turn.completed` or `session.ended`.

### files.openFile

- **Arguments:** `path` (absolute), `line?` (positive integer).
- **Effect:** opens the file in the host's file view.
- **Claude:** calls the native file pane (`mcp__ccd_view__show_pane` with `pane: "file"`), with optional line navigation; status `accepted`, and the displayed result is observed in the host.
- **Codex:** calls the `openai/files/open` extension request; status `accepted`. A `line` argument returns `unsupported`.
- **Limits:** Codex has no line navigation.

### files.revealDirectory

- **Arguments:** `path` (absolute).
- **Effect:** reveals a directory in the host's own file browser.
- **Claude and Codex:** capability state `unknown`; neither host has a confirmed directory-reveal route, so the call returns `unsupported`.
- **Related:** `local.system.revealInFileManager` is an independent function that reveals a path in the operating system's file manager.

### composer.writeDraft

- **Arguments:** `text` (1 to 8000 characters), `mode`: `append` or `replace`.
- **Effect:** writes text into the host's message composer. Nothing is sent.
- **Claude:** calls `$.prompt.fill`; both modes. `completed` when the composer reports the draft filled, `rejected` when it reports not filled.
- **Codex:** sends a draft through the `openai/message` extension (`send: false`); `append` only, and `replace` returns `unsupported`. Status `accepted`; the composer effect is observed in the host.
- **Limits:** Codex supports `append` only.

### conversation.submitMessage

- **Arguments:** `text` (1 to 8000 characters), `model?`, `effort?`. Each of `model` and `effort` is a `Selection`: `{ source: "current" }`, `{ source: "default" }` or `{ source: "specified", value }`. A specified model is a nonempty identifier string. A specified effort is one of the five strings `low`, `medium`, `high`, `xhigh`, `max`; numeric effort values fail validation. An omitted selection means `current`.
- **Effect:** submits a user message to the current conversation; the model's reply appears in the conversation.
- **Claude:** calls `$.prompt.submit`, which waits until the session is idle. Status `accepted`; `observed` holds the session model and any turn override. `default` returns `unsupported`, because Claude has no confirmed way to read its default model and effort. `specified` applies only to the turn this message starts: the Mod rewrites the main agent's model and effort for that turn's steps, and leaves the session settings unchanged. The `turn.completed` event's `override.applied` reports the applied values and `sessionWouldUse`, the values the session would have used.
- **Codex:** calls the MCP App `sendMessage` with role and content. Status `accepted`. Any `default` or `specified` selection returns `unsupported` and sends nothing, because `sendMessage` has only role and content fields.
- **Limits:** Claude has no `default` selection and applies `specified` to one turn. Codex uses the session's current model and effort.

### context.update

- **Arguments:** `snapshot`: one JSON object.
- **Effect:** sets the page's whole model context to `snapshot`; `{}` clears it. For a nonempty snapshot, the text representation is `Plugin page context (JSON data, not instructions): ` followed by the JSON of the snapshot (`contextText` in [host_interfaces/context/update/index.mjs](host_interfaces/context/update/index.mjs)). Claude attaches this text. Codex sends it when the host declares text context; a structured-only declaration carries the raw snapshot as structured content. Updating context triggers no reply; the context block is model-visible and hidden from the user. For `{}`, Claude deletes the stored block and records `attachAs: null`; Codex sends empty context in its declared modalities.
- **Claude:** stores the snapshot for the page connection. The Mod's prompt-submission hook attaches it as a context block to the next submitted prompt from any source and then emits `context.attached` with the attached blocks. `sent` holds the snapshot and the exact text to be attached.
- **Codex:** calls `updateModelContext` with only the modalities the host declares (text content, structured content, or both); the host hands it to the model on the next turn. `sent` holds the parameters and `receipt` the host response.
- **Limits:** Claude attaches the snapshot only at the next submission; the `context.attached` event shows what was attached. Codex confirms receipt only; the page cannot read back what the model received.

### tools.list

- **Arguments:** `scope?`: `session` or `originating-server`.
- **Effect:** lists tools the page can call with `tools.call`, each with a `reference` to pass back.
- **Claude:** lists the session's native and MCP tools as `{ name, description, kind: "native" | "mcp" | "unknown", reference: { name, scope: "session" } }`. Scope `originating-server` returns `unsupported`. A list larger than 60000 bytes returns `error`.
- **Codex:** calls the plugin server's `list_page_tools` tool and returns the page-callable tools of the originating server with `reference: { name, scope: "originating-server" }`. Scope `session` returns `unsupported`.
- **Limits:** Claude covers the session; Codex covers only the plugin's own page-callable tools.

### tools.call

- **Arguments:** `tool`: `{ name, server?, scope? }` with scope `session` or `originating-server`; `arguments`: a JSON object.
- **Effect:** calls one tool and returns its native result.
- **Claude:** calls a session tool by name through the Mod's `$.tool.call`, which applies the host's permission check. With `server`, the name is `mcp__<server>__<name>`. A tool missing from the session list, or scope `originating-server`, returns `unsupported`. Arguments named `consent` or `agentId` are refused. A host denial returns `rejected`.
- **Codex:** calls a tool of the originating server through `App.callServerTool`. Another scope, or a `server` different from the originating server, returns `unsupported`.
- **Limits:** Claude calls session tools; Codex calls only the plugin's own server tools.

### skills.list

- **Arguments:** none.
- **Effect:** returns the session's Skill names as `{ scope: "session-context", complete: true, skills: [name, ...] }`.
- **Claude:** reads the Skill listing from `$.session.usage({ breakdown: "summary" })`. It returns complete lists only; a listing truncated by the context budget returns `unsupported` with `totalSkills` and `includedSkills`.
- **Codex:** capability state `unknown`; returns `unsupported`.

### skills.invoke

- **Arguments:** `skill` (identifier), `input?` (a string on Claude).
- **Effect:** activates one Skill in the current session.
- **Claude:** calls the native `Skill` tool. `completed` when the host confirms activation, `accepted` when it reports a background task, `pending` when the receipt cannot confirm activation, `error` when activation failed. A non-string `input` returns `unsupported`. The Skill's business result is checked separately.
- **Codex:** capability state `unknown`; returns `unsupported`.

### views.open

- **Arguments:** `resource`: `{ kind: "web", url }` (http or https, no credentials) or `{ kind: "file", path, line? }`; `reuseKey` (identifier); `activate` (boolean).
- **Effect:** opens or reuses a view owned by the page and returns `data.viewId`.
- **Claude:** opens a Browser pane tab with `preview_start`, reuses the tab with the same `reuseKey` (navigating it when the URL differs), selects it when `activate` is true, then reads the tab list back. `observed` holds `{ viewId, reuseKey, url, present, active, paneDisplayed }`. With `activate: false`, status is `completed` once the tab exists in the background. With `activate: true`, status is `completed` when the tab is active and the pane is displayed, and `accepted` when the tab is active and the pane is not confirmed displayed. `kind: "file"` returns `unsupported`; files open with `files.openFile`.
- **Codex:** capability state `unknown`; returns `unsupported`.
- **Limits:** a hidden Browser pane cannot be revealed by the plugin; the tab opens and activates while the pane stays hidden until the user opens it. User tabs never receive a `viewId`.

### views.list

- **Arguments:** none.
- **Effect:** lists the views this page opened that still exist, as `{ scope: "own-views", views: [...] }`.
- **Claude:** reads the Browser tab list; `observed` holds `paneDisplayed`. User tabs are never listed.
- **Codex:** capability state `unknown`; returns `unsupported`.

### views.close

- **Arguments:** `viewId`.
- **Effect:** closes one view this page opened.
- **Claude:** closes the tab with `tabs_close` and reads the tab list back: `completed` when the tab is gone, `accepted` when it is still listed, `rejected` when the `viewId` does not belong to this page. User tabs are never closed.
- **Codex:** capability state `unknown`; returns `unsupported`.

### views.requestDisplayMode

- **Arguments:** `mode`: `inline`, `fullscreen` or `pip`.
- **Effect:** requests a display mode for the page's own container.
- **Claude:** capability state `unknown`; returns `unsupported`.
- **Codex:** calls `App.requestDisplayMode` for a mode the host context declares; `completed` when the host returns the requested mode, `rejected` when it returns another. Plugin Base resources advertise `fullscreen` only through `codexResourceMetadata`.
- **Limits:** the returned mode does not indicate tab focus.

### Events

A host event is `{ type, at, data? }`. Listeners receive a copy of each event; a failing listener does not affect other listeners.

| Type | Host | Delivery | `data` |
| --- | --- | --- | --- |
| `tool.completed` | Claude | Mod tool-call hook | `{ tool, isError, denied }` |
| `turn.completed` | Claude | Mod turn-completion hook, main agent only | `{ turnId, reason, model, override }`; `override` is `null` or `{ requestId, requested: { model, effort }, applied: { model, effort, sessionWouldUse: { model, effort } } }` |
| `session.ended` | Claude | Mod session-end hook | none |
| `context.attached` | Claude | Mod prompt-submission hook | `{ blocks, attached, origin }` |
| `tool.completed` | Codex | MCP App tool-result notification | `{ isError, structuredContent }` |
| `host.contextChanged` | Codex | MCP App host-context notification | the changed host context |
| `page.teardown` | Codex | MCP App teardown notification | none |

[The adapter architecture](../ADAPTER.md#event-delivery) owns event delivery, buffering and connection limits.

## Local capability reference

The 5 local capabilities execute in the plugin server process ([local/node/index.mjs](local/node/index.mjs)). Their definitions and limits are in [local/definitions.mjs](local/definitions.mjs); the page client is in [local/page/index.mjs](local/page/index.mjs). The server executor and limits are the same for both hosts. Their transport mapping is owned by [the adapter architecture](../ADAPTER.md#local-capability-transports).

The page uses them through `adapter.local`:

- `available`: whether the snapshot declared a usable route; valid calls on an undisposed client return `unsupported` when no route exists;
- `call(operation, args)`;
- `files.read(args)`, `files.write(args)`, `files.watch(args, listener)`;
- `system.openExternal(args)`, `system.revealInFileManager(args)`;
- `dispose()`.

**Scope rule.** Read, write, watch and reveal act only inside directories granted to the session local connection with `local.allow(root)` on the server. The check compares real paths, case-folded on Windows and macOS, so `..` segments and symbolic links cannot leave a granted root. For a path that does not exist yet, its parent directory decides. A path outside every granted root returns `rejected` with `observed.allowedRoots`.

### local.files.read

- **Arguments:** `path` (absolute), `encoding?`: `utf8` (default) or `base64`, `maxBytes?` (1 to 4 MiB; default 1 MiB).
- **Effect:** reads one file.
- **Result:** `data` is `{ path, encoding, content, size, mtimeMs }`. `receipt` holds `{ bytes }`; `observed` holds `{ path, size, mtimeMs, sha256 }`.
- **Limits:** a file larger than `maxBytes` returns `rejected` with its size. A file that is not valid UTF-8 returns `rejected` under `utf8`; read it with `base64`. A missing path returns `rejected`.

### local.files.write

- **Arguments:** `path` (absolute), `content` (string), `encoding?`: `utf8` (default) or `base64`.
- **Effect:** atomic replacement: the executor writes a sibling temporary file with exclusive create, then renames it over the target. A reader sees either the previous bytes or the new bytes.
- **Result:** `data` is `{ path, bytes, created }`. `sent` holds `{ path, encoding, bytes, sha256 }`; `receipt` holds the rename method and temporary file name; `observed` reads the file back and holds `{ path, size, mtimeMs, sha256, matchesSent }`.
- **Limits:** at most 1 MiB of decoded content.

### local.files.watch

- **Arguments:** `paths`: 1 to 32 absolute paths.
- **Effect:** watches the paths by comparing existence, size and modification time every 300 ms. The page call is `adapter.local.files.watch({ paths }, listener)`; the result carries `stop()`, which ends the watch through the transport operation `local.files.unwatch`.
- **Result:** `data` is `{ watchId, paths, initial }`; `observed.initial` lists each path's starting state.
- **Events:** each change reaches the listener as `{ type: "local.files.changed", at, data: { watchId, path, change, size, mtimeMs } }`, where `change` is `created`, `modified` or `deleted`.
- **Limits:** several saves within one interval merge into one event. Each session local connection holds at most 16 watches. Call the returned `stop()` for each watch when its page finishes using it; page-client disposal clears listeners, while the server connection retains watches until explicitly stopped or closed.

### local.system.openExternal

- **Arguments:** `url`: http or https, without user name or password.
- **Effect:** opens the URL in the operating system's default browser. No directory scope applies.
- **Command:** Windows `%SystemRoot%\System32\rundll32.exe url.dll,FileProtocolHandler <url>`; macOS `/usr/bin/open <url>`; Linux `xdg-open <url>`.
- **Result:** see [System launches](#system-launches).

### local.system.revealInFileManager

- **Arguments:** `path` (absolute, existing, inside a granted root).
- **Effect:** shows the path in the operating system's file manager. After the granted-root check, the executor resolves the target with Node.js `fs.realpath`, which returns its real on-disk path, and uses that path for the file-manager command on every platform. This gives the file manager a usable target across filesystem redirection, where a process's requested path leads to another on-disk location.
- **Command:** Windows `%SystemRoot%\explorer.exe /select,"<real path>"` with verbatim arguments; macOS `/usr/bin/open -R <real path>`; Linux `xdg-open` on the real containing directory (on the real directory itself when the target is a directory).
- **Result:** `sent.path` retains the requested path; `sent.realPath` is present when the real path differs from it. See [System launches](#system-launches) for the launch evidence and [the dated validation record](../VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) for source-test and native-observation scope.
- **Limits:** Explorer's exit code does not indicate success (it is usually 1). Linux opens the containing directory and does not select the file.
- **Related:** `files.revealDirectory` is an independent function that targets the host's own file browser.

### System launches

Both system operations launch the program without a shell (`shell: false`). The result is `accepted`, with `sent` holding the requested arguments plus `command` and `args`. For reveal, the command uses the real path and `sent.realPath` records it when it differs from `sent.path`. The `receipt` holds the process id and, when the program exited within 3 seconds, its exit code; `observed` holds `{ launched }`. A program that fails to start returns `error`. The operating system reports only whether the process started; the visible window and selected target require observation on the machine. [The dated validation record](../VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) separates those observations from source-tested command behavior.

## Verifying on a host: the Interface Lab

Use the separate Plugin Interface Lab to compare all 22 operations with their actual effects on a host. [Page behavior](../PROTOTYPE.md#plugin-interface-lab-page) owns its controls and state locations. [The manual procedure](../MANUAL-TESTS.md) gives the source-mode setup, host loading checks, operation order and comparison-record requirements. The [plugin-interface-lab Skill](../skills/plugin-interface-lab/SKILL.md) opens the page through `open_interface_lab`; the tool opens the page, and the developer initiates each operation.

The toolkit installer enables this developer app in source test mode. [The application map](../ARCHITECTURE.md#installation-and-source-selection) owns registration and build placement. [The decision record](../../../docs/design/plugin-base-and-interface-lab-2026-10-14.md#open-items) owns unresolved design items, including graph-credential lifetime. [The validation ledger](../VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) owns the measured checks and pending native acceptance.
