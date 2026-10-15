# Plugin Base and Interface Lab

Date: 2026-10-14. Decision: the toolkit's business-independent plugin foundation becomes one closed module, the Plugin Base, at `src/graph_skill_toolkit/plugin_base/`. It owns 17 host interfaces, 5 local capabilities, page presentation in both hosts and an evidence record on every call, and it exposes three entry files plus one usage document. The Graph Skill canvas and a dedicated Interface Lab are its two business consumers. Native acceptance on both hosts is pending.

## Goal

The graph-skill toolkit ships a Graph Skill canvas plugin into two desktop agent hosts, Claude Code Desktop and Codex Desktop. This decision defines a reusable Plugin Base: one closed module that every plugin of the same kind builds on. A plugin of this kind is a page shown inside a desktop coding-agent host that interacts with the current conversation.

The Graph Skill canvas is one business consumer of the Plugin Base. The Interface Lab is a second consumer: a dedicated developer page and Skill that exercises every Plugin Base interface on both hosts and shows explicit, comparable results.

The user rules goal, principle and effect and owns native observation; the coding agent owns every implementation decision recorded here.

## Terms

- **Host**: the desktop application that runs the agent session and displays the plugin page. The two hosts are Claude Code Desktop and Codex Desktop.
- **Plugin Base**: the closed module at `src/graph_skill_toolkit/plugin_base/` that owns every business-independent plugin foundation and exposes only its entry files and usage documentation.
- **Interface Lab**: the developer page, MCP server entry and Skill that call every Plugin Base operation on a host and record the results.
- **MCP** (Model Context Protocol): the protocol a host uses to talk to the plugin's server process, for tools and resources.
- **MCP App**: the Model Context Protocol Apps standard that Codex uses to embed a plugin page in the conversation and let the page talk to the host. The toolkit uses its SDK `@modelcontextprotocol/ext-apps` version 2.0.3, installed in `src/graph_skill_toolkit/node_modules`.
- **Claude Mod**: JavaScript hook code that runs inside a Claude Code session as part of a Claude plugin. It reaches host APIs through a `$` handle and registers hooks with `on(event, ...)`.
- **Browser pane**: the Claude Desktop side pane that shows web pages. Claude shows the plugin page there through a loopback HTTP preview, meaning an HTTP page served on the local machine's own network address.
- **Host interface**: an operation only the host can perform for the page, for example writing the composer draft, submitting a message, calling a host tool or opening a host view.
- **Local capability**: an operation the plugin performs on the local machine without the host: reading or writing a file, watching files, opening a URL in the system browser, or revealing a path in the system file manager.
- **Evidence**: the structured record every Plugin Base call returns besides its status. It holds what was sent, what the host returned, what was observed about the actual effect, and which host limits applied.
- **viewId**: the identifier `views.open` returns for a view that the calling plugin connection owns; the plugin's later view operations name the view by this identifier.
- **Effort**: the reasoning-effort setting a model request runs with. Claude Code declares it as `low`, `medium`, `high`, `xhigh`, `max` or a number.
- **Composer**: the host's message input box where the user types the next message.
- **Skill**: a host instruction asset with a `SKILL.md` that the host can activate in a session.

## Sources: user rulings

Each ruling is quoted verbatim with an English gloss.

1. 2026-10-12, recorded in the scope record `evidence/native-launch-20261012/interface-scope-correction.md` (lines 11-12):
   - 「“任何外部编辑器保存文件，都立即自动弹出”不需要实现这个功能」 — "Automatic opening whenever any external editor saves a file does not need to be implemented."
   - 「“或系统文件管理器打开目录”，没有这个要求，只要求宿主的文件管理器打开浏览器，定位到目录」 — "There is no requirement for the system file manager to open the directory; the requirement is that the host's own file browser opens and locates the directory."
   This ruling establishes directory reveal inside the host's own file browser as a host interface.
2. 2026-10-14: 「“而系统资源管理器已被你排除在要求之外”，加回来，但这是另外独立的接口功能。」 — "Add the system file manager back into the requirements, as a separate, independent interface function." Revealing a path in the operating-system file manager is required as its own function.
3. 2026-10-14: 「提交消息需要同时提交执行消息的模型和effort配置，可以指定、默认或者用当前session的配置。」 — "Message submission must carry the model and effort configuration that execute the message: specified, default, or the current session's configuration."
4. 2026-10-14: 「“设置上下文（context.set）和移除上下文（context.remove）”的应用场景是什么？……考虑必要性，是否去掉。」 — "What is the scenario for set context (context.set) and remove context (context.remove)? ... Consider whether they are necessary and whether to remove them." The coding agent's decision is one `context.update` operation; its scenario and necessity are stated in the host interface catalog below.
5. 2026-10-14: 「读写文件、监听本地文件和打开外部浏览器或系统资源管理器作为插件通用功能，不属于插件与宿主接口。这些与业务无关的插件开发底座能力需要成为一个闭包模块，放在一个模块文件路径里，只向外部暴露接口和接口使用说明。」 — "Reading and writing files, watching local files, and opening the external browser or the system file manager are general plugin functions and belong outside the plugin-host interfaces. These business-independent plugin foundation capabilities must form one closed module at one module path that exposes only its interfaces and their usage documentation."
6. 2026-10-14: 「我说的插件底座包括Claude和codex的接口」 — "The plugin base I mean includes the Claude and Codex interfaces."
7. 2026-10-14: 「做一个专用的接口测试页面和skill，不要和show graph混在一起」 — "Build a dedicated interface test page and Skill; keep it separate from show graph."
8. 2026-10-14: 「每一个接口测试的效果都要有显式的结果做对照，测试页面要给出文字详细提示，比如提交消息codex无法指定模型字段，上下文接口悄悄发了什么上下文，把发送的上下文结果挖出来给开发者看到」 — "Every interface test's effect needs an explicit result to compare against. The test page must give detailed textual guidance, for example that Codex message submission cannot specify the model field, and what context the context interface silently sent; dig out the sent context and show it to the developer."
9. Standing requirements from 2026-10-12 and 2026-10-13, recorded in `evidence/prime-interface-20261013/brief.txt`: one shared HTML page serves both hosts through a Codex adapter and a Claude adapter; writing a draft fills the composer without sending; a direct tool call is distinct from sending a message; an interface that cannot be connected states its reason; a host interface is implemented through the host's own route, without an agent-delegated or operating-system-window substitute.
10. Standing rule of 2026-10-14: the canvas is the single owner of Graph Skill presentation ([`canvas-single-presentation-owner-2026-10-14.md`](canvas-single-presentation-owner-2026-10-14.md)).

## Current facts

Verified on 2026-10-14 on branch `claude/toolkit-host-interfaces`, created from commit `a4e8cd50`. At that commit, after `npm ci` and `npm run build`, `npm test` passes 188 of 188 tests. Paths are relative to [`src/graph_skill_toolkit/`](../../src/graph_skill_toolkit/) unless absolute.

### Host operation code

1. The host catalog [`ports/host/catalog.mjs`](../../src/graph_skill_toolkit/ports/host/catalog.mjs) lists 15 operations (lines 1-19): `files.revealDirectory`, `files.openFile`, `composer.writeDraft`, `conversation.submitMessage`, `context.set`, `context.remove`, `tools.list`, `tools.call`, `views.open`, `views.list`, `views.activate`, `views.close`, `views.requestDisplayMode`, `skills.list` and `skills.invoke`. Each operation has a directory `host_interfaces/<group>/<operation>/` holding `index.mjs` (shared definition), `codex.mjs` (Codex mapping) and `claude.mjs` (Claude mapping).
2. The page facade [`adapters/facade/index.mjs`](../../src/graph_skill_toolkit/adapters/facade/index.mjs) line 140 defines `host.getInfo` and `host.getCapabilities` outside the catalog. The factory is `adapters/factory/index.mjs`. Codex uses `adapters/codex/{connection,driver}/`. Claude uses an HTTP connection and driver in `adapters/claude/{connection,driver}/`, a loopback bridge in `adapters/claude/bridge/server.mjs`, and Claude Mod hooks, lifecycle and operations in `adapters/claude/mod/`.
3. The interface laboratory is embedded in the graph canvas page: [`ui/workbench/index.tsx`](../../src/graph_skill_toolkit/ui/workbench/index.tsx) imports `InterfaceLab` (line 10) from `ui/interface_lab/index.tsx` and renders it (line 104). Its argument samples come from `application/graph/interface_samples/index.mjs`.
4. One MCP server, [`server/main.mjs`](../../src/graph_skill_toolkit/server/main.mjs), registers `show_graph`, `inspect_graph`, `watch_graph`, `list_canvas_tools` (line 133) and the canvas resource. Codex `tools.list` calls the canvas-specific tool `list_canvas_tools` ([`host_interfaces/tools/list/codex.mjs`](../../src/graph_skill_toolkit/host_interfaces/tools/list/codex.mjs) line 5), which ties a generic host interface to one business server.

### Context routes

5. Claude `context.set` ([`host_interfaces/context/set/claude.mjs`](../../src/graph_skill_toolkit/host_interfaces/context/set/claude.mjs) lines 1-7) stores the value in the page connection's Mod state. Claude `conversation.submitMessage` ([`host_interfaces/conversation/submit_message/claude.mjs`](../../src/graph_skill_toolkit/host_interfaces/conversation/submit_message/claude.mjs) lines 3-6) appends that stored value to the message as visible text and submits it through `$.prompt.submit({ text })`. The Mod hooks in [`adapters/claude/mod/hooks/register.js`](../../src/graph_skill_toolkit/adapters/claude/mod/hooks/register.js) register `session.start` (line 9), `session.end` (line 15), `command.run` and `tool.call`; no `prompt.submit` hook is registered. The stored context therefore reaches the model only when the same page submits a message, as visible text.
6. Codex `context.set` calls `app.updateModelContext` with the page's full snapshot under `structuredContent.toolkitContext` ([`adapters/codex/driver/shared.mjs`](../../src/graph_skill_toolkit/adapters/codex/driver/shared.mjs) `writeContext`, lines 12-20). The Claude and Codex routes of the current `context.set` have different effects.

### MCP Apps SDK

7. Each `ui/update-model-context` request overwrites the previous context stored by the view (`node_modules/@modelcontextprotocol/ext-apps/dist/src/app-bridge.d.ts` lines 627-628). `updateModelContext` makes the context available to the model in future turns without triggering an immediate model response; the host typically sends it with the next user message, from the user or from `sendMessage`, and only the last update is sent (`dist/src/app.d.ts` lines 892-899).
8. `sendMessage` takes `McpUiMessageRequest` parameters: a role, content blocks and `_meta` (`app.d.ts` lines 820-867). The parameters have no model field and no effort field.
9. `openLink` asks the host to open an external URL in the default browser, and the host may deny it (`app.d.ts` lines 962-976). `getHostContext` (line 348), `ontoolresult` (line 447), `onhostcontextchanged` (line 511) and `onteardown` (line 543) supply host context, tool results, host context changes and teardown notice to the page.

### Claude Mod declarations

10. The Claude Mod type declarations are a saved snapshot written by early-access Claude Code 2.1.277: `evidence/native-launch-20261012/claude-code-reference.d.ts`. In it:
    - `$.prompt.submit` takes `PromptSubmitArgs` (line 7192, used at line 3907), which omits `origin`, `turnId`, `wait` and `context` from `PromptSubmitInput` (lines 7217-7262). The caller supplies `text` and `attachments` only.
    - A `prompt.submit` hook may attach `context` blocks that the model reads and the user never sees (lines 7226-7235).
    - The `turn.step` hook fires before each model request of a turn, main or subagent, and may rewrite `model` and `effort` for that request while the turn, index and message count stay pinned (lines 3658-3666; `TurnStepInput` lines 10672-10700, where `effort` is the session's setting or the model's default).
    - The `turn.complete` hook fires when a model turn ends (lines 3668-3675).
    These declarations describe the 2.1.277 type contract and require re-verification against the installed host version.
11. `ADAPTER.md` line 9 and `ARCHITECTURE.md` line 106 link to `evidence/native-launch-20261012/`. This branch's checkout does not contain that directory; facts 10 and ruling 1 were read from the copy held in the local toolkit release 0.3.2 worktree of this repository.

### Claude Desktop observations

12. Tool descriptions observed in a live Claude Desktop session on 2026-10-14: `mcp__ccd_view__show_pane` with pane `file` opens one file, with an optional line, in the Files pane and accepts files only; `mcp__ccd_host__reveal_path` shows a file or folder in the system file manager (File Explorer or Finder) after a user approval card on Windows. No Claude Desktop tool locates a directory inside the host's own file browser.
13. Claude Desktop 2.37337.1.0 reveals a hidden Browser pane only through `preview_start` opening a local file. [`VALIDATION.md`](../../src/graph_skill_toolkit/VALIDATION.md) lines 412-415 record the same finding for the earlier version.

## Decisions

### 1. Plugin Base module boundary

- **Path.** The Plugin Base lives at `src/graph_skill_toolkit/plugin_base/`.
- **Contents.** It contains every business-independent plugin foundation:
  - the host interface catalog and contracts;
  - the Codex and Claude implementations of every host interface;
  - host connection, identity and capability detection;
  - page presentation in each host: the Codex MCP App resource and widget session, and the Claude loopback HTTP page, authenticated bridge, preview configuration and Browser pane guidance;
  - the Claude Mod execution side;
  - the local HTTP listener;
  - the local capabilities.
- **Entry files.** It exposes exactly three entry files, one per runtime. The three runtimes cannot share modules: a browser page cannot import Node file APIs, and the Claude Mod engine accepts `$` only as a plain argument in call position.
  - `plugin_base/page/index.mjs` is the browser side. It connects to the host, calls host interfaces, receives host events, and calls local capabilities through the plugin's own backend.
  - `plugin_base/server/index.mjs` is the Node side. It creates the plugin's MCP server with page presentation for both hosts, registers business tools, and serves local capabilities to the page.
  - `plugin_base/claude_mod/index.js` is the Claude Mod side. It registers the base's hooks so that the Mod executes Claude host interfaces for every page bridge of every plugin built on the base.
- **Usage document.** `plugin_base/README.md` documents every interface: its arguments, effect, per-host support and limits, and evidence fields. It also explains how to build a plugin on the base.
- **Closure rule.** Code outside `plugin_base/` imports only the three entry files. Code inside `plugin_base/` imports only its own files, third-party packages and Node built-ins. An automated test enforces both directions.
- **Rationale.** Rulings 5 and 6 require one closed module that holds both the local capabilities and the Claude and Codex host interfaces. One module gives each capability one owner. Business plugins reuse the base through its entries and documentation, so the base's internals can change without touching them.

### 2. Host interface catalog

The catalog holds 17 operations in six groups.

**Identity and environment**

1. `host.getInfo` returns the current host identity.
2. `host.getCapabilities` returns each operation's availability with its scope and constraints.
3. `host.getContext` returns the workspace roots, theme, locale and available display modes. Codex reads `App.getHostContext()`. Claude reads Mod session facts, starting with `$.session.root()`, plus further facts identified during implementation. Every plugin needs this operation to follow the host theme and locate the project.

**Events, from host to page**

4. `events.subscribe` delivers host notifications to the page: a tool call completed, a turn completed, the session ended or the page is being torn down, and the host context (theme or display mode) changed. Codex sources are the MCP App notifications `ontoolresult`, `onhostcontextchanged` and `onteardown`. Claude sources are the Mod hooks `turn.complete`, `session.end` and `tool.call` results, relayed through the bridge. Rationale: a message submission confirms only that the host received the message. Knowing that the agent finished, or that a file-changing tool ran, requires a notification from the host. Every other operation runs from page to host, and this operation supplies the host-to-page direction.

**Files in the host**

5. `files.openFile` opens a file, with an optional line, in the host's own file view.
6. `files.revealDirectory` locates a directory in the host's own file browser. Its status on both hosts is `unknown`, and Claude Desktop offers no tool for it (current fact 12). The operation stays in the catalog because ruling 1 requires it, and it reports the reason it cannot connect.

**Composer and conversation**

7. `composer.writeDraft` fills the composer without sending.
8. `conversation.submitMessage` submits one message. Its arguments include `model` and `effort`, each one of:
   - `{ source: "current" }`, the current session's setting, which applies when the argument is omitted;
   - `{ source: "default" }`, the host's default for a new session;
   - `{ source: "specified", value }`, an explicit value.

   Each host's capability declaration lists the sources it supports.
   - Claude route: the base submits through `$.prompt.submit`, then rewrites `model` and `effort` in the `turn.step` hook for the requests of the turn that this submission started. Session settings stay unchanged. Correlating that turn and reading the host default are open items.
   - Codex route: MCP App `sendMessage` carries no model or effort field (current fact 8), so Codex declares only the `current` source. A `specified` or `default` request returns `unsupported` with that explanation.
9. `context.update` replaces the page's whole context snapshot; an empty snapshot clears it. The host gives the snapshot to the model with the next turn, whoever sends that turn, without triggering a turn and without showing it to the user.
   - Scenario: the user selects a node on a canvas, then types "change this node's output to JSON"; the model knows which node "this" means.
   - Necessity: a message submission triggers a reply on every selection; a draft is visible and the user must keep it; a plugin tool requires the model to know to call it. Context update is the only route by which page state reaches the next turn silently.
   - One operation covers setting and clearing because the MCP App standard defines whole-snapshot overwrite (current fact 7).
   - Codex route: `updateModelContext`.
   - Claude route: a `prompt.submit` hook attaches the snapshots of this session's pages as context blocks to the next prompt, from any sender. The hook attaches only pages of the same session.

**Tools and Skills**

10. `tools.list` lists the tools callable in the declared scope. On Codex it lists the originating plugin server's page-callable tools through a generic server tool that `plugin_base/server` registers under a name independent of any business.
11. `tools.call` calls a tool directly and returns its result. It is distinct from asking the agent to call the tool.
12. `skills.list` lists the host Skill names available in the current session.
13. `skills.invoke` activates a Skill natively. The Skill's business result is a separate outcome.

**Views**

14. `views.open` opens a web or file view and returns a `viewId` owned by this plugin connection. With `activate: true`, the view ends visible and in front. Calling `views.open` with the same `reuseKey` and `activate: true` activates an existing own view; the catalog has no separate activate operation.
15. `views.list` lists the plugin's own views.
16. `views.close` closes one of the plugin's own views.
17. `views.requestDisplayMode` requests `inline`, `fullscreen` or `pip` for the plugin's own container.

Views owned by others, such as the user's own browser tabs, are outside the Plugin Base.

### 3. Local capabilities

The Plugin Base provides five local capabilities in the namespace `local.*`:

- `local.files.read` reads a file.
- `local.files.write` writes a file by atomic replacement.
- `local.files.watch` subscribes to changes of files.
- `local.system.openExternal` opens a URL in the system default browser.
- `local.system.revealInFileManager` selects a path in File Explorer or Finder; on Linux it opens the containing directory.

They execute in the plugin's own Node process, and the page reaches them through the plugin's authenticated backend. Process launch is shell-free with explicit arguments. Local capabilities and host interfaces are separate groups: `files.revealDirectory` acts in the host's own file browser, and `local.system.revealInFileManager` acts in the operating-system file manager, as two independent functions (ruling 2). The graph code that reads and watches skill files uses these capabilities.

### 4. Evidence on every call

Every host interface call and local capability call returns `status`, `message` and `evidence`. The evidence holds four fields:

- `sent`: the exact payload delivered to the host or the operating system. For `context.update` it is the full snapshot. On Claude it also includes the context blocks the `prompt.submit` hook actually attached, captured from the hook's resolved result when the next prompt enters.
- `receipt`: the raw host response.
- `observed`: data the base reads back about the actual effect, for example the active tab after `views.open`, or the model and effort the `turn.step` hook applied.
- `limits`: the host limits that applied, in plain text, for example "Codex MCP App sendMessage has no model field; the message runs with the current session model."

The status values keep these meanings:

- `accepted`: the host acknowledged the request.
- `completed`: the defined effect is established.
- `pending`: the outcome is unknown; the base never resends automatically.
- `unsupported`: the host offers no route for the request.
- `rejected`: the host or the user refused the request.
- `error`: the call failed.

### 5. Business consumers

- Business apps live under `src/graph_skill_toolkit/apps/<name>/` and import only the Plugin Base entries.
- `apps/graph_canvas/` holds the Graph Skill canvas: graph source, projection, live source, runtime compiler adapter and relay, the canvas UI, diagnostics, and the tools `show_graph`, `inspect_graph` and `watch_graph`. The canvas page holds graph presentation only and contains no interface laboratory.
- `apps/interface_lab/` holds the Interface Lab: its own MCP server entry with server name `plugin-interface-lab` and tool `open_interface_lab`, its own page, and its own Skill `skills/plugin-interface-lab/SKILL.md`. The Interface Lab is a developer tool: test mode registers it, and the installed release mode leaves it out.
- Rationale: ruling 7 requires a dedicated test page and Skill separate from `show_graph`, and ruling 10 makes the canvas the single owner of Graph Skill presentation.

### 6. Interface Lab page requirements

For each of the 17 host interfaces and 5 local capabilities, the Interface Lab page shows:

- what the operation does, in one plain sentence;
- the expected visible effect per host and where to look for it, for example "the composer shows the text; nothing is sent";
- the host's support state and its limits in detailed text, for example "Codex: model and effort cannot be specified; the message uses the current session's settings";
- editable JSON arguments with a working sample;
- after a call: the status, the exact `sent` payload, the raw `receipt`, the `observed` effect data and the `limits` that applied;
- for `context.update`: the snapshot sent and, on Claude, the context blocks the next prompt actually carried. A verification action submits a message that asks the model to repeat the context it received, so the developer compares the reply with what was sent;
- a comparison row where the developer records the observed effect against the expected effect, as matches, differs or not observed, with a note. The lab writes each record with `local.files.write` to an evidence file under the lab's state directory, so native acceptance has a durable log.

Rationale: ruling 8 requires an explicit result to compare against for every interface, detailed guidance text, and visibility of the context actually sent.

### 7. Implementation order

1. Create `plugin_base/` and relocate the existing host code into it with unchanged behavior; add the closure test.
2. Relocate the graph code into `apps/graph_canvas/`, consuming only the Plugin Base entries; take the laboratory out of the canvas page.
3. Revise the catalog to the 17 operations of decision 2: `context.update`, activation through `views.open`, `model` and `effort` on `conversation.submitMessage`, `host.getContext`, `events.subscribe`, and the evidence fields of decision 4.
4. Add the local capabilities of decision 3 and route graph file reading and watching through them.
5. Build the Interface Lab of decisions 5 and 6 with its server, page and Skill, and register it in test mode.
6. Run native acceptance on both hosts: invoke each operation once per host and record `sent`, `receipt`, `observed` and the developer's comparison.

Rationale: the boundary exists before the catalog changes, so each later step changes one owner at a time.

## Acceptance criteria

| Criterion | Evidence | Stop condition |
| --- | --- | --- |
| The Plugin Base is closed. | The closure test passes: no import from outside `plugin_base/` reaches its internals, and no import from inside `plugin_base/` reaches the rest of the toolkit. | Any import crossing the boundary. |
| The usage document is complete. | `plugin_base/README.md` documents all 17 host interfaces and 5 local capabilities with arguments, effects, per-host support, limits and evidence fields. | Any operation missing or lacking one of those items. |
| The canvas keeps its behavior. | The graph canvas page shows no interface laboratory; `show_graph`, `inspect_graph` and `watch_graph` keep their documented behavior. | A laboratory on the canvas page, or a changed tool behavior. |
| The Interface Lab is independent and complete. | `open_interface_lab` opens the lab on both hosts independently of `show_graph`, and the lab lists all 22 operations with the per-operation text of decision 6. | A missing operation or missing guidance text. |
| Every call shows its evidence. | Each Interface Lab call shows `sent`, `receipt`, `observed` and `limits`; `context.update` shows the context actually sent and, on Claude, actually attached. | Any call whose result lacks one of those fields. |
| Native acceptance is recorded (pending). | Per host and per operation: the invocation, the evidence and the developer's comparison, written to the lab's evidence file. | A missing record for any operation on either host. |

An automated test pass is source evidence only and establishes no host effect.

## Open items

Each item names the evidence that settles it.

- **Claude turn correlation and host default.** The base must correlate the turn started by a page's `prompt.submit` with that turn's `turn.step` requests, and must locate the source of the host's default model and effort. Settling evidence: a native Claude session in which a page submission with a specified model shows that model in the `turn.step` record of the same turn, and a host API or file that reports the default.
- **Claude Mod API version.** The installed host's Mod API must match the 2.1.277 declarations for `prompt.submit` context blocks, `turn.step` and `turn.complete`. Settling evidence: the installed host's type declarations or a native run of each hook.
- **Codex per-message model or effort.** Settling evidence: a Codex extension field, documented or observed, that sets a model or effort for one message.
- **Host-own-browser directory reveal.** Settling evidence: a route on either host that locates a directory in the host's own file browser, observed natively.
- **Claude Browser pane activation.** `views.open` with `activate: true` needs a host route that makes a hidden Browser pane visible beyond `preview_start` on a local file. Settling evidence: a native observation of such a route.
- **Native launch evidence in the branch.** The `evidence/native-launch-20261012/` files cited by current facts 10 and 11 and by ruling 1 must be present in this branch for its links to resolve. Settling evidence: the directory tracked in the branch with its content unchanged.

## Validation scope

This record establishes the module boundary, catalog, local capabilities, evidence fields, consumers and Interface Lab requirements as decisions. The current facts rest on source reading, SDK type declarations, a saved Claude Code 2.1.277 type snapshot and live Claude Desktop tool descriptions of 2026-10-14. No implementation, build, test run or native host observation is part of this record. No release, publication or commit is part of this decision.

## Revision log

- 2026-10-14: Created. Records the Plugin Base as one closed module with three runtime entries and a usage document, the 17-operation host interface catalog, the 5 local capabilities, the evidence record on every call, the Graph Skill canvas and Interface Lab as business consumers, the Interface Lab page requirements, the implementation order, acceptance criteria and open items.
