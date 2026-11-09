# Canvas page behavior

Users inspect a Graph Skill's graph, its selected node and its compile state inside their desktop host.

The toolkit presents one page, the **Graph Skill canvas**, which shows a caller-selected graph and its selected node. The canvas has one self-contained HTML build, `dist/canvas.html`, shared by both hosts. The Interface Lab, the developer page that tests Hostpane's operations and page triggers, is Hostpane's test page, and [Hostpane's `docs/LAB.md`](https://github.com/SevenX77/hostpane/blob/main/docs/LAB.md) owns its page behaviour.

This document owns the canvas's visible behavior. [Hostpane usage](https://github.com/SevenX77/hostpane/blob/main/README.md) owns the full reference for the 17 host interfaces and 5 local capabilities; Hostpane is the separately versioned package that provides the toolkit's host integration. [Hostpane's adapter architecture](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md) owns connection and host routes. [ARCHITECTURE.md](ARCHITECTURE.md) owns the application map and graph-data path. [MANUAL-TESTS.md](MANUAL-TESTS.md) owns native observation, and [VALIDATION.md](VALIDATION.md) owns measured results.

## Terms

- **MCP (Model Context Protocol)** carries host requests to the plugin's tool server and resources back to the host.
- **MCP App** is the extension through which Codex attaches an interactive HTML page to a tool result.
- **Claude Mod** is hook code loaded inside a Claude Code session. It supplies session facts, executes host requests and guides page presentation.
- **Browser pane** is Claude Code Desktop's web-tab panel.
- **Loopback HTTP page** is a web page served by the plugin on the same computer, at `127.0.0.1`.
- **Skill** is a host-discoverable `SKILL.md` instruction asset. The toolkit's `graph-skill-canvas` Skill guides the agent to present the canvas, for example [`skills/graph-skill-canvas/SKILL.md`](skills/graph-skill-canvas/SKILL.md).

## Graph Skill canvas page

The canvas uses [its HTML template](apps/graph_canvas/ui/template/canvas.html), [page entry](apps/graph_canvas/app/main.tsx) and [workbench](apps/graph_canvas/ui/workbench/index.tsx). Its layout is a full-bleed canvas with floating cards: the graph fills the window, and the header card, host chip, view controls and detail panel float above it.

**Design.** The canvas takes its design from the **template core**: the shared interface design of the owner's projects, in `core/` of the UI/UX template project, read through the git submodule `vendor/ui-ux-template` at the repository root, at commit `b02291a`. The template core supplies **design tokens** (named CSS custom properties such as `var(--signal)` in `core/dist/tokens.css`, each carrying one colour, radius, shadow or timing value), base component styles (`core/styles/base.css`), scene styles such as the canvas blueprint (`core/styles/scenes.css`) and interaction behaviour (`core/behavior/ux.js`, imported by the page as `UX`). The canvas template inlines the core style files it uses: `tokens.css`, `base.css` and `scenes.css`. The [build script](scripts/build/main.mjs) replaces each `/* INLINE_CSS <path> */` marker with the named file, so the page remains one self-contained HTML file. Page CSS adds layout, such as grid columns and positions, and takes every colour and shadow from design tokens. The canvas uses the **theme pair** Prism (浅, light) and Aurora (深, dark). A script in the page head applies the theme before the first paint: the theme the user last chose on the canvas, else the operating system's `prefers-color-scheme`. A 浅/深 segmented control (`.seg`, a row of buttons of which one is current, marked by a sliding indicator) switches the theme and remembers it under the browser storage key `canvas-scheme`. An **overlay** is a panel drawn above the content that takes no part in the content's layout, so opening or closing it moves nothing beneath it.

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

**Selection.** A click on a node selects it, and a second click on the selected node clears the selection. With the keyboard, Tab moves focus between nodes and Enter or Space selects the focused node; Esc on a node, or a click on empty canvas, clears the selection. The selected node takes the selected background and a higher shadow, with no outline ring. Its edges take its kind colour, other edges fade, and nodes unrelated to it fade while its direct neighbours stay fully readable. This fading reports relations, so it holds whatever the pointer does; the canvas opts out of the template's hover dimming (`data-dim="none"`, UI rule 6), because a graph is read as a whole. A node shows its kind letter, its label and, except for the Input and Output boundary nodes whose labels already name them, its kind. Selection persists across graph snapshots while the same node id exists. Selection is page state: it submits no message and changes no business files. The canvas's controls serve graph presentation and inspection.

**Detail panel.** The selected node's details open in an overlay panel on the right, 280 pixels wide; below 720 pixels of width the panel is a bottom sheet. It shows the node id, its kind and the labels of its upstream and downstream nodes, with a close button. When the panel opens, the canvas view moves aside, and it returns when the panel closes; nodes never move.

**Header card.** A floating card at the top left shows:

- the graph id with a tag counting nodes and edges, for example `3 节点 · 2 连线`;
- the selected absolute Skill root, or `示例画布 · 未选择 Skill` for the rootless demonstration;
- a status line for an error or an unknown-identity reason, hidden when empty;
- the invalid-graph notice when the Skill does not compile.

Below 720 pixels of width the header card spans the window beneath the host chip.

**Host chip.** A floating chip at the top right, rendered by [host status](apps/graph_canvas/ui/host_status/index.tsx), shows a status dot and one plain state: the host name and version once the page is connected and the host identity is confirmed, otherwise the state in words (连接中, 身份未确认, 连接失败 or 未连接宿主). The dot is green when connected and confirmed, yellow while connecting or while the identity is unconfirmed, and red when the connection failed or the page runs without a host. The chip's tooltip adds the toolkit plugin version. The chip also holds the 浅/深 switch and an ⓘ toggle that reveals the host-connection data as JSON. The page refreshes host facts every 2 seconds while connected.

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

## Host presentation

**Codex Desktop.** `show_graph` attaches the canvas's MCP App view to the presenting tool result. The canvas resource advertises fullscreen. Opening the canvas is a separate business flow from generic owned-view operations. The host-reported display mode and visible focus each have their own observation.

**Claude Code Desktop.** The Mod supplies actual session root and identity, requests HTML presentation and adds ordered preview guidance. Record existing tabs, attach the returned preview by name, navigate the returned HTTP tab, select it, then inspect the final inventory and visibility. Each dependent action waits for the preceding result. If the Browser pane stays hidden, the user opens it through the preview card's Open button or Browser toggle. The plugin preserves existing tabs and keeps presentation confined to the requested page.

The [`graph-skill-canvas` Skill](skills/graph-skill-canvas/SKILL.md) states the agent's part of this presentation in both hosts. [ARCHITECTURE.md](ARCHITECTURE.md#installation-and-source-selection) owns registration; [README.md](README.md#switch-the-desktop-source-for-testing) gives source-mode commands.

## Evidence boundary

The descriptions above are source-checked page behavior of the canvas. A standalone browser render establishes layout at that scope. [The page guide and template redesign record](VALIDATION.md#plugin-page-guide-and-template-redesign-2026-11-07) states the standalone renders of the canvas and the live-host observations they still need. [VALIDATION.md](VALIDATION.md) records the measured candidates and remaining evidence. Use [MANUAL-TESTS.md](MANUAL-TESTS.md) to observe the canvas in a loaded host.
