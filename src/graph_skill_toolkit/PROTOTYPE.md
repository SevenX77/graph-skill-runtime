# Canvas and Interface Lab page behavior

Users can inspect graph state, and developers can compare interface results with the effects observed in their desktop host.

The toolkit presents two separate pages. The **Graph Skill canvas** shows a caller-selected graph and its selected node. The **Plugin Interface Lab** is the developer page for comparing host and local operations with their actual effects. Each page has one self-contained HTML build shared by both hosts.

This document owns visible behavior and the lab's state locations. [Hostpane usage](https://github.com/SevenX77/hostpane/blob/main/README.md) owns the full reference for the 17 host interfaces and 5 local capabilities; Hostpane is the separately versioned package that provides the toolkit's host integration. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md) owns connection and host routes. [ARCHITECTURE.md](ARCHITECTURE.md) owns the application map and graph-data path. [MANUAL-TESTS.md](MANUAL-TESTS.md) owns native observation, and [VALIDATION.md](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) owns measured results.

## Terms

- **MCP (Model Context Protocol)** carries host requests to the plugin's tool server and resources back to the host.
- **MCP App** is the extension through which Codex attaches an interactive HTML page to a tool result.
- **Claude Mod** is hook code loaded inside a Claude Code session. It supplies session facts, executes host requests and guides page presentation.
- **Browser pane** is Claude Code Desktop's web-tab panel.
- **Loopback HTTP page** is a web page served by the plugin on the same computer, at `127.0.0.1`.
- **Capability** is an operation's current host declaration, including `available`, `unavailable` or `unknown`, a reason, scope and limits.
- **Evidence** is the displayed record of sent data, raw receipt, read-back observation and applicable limits.
- **Skill** is a host-discoverable `SKILL.md` instruction asset. The lab has its own `plugin-interface-lab` Skill.

## Graph Skill canvas page

The canvas uses [its HTML template](apps/graph_canvas/ui/template/canvas.html), [page entry](apps/graph_canvas/app/main.tsx) and [workbench](apps/graph_canvas/ui/workbench/index.tsx). Its layout is a full-bleed canvas with floating cards: the graph fills the window, and the header card, host chip, view controls and detail panel float above it.

**Design.** Both toolkit pages take their design from the **template core**: the shared interface design of the owner's projects, in `core/` of the UI/UX template project, read through the git submodule `vendor/ui-ux-template` at the repository root, at commit `b02291a`. The template core supplies **design tokens** (named CSS custom properties such as `var(--signal)` in `core/dist/tokens.css`, each carrying one colour, radius, shadow or timing value), base component styles (`core/styles/base.css`), scene styles such as the canvas blueprint (`core/styles/scenes.css`) and interaction behaviour (`core/behavior/ux.js`, imported by the pages as `UX`). Each page template inlines the core style files it uses; the canvas inlines `tokens.css`, `base.css` and `scenes.css`. The [build script](scripts/build/main.mjs) replaces each `/* INLINE_CSS <path> */` marker with the named file, so each page remains one self-contained HTML file. Page CSS adds layout, such as grid columns and positions, and takes every colour and shadow from design tokens. Both pages use the **theme pair** Prism (浅, light) and Aurora (深, dark). A script in the page head applies the theme before the first paint: the theme the developer last chose on that page, else the operating system's `prefers-color-scheme`. A 浅/深 segmented control (`.seg`, a row of buttons of which one is current, marked by a sliding indicator) switches the theme and remembers it per page, under the browser storage key `canvas-scheme` for the canvas and `lab-scheme` for the lab. An **overlay** is a panel drawn above the content that takes no part in the content's layout, so opening or closing it moves nothing beneath it.

**The canvas.** [The canvas component](apps/graph_canvas/ui/canvas/view.tsx) draws the graph on an infinite canvas bound with the template core's `UX.canvas`, over a dot-grid background. Dragging empty space pans the view; Ctrl or Cmd with the mouse wheel zooms it. The controls at the bottom left are zoom out (−), the current zoom percentage, zoom in (+) and 适合 (fit the whole graph). Node positions come only from the graph projection; the view fits the graph again when the graph id, a node id or a node position changes.

**Nodes and edges.** Each node is a 224 × 60 pixel card holding a kind badge, the node label and the node kind. A phase node's label is its phase id; the boundary nodes are labelled Input and Output. The badge letter names the kind and takes the kind's category token:

| Kind | Badge | Colour token |
| --- | --- | --- |
| INPUT | I | `--c1` |
| LOGIC | L | `--c2` |
| AGENT | A | `--c3` |
| SUBGRAPH | S | `--c4` |
| OUTPUT | O | `--c5` |

Edges are curves from the bottom centre of one node to the top centre of the next, ending in an arrow.

**Selection.** A click on a node selects it, and a second click on the selected node clears the selection. With the keyboard, Tab moves focus between nodes and Enter or Space selects the focused node; Esc on a node, or a click on empty canvas, clears the selection. The selected node takes the selected background and a higher shadow, with no outline ring. Its edges take its kind colour, other edges fade, and nodes unrelated to it fade while its direct neighbours stay fully readable. Selection persists across graph snapshots while the same node id exists. Selection is page state: it submits no message and changes no business files. The canvas's controls serve graph presentation and inspection; the separate Interface Lab owns operation-testing controls.

**Detail panel.** The selected node's details open in an overlay panel on the right, 280 pixels wide; below 720 pixels of width the panel is a bottom sheet. It shows the node id, its kind and the labels of its upstream and downstream nodes, with a close button. When the panel opens, the canvas view moves aside, and it returns when the panel closes; nodes never move.

**Header card.** A floating card at the top left shows:

- the graph id with a tag counting nodes and edges, for example `3 节点 · 2 连线`;
- the selected absolute Skill root, or `示例画布 · 未选择 Skill` for the rootless demonstration;
- a status line for an error or an unknown-identity reason, hidden when empty;
- the invalid-graph notice when the Skill does not compile.

Below 720 pixels of width the header card spans the window beneath the host chip.

**Host chip.** A floating chip at the top right, rendered by [host status](apps/graph_canvas/ui/host_status/index.tsx), shows a status dot, the live host name and the host software version the host reports. The dot is green when the page is connected and the host identity is confirmed, yellow while connecting or while the identity is unconfirmed, and red when the connection failed or the page runs without a host; any state other than connected is also named in words. The chip's tooltip adds the toolkit plugin version. The chip also holds the 浅/深 switch and an ⓘ toggle that reveals the host-connection data as JSON. The page refreshes host facts every 2 seconds while connected.

**Invalid graph.** The runtime compiler owns whether the selected Graph Skill is valid. When compilation fails, the [invalid-graph notice](apps/graph_canvas/ui/diagnostics/index.tsx) appears inside the header card. It reports the number of runtime problems and shows each retained diagnostic's code, message, source path, line and field path verbatim. The display is bounded to 50 diagnostics with a remaining count. The last compiled graph stays drawn and faded behind it, and a note states whether a compiled graph is available. A valid save supplies a fresh snapshot, clears the notice and redraws the graph in the same page.

**Errors and recovery.** Selection failures, an unreachable runtime or an out-of-contract reply appear on the status line. The workbench retains its last valid graph while the graph connection recovers. A standalone page with neither a host connection nor a graph connection shows the labelled demonstration graph. [ARCHITECTURE.md](ARCHITECTURE.md#save-to-render-flow-and-lifecycle) owns file observation, transport recovery and save-to-render timing.

**Behaviour hooks.** Tests and manual procedures locate the page's state through these names:

| Hook | Meaning |
| --- | --- |
| `#skill-path` | The Skill root shown in the header card. |
| `data-node` | A node card, valued with its node id. |
| `data-edge` | An edge, valued `<from>:<to>`, for example `input:process`. |
| `data-selected-node` | The detail panel's node id, present while a node is selected. |
| `data-host-info` | The host-connection JSON behind the ⓘ toggle. |
| `data-diagnostic-code` | One invalid-graph diagnostic, valued with its code. |
| Document dataset `connection` | Host connection: `connecting`, `connected`, `failed` or `standalone`. |
| Document dataset `graphConnection` | Graph connection: `connecting`, `live`, `invalid` or `failed`. |
| Document dataset `toolResult` | Latest graph payload: `received` or `invalid`. |

## Plugin Interface Lab page

The lab uses [its page entry](apps/interface_lab/app/main.tsx), [UI](apps/interface_lab/ui/index.tsx), [guide views](apps/interface_lab/ui/guide.tsx), [template](apps/interface_lab/ui/template/lab.html), [per-operation guidance](apps/interface_lab/application/guide.mjs), [quick-start data](apps/interface_lab/application/handbook.mjs), [routes](apps/interface_lab/application/route.mjs) and [runner](apps/interface_lab/application/runner.mjs). Its template inlines `tokens.css` and `base.css` and uses the template core and theme pair described under [the canvas page](#graph-skill-canvas-page). `open_interface_lab` presents it independently of `show_graph`. Opening the page runs no test operation; the developer chooses each call.

An **operation** is one call a page can make through Hostpane: either a **host interface**, which the host performs, such as `composer.writeDraft` (17 exist), or a **local capability**, which the plugin's own Node.js process performs, such as `local.files.read` (5 exist). Each operation's **definition** in Hostpane carries its id, label, sample arguments, `params` (one row `{ name, type, required, note }` per argument) and `returns` (one sentence describing the result's `data`); Hostpane exposes them to pages as `INTERFACES` and `LOCAL_DEFINITIONS`.

### Modes and navigation

The lab page has two modes, chosen by the segmented control that opens the floating top bar:

- **guide mode** (指南) documents how a plugin uses Hostpane and what each operation takes and returns;
- **test mode** (测试) runs an operation against the live host and records its result and the developer's comparison.

The URL hash holds the mode and the selection, so a reload or a shared link opens the same view: `#guide/start` is the quick start, `#guide/composer.writeDraft` is that operation's guide, and `#lab/composer.writeDraft` is that operation in test mode. Without a valid hash, the page reopens at the place remembered in the browser storage key `lab-route`, else at the quick start. An unknown operation id opens the quick start in guide mode and the first operation in test mode. A script in the page head sets `data-mode` on `<html>` before the first paint, so the layout does not change once the application starts.

One operation list serves both modes. It groups the 22 operations, and in guide mode a 快速上手 (quick start) entry comes first. The selected operation stays selected across mode switches. In an operation's guide, the button 在测试页运行 → (run on the test page) opens the same operation in test mode; in test mode, the button 参数说明 (parameter description) returns to its guide. Switching to test mode from the quick start opens the first operation.

### Guide mode

**Quick start.** The quick start, from the [quick-start data](apps/interface_lab/application/handbook.mjs), states what a Hostpane plugin consists of: the plugin server (`hostpane/server`, a Node.js process the host starts as an MCP server, which serves the page and tools), the page (`hostpane/page`, one self-contained HTML file that calls the operations through an adapter object) and the Claude Mod (`hostpane/claude-mod`, which presents the page in the Browser pane and performs host operations for it; Codex does not need it). Four steps follow, each with code and a link to its section of [Hostpane's README](https://github.com/SevenX77/hostpane/blob/main/README.md):

1. start the plugin server with `servePlugin`;
2. register the page in the Claude Mod with `registerPluginBase(on, { pluginName, pages })`;
3. connect the page with `createHostAdapter` and `connect`;
4. call an operation, for example `adapter.composer.writeDraft({ text: "Hello", mode: "append" })`, and read `result.status`.

The quick start then shows the **result envelope** every operation resolves to, `{ status, message, data?, requestId?, evidence: { sent, receipt, observed, limits } }`, with the meaning of each of the six statuses (`completed`, `accepted`, `pending`, `unsupported`, `rejected`, `error`) and of each of the four **evidence slots**: `sent` (the arguments actually sent), `receipt` (the host's or system's raw receipt), `observed` (the effect read back) and `limits` (the host limits that applied). It ends with shortcuts to six common operations: `composer.writeDraft`, `conversation.submitMessage`, `context.update`, `tools.call`, `files.openFile` and `local.files.read`.

**Operation guide.** [The operation guide](apps/interface_lab/ui/guide.tsx) shows, from top to bottom:

- the operation id, its Hostpane label, and the current host's declaration for it: 可用 (available), 不可用 (unavailable) or 未声明 (not declared); for a local capability the tag reflects whether the page has a local-capability connection;
- the operation's purpose, and for a local capability the note that the plugin's own process performs it without the host;
- a field table with the columns 字段 (field), 类型 (type), 必填 (required) and 说明 (note), rendered from the definition's `params`; an operation without arguments says to pass `{}`;
- the definition's `returns` sentence;
- a page-side call example, `const result = await adapter.<id>(<args>)` with the first preset's arguments; `events.subscribe` and `local.files.watch` show a listener form with its stop call instead;
- the expected behaviour on Claude and on Codex, with the current host's row highlighted;
- the limits the current host declares for the operation;
- a link to the operation's section of Hostpane's README.

For `composer.writeDraft` the field table has two rows: `text`, type `string`, required, 1 to 8000 characters with a non-blank character; and `mode`, type `"append" | "replace"`, required, where `append` appends to the draft and `replace` replaces it and Codex does not support `replace`. Hostpane's README remains the full reference.

### Test mode

**Detail column.** The detail column shows, in this order:

1. the head card: operation id, signal tag, purpose and signal detail. A red note appears only when the host declaration is not `available`, when the page has no local-capability connection for a local capability, or when the current permission mode blocks or limits the operation.
2. the run card: preset buttons and the 运行 (run) button on one row; for `context.update`, the context probe button 让模型复述 (ask the model to repeat); for `files.openFile` and `files.revealDirectory`, the workspace-directory field; for a local capability, the sample-file path; the JSON argument editor, sized to its content up to 14 lines; and the waiting and save notes.
3. the expectation card: the current host's expectation, how to check it, the declared limits, and the other host's expectation folded behind a toggle.
4. the call records of the selected operation, newest first.

**Operation list.** Each operation shows its signal dot, a 不可用 or 部分 tag when the current permission mode blocks or limits it, and its call count. Above the list, a tally counts the operations of each signal colour. At the bottom, the folded block 连接与目录 (connection and directories) lists the host, the connection and transport, the permission mode, local-capability availability and the lab state directory. The top bar's host chip shows the host name with a status dot, and its tooltip repeats the connection and transport, permission mode and local-capability availability.

**Interface signal.** One reading of an operation's latest call decides its list dot, its head-card tag and the record's tag, so all three agree. [The signal module](apps/interface_lab/application/connection_status/index.mjs) owns the judgement:

| Condition, checked in this order | Signal |
| --- | --- |
| The page is not connected | Grey, 尚未连接 (not connected). |
| A host interface while the host identity is unconfirmed | Grey, 宿主待确认 (host awaiting confirmation). |
| A host interface whose declaration is `unavailable`, or a local capability without a local-capability connection | Red, 当前不可用 (currently unavailable). |
| A call of this operation is running | Yellow, 测试中 (testing). |
| A latest call exists on the current connection | The call's own signal, below. |
| No call yet | Grey, 未测试 (untested). |

A call's own signal is set by the developer's comparison when one is chosen: **matches** is green, **differs** and **not observed** are red. Without a comparison its status decides: `completed` is green; `accepted` is yellow, 已受理，待确认 (accepted, awaiting confirmation); `pending` is yellow, 等待回执 (awaiting receipt); `rejected`, `unsupported` and `error` are red. Yellow therefore means a test is still open, and green or red means it is closed. A comparison of **matches** never rewrites the call's `accepted` status as `completed`.

Every signal uses calls from the current adapter connection; host-interface signals also require the call's captured host id, version, transport and session to equal the current host's. The page reads the adapter's host facts after each call and every 5 seconds, since the permission mode can change while the page stays open. Replacing the adapter starts a fresh lab session, including its calls, events, comparisons and workspace selection.

**Workspace and presets.** On connection, the page selects `workspaceRoots[0]`, then `cwd`, from `host.getContext` when supplied. Codex currently supplies neither path, so the developer enters a real absolute workspace directory in the run card's workspace field. An unknown workspace leaves host-file preset paths empty. Changing the workspace clears the `files.openFile` and `files.revealDirectory` argument drafts so their presets use the new root. Local file presets use the lab sandbox. Host file and directory presets use the workspace; the [manual procedure](MANUAL-TESTS.md#files-draft-message-and-context) checks the actual target before dispatch. View closure uses the latest owned view handle. The first file-open preset opens the workspace README without `line`. The separate `line: 2` preset is labelled as a Claude variant; on Codex it tests an unsupported parameter, independently of basic file opening. [The operation reference](https://github.com/SevenX77/hostpane/blob/main/README.md#host-interface-reference) owns argument constraints.

**Running.** The run button is enabled when the page is connected and idle. Hostpane performs the final capability and argument checks; an unavailable or unknown host operation produces an explicit unsupported result with its reason. During [automatic Claude receipt waiting](https://github.com/SevenX77/hostpane/blob/main/README.md#claude-host-operation-waiting-and-evidence-sizes), the run card shows “宿主处理中…已等待 N 秒” (“Host processing; waited N seconds”). For `conversation.submitMessage` and `skills.invoke` the note adds that a submission waits in the queue until the session is idle and that waiting for the receipt submits nothing again.

**Call records.** The newest record is expanded. Each older record folds to one line and opens on a click. A record shows, in order:

- its message;
- `data`, when present, as a full-width panel;
- each non-empty evidence slot as its own panel;
- the empty slots named on one line, for example `无内容：receipt · observed` (nothing in: receipt, observed), so all four slots stay accounted for;
- a stop control for an explicit event subscription or a file watch, and 查询回执（不会重发） (query the receipt; nothing is sent again) for a `pending` result with a request id;
- the comparison controls 与预期一致 (matches), 与预期不符 (differs) and 未观察到效果 (not observed), and a note field.

A record's head line holds its signal tag, its comparison or 待对照 (awaiting comparison), the request id when present and the local time with its UTC offset, whose tooltip names the captured host; a folded record adds its message beneath.

**Context updates.** A completed `context.update` record displays the model-visible text extracted from `evidence.sent`. A structured-only Codex update carries the snapshot with no text block to extract. The probe button 让模型复述 submits a separate message asking the model to repeat the page context verbatim; record a missing text block honestly for that modality. Claude's `context.attached` events show the delivered blocks and their origin under the [two-path context contract](https://github.com/SevenX77/hostpane/blob/main/README.md#contextupdate). Codex confirms receipt; the model's answer supplies separate consumption evidence. A clearing update has its own empty-context note. [Hostpane usage](https://github.com/SevenX77/hostpane/blob/main/README.md#contextupdate) owns exact text and clearing semantics.

**Event log.** The event log receives host events and local file changes, each row with type, local time and expandable source and data. It keeps the most recent 400 rows and offers filtering by type or source and clearing. The page subscribes to all host events at startup; an explicit subscription test has its own source label and stop control, and file-watch calls also expose a stop control.

**Comparison and saving.** Changing a record's comparison, or leaving an edited note field, saves the session's records through `local.files.write`. The run card reports the save result and path. The developer checks that save before treating a comparison as durable.

### Layout and components

The lab reuses the template's sample components as they stand: the floating top bar `.bar`, segmented controls `.seg` for the mode switch, operation list and comparison controls, cards `.card`, tags `.tag`, buttons `.btn`, inputs `.input` and labels `.label`. Its layout is a main column with asides, sized for Claude Code Desktop's Browser pane and Codex Desktop's MCP App view:

| Window width | Test mode | Guide mode |
| --- | --- | --- |
| 1180 pixels and wider | Three columns: operation list 232 pixels, detail, event log 320 pixels. | Two columns: operation list 232 pixels and detail; the event log is an overlay drawer. |
| 720 to 1179 pixels | Two columns: operation list 220 pixels and detail; the event log is an overlay drawer. | The same as test mode. |
| Below 720 pixels | One column; the operation list and the event log are overlay drawers. | The same as test mode. |

The detail column's content is at most 920 pixels wide. The drawers are frosted overlays: the top bar's 事件 (events) button, which also shows the event count, opens the event-log drawer whenever the log is a drawer, and below 720 pixels the 接口 (operations) button opens the operation-list drawer. Esc, or a press outside the drawer and the top bar, closes it; that press acts on nothing else.

The floating top bar holds, from left to right, the mode switch, the host chip, the 事件 button when the event log is a drawer, the 浅/深 switch, and the switch 聚焦时淡化周围 (fade the surroundings while focusing), which fades components around the focused one. Below 720 pixels the 接口 button comes first, and the host chip and the fade switch are hidden; the host facts remain in the 连接与目录 block.

### Lab state and comparison files

[The lab state module](apps/interface_lab/server/state.mjs) selects and creates the nominal state directory, then resolves its real on-disk path with Node.js `fs.realpath`. The nominal path is the path the process requests; the real path is the location returned by that filesystem lookup. When the lab is first opened, the server prepares `sandbox/` and `records/` under the real directory and creates `sandbox/sample.txt` if it is absent. `sample.txt` is a runtime scratch fixture for local-capability tests that read, write, watch and reveal files. The lab server owns this fixture under its state directory, separate from the user workspace and installed plugin assets. Preparation preserves an existing sample file. Claude host-file presets follow the workspace scope in the [file-open reference](https://github.com/SevenX77/hostpane/blob/main/README.md#filesopenfile). The returned `stateDirectory`, `sandbox`, `records` and `sampleFile` all use real paths. The lab page's 连接与目录 block shows the state directory, a local-capability run card shows the sample file, the open-tool text shows those paths, and comparison files are written under the real records directory.

| System | Nominal lab state directory and real-path handling |
| --- | --- |
| Windows | `%LOCALAPPDATA%\plugin-interface-lab`; with no `LOCALAPPDATA`, `<home>/AppData/Local/plugin-interface-lab`. Preparation resolves the real path. |
| Windows packaged host | MSIX is the Windows packaged-app format. Windows can redirect a packaged host's and its descendant processes' writes under `%LOCALAPPDATA%` into the package's private directory. For Claude Desktop the real lab directory has the form `%LOCALAPPDATA%\Packages\<package family name>\LocalCache\Local\plugin-interface-lab`. The lab reports and uses the resolved directory. |
| macOS | `~/Library/Application Support/plugin-interface-lab`, resolved to its real path. |
| Linux | `$XDG_STATE_HOME/plugin-interface-lab`, or `~/.local/state/plugin-interface-lab`, resolved to its real path. |

[The dated validation record](VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) owns the packaged-host finding, source-tested path behavior and remaining native confirmation.

One page session saves `<lab state directory>/records/<host>-<session start>.json`. The session-start timestamp has colons and periods converted to hyphens. The schema is `plugin-interface-lab.records.v1`. It stores host information, session start, and each call's operation, arguments, time, status, message, evidence, comparison verdict and note. The page writes it through `local.files.write`.

Raw result `data`, the event log and candidate/build identity are separate from the saved entry fields. The [manual procedure](MANUAL-TESTS.md#settlement-and-reporting) retains those supplemental observations when needed. The server grants its lab state directory to the session local connection. [ARCHITECTURE.md](ARCHITECTURE.md#local-capabilities-in-the-process) owns shared grants and lifecycle.

## Host presentation

**Codex Desktop.** `show_graph` and `open_interface_lab` each attach their own MCP App view to the presenting tool result. A page resource advertises fullscreen. Opening a page is a separate business flow from generic owned-view operations. The host-reported display mode and visible focus each have their own observation.

**Claude Code Desktop.** The Mod supplies actual session root and identity, requests HTML presentation and adds ordered preview guidance. Record existing tabs, attach the returned preview by name, navigate the returned HTTP tab, select it, then inspect the final inventory and visibility. Each dependent action waits for the preceding result. If the Browser pane stays hidden, the user opens it through the preview card's Open button or Browser toggle. The plugin preserves existing tabs and keeps presentation confined to the requested page.

The lab's [Skill](skills/plugin-interface-lab/SKILL.md) opens the lab and defines the context-probe reply and bounded Skill-activation test. Source test mode enables the lab through `GRAPH_SKILL_INTERFACE_LAB=1` and installs that Skill. [ARCHITECTURE.md](ARCHITECTURE.md#installation-and-source-selection) owns registration; [README.md](README.md#switch-the-desktop-source-for-testing) gives source-mode commands.

## Evidence boundary

The descriptions above are source-checked page behavior. A standalone browser render establishes layout at that scope. [The page guide and template redesign record](VALIDATION.md#plugin-page-guide-and-template-redesign-2026-11-07) states the standalone renders of the current pages and the live-host observations they still need. Native acceptance of all 22 operations in Claude Code Desktop and Codex Desktop is pending. The [current validation baseline](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) records the measured candidate and remaining evidence. Use [MANUAL-TESTS.md](MANUAL-TESTS.md) to compare receipts with actual host effects and saved records.
