# Claude host-interface connection verdicts

Date: 2026-10-16.

## Goal and scope

Every host interface exposed by the Plugin Interface Lab gives a definitive answer on Claude Code Desktop: a supported host route with explicit operating conditions, or an unavailable route with the exact host limitation. Each invocation preserves enough evidence to compare its reported status with its actual effect.

This record owns the connection decisions, their rationale, the Claude interface verdicts and the dated evidence that motivates them. The [Plugin Base reference](../../src/graph_skill_toolkit/plugin_base/README.md) owns operation arguments, statuses, evidence fields, transport bounds and waiting semantics. The [manual procedure](../../src/graph_skill_toolkit/MANUAL-TESTS.md) owns native observation. [Page behavior](../../src/graph_skill_toolkit/PROTOTYPE.md) owns the lab display and scratch-file locations. The [Plugin Base design](plugin-base-and-interface-lab-2026-10-14.md) owns the shared foundation and app boundaries.

The decisions below define the current contract. The dated observation describes the candidate that produced its saved record. Acceptance of the implementation requires the source checks and fresh native observations specified below.

## Terms

- **Mod** is the Claude-side plugin component loaded at session start. It registers hooks and executes host calls through Claude Code's `$` interface. The toolkit's Mod identity is `graph-skill-canvas-mod`.
- **Bridge** is the loopback HTTP owner between the page and the Mod. Loopback means the connection stays on the same computer. The bridge owns queued host requests, their identities and their receipts.
- **Page context** is text the model reads beside a prompt, hidden from the user. The page stores a snapshot through `context.update`. Inline context delivery is the visible transcript representation used for the plugin's own message submissions on Claude.
- **Slash-command submission** is a prompt whose text starts with `/` followed by a command or Skill name and optional input. A Skill is a host-discoverable instruction asset. Claude processes the submission through its conversation command route.
- **Nominal path** is the filesystem path the process requests. **Real path** is the on-disk location returned by filesystem resolution. A packaged Windows host can redirect a nominal path into its private storage.
- **Interface Lab** is the dedicated developer page that exercises the Plugin Base's 17 host interfaces and 5 local capabilities. Host interfaces ask Claude for information or an effect. Local capabilities execute in the plugin server process.
- **Native observation** is a comparison against the running host, its transcript or an operating-system surface. A source test establishes behavior under its test inputs and simulated host replies.

## Dated native evidence

The native record is:

```text
C:\Users\test\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\plugin-interface-lab\records\claude-2026-10-16T05-53-51-286Z.json
```

Its schema is `plugin-interface-lab.records.v1`. It contains 21 entries, with `startedAt` equal to `2026-10-16T05:53:51.286Z`. Its confirmed connection identifies Claude Code `2.1.299`, session `891935b6-d7b4-4846-8b83-d6440cc4b865`, through the Mod. The engine identity and the desktop application's About-panel identity have separate observation scopes. The record's notes retain the absence of an attached session window during the file/view checks and the missing screen-control grant.

Coordinates such as `/entries/9` below are zero-based JSON pointers into this exact record. Notes in the saved record are the observer's comparisons. Supplemental transcript and event observations are identified through those notes.

The inspected Claude Code `2.1.299` declaration file is:

```text
C:/Users/test/AppData/Local/Temp/claude/bundled-skills/2.1.299/243f91a0fd25db8f9900ccd388ea9c3a/plugin-authoring/types/claude-code.d.ts
```

The declaration coordinates below identify the relevant types and call contracts. The Mod engine accepts `$` as a plain argument to declared functions in call position; host-facing helpers follow that calling convention.

## Decisions and rationale

### 1. Complete tool lists and result receipts

Claude returns the complete session tool inventory and forwards complete result receipts through the Mod. The bridge applies the process-protection request-body bound owned by the [`tools.list` reference](../../src/graph_skill_toolkit/plugin_base/README.md#toolslist). Result content retains its original structure across the Mod-to-page route.

Evidence: `/entries/9` reports that the 60,000-byte application receipt guard prevented the tool list from returning. Source inspection at repository commit `73091304` located the guard in [the tool-list implementation](../../src/graph_skill_toolkit/plugin_base/host_interfaces/tools/list/claude.mjs) and [Mod result reporting](../../src/graph_skill_toolkit/plugin_base/adapters/claude/mod/lifecycle/index.mjs); [the bridge](../../src/graph_skill_toolkit/plugin_base/adapters/claude/bridge/server.mjs) accepted request bodies up to 64 KiB. `HttpInit`, declaration lines 5291–5324, describes the HTTP body as text and supplies no documented body-size limit. These coordinates establish application-owned limits and the need for a bridge transport guard sized for full receipts.

### 2. Context delivery follows the submitting source

Claude uses hidden page-context attachment for prompts from other sources and visible inline delivery for messages submitted by this plugin. The plugin's own origin passes through its prompt hook unchanged. This preserves one delivery of each context block if the host routes that origin through the hook. The [`context.update` reference](../../src/graph_skill_toolkit/plugin_base/README.md#contextupdate) owns the exact representation and event behavior; [`conversation.submitMessage`](../../src/graph_skill_toolkit/plugin_base/README.md#conversationsubmitmessage) owns submission evidence. Codex retains its native `updateModelContext` route.

Evidence: `/entries/16` records exact hidden-block delivery on a subsequent prompt from another source, and missing delivery on the lab's own submission in `/entries/17`. `PromptSubmitInput.context`, declaration lines 9305–9313, defines the hidden slot. `PromptSubmitArgs`, lines 9204–9217, reserves context for hooks. The `$.prompt.submit` contract, lines 2984–2996, skips the calling hook and identifies plugin origin. [The prompt hook](../../src/graph_skill_toolkit/plugin_base/adapters/claude/mod/hooks/base.js) and [message implementation](../../src/graph_skill_toolkit/plugin_base/host_interfaces/conversation/submit_message/claude.mjs) own the two Claude paths.

### 3. Host-file presets use the session workspace

The lab derives host-file presets from the connected session workspace. Its scratch fixture remains the local-capability test target. [Lab state and comparison files](../../src/graph_skill_toolkit/PROTOTYPE.md#lab-state-and-comparison-files) owns the fixture's purpose and location. The [file observation procedure](../../src/graph_skill_toolkit/MANUAL-TESTS.md#files-draft-message-and-context) owns workspace selection and editing the preset.

Evidence: `/entries/5` records the host rejecting the sandbox file because it was outside the working directory and granted folders. The session's actual roots are recorded in `/entries/3`. Workspace scope and a displayed session are separate preconditions; [status and diagnostics](#5-status-and-diagnostics-preserve-the-hosts-answer) owns the native file-view refusal finding.

### 4. The page follows the existing request to settlement

The Claude driver automatically waits for the existing request's receipt. The bridge marks a final unknown outcome as settled when session disconnection or an identity change closes that request's lifecycle. A transport failure preserves the request identity for a later query. The [waiting contract](../../src/graph_skill_toolkit/plugin_base/README.md#claude-host-operation-waiting-and-evidence-sizes) owns intervals, endpoints and stop conditions. [Page behavior](../../src/graph_skill_toolkit/PROTOTYPE.md#plugin-interface-lab-page) owns the live waiting display and manual recovery control.

Evidence: `/entries/17` required a receipt query to obtain the accepted submission outcome. The `$.prompt.submit` declaration, lines 2984–2996, schedules a plugin prompt once the session is idle. A busy conversation can therefore outlast one bridge response interval. Receipt observation remains separate from sending another operation.

### 5. Status and diagnostics preserve the host's answer

File, draft and view operations report the host's actual refusal or effect. Native-reply errors retain the raw reply in returned data. The [result reference](../../src/graph_skill_toolkit/plugin_base/README.md#results-and-evidence) owns diagnostic preservation. [`files.openFile`](../../src/graph_skill_toolkit/plugin_base/README.md#filesopenfile), [`composer.writeDraft`](../../src/graph_skill_toolkit/plugin_base/README.md#composerwritedraft) and the [view reference](../../src/graph_skill_toolkit/plugin_base/README.md#viewsopen) own operation-specific mappings.

Evidence: `/entries/6` records an accepted label alongside the host sentence “This session isn't open in any window right now, so its view was left alone” and empty views. `/entries/8` records a refused draft with the cause absent from the result shown to the developer. `/entries/12` and `/entries/13` record unrecognized tab-list errors whose results omitted the raw reply. `PromptFillResult`, declaration lines 8864–8876, defines `no_composer`, `dialog` and an absent cause as distinct cases. The saved record supports an unknown cause for that particular draft refusal; the contract preserves a cause when the host supplies it.

### 6. Skill invocation uses the conversation command route

Claude activates a Skill by submitting its slash command through `$.prompt.submit`. Activation and the Skill's reply are checked in the conversation and its subsequent turn event. The [`skills.invoke` reference](../../src/graph_skill_toolkit/plugin_base/README.md#skillsinvoke) owns the command construction, accepted status and submit receipt.

Evidence: `/entries/19` records a direct Skill-tool success receipt with no corresponding Skill load or echo reply in the transcript. The `$.tool.call` declaration, lines 3071–3082, defines a direct tool call. `PromptSubmitInput.command`, lines 9271–9290, identifies submissions that run a slash command. The prompt submission and command execution declarations, lines 2984–2996 and 3124–3135, define the idle-session conversation routes. The selected route supplies conversation work that the observation requires.

### 7. Observation controls use the current connection and explicit inputs

The Mod queues events while a page bridge is connected. The lab renders run-card and event times in local time with the UTC offset. Clearing context uses the required snapshot argument in the [`context.update` reference](../../src/graph_skill_toolkit/plugin_base/README.md#contextupdate). The lab's accepted label states that the effect still needs observation, as specified in [Page behavior](../../src/graph_skill_toolkit/PROTOTYPE.md#plugin-interface-lab-page).

Evidence: `/entries/4` notes pre-connection events and a page clock inconsistent with the observer's local time. `/entries/18` and `/entries/20` distinguish a missing snapshot argument from a successful empty snapshot. The [file-view status finding](#5-status-and-diagnostics-preserve-the-hosts-answer) supplies the distinction between acceptance and observed effects.

### 8. A hidden Browser pane is shown through the host pane tool

On Claude, `views.open` with `activate: true`, and the ordered presentation guidance shared by the canvas and the lab, show a hidden Browser pane once with `mcp__ccd_view__show_pane` and `pane: "preview"`, then read the tab inventory again. The user opens the pane manually only when the pane is still hidden after that request, for example when the session is not displayed in any window.

Evidence (Claude Code `2.1.309`, Claude Desktop `4.29.0.0`, 2026-10-29): with the lab tab active and the pane hidden, `show_pane` with `pane: "preview"` replied `Showing the preview pane.` and the following `tabs_context` reply ended `The Browser pane is currently displayed.` The same call made before any Browser tab existed was refused with `This session's built-in browser has no page open, so there is nothing to show.`

### 9. Native replies are read in the 2.1.309 shape

The Mod reads a native tool reply whose `result` is an array of `{ type, text }` blocks, and reports a host refusal with the host's reason. Evidence: on 2026-10-29 `views.open` and `views.list` reported "宿主没有返回可识别的标签页清单" (gloss: "the host returned no recognizable tab inventory") although the raw reply held the tab JSON inside `result[0].text`; `tools.call` reported a refusal without the host's `deny` text.

### 10. Local paths are checked under a packaged-host redirect

A local-capability target is inside a granted root when its real path lies under the root's real path, or when its nominal path lies under the granted root with no link component between them. Evidence: on 2026-10-29 Claude Desktop's packaged view resolved `...\AppData\Local\plugin-interface-lab\sandbox` to itself but `...\sandbox\sample.txt` to `...\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\plugin-interface-lab\sandbox\sample.txt`, so read, write, watch and reveal of the lab's own sample file were rejected as outside the granted directory. The link-component check keeps a junction or symbolic link inside the root from reaching a target outside it.

## Claude interface verdicts

“Connects” means the current contract provides a host route under the stated conditions. API-availability verdicts apply to the inspected Claude Code `2.1.299` surface; another host build requires its own declaration review and native observation. Fresh native acceptance uses the checks below. “Cannot connect on Claude” identifies a missing host API and produces an explicit unsupported result. File, draft and owned-view operations require a displayed session window; a host report that the session lacks a window yields `rejected` with the host's reason.

| Host interface | Contract verdict | Conditions or reason |
| --- | --- | --- |
| [`host.getInfo`](../../src/graph_skill_toolkit/plugin_base/README.md#hostgetinfo) | Connects | Confirmed live connection. |
| [`host.getCapabilities`](../../src/graph_skill_toolkit/plugin_base/README.md#hostgetcapabilities) | Connects | Confirmed live connection. |
| [`host.getContext`](../../src/graph_skill_toolkit/plugin_base/README.md#hostgetcontext) | Connects | Live session facts. |
| [`events.subscribe`](../../src/graph_skill_toolkit/plugin_base/README.md#eventssubscribe) | Connects | Events from the connected page interval. |
| [`files.openFile`](../../src/graph_skill_toolkit/plugin_base/README.md#filesopenfile) | Connects | Workspace or granted file; displayed session window. |
| [`files.revealDirectory`](../../src/graph_skill_toolkit/plugin_base/README.md#filesrevealdirectory) | Cannot connect on Claude | The file pane opens files only: `show_pane` with `pane: "file"` refuses a directory path as unresolvable and requires a path (observed on `2.1.309`). |
| [`composer.writeDraft`](../../src/graph_skill_toolkit/plugin_base/README.md#composerwritedraft) | Connects | Displayed session with a composer and no blocking dialog. |
| [`conversation.submitMessage`](../../src/graph_skill_toolkit/plugin_base/README.md#conversationsubmitmessage) | Connects | Runs when idle; current or specified settings. |
| [`context.update`](../../src/graph_skill_toolkit/plugin_base/README.md#contextupdate) | Connects | Hidden for other senders; inline for this plugin's messages. |
| [`tools.list`](../../src/graph_skill_toolkit/plugin_base/README.md#toolslist) | Connects | Complete session list within the bridge transport bound. |
| [`tools.call`](../../src/graph_skill_toolkit/plugin_base/README.md#toolscall) | Connects | Session tool and normal host permission checks. |
| [`skills.list`](../../src/graph_skill_toolkit/plugin_base/README.md#skillslist) | Connects | Host confirms a complete listing. |
| [`skills.invoke`](../../src/graph_skill_toolkit/plugin_base/README.md#skillsinvoke) | Connects | Slash-command submission; transcript activation observed separately. |
| [`views.open`](../../src/graph_skill_toolkit/plugin_base/README.md#viewsopen) | Connects | Web view owned by the page; a hidden pane is shown through `show_pane`; displayed session window. |
| [`views.list`](../../src/graph_skill_toolkit/plugin_base/README.md#viewslist) | Connects | Page-owned views; displayed session window. |
| [`views.close`](../../src/graph_skill_toolkit/plugin_base/README.md#viewsclose) | Connects | Existing page-owned view; displayed session window. |
| [`views.requestDisplayMode`](../../src/graph_skill_toolkit/plugin_base/README.md#viewsrequestdisplaymode) | Cannot connect on Claude | The page's container is the Browser pane; the host can show or close it and collapse the sidebar, and has no inline, fullscreen or picture-in-picture route (inspected on `2.1.309`). |

## Acceptance criteria

The implementation owner supplies source evidence. The native observer supplies candidate-bound host evidence through the [manual procedure](../../src/graph_skill_toolkit/MANUAL-TESTS.md). The coordinating reviewer reconciles those results with this contract.

| Required result | Acceptance evidence |
| --- | --- |
| Complete receipts with a bounded transport. | Tests pass a receipt above the observed application guard intact and reject a body above the documented bridge bound. |
| Both Claude context paths and stable Codex behavior. | Hook and message tests establish own-origin skipping, inline blocks and delivery evidence. A fresh native run checks the plugin-submitted probe and a prompt from another source. |
| Correct presets and explicit clearing. | Guide tests resolve the host-file preset to the workspace README and pass an empty snapshot through the required argument. |
| Automatic receipt waiting. | Driver tests cover repeated pending receipts, settlement and transport failure; bridge tests cover disconnected settlement. Native observation retains one request identity through a busy-session submission. |
| Faithful status and diagnostics. | Tests cover an empty file-view reply, composer refusal causes and raw native reply data on view errors. A displayed-session run observes positive file, draft and owned-view effects. |
| Conversation-based Skill activation. | A source test verifies the submitted slash command. A native run records activation, the bounded Skill response and its turn event. |
| Connection-scoped, readable observation. | Tests cover dropping events with no bridge. Native comparison checks connection timing, local timestamps and the effect-observation label. |
| Complete lab and closed Plugin Base. | All 17 table entries have matching guide expectations. `npm run build`, `npm test` and `npm run typecheck` pass from `src/graph_skill_toolkit/`; the Node suite includes `tests/plugin_base/closure.test.mjs`. |
| Valid Mod and consistent documents. | Claude Code `2.1.299` validates `dist/claude-mod`. The reference, manual procedure and page behavior agree; relative links resolve and new text is UTF-8 with LF line endings. |

The Mod validation command runs from the toolkit root:

```text
C:/Users/test/AppData/Roaming/Claude/claude-code/2.1.299/f0584be0fbaf/claude.exe plugin validate dist/claude-mod
```

## Open items

- **Claude native re-observation.** A fresh session loads the candidate server and Mod and is displayed in a window. The observer records the table's supported paths, exact unsupported reasons, both context paths, large tool inventory, automatic waiting, Skill activation and truthful refusals. Retain saved comparisons, transcript/event coordinates and candidate identity. The dated record above remains evidence for its own candidate.
- **Codex Desktop observation.** The native run depends on a screen-control grant. After that grant, the observer covers the host's declared variants and all local capabilities. Codex context delivery remains governed by its native route in the operation reference.

## Revision log

- 2026-10-29: Adds decisions 8 to 10 from a Claude Code `2.1.309` run: the hidden Browser pane is shown through `show_pane`, native replies are read in the array shape with refusal reasons, and local paths are checked under the packaged-host redirect. Restates the two unsupported verdicts with the observed host facts.
- 2026-10-16: Establishes the Claude connection verdicts, source-specific context delivery, complete-receipt transport, workspace presets, automatic receipt waiting and evidence-based status rules from the dated native record and installed engine declarations.
