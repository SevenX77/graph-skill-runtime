# Plugin Base and Interface Lab

> Since 2026-11-07 the Plugin Base this record names is the separate package Hostpane; see [the extraction decision](hostpane-extraction-2026-11-07.md). Paths below are as of this record's date.

Date: 2026-10-14. The toolkit has one closed, business-independent Plugin Base, two business apps and one composition root. The Plugin Base implements 17 host interfaces and 5 local capabilities. The apps are the Graph Skill canvas and the separate Plugin Interface Lab. Source-level checks are recorded in the [validation ledger](../../src/graph_skill_toolkit/VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14). Native acceptance of all 22 operations on both hosts is pending.

## Goal and authority

A plugin page displayed inside a desktop coding-agent host needs a reusable foundation for interaction with the current conversation and the local machine. That foundation must expose a bounded public interface and enough usage documentation for a developer to build a business app independently of its internals. Each operation must expose evidence that a developer can compare with the actual effect.

The Graph Skill canvas owns Graph Skill presentation. The Plugin Interface Lab owns developer testing of the foundation. The toolkit composes both apps into one plugin process and one Claude Mod. The user rules on goals, principles and required effects. Coding agents own implementation choices within those rules. Native observation is performed through the manual procedure and reviewed at the measured candidate's scope.

This decision owns user rulings, selected design and rationale, implementation status, acceptance criteria and open items. The [Plugin Base usage document](../../src/graph_skill_toolkit/plugin_base/README.md) owns construction and the full operation reference. [ADAPTER.md](../../src/graph_skill_toolkit/ADAPTER.md) owns host connection and route mappings. [ARCHITECTURE.md](../../src/graph_skill_toolkit/ARCHITECTURE.md) owns module placement, process composition, routes and lifecycle. [PROTOTYPE.md](../../src/graph_skill_toolkit/PROTOTYPE.md) owns visible behavior. [MANUAL-TESTS.md](../../src/graph_skill_toolkit/MANUAL-TESTS.md) owns native observation. The validation ledger owns dated measurements.

## Terms

- **Host** is the desktop application that runs the agent session and displays a plugin page: Claude Code Desktop or Codex Desktop.
- **Plugin Base** is the closed reusable module at `src/graph_skill_toolkit/plugin_base/`.
- **Business app** is a plugin function with its own tools, page and instruction assets. The canvas and the Interface Lab are the toolkit's two apps.
- **Composition root** is the code that assembles those apps into one process and one Claude Mod.
- **MCP (Model Context Protocol)** carries tool and resource requests between a host and a plugin server. This toolkit uses standard input and output, or stdio.
- **MCP App** is the MCP extension that lets Codex display the plugin's HTML resource inside its own frame and carry page messages. The toolkit uses `@modelcontextprotocol/ext-apps` 2.0.3.
- **Claude Mod** is JavaScript hook code loaded inside a Claude Code session, with host API calls through the `$` argument.
- **Browser pane** is Claude Code Desktop's web-tab panel. Claude plugin pages are local HTTP pages shown there.
- **Host bridge** is the authenticated local HTTP channel between a Claude page and its Mod. The listener uses loopback address `127.0.0.1`, which refers to the same computer.
- **Host interface** is an operation that asks the host for an effect or information, including host events.
- **Local capability** is an operation whose effect belongs to the plugin's Node process. Codex transports its page calls through MCP; Claude transports them through HTTP.
- **Granted root** is a directory the server grants to a session's local connection through `allow(root)`.
- **Evidence** is an operation's payload record, raw receipt, read-back observation and applicable limits. Its four display slots may contain empty values.
- **Effort** is a model turn's reasoning-effort setting. The Plugin Base accepts the five strings `low`, `medium`, `high`, `xhigh`, `max` for a specified effort.
- **Skill** is a host-discoverable instruction asset containing `SKILL.md`.
- **Source test mode** registers a built source checkout in installer-owned host profiles. **Installed mode** registers the active release payload.

## Sources: user rulings


Each ruling is quoted verbatim with an English gloss.

1. 2026-10-12, transcribed from the scope record `evidence/native-launch-20261012/interface-scope-correction.md`, lines 11–12. The evidence-availability item below states this source's current location boundary:
   - 「“任何外部编辑器保存文件，都立即自动弹出”不需要实现这个功能」 — "Automatic opening whenever any external editor saves a file does not need to be implemented."
   - 「“或系统文件管理器打开目录”，没有这个要求，只要求宿主的文件管理器打开浏览器，定位到目录」 — "There is no requirement for the system file manager to open the directory; the requirement is that the host's own file browser opens and locates the directory."
   This ruling establishes directory reveal inside the host's own file browser as a host interface.
2. 2026-10-14: 「“而系统资源管理器已被你排除在要求之外”，加回来，但这是另外独立的接口功能。」 — "Add the system file manager back into the requirements, as a separate, independent interface function." Revealing a path in the operating-system file manager is required as its own function.
3. 2026-10-14: 「提交消息需要同时提交执行消息的模型和effort配置，可以指定、默认或者用当前session的配置。」 — "Message submission must carry the model and effort configuration that execute the message: specified, default, or the current session's configuration."
4. 2026-10-14: 「“设置上下文（context.set）和移除上下文（context.remove）”的应用场景是什么？……考虑必要性，是否去掉。」 — "What is the scenario for set context (context.set) and remove context (context.remove)? ... Consider whether they are necessary and whether to remove them." The coding agent selects one whole-snapshot `context.update` operation for the scenario and rationale stated below.
5. 2026-10-14: 「读写文件、监听本地文件和打开外部浏览器或系统资源管理器作为插件通用功能，不属于插件与宿主接口。这些与业务无关的插件开发底座能力需要成为一个闭包模块，放在一个模块文件路径里，只向外部暴露接口和接口使用说明。」 — "Reading and writing files, watching local files, and opening the external browser or the system file manager are general plugin functions and belong outside the plugin-host interfaces. These business-independent plugin foundation capabilities must form one closed module at one module path that exposes only its interfaces and their usage documentation."
6. 2026-10-14: 「我说的插件底座包括Claude和codex的接口」 — "The plugin base I mean includes the Claude and Codex interfaces."
7. 2026-10-14: 「做一个专用的接口测试页面和skill，不要和show graph混在一起」 — "Build a dedicated interface test page and Skill; keep it separate from show graph."
8. 2026-10-14: 「每一个接口测试的效果都要有显式的结果做对照，测试页面要给出文字详细提示，比如提交消息codex无法指定模型字段，上下文接口悄悄发了什么上下文，把发送的上下文结果挖出来给开发者看到」 — "Every interface test's effect needs an explicit result to compare against. The test page must give detailed textual guidance, for example that Codex message submission cannot specify the model field, and what context the context interface silently sent; dig out the sent context and show it to the developer."
9. Standing requirements from 2026-10-12 and 2026-10-13, recorded in [`evidence/prime-interface-20261013/brief.txt`](../../src/graph_skill_toolkit/evidence/prime-interface-20261013/brief.txt): one shared HTML page serves both hosts through a Codex adapter and a Claude adapter; writing a draft fills the composer without sending; a direct tool call is distinct from sending a message; an interface that cannot be connected states its reason; a host interface is implemented through the host's own route, without an agent-delegated or operating-system-window substitute.
10. Standing rule of 2026-10-14: the canvas is the single owner of Graph Skill presentation ([`canvas-single-presentation-owner-2026-10-14.md`](canvas-single-presentation-owner-2026-10-14.md)).


## Verified premises and evidence limits

The current [catalog](../../src/graph_skill_toolkit/plugin_base/ports/host/catalog.mjs), [local definitions](../../src/graph_skill_toolkit/plugin_base/local/definitions.mjs), [process runner](../../src/graph_skill_toolkit/plugin_base/server/serve.mjs), [composition](../../src/graph_skill_toolkit/composition/server.mjs) and app sources establish module names and implemented behavior. The [message validator](../../src/graph_skill_toolkit/plugin_base/host_interfaces/conversation/submit_message/index.mjs) accepts the five effort strings in Terms. A numeric host declaration supplies no additional Plugin Base input variant.

The installed MCP Apps library declares whole-snapshot context updates for future turns, with no immediate response. Its message request has role, content and metadata fields, with no per-message model or effort field. The Codex adapter therefore supports the current session selection only. Codex Desktop 26.1007's page connection policy admits `https` and `wss`, which motivates the page-only MCP routes for graph and local data. [The live-graph transport decision](live-graph-transport-2026-10-14.md) owns that policy finding.

The Claude implementation uses prompt-submission context blocks and main-agent turn-step overrides. A saved early-access Claude Code 2.1.277 declaration snapshot was inspected during design. Its external evidence location is listed under Open items. Verification against the installed Mod API and native hook execution remains open. Current source and fake-host checks establish the implementation's behavior under the tested declarations.

A live Claude Desktop tool-description inspection reported on 2026-10-14 distinguishes native file-pane opening from operating-system file-manager reveal. A route for directory reveal in the host's own file browser remains unconfirmed. Historical Browser-pane findings have their stated version and candidate scopes in the validation ledger. These observations supply premises for adapter limits; native acceptance of the current 22-operation set remains pending.

## Decisions and rationale

### 1. Closed Plugin Base

All business-independent plugin foundation lives in `plugin_base/`. Its public surface consists of [the page entry](../../src/graph_skill_toolkit/plugin_base/page/index.mjs), [page type declarations](../../src/graph_skill_toolkit/plugin_base/page/types.ts), [server entry](../../src/graph_skill_toolkit/plugin_base/server/index.mjs), [Claude Mod entry](../../src/graph_skill_toolkit/plugin_base/claude_mod/index.js) and [usage documentation](../../src/graph_skill_toolkit/plugin_base/README.md).

The browser, Node server and Claude Mod have separate runtime entries, with a type-only page companion. External production code imports these entries. Internal code imports its own modules, third-party packages and Node built-ins. [The closure test](../../src/graph_skill_toolkit/tests/plugin_base/closure.test.mjs) enforces both directions. One closed module gives host mappings, presentation, local operations and process helpers a single reusable owner. The module map belongs to ARCHITECTURE.md, and the export reference belongs to the usage document.

### 2. Shared plugin process and composition

`servePlugin({ serverInfo, apps })` creates the listener, host bridge and local executor once per process, and calls each app factory once. Per MCP session it creates the server and one local connection, registers apps, then registers page-only local tools and the page-tool inventory. The apps share session grants through that local connection. Process shutdown releases app resources and shared services. [ARCHITECTURE.md](../../src/graph_skill_toolkit/ARCHITECTURE.md#plugin-process-and-composition) owns the exact composition and lifecycle.

The toolkit composition always includes the canvas. It enables the lab when `GRAPH_SKILL_INTERFACE_LAB=1`. One process gives every shared service one lifecycle owner, while separate apps preserve distinct business responsibilities. Source test mode sets the lab switch and registers its Skill for both hosts. Installed mode selects the canvas release projection.

### 3. Host interfaces and honest capability boundaries

The [17-interface reference](../../src/graph_skill_toolkit/plugin_base/README.md#host-interface-reference) owns the complete vocabulary and operation details. Every interface has a shared definition and one implementation per host. The facade refreshes confirmed identity and capability before dispatch. [ADAPTER.md](../../src/graph_skill_toolkit/ADAPTER.md#identity-authority-and-facade-behavior) owns this authority boundary and the route table.

The catalog preserves required effects even when their current route is unknown. `files.revealDirectory` targets the host's own file browser; `local.system.revealInFileManager` targets the operating system. Each retains its independent result. A direct tool call returns the native tool response, while message submission starts conversation work. View handles name only views opened for the calling page.

Message submission carries model and effort selections with sources `current`, `default` or `specified`. The validator accepts specified effort values as the five strings in Terms. Claude implements a specified selection for the single main-agent turn started by the submitted text. Codex accepts current settings only. Each unsupported selection returns its declared limit without sending a message. The open items track correlation and host-default discovery.

`context.update` supplies one whole snapshot for the next turn; `{}` clears it. A selected canvas node is a motivating use: a later user prompt can refer to that selection without sending a message on every click. A draft requires visible composer content, and a tool requires the model to request the state. Whole-snapshot context provides model-visible page state without triggering a reply. One operation covers setting and clearing because the MCP Apps context contract uses whole-snapshot overwrite. This is a reusable foundation scenario; the current canvas's visible behavior is defined by PROTOTYPE.md.

### 4. Local capabilities

The [five-capability reference](../../src/graph_skill_toolkit/plugin_base/README.md#local-capability-reference) owns reading, writing and watching files, opening a system browser and revealing a path in the system file manager. The Node process owns those effects. File operations check granted roots; URL opening uses its own URL validation. Host-specific transport carries page requests to the same executor.

The canvas's own reading, compilation and observation belong to its server-side business logic. They use Node directly. Page local capabilities provide bounded access from pages to the local machine. This separation keeps graph interpretation with the canvas and reusable file operations with the Plugin Base.

### 5. Evidence and observation

Results from host invocation and local calls carry evidence. The facade and local client populate payload records and limits; native receipts and read-back observations occupy the other slots when available. The Interface Lab displays all four slots for every call. The [usage reference](../../src/graph_skill_toolkit/plugin_base/README.md#results-and-evidence) specifies optional fields, convenience methods and status meanings.

Receipt, read-back state, visible effect, model consumption and business outcome are distinct observations. Claude's later `context.attached` and `turn.completed` events add evidence about attached blocks and applied overrides. The lab records the developer's comparison alongside the call evidence. This meets the requirement for explicit comparable results while preserving the uncertainty of accepted and pending calls.

### 6. Separate canvas and Interface Lab apps

The canvas owns graph display, selected-node details and host/version status. The Interface Lab has its own presenting tool `open_interface_lab`, page and `plugin-interface-lab` Skill. Its `lab_echo` tool provides a bounded direct-tool-call target. [PROTOTYPE.md](../../src/graph_skill_toolkit/PROTOTYPE.md) owns both pages' visible controls and the lab's state locations.

The lab must list all 22 operations with purpose, both hosts' expected effect, checking guidance, current capability and limits, editable arguments and presets. Every call must show its result and all four evidence slots. Context update must expose sent text and a model-echo probe. The event log must show host events and local changes. Each call must offer matches, differs or not observed with a note and save comparisons in the records file. A dedicated page keeps developer testing separate from business graph presentation.

## Implementation status

The implementation is on branch `claude/toolkit-host-interfaces`. Its sequence is recorded here for source identity:

| Commit | Implemented result |
| --- | --- |
| `f6dbba98` | Decision record. |
| `3773e6f6` | Host code in `plugin_base/` and graph code in `apps/graph_canvas/`. |
| `29557f9b` | Closed entries and closure test. |
| `e1061429` | 17-interface catalog, evidence and host events. |
| `514ae7f5` | Local capabilities, process runner, composition, Interface Lab and source-mode registration. |

The [usage document](../../src/graph_skill_toolkit/plugin_base/README.md) is present and covers all 22 operations and plugin construction. The adapter and application-map documents describe the Plugin Base layout. Build output placement is owned by [ARCHITECTURE.md](../../src/graph_skill_toolkit/ARCHITECTURE.md#build-outputs). The [current validation baseline](../../src/graph_skill_toolkit/VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) records the checks against `514ae7f5` content and the observed source-mode configuration.

The [2026-10-15 native observation](../../src/graph_skill_toolkit/VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) covers the five local capabilities on Claude Desktop with Claude Code engine `2.1.295` on Windows `10.0.26200`. The running server came from the build preceding `f58fd018`; the session's Mod predates `99787b80`. File reading, watch startup, writing and the external browser have observed effects. File-manager reveal has a recorded mismatch caused by filesystem redirection. The real-path behavior in `f58fd018` is source-tested. A new session must load that server and the Mod payload reader from `99787b80` before native confirmation of reveal and the 17 host interfaces. All 22 operations on Codex Desktop remain unobserved. The validation ledger owns the per-call results, source-check counts and remaining observation requirements.

## Acceptance criteria

Source checks establish their tested contracts. Native effects require candidate-bound observation through the [manual procedure](../../src/graph_skill_toolkit/MANUAL-TESTS.md).

| Criterion | Required evidence | Source evidence | Native observation | Stop condition |
| --- | --- | --- | --- | --- |
| The Plugin Base is closed. | Four allowed entry files and both dependency directions enforced. | Present: closure test passes. | Not applicable. | An import crossing the boundary. |
| The usage document is complete. | All 17 host interfaces and 5 local capabilities have arguments, effects, per-host behavior, limits and evidence; plugin construction is explained. | Present: usage document covers all 22 operations and its links resolve. | Not applicable. | A missing operation, reference field or link target. |
| One process serves both apps under the declared switch. | Shared listener, bridge and local executor; canvas always enabled and lab source-test-only. | Present: composition source and protocol test. | Pending. | Duplicated shared owners or lab registration in installed mode. |
| The canvas keeps its business behavior. | Graph, selection, diagnostics and host/version status follow their page and tool contracts. | Present: canvas and integration tests. | Pending on both hosts. | Lab controls in the canvas or a contract mismatch. |
| The Interface Lab is independent and complete. | Its own tool, page and Skill expose all 22 operations and the required guidance. | Present: guide test, protocol test and standalone browser render. | Claude Desktop: the lab page served five local calls; host connection awaited a new-session Mod. Full coverage remains pending on both hosts. | A missing operation, page or guidance item. |
| Each call exposes comparable evidence. | Four displayed evidence slots, context readout/probe and a durable comparison. | Present: result construction and page source. | Claude Desktop: five saved local-call entries, including browser `matches` and reveal `differs`; the three file-call verdicts are `null`. Host-call coverage and Codex remain pending. | Missing evidence display or false inference of an effect. |
| Local file access respects granted roots. | Rejection outside grants through both transports. | Present: local tests and protocol integration. | Pending on both hosts. | A file effect outside the granted scope. |
| Native acceptance is recorded. | Per host and operation: invocation, evidence, visible effect or declared unsupported state, and comparison note in a saved record. | Not applicable. | Partial: five local capabilities observed on Claude Desktop's earlier running build; fixed reveal, 17 Claude host interfaces and all 22 Codex operations remain pending. | Missing coverage or an unbound candidate. |

## Open items

The [2026-10-16 Claude connection verdicts](interface-connect-verdicts-2026-10-16.md) own the current host-interface decisions, dated native findings and displayed-window re-observation requirements.

Each item names the evidence that settles it.

- **Native acceptance on both hosts.** The [2026-10-15 record](../../src/graph_skill_toolkit/VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) supplies five local-capability observations on Claude Desktop's earlier running build, including the failed reveal. Settling evidence: a new Claude Desktop session loads the real-path server and the Mod payload reader, confirms reveal and covers the 17 host interfaces; a Codex Desktop session covers all 22 operations. Each host's saved comparison must include the actual effect or declared unsupported state and notes, accompanied by candidate identity and supplemental observations.
- **Graph-credential lifetime.** Each MCP-session registration creates a graph connection with `close()`. Session end has no caller for that method, so the credential lasts until process shutdown; stdio serves one session per process. Settling evidence: lifecycle ownership that revokes a session's graph credential at session end, with a regression showing rejection after revocation. [ARCHITECTURE.md](../../src/graph_skill_toolkit/ARCHITECTURE.md#local-graph-data-and-authorization) owns the current lifecycle.
- **Claude turn correlation.** Specified settings bind by text matching to the next `turn.start`. Identical submissions close together can bind ambiguously. Settling evidence: a host correlation key for the turn started by `prompt.submit`, and a native record tying the requested and applied override to that turn.
- **Host default model and effort.** `default` remains unsupported on both hosts. Settling evidence: a verified host API or owned configuration source that reports those defaults.
- **Installed Claude Mod API.** Settling evidence: installed-version declarations or native execution of prompt-submission context, turn-start, turn-step and turn-completion hooks.
- **Codex per-message model or effort.** Settling evidence: a documented or observed extension field with this per-message effect.
- **Host file-browser directory reveal.** Settling evidence: a native host route that locates a directory in that host's own file browser.
- **Hidden Claude Browser pane.** Settling evidence: a host route that displays the hidden pane while preserving the selected page and unrelated views.
- **Historical native-source availability.** `evidence/native-launch-20261012/` is absent from this branch. The scope quotation in ruling 1 and the saved Claude Code 2.1.277 declaration premise above refer to that external record. Settling evidence: the exact source files made available in a reviewable branch location with their identity preserved.

## Validation scope

The current documentation describes source-checked implementation and separates it from native observation. The validation ledger owns the 2026-10-14 typecheck, build, 184 Node test passes, 51 installer test passes, Mod validation and warning, standalone lab render and source-mode switch. The browser render occurred outside an agent host. The reported mode status establishes configuration, with host loading pending.

The [2026-10-15 observation](../../src/graph_skill_toolkit/VALIDATION.md#native-observation-of-the-local-capabilities-on-claude-desktop-2026-10-15) adds native evidence for five local capabilities on Claude Desktop's earlier running build. The real-path reveal implementation has source-test evidence; its packaged-host effect requires a new-session observation. Complete native acceptance of the 22-operation set and installed-version Mod host-interface behavior remain open. Release, publication and merge have their own authorization and acceptance boundaries.

## Revision log

- 2026-10-14: Created. Records the Plugin Base as one closed module with three runtime entries and a usage document, the 17-operation host interface catalog, the 5 local capabilities, the evidence record on every call, the Graph Skill canvas and Interface Lab as business consumers, the Interface Lab page requirements, the implementation order, acceptance criteria and open items.
- 2026-10-14: Revised to the implemented design on branch `claude/toolkit-host-interfaces` (commits `3773e6f6` to `514ae7f5`), adding the plugin process and composition decision, the local capability transports and scope, the implementation status with its verification results, and the per-row source and native evidence in the acceptance criteria.
- 2026-10-14: Synchronized the eight-document set with the implemented layout, recorded the completed usage reference, specified five-string effort validation and added the graph-credential lifetime open item.

- 2026-10-15: Recorded the first five local-capability observations on Claude Desktop, the filesystem-redirection finding, the source-tested real-path behavior and the remaining new-session and Codex Desktop observation scope.

- 2026-10-16: Linked the Claude host-interface connection decision and its native re-observation scope.
