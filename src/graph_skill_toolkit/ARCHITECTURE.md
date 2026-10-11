# Graph Skill toolkit architecture

The toolkit owns host delivery: shared instructions, runtime command installation, graph presentation and their local lifecycle. Its source root is `src/graph_skill_toolkit/`, directly beside `src/graph_skill_runtime/`, the independently installable Python execution engine. A responsibility module has its own directory even when its implementation occupies one file. The [current validation baseline](VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) owns required results and acceptance; [PROTOTYPE.md](PROTOTYPE.md) owns the current shared-interface and host-operation contract. The [structure decision](INSTALLATION-DECISIONS.md#toolkit-source-structure-decision-2026-10-10) retains source-layout rationale.

## Source navigation

```text
src/
├── graph_skill_runtime/       Python runtime, SDK, CLI and runtime MCP tools
└── graph_skill_toolkit/       Host delivery and installation
    ├── app/                  React browser entry and adapter selection
    ├── ports/host/           Typed host actions, capabilities and results
    ├── ui/
    │   ├── template/         One HTML structure and styles
    │   ├── canvas/           Validation, graph types and one React renderer
    │   └── workbench/        Selection, test controls and operation receipts
    ├── adapters/
    │   ├── codex/
    │   │   ├── browser/     Host operation translation
    │   │   ├── resource/    Host-facing display-mode metadata
    │   │   ├── session/     Per-connection, per-root view identifiers
    │   │   └── transport/   Bounded MCP Apps browser protocol
    │   └── claude/
    │       ├── browser/      Embedded snapshot and bridge client
    │       ├── bridge/       MCP-owned HTTP pages and operation relay
    │       ├── preview/      Pure shared-template snapshot rendering
    │       ├── preview_configuration/  Owned project launch entry
    │       └── mod/          Host operations, polling and preview guidance
    ├── server/               Canvas MCP tools and resource delivery
    ├── presentation/         Selected business document identity
    ├── skill_source/         Explicit business-root reading
    ├── projection/           Source graph to presentation graph
    ├── demo/                 Labeled demonstration graph
    ├── hooks/                Follow-up guidance after relevant tool use
    ├── installer/            Acquisition, ownership and installation
    ├── scripts/              Build, preview and acceptance entry points
    ├── bin/                  Global command dispatch
    ├── npm/                  Lightweight npm distribution inputs
    ├── skills/               Discoverable host instruction assets
    └── tests/                Toolkit regression evidence
```

`ui/template/canvas.html` owns the HTML shell and styles. `ui/canvas/index.mjs` validates presentation data, `ui/canvas/types.ts` defines its types, and `ui/canvas/view.tsx` is the single graph renderer. `ui/workbench/index.tsx` owns graph selection, nine test controls and correlated operation results. `app/main.tsx` mounts the common React interface and selects exactly two browser adapters through the contract in `ports/host/index.ts`. Codex's `browser/index.mjs` translates actions; `resource/index.mjs` owns display metadata; `session/index.mjs` owns reusable view identifiers; `transport/index.mjs` owns browser protocol and connection teardown. Claude's adapter is `adapters/claude/browser/index.mjs`; its `preview/publisher.mjs` renders snapshots as a pure computation, `bridge/server.mjs` owns HTTP pages and operations, `preview_configuration/index.mjs` owns the project launch entry, and the Mod translates host events and actions. `server/main.mjs` owns the canvas MCP use-case order and selected-root inspection, while `skill_source/files.mjs` reads the explicitly selected root and `projection/graph.mjs` constructs presentation data. `presentation/index.mjs` gives that root's actual `SKILL.md` one absolute path and encoded file URL for both hosts. Runtime compilation remains the authority for the full portable format.

The installer has one directory per responsibility:

| Directory | Owned responsibility |
| --- | --- |
| `download/` | Release selection, transfer and checksum verification |
| `archive/` | Safe archive validation and extraction |
| `discovery/` | Read-only client evidence and target selection |
| `hosts/` | Host projection inventories and configuration shapes |
| `ownership/` | Recorded resource identity and conditional write/rollback rules |
| `locking/` | Installer serialization and abandoned-process checks |
| `runtime_layout/` | Installation root and private-runtime paths |
| `runtime_payload/` | Pinned interpreter inputs and private-runtime provisioning |
| `install/` | Installation, update, status, cleanup and uninstall ordering |
| `entry/` | Bounded isolated-Python command bootstrap |
| `bundle/` | Source-bound complete platform archive assembly |
| `verify_bundle/` | Archive inventory and source correspondence inspection |

Python responsibility packages use `__init__.py`; `bundle/` and `verify_bundle/` also have `__main__.py` command entry points. `runtime_payload/runtime-lock.json` owns interpreter pins. `scripts/build/main.mjs`, `scripts/pack_installer/main.mjs`, `scripts/preview/main.mjs` and `scripts/check_codex/main.mjs` own their named operations. Small bootstrap files dispatch to these owners rather than reproducing their logic.

## Shared view and host delivery

HTML is the webpage containing the graph, styles and browser interactions. MCP, the Model Context Protocol, carries host tool requests and results. An MCP App attaches an interactive webpage to a tool result for a supporting host. Codex receives the common page through this channel. Claude receives the same template and executable UI with current graph/root JSON and browser connection data inserted into one slot, served from the same HTTP origin as its operation bridge. An origin identifies a protocol, host and port. React composes this page from reusable components; TypeScript checks its data and operation interfaces during development.

A Mod is a plugin whose event handlers run inside Claude Code. The Mod reads `$.session.root()` to select the actual preview project's launch configuration, separately from the business `skill_root`. It verifies that the returned document identifies the selected business root's `SKILL.md`. Its ordered guidance inventories tabs, attaches HTTP and retains the actual returned tab identity, then opens or reuses the actual document if it is absent or the pane is hidden. Navigation and final selection target the retained HTTP tab. A subsequent inspection must establish the displayed pane, active canvas, retained exact document and preserved pre-existing pages. Both useful tabs remain open. The [manual guide](MANUAL-TESTS.md) gives the observation procedure. The Mod also polls the authenticated per-root loopback bridge for explicit page actions. Draft filling uses the host's append interface. Canvas send carries saved same-root selection as labeled JSON, and the ordinary prompt hook supplies context to normal submissions. Tool listing reads the live fixed allowlist. Fixed inspection submits one normal host prompt and returns an accepted page receipt; the conversation owns the actual tool call, permissions and graph result. Browser and Mod credentials grant different operations. The MCP process owns HTTP, receipts and temporary preview configuration; the Mod owns polling, host calls and context added to the next prompt. Session end disconnects the view and clears Mod state; a later graph display can restart polling. The [prototype contract](PROTOTYPE.md#host-and-delivery-constraints) defines operation and unknown-outcome semantics.

Codex's normal Skill guidance opens or reuses the selected root's actual `SKILL.md` through a standalone host `open_in_codex` invocation with the exact path and `line=1`. After its response, a separate invocation calls `show_graph` as the final presentation. The calls occupy distinct tool batches; the [focus decision](evidence/codex-native-20261011/focus-decision.md) owns the evidence and alternatives. The host owns visibility and focus; a queued file-open request establishes a pending action. Page loading itself performs no file-opening or focus action. Follow-up guidance coalesces one display per relevant operation/root and excludes file-preview, navigation and canvas controls from recursive display.

The Codex resource owner supplies `availableDisplayModes=["fullscreen"]` and `preferredDisplayMode="fullscreen"` through resource listing and reading. Fullscreen names the host's canvas-sidebar mode. The session owner assigns one opaque `widgetSessionId` for each canonical business root within one server connection; the host additionally scopes reuse by conversation, server and resource identity. The host owns opening, hiding, reopening, tab identity and disposal. The [closed-canvas decision](evidence/codex-native-20261011/closed-reopen-decision.md) records the prior inline-retention failure and the sole-mode choice. The shared page's rendering and action owners remain independent of that metadata.

Codex's browser adapter appends drafts only when the host advertises the draft-message extension, stores selected context through the host's model-context interface, and calls only the fixed originating-server inspection tool. Its host-wide tool-list capability is explicitly unavailable. Document opening uses the advertised file interface; folder opening requests an agent action. Transport teardown removes its window listener and settles pending requests as unknown outcomes; closed transports reject new actions before sending. These responsibilities remain separate from host session disposal and from the server connection's view-identifier map.

A subsequent graph call replaces the in-memory snapshot at the active view URL; the next normal navigation loads current content. Source changes between calls have no automatic watching guarantee. The preview configuration owner merges one URL-only entry into the actual host project's `.claude/launch.json`, preserving unrelated content and rejecting changed or redirected owned resources. Normal shutdown closes HTTP sockets and removes only unchanged owned configuration, preserving external edits. The business `SKILL.md` remains user-owned and is read for display. The `inspect_graph` tool only reads presentation data for a canonical root already selected in the same connection; it also returns the document identity and leaves runtime compilation and preview mutation outside its operation.

Codex's `transport/` implements the required MCP Apps `2026-01-26` subset while the server and interoperability tests retain the official SDK. The [bundle measurement](evidence/prototype-bundle-size.json) records the historical size reason for selecting that subset. Claude HTML presentation checks the actual `SKILL.md` against the host file loader's 524,288-byte limit before creating its view; oversized documents receive an explicit error. HTTP graph delivery has no such file-loader bound. The compact transport retains its measured and tested subset; the [AppBridge tests](evidence/prototype-mcp-transport.log) establish measured protocol exchanges within that scope. Native host observations supply the separate evidence below. Unknown outcomes stay pending for inspection.

The [current native acceptance](VALIDATION.md#native-result-and-decision-basis) establishes the measured required effects in both hosts. Claude retains its named-candidate button effects, document/canvas display, ordered hidden/visible ordinary-edit follow-up, unrelated-page preservation and fresh-session operation. Its ended-page ready header can remain stale beside a failed-action error; automatic tab retirement remains unverified. Codex has actual current-stage loading, closed/repeated display and ordinary-edit activation, with scoped reuse of unchanged button and real second-task isolation evidence. Its directory effect uses Windows Explorer, and its rename observation establishes the updated visible heading while the group accessibility description stayed stale. The [manual tests](MANUAL-TESTS.md) own individual results and limits. Agents may use Computer Use when needed and must release control immediately after use and while waiting. The [prior reveal implementation](evidence/dual-view-candidate/retired-preview-entry.mjs.txt) and its [tests](evidence/dual-view-candidate/retired-preview-entry.test.mjs.txt) remain historical evidence.

## Source, payload and session identities

A source folder identifies where contributors maintain a responsibility. A generated payload identifies the files installed for a particular candidate. A host session identifies the server, instructions and Mod actually loaded. Moving source does not prove that an installed payload or an existing session has changed.

The current `0.3.4` source contains the shared-page prototype; the recorded installed global payload remains `0.3.3`. Claude's isolated project stage has the scoped native acceptance linked above. Codex user and project configurations point to an immutable `0.3.4` stage, and its actual Desktop process and resource inventory separately establish loading. [VALIDATION.md](VALIDATION.md#candidate-identity-and-evidence-applicability) owns exact byte bindings and the single-metadata-change applicability analysis. The native phase is attained within those measured scopes. The parent goal remains partially attained pending frozen-source gates, release artifacts, installed acceptance and publication. The full graph editor is future work.

The build keeps generated `dist/canvas.html`, `dist/server.mjs`, `dist/after-tool.mjs` and `dist/installer.mjs`. The installer maps `adapters/claude/mod/` to the existing payload member `claude-mod/`, preserving its installed resource-ownership contract. This mapping has one source owner. Packaged Python installer modules retain `installer/<module>/` directories, with the lifecycle command at `installer/entry/main.py`. The bundle inventory includes `README.md`, `PROTOTYPE.md` and `MANUAL-TESTS.md`, so packaged usage links reach the operation contract and native procedure. Local ignored evidence remains a separate review resource and may be absent from public source and product archives.

The Python wheel includes only `graph_skill_runtime`; the Python source distribution explicitly excludes this toolkit. Toolkit platform archives and its npm bootstrap retain their separate distribution boundary. Relocated source and packaged documents create a new candidate identity; prior source-bound archives, hashes and native observations retain their original scope.

The toolkit's `package.json` is the version owner, including browser adapter metadata. A source or npm bootstrap delegates lifecycle operations on an existing installation to that payload's own command entry. This lets the installation owner resolve its recorded layout; the incoming bootstrap does not assume that an older payload already has the new Python module paths. Explicit install/update still uses the incoming candidate's preflight and ownership rules.

The initial file-browser discrepancy came from different checkouts. `D:/coding/graph-skill-runtime` was the main checkout; implementation was in the managed task worktree at `C:/Users/test/.codex/worktrees/toolkit-release-0-3-2/graph-skill-runtime`. The current task worktree exposes the adapter directory at `src/graph_skill_toolkit/adapters/`. Verify the opened checkout and revision when browsing source; folder names alone establish neither loaded host behavior nor release acceptance.
