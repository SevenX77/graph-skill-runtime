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

The canvas uses [its HTML template](apps/graph_canvas/ui/template/canvas.html), [page entry](apps/graph_canvas/app/main.tsx) and [workbench](apps/graph_canvas/ui/workbench/index.tsx). The workbench displays:

- the selected absolute skill root, or a labeled rootless demonstration;
- the graph id and node/edge counts;
- nodes and edges, drawn by [the canvas component](apps/graph_canvas/ui/canvas/view.tsx);
- the selected node's id and kind in a details panel;
- live host identity and the reported host software version beside the toolkit plugin version, rendered by [host status](apps/graph_canvas/ui/host_status/index.tsx);
- expandable host-connection data and a visible error or unknown-identity reason when applicable.

Pointer selection and keyboard selection with Tab and Enter update the node details. Selection persists across graph snapshots while the same node id exists. Selection itself is page state: it submits no message and changes no business files. The canvas's controls serve graph presentation and inspection. The separate Interface Lab owns operation-testing controls.

The runtime compiler owns whether the selected Graph Skill is valid. When compilation fails, the [invalid-graph notice](apps/graph_canvas/ui/diagnostics/index.tsx) appears above the graph area. It reports the number of runtime problems and shows each retained diagnostic's code, message, source path, line and field path verbatim. The display is bounded to 50 diagnostics with a remaining count. The last compiled graph stays visible and dimmed; a note states whether a compiled graph is available. A valid save supplies a fresh snapshot, clears the notice and redraws the graph in the same page.

Selection failures, an unreachable runtime or an out-of-contract reply appear as errors. The workbench retains its last valid graph while the graph connection recovers. A standalone page with no connection shows the labeled demonstration. [ARCHITECTURE.md](ARCHITECTURE.md#save-to-render-flow-and-lifecycle) owns file observation, transport recovery and save-to-render timing.

## Plugin Interface Lab page

The lab uses [its page entry](apps/interface_lab/app/main.tsx), [UI](apps/interface_lab/ui/index.tsx), [template](apps/interface_lab/ui/template/lab.html), [guidance data](apps/interface_lab/application/guide.mjs) and [runner](apps/interface_lab/application/runner.mjs). `open_interface_lab` presents it independently of `show_graph`. Opening the page runs no test operation. The developer chooses each call.

The page header shows the confirmed host name/version, connection state and transport, local-route availability, lab state directory and an editable workspace directory for host-file presets. On connection, the page selects `workspaceRoots[0]`, then `cwd`, from `host.getContext` when supplied. Codex currently supplies neither path, so the developer enters a real absolute workspace directory. An unknown workspace leaves host-file preset paths empty. Changing the workspace clears the `files.openFile` and `files.revealDirectory` parameter drafts so their defaults use the new root. Its sample-file note links the local test fixture to the [lab state directory](#lab-state-and-comparison-files).

The operation list groups all 22 operations: 17 host interfaces and 5 local capabilities. Each operation has a state dot and a call count. The dot, the selected operation's top status and the latest call record show one reading of the latest call of that interface on the current page connection. Yellow means a test is open: the call is running, a receipt is awaited, or a person has not yet compared an accepted call. A closed test is green or red: a completed call or a comparison of "matches" is green; a refusal, an unsupported request, an error, or a comparison of "differs" or "not observed" is red. An operation with no call is grey, unless its declaration or missing local route already makes it unavailable, which is red. File permissions and scope are checked when the operation runs. [The signal module](apps/interface_lab/application/connection_status/index.mjs) owns the judgement, and [the UI](apps/interface_lab/ui/index.tsx) renders it in all three places.

Selecting an operation shows its purpose, expected effect on both hosts, checking guidance, current interface signal and reason, and host-declared limits. The current host's expectation is highlighted. The developer can edit the JSON arguments or select a preset. Local file presets use the lab sandbox. Host file and directory presets use the workspace shown in the header; the [manual procedure](MANUAL-TESTS.md#files-draft-message-and-context) checks the actual target before dispatch. View closure uses the latest owned view handle. The first file-open preset opens the workspace README without `line`. The separate `line: 2` preset is labeled as a Claude variant; on Codex it tests an unsupported parameter, independently of basic file opening. The current Codex file-extension route accepts a file `path` and declares neither line navigation nor host-directory reveal. [The operation reference](https://github.com/SevenX77/hostpane/blob/main/README.md#host-interface-reference) owns those argument constraints.

The run button is enabled when the page is connected and idle. Hostpane performs final capability and argument checks. An unavailable or unknown host operation produces an explicit unsupported result with its reason. Each result card reports one invocation's status, captured host, message, request id when present, returned data and all four evidence slots: `sent`, `receipt`, `observed`, `limits`. Empty evidence slots remain visible with an empty-value marker. On Claude, `accepted` is labeled “已受理（效果需观察）” (“Accepted; effect needs observation”).

The continuing interface signal starts from the current connection and declaration; a declaration alone leaves connection unverified. A completed call supplies successful connection evidence unless marked **not observed** or **differs**. An accepted call supplies that evidence when marked **matches**. Once confirmed on the same connection, a later accepted call without a new **matches** comparison, or a later call marked **not observed**, preserves the connected signal while leaving that invocation's effect unverified. Without prior successful evidence, those outcomes leave effect confirmation pending. Each call card retains its own status and comparison; observing a match does not rewrite `accepted` as `completed`.

A **differs** comparison on a decisive call changes the signal to limited, and a generic rejected call reports a current block. A rejected result carrying `data.failureScope: "request"` describes a missing or unauthorized target, rather than an interface outage: it leaves existing connection evidence in force; without decisive call evidence, the signal is “request target limited, interface unverified.” An unsupported parameter variant likewise leaves an earlier successful basic call connected. An unsupported result carrying `data.capabilityState: "unavailable"` or `"unknown"` supplies an interface-level change as decisive evidence. Pending or error results alone leave the preceding signal intact. For host interfaces, an unavailable or unknown current declaration or unconfirmed host identity takes precedence over call evidence.

The page reads the adapter's current host facts after each call. Every signal uses calls from the current adapter connection; host signals also require the captured host id, version, transport and session to match. Replacing the adapter starts a fresh lab session, including its calls, events, comparison state and workspace selection. Saved call records retain per-invocation evidence. [The captured-host module](apps/interface_lab/application/result_status/index.mjs) and [signal module](apps/interface_lab/application/connection_status/index.mjs) own those boundaries.

A context-update card displays the model-visible text extracted from `evidence.sent` after a completed update. A structured-only Codex update carries the snapshot with no text block to extract. Its probe button submits a separate message asking the model to repeat the page context verbatim; record a missing text block honestly for that modality. Claude's `context.attached` events show the delivered blocks and their origin under the [two-path context contract](https://github.com/SevenX77/hostpane/blob/main/README.md#contextupdate). Codex confirms receipt; the model's answer supplies separate consumption evidence. Clearing context has its own empty-context readout. [Hostpane usage](https://github.com/SevenX77/hostpane/blob/main/README.md#contextupdate) owns exact text and clearing semantics.

The right-hand event log receives host events and local file changes, with type, time, source and expandable data. The event log and run cards render local time with the UTC offset, using `toLocaleTimeString` with `timeZoneName: "short"`. It keeps the most recent 400 rows and offers filtering and clearing. The page subscribes to host events at startup; an explicit subscription test has its own source label and stop control. File-watch calls also expose a stop control. During [automatic Claude receipt waiting](https://github.com/SevenX77/hostpane/blob/main/README.md#claude-host-operation-waiting-and-evidence-sizes), the page shows “宿主处理中…已等待 N 秒” (“Host processing; waited N seconds”) and a known wait reason. The busy-turn reason explains that submission is queued until the session is idle. Manual receipt lookup appears for a remaining unknown result and uses the existing request identity.

Each call has comparison controls for **matches**, **differs** and **not observed**, plus a note. Changing the comparison or leaving an edited note field triggers record saving. The page reports the save result and path. The developer checks that save before treating a comparison as durable.

### Lab state and comparison files

[The lab state module](apps/interface_lab/server/state.mjs) selects and creates the nominal state directory, then resolves its real on-disk path with Node.js `fs.realpath`. The nominal path is the path the process requests; the real path is the location returned by that filesystem lookup. When the lab is first opened, the server prepares `sandbox/` and `records/` under the real directory and creates `sandbox/sample.txt` if it is absent. `sample.txt` is a runtime scratch fixture for local-capability tests that read, write, watch and reveal files. The lab server owns this fixture under its state directory, separate from the user workspace and installed plugin assets. Preparation preserves an existing sample file. Claude host-file presets follow the workspace scope in the [file-open reference](https://github.com/SevenX77/hostpane/blob/main/README.md#filesopenfile). The returned `stateDirectory`, `sandbox`, `records` and `sampleFile` all use real paths. The page header and open-tool text show those paths, and comparison files are written under the real records directory.

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

The descriptions above are source-checked page behavior. A standalone browser render establishes layout at that scope. Native acceptance of all 22 operations in Claude Code Desktop and Codex Desktop is pending. The [current validation baseline](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) records the measured candidate and remaining evidence. Use [MANUAL-TESTS.md](MANUAL-TESTS.md) to compare receipts with actual host effects and saved records.
