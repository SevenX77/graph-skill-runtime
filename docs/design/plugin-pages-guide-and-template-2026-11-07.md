# Plugin page guide and shared-design redesign of the toolkit pages

Date: 2026-11-07.

Status: established 2026-11-07 (owner request of 2026-11-07; implementation decisions derived by the coordinator)

## Purpose

A developer building a plugin page on Hostpane learns how to use it, every operation's fields, and can try any operation on the live host, from one page shown inside Claude Code Desktop's Browser pane or Codex's MCP App view; every toolkit page (graph canvas, Interface Lab, guide) shows its information in the owner's shared interface design, sized for those two built-in browsers, with the most important facts read first.

## Terms

- **Hostpane**: the project at `D:/coding/hostpane` (private GitHub repository `SevenX77/hostpane`) that runs one plugin page in each host's pane and calls that host's interfaces. The toolkit pins it by commit in `src/graph_skill_toolkit/package.json`, currently `be973a37504bb6020b4948ae4ca82763480e76e6`.
- **Toolkit**: `src/graph_skill_toolkit/` in repository `graph-skill-runtime`, branch `claude/toolkit-host-interfaces`. It holds the business apps `apps/graph_canvas` and `apps/interface_lab` and builds each page into one self-contained HTML file under `dist/`.
- **Browser pane**: the side pane beside the conversation in Claude Code Desktop, in which the toolkit's Claude Mod presents a page.
- **MCP App view**: the sandboxed frame in which Codex Desktop renders an MCP App, an MCP resource holding one HTML page attached to one tool result.
- **Operation**: one call a page can make through Hostpane. It is either a **host interface**, an operation the host performs, such as `composer.writeDraft` (17 exist), or a **local capability**, an operation the plugin's own Node process performs, such as `local.files.read` (5 exist).
- **Definition**: the object in Hostpane that owns one operation's shared facts, `{ id, label, sample, fields, params, returns, validate }`. `fields` lists the argument names in order; `params` and `returns` document the arguments and the result (Decision 2); `validate` throws on invalid arguments; `sample` is a valid example argument object.
- **Graph canvas**: the toolkit page that shows one portable Graph Skill's graph, opened by the MCP tool `show_graph`.
- **Interface Lab** (lab): the toolkit page, opened by the MCP tool `open_interface_lab`, on which a developer runs any operation against the live host and reads its result and evidence.
- **Guide**: the usage documentation for Hostpane operations, shown as a mode of the Interface Lab page (Decision 1).
- **Template core**: the shared design of the owner's projects, in `core/` of the template project `D:/coding/ui-ux-template` (GitHub `SevenX77/ui-ux-template`). It contains design tokens (`core/dist/tokens.css`), base and scene styles (`core/styles/`), interaction behaviour (`core/behavior/ux.js`) and the UI rules (`core/rules/UI-RULES.md`). The toolkit reads it through the git submodule `vendor/ui-ux-template` at the repository root.
- **Design token**: a named CSS custom property in `core/dist/tokens.css`, such as `var(--signal)` or `var(--glass)`, that carries one colour, radius, shadow, easing or duration value.
- **Theme pair**: a light theme and a dark theme between which the light/dark switch moves; this record uses the pair Prism (彩光, light) and Aurora (极光, dark).
- **Sample component**: a component of the template's handbook `templates/html/ui-handbook.html`, with its class names, that a consuming page reuses as it stands.
- **Segmented control**: the handbook's `.seg` component, a row of buttons of which one is current, marked by a sliding indicator.
- **Overlay**: a panel drawn above the content that takes no part in the content's layout, so opening or closing it moves nothing beneath it.
- **Result envelope**: the `HostResult` every operation resolves to, `{ status, message, data?, requestId?, evidence: { sent, receipt, observed, limits } }`. Its `status` is one of `completed`, `accepted`, `pending`, `unsupported`, `rejected`, `error`; `sent`, `receipt`, `observed` and `limits` are the four **evidence slots**.

## Owner request

- 「做一个使用指南的页面，写清楚怎么用，接口字段参数，并导航测试页」 (gloss: "Make a usage-guide page that states clearly how to use it and the interfaces' fields and parameters, and navigates to the test page.")
- 「所有页面用ui/ux template项目的模板重新做，找合适的样章组件，布局规划合理，以适配Claude和codex的内置浏览器画幅为主。信息显示要从用户角度考虑，高效、简洁、突出重点、不罗嗦、展示效率高」 (gloss: "Redo all pages with the ui/ux template project's templates, find suitable sample components, plan the layout sensibly, mainly fitted to the frame of Claude's and Codex's built-in browsers. Information display should take the user's view: efficient, concise, highlighting key points, not wordy, high display efficiency.")

## Facts

All facts below were observed on 2026-11-07.

1. **Two toolkit pages exist.**
   - The graph canvas: tool `show_graph`, template `apps/graph_canvas/ui/template/canvas.html`. Its template declares its own colours, for example `--accent: #675ec7; --edge: #9ba8be;` on `:root`, and reads nothing from the template core.
   - The Interface Lab: tool `open_interface_lab`, template `apps/interface_lab/ui/template/lab.html`. It already inlines the template core's tokens and base styles:

     ```html
     <style>/* INLINE_CSS ../../../../../../vendor/ui-ux-template/core/dist/tokens.css */</style>
     <style>/* INLINE_CSS ../../../../../../vendor/ui-ux-template/core/styles/base.css */</style>
     ```

     It uses `UX` from `core/behavior/ux.js` and the theme pair Prism/Aurora (`<html lang="zh" data-scheme="prism">`). Its layout breakpoints are `@media (max-width: 1179px)` and `@media (max-width: 719px)`.
   - `src/graph_skill_toolkit/scripts/build/main.mjs` replaces each `/* INLINE_CSS <path> */` marker with the named file's contents and writes `dist/canvas.html` and `dist/interface-lab.html`.
2. **The template core.** The submodule `vendor/ui-ux-template` stands at commit `24e3a36`; the template's `main` is `b02291a`. `core/rules/UI-RULES.md` is version 0.8 with 27 rules, among them:
   - rule 1, choose a theme pair first;
   - rule 4, use few lines and give each line a job;
   - rule 6, give each component a core and four states through `core/behavior/ux.js`, declared with `data-scope`, `data-cmp` and `data-tool`;
   - rule 11, lay out by what is read first, choosing one of hero, bands, main with aside, full-bleed with floats, kanban, swimlanes;
   - rule 26, every canvas is infinite and every side panel is an overlay, bound through `UX.canvas` and `data-canvas`.

   The template's `docs/ARCHITECTURE.md` states that a consuming template defines no colour, size, radius, shadow, easing, duration, spacing or interaction-timing value and reads core tokens through `var(--…)`.
3. **Sample components chosen from the handbook.** Top bar `.bar` / `.bar-in` holding a segmented control `.seg`; a navigation list built as a `.seg` selector; cards `.card`; tags `.tag`; buttons `.btn` with the variants `.sec2`, `.ghost`, `.sm`; inputs `.input`; labels `.label`; and the canvas blueprint sample `#bp` in `core/styles/scenes.css`. The blueprint sample consists of `.bp`, a dot-grid board `.bp-board` marked `data-canvas`, compact nodes with a coloured letter badge, edges `.bp-svg path.e` that take colour only with the class `.on`, a detail panel `.bp-side` drawn as an overlay, and the zoom and fit controls `.cvz`. Its handbook markup is:

   ```html
   <div class="bp" id="bp" data-scope="bp" data-hold><div class="bp-board" id="bpBoard" data-canvas></div><div class="cvz" data-keep role="group" aria-label="画布视图"><button data-cv="out" aria-label="缩小画布">−</button><output data-cv="z">100%</output><button data-cv="in" aria-label="放大画布">+</button><button data-cv="fit">适合画布</button></div><aside class="bp-side" id="bpSide" data-keep></aside></div>
   ```
4. **Frames of the two built-in browsers.** The Codex MCP App view in fullscreen was observed at a viewport of `1205×1292` CSS pixels (toolkit `VALIDATION.md`, row "Later native Codex display"). The Claude Browser pane sits beside the conversation; the page measured `1024×768` while the pane was hidden, its default state, and a side pane is typically about 600 to 1100 pixels wide.
5. **Operation facts live in Hostpane definitions.** Each host interface's definition is exported from `src/host_interfaces/<group>/<name>/index.mjs`, collected by the catalog `src/ports/host/catalog.mjs`, and exposed to pages as `INTERFACES`, a list of `{ id, label, sample, params, returns }` at the pinned commit `be973a37` (Decision 2). `src/local/definitions.mjs` exports `LOCAL_DEFINITIONS` for the 5 local capabilities in the same shape. At the earlier pin `2edc5415`, observed when this decision was taken, `INTERFACES` held `{ id, label, sample }` and the definition of `composer.writeDraft` read:

   ```js
   export const definition = { id: "composer.writeDraft", label: "写入草稿", sample: { text: "接口草稿测试", mode: "append" }, fields: ["text", "mode"], validate(args) {
     if (!text(args.text)) throw new Error("消息须包含 1–8000 个字符。");
     if (!["append", "replace"].includes(args.mode)) throw new Error("草稿模式必须为 append 或 replace。");
   } };
   ```

   At that commit an argument's type and constraints existed only in this validation code and in prose in Hostpane's `README.md`, sections "Host interface reference" and "Local capability reference"; for this operation the README read "`text` (1 to 8000 characters), `mode`: `append` or `replace`".
6. **Per-operation guidance lives in the lab app.** `apps/interface_lab/application/guide.mjs` exports `GUIDES`, one entry per operation with `purpose`, `expect` (the expected effect, separately for `claude` and `codex`), `check` (how to confirm the effect) and `presets` (named argument sets).
7. **The lab calls host interfaces from the Browser pane.** In a Claude Code 2.1.317 session, `open_interface_lab` presented the lab in the Browser pane; the page called `tools.call` → `lab_echo` through the Claude Mod and received `{"echo":{"text":"接口测试 ✓"},...}` intact.

## Decisions

1. **The guide is a mode of the Interface Lab page.** The lab page has two modes, 指南 (guide) and 测试 (lab), switched by a segmented control in the top bar.
   - Both modes share one operation list and one selected operation.
   - In guide mode, the button 在测试页运行 (run on the test page) switches to lab mode on the same operation; in lab mode, the button 参数说明 (parameter reference) switches back to guide mode on the same operation.
   - The URL hash holds the mode and the operation, for example `#guide/composer.writeDraft` and `#lab/composer.writeDraft`, so a reload or a shared link opens the same view.
   - Guide mode has a 快速上手 (quick start) entry above the operation list (Decision 3).

   Reason: a Codex MCP App view is one HTML resource attached to one tool result and cannot navigate to another document, so switching inside one page is the navigation that behaves the same on both hosts; sharing the selection makes "read, then try" one click.

2. **Hostpane's definitions own field metadata.** Each host-interface and local-capability definition gains `params`, a list of `{ name, type, required, note }` with one row per argument, and `returns`, one sentence describing the result's `data`. For `composer.writeDraft` the `mode` row is:

   ```js
   { name: "mode", type: "\"append\" | \"replace\"", required: true, note: "append 追加到草稿末尾；replace 替换整个草稿（Codex 不支持）。" }
   ```

   `INTERFACES` and `LOCAL_DEFINITIONS` expose `params` and `returns` to pages, so the guide renders each operation's parameter table and result sentence from them. A Hostpane test requires that every definition's `params` names equal its `fields`, in the same order.
   Reason: the definition already owns `fields` and the validation that `validateArguments` applies; keeping the parameter table in the same object keeps the guide's table equal to what validation accepts.

3. **The lab app owns the quick start and per-host behaviour.** The quick start is display data in `apps/interface_lab/application/handbook.mjs`. It states:
   - what a Hostpane plugin consists of;
   - the four code steps: `servePlugin` in the plugin server, `registerPluginBase` with `pluginName` in the Claude Mod, `createHostAdapter` and `connect` in the page, and `invoke` with its result envelope;
   - the six result statuses and the four evidence slots.

   Each quick-start item links the Hostpane `README.md` section that gives the full detail, for example "Building a plugin" and "Results and evidence". Per-operation host behaviour in guide mode reuses `GUIDES` (Fact 6).
   Reason: the quick start is the lab's presentation of Hostpane to a developer; Hostpane's `README.md` remains the full reference, and the links lead to it for depth.

4. **Every page uses the template core by reference.**
   - Both page templates inline `core/dist/tokens.css` and `core/styles/base.css`; the canvas template also inlines `core/styles/scenes.css`.
   - Interaction states run on `core/behavior/ux.js`.
   - The submodule `vendor/ui-ux-template` moves from `24e3a36` to `b02291a`.
   - Both pages use the theme pair Prism/Aurora. The initial theme follows `prefers-color-scheme`; a manual switch in the top bar overrides it and is remembered per page.
   - Page CSS adds only layout, such as grid columns and positions, and reads every colour, radius and shadow from core tokens and uses the easing token `--ease`; transition durations take the values of the template's motion table (UI rule 10: tools .25s, module .35s, push .52s); for example the canvas's `--accent: #675ec7` is removed and the page reads `var(--signal)`.

   Reason: the template core is the one design of the owner's projects, and UI rule 1 and the template's consuming rule (Fact 2) give a consuming page no design values of its own.

5. **Layouts are sized for the two built-in browsers.** The primary target width is 760 to 1210 pixels.
   - The lab uses the layout "main with aside":
     - at 1180 pixels and wider, three columns: operation list 232 pixels, detail, event log 320 pixels;
     - from 720 to 1179 pixels, two columns, with the event log as a frosted overlay drawer opened from the top bar;
     - below 720 pixels, one column, with the operation list as an overlay drawer.
   - The canvas uses the layout "full-bleed with floats": the graph fills the page and the bar, controls and panels float above it.

   Reason: the Claude side pane is usually narrower than 1100 pixels and the Codex fullscreen view is about 1200 pixels wide (Fact 4); each breakpoint keeps the detail column at least about 480 pixels wide.

6. **The lab's detail column shows what is read first, first.** Its order is:
   1. the operation id with its signal tag, a `.tag` showing the lab's current reading for that operation (the same signal as the list's dot: untested, running or awaiting comparison, connected, or limited, judged from the host declaration and the calls on this connection), and its one-line purpose;
   2. the run card: preset chips, the JSON argument editor, and the run button on the same row as the presets;
   3. the expectation for the current host only, with its one-line check; the other host's expectation opens behind a toggle;
   4. call records, the newest expanded and older ones collapsed.

   Within a call record, empty evidence slots collapse into one line naming them (constructed example: `receipt · limits: empty`), so all four slots stay accounted for without empty boxes.
   Reason: the developer's loop is choose, run, compare; the purpose and expectation are short context for that loop, and the run card and its result are what the developer looks at most.

7. **The canvas follows the blueprint sample.**
   - A floating glass header card at the top left shows the graph id, the node and edge counts, the Skill root path, the status line and the invalid-graph notice; a separate glass host chip at the top right shows the host status, the theme switch and the host-connection details.
   - The graph is an infinite canvas bound with `UX.canvas`: dragging empty space pans, Ctrl or Cmd with the wheel zooms, and zoom and fit controls are offered. Node positions come only from the graph projection.
   - Nodes are compact cards with a kind badge and the node id. The badges are `I` INPUT, `L` LOGIC, `A` AGENT, `S` SUBGRAPH, `O` OUTPUT.
   - Edges are curves that take colour only when they belong to the selected node.
   - The selected node's details open in an overlay side panel, which never moves nodes.
   - An invalid graph shows a floating card over the canvas that lists each runtime diagnostic verbatim.
   - These behaviour hooks keep their names: `#skill-path`, `data-node`, `data-edge`, `data-selected-node`, `data-host-info`, `data-diagnostic-code`, and the document dataset keys `connection`, `graphConnection` and `toolResult`.

   Reason: UI rule 26 and the blueprint sample describe a dependency graph on an infinite canvas with an overlay panel; tests and manual procedures locate the page's state through the named hooks.

## Acceptance

- [x] In Hostpane, `npm run typecheck` and `npm test` pass, including the test that every definition's `params` names equal its `fields` (Decision 2); the declarations under `types/` are regenerated; the commit is pushed; and the toolkit's `hostpane` pin names that commit. Observed 2026-11-07: at commit `be973a37504bb6020b4948ae4ca82763480e76e6`, on `SevenX77/hostpane` `main`, typecheck passed and `npm test` reported 183 passed, 0 failed; `tests/base/closure.test.mjs` compares each definition's `params` names with its `fields`; the installed package's `types/` declarations carry `params` and `returns`; `src/graph_skill_toolkit/package.json` pins that commit.
- [x] In the toolkit, `npm run build`, `npm run typecheck`, `npm test` and `npm audit` pass. Tests cover parsing of the URL hash (Decision 1) and the guide data: every operation has `params` and `returns`, and every quick-start link resolves to an existing heading of Hostpane's `README.md`. Observed 2026-11-07: build passed (canvas 904006 bytes, Interface Lab 911462 bytes), typecheck passed, `npm test` reported 85 passed, 0 failed, and `npm audit` reported 0 vulnerabilities; `tests/interface_lab/handbook.test.mjs` covers hash routes, mode switching, `params` and `returns` for every guided operation, and README headings for every quick-start step and every operation guide.
- [ ] Browser-pane screenshots exist of guide mode, lab mode and the canvas at `820×900` and `1210×900` and at 390 pixels wide, each in light and dark theme, with no console errors. Observed 2026-11-07, standalone without a host connection: the lab's quick start, an operation guide and test mode at `820×900` and `1210×900`, test mode at `375×812`, in light and dark; the canvas at `820×900` in light and dark with a node selected, and at `375×812`; no console errors and no horizontal scroll at 375 pixels. Missing: the canvas at `1210×900`, guide mode at the narrow width, the narrow width of 390 pixels, and both themes for every narrow view.
- [ ] In a live Claude Code session, the lab still calls a host interface through the Mod, for example `tools.call` → `lab_echo`, and the navigation guide → 测试 → 参数说明 keeps the selected operation. Observed 2026-11-07: in a Claude Code 2.1.317 session `tools.call` → `lab_echo` returned through the Mod, but that session's MCP server served the previous page build; guide → test → guide kept `composer.writeDraft` only in the standalone render. Missing: both observations on the redesigned build in a live session started after this build.
- [x] The toolkit's `PROTOTYPE.md` describes both lab modes and the redesigned canvas, and `VALIDATION.md` records the measurements above. Observed 2026-11-07: `PROTOTYPE.md` sections "Graph Skill canvas page" and "Plugin Interface Lab page" describe them, and `VALIDATION.md` section "Plugin page guide and template redesign, 2026-11-07" records the checks, the standalone renders and the pending live-host observations.

## Application state

Applied on 2026-11-07 on branch `claude/toolkit-host-interfaces`, except the two acceptance items still unticked: the browser renders still missing and the observation of the redesigned build in a live Claude Code session.

Since 2026-11-09 the Interface Lab is Hostpane's test page ([Hostpane decision](https://github.com/SevenX77/hostpane/blob/main/docs/design/interface-lab-in-hostpane-2026-11-09.md)). Where this record places the lab in the toolkit, it describes the layout of its date.
