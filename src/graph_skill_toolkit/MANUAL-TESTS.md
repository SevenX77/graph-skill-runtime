# Native observation of the canvas and Plugin Interface Lab

This guide owns the procedure for observing a loaded toolkit candidate in Claude Code Desktop and Codex Desktop. [The current validation baseline](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) owns acceptance status and dated results. Native acceptance of all 22 current operations on both hosts is pending. Historical native measurements retain their candidate scope in [VALIDATION.md](VALIDATION.md). The [Claude connection decision](../../docs/design/interface-connect-verdicts-2026-10-16.md) owns the current verdict table and the 2026-10-16 native evidence.

A **candidate** is the exact selected source/build or installed release being observed. A **host interface** asks the desktop host for information or an action. A **local capability** executes an effect in the plugin's own process. The separate **Plugin Interface Lab** provides controls and evidence for 17 host interfaces and 5 local capabilities. [Plugin Base usage](plugin_base/README.md) owns their full argument and result reference. [PROTOTYPE.md](PROTOTYPE.md) owns the visible pages and saved-record format.

A person performs the comparisons. An agent may prepare the candidate and reconcile evidence within its authorization. Keep normal host permissions and approvals. Use disposable inputs and stop dependent tests when the loaded candidate, root, host identity or connection is wrong.

## Source mode and loaded host check

Source test mode selects a built checkout for the existing installer-owned profiles. Installed mode selects the active release. [The mode command](README.md#switch-the-desktop-source-for-testing) changes configuration. A running host loads the selected server and applicable Mod after reload or restart. A **Claude Mod** is hook code loaded inside the Claude session; it carries host operations and page presentation.

1. From the toolkit source directory, record `npm run mode:status` and ordinary `graph-skill status`. Retain time, installed release identity, `installed_version`, `source_version`, configured targets, source path, mode and reported problems. Record the checkout and built-file hashes separately.
2. Run `npm run build`, then `node bin/graph-skill.mjs mode test --dry-run`. The dry run checks existing assets and skips the build. Review planned paths and changes. Run `npm run mode:test` to build and apply the source selection. Retain the result, `reload_required`, installation manifest selection, server/hook/Skill references and Claude Mod directory. The source-test registrations must include `GRAPH_SKILL_INTERFACE_LAB=1` and the `plugin-interface-lab` Skill.
3. Reload or restart every host named in `reload_required`. Begin a fresh task or session. Identify the live plugin process, the script path it runs and its candidate/build identity. For Claude, establish the loaded Mod path. Configuration alone leaves loading unverified; keep this gap explicit when the live identity cannot be established.
4. Record the desktop version and any separately reported engine version. The lab's connection identity may name a different software layer from the desktop About panel. Retain both with their sources. Confirm the page's current connection and capability evidence before operation tests.

A managed-file conflict or changed source hash requires diagnosis before testing. Rebuild and repeat source selection when tracked assets change. `mode:status` reports configuration and tracked drift; it leaves loaded process identity to observation. A repeated matching selection may return `unchanged` with no reload request. Keep installer receipts distinct from native effects.

## Open the Interface Lab

The `plugin-interface-lab` **Skill** is a discoverable instruction asset that guides the host agent to open this developer page. Invoke that Skill or call `open_interface_lab` through the `graph-skill-canvas` server in source test mode. **MCP (Model Context Protocol)** is the protocol by which the host calls this plugin server's tools. Claude names this tool `mcp__graph-skill-canvas__open_interface_lab`. Opening the page runs no test operation.

- **Codex:** call `open_interface_lab` once. Its **MCP App** view, an interactive HTML resource attached to the result, is the lab. Observe the actual displayed page, current connection and host identity.
- **Claude:** follow the Mod's ordered preview guidance. Record existing **Browser pane** tabs, the host's web-tab panel. Attach the returned preview configuration by name, retain the returned HTTP tab id, navigate that tab to the lab URL, select it, and inspect the final tab inventory and visibility. Wait for each dependent action. If the pane stays hidden, use the preview card's Open button or the Browser toggle and record the manual visibility action. Preserve unrelated pages.

Record the lab state directory shown in the header. [PROTOTYPE.md](PROTOTYPE.md#lab-state-and-comparison-files) owns platform locations and comparison-file fields. Confirm its sandbox paths before local file tests.

## Compare every operation

Use the operation list in the lab as the coverage checklist. It must contain all 17 host interfaces and 5 local capabilities in [the usage reference](plugin_base/README.md). A **capability declaration** gives the current support state, scope, constraints and limits. Read it before each operation.

For each operation:

1. Read the page's purpose, expected effect for the current host, checking guidance and declared limits.
2. Choose a preset and edit its JSON arguments to valid disposable inputs. Test available variants only within their declared constraints. An unsupported variant may be checked explicitly as a separate negative case.
3. Run once. Retain the input, status, message, request id, returned data and the four evidence slots: what was sent, raw receipt, read-back observation and limits. Empty evidence is an observation boundary.
4. Look at the host or operating-system surface named by the expectation. Compare the visible effect with the shown evidence. A returned state and visible focus are separate observations. A model reply and a tool receipt also have separate meanings.
5. Select **matches**, **differs** or **not observed**, and add a note explaining the actual effect or why observation is missing. Record `unsupported` or capability `unknown` with its reason. A truthful unsupported result may match the declared boundary while leaving feature parity unverified.
6. Check the save message and comparison-file path. The page writes comparisons when a verdict or note changes. Keep a screenshot or native event coordinate when the effect cannot be represented by the saved fields.

A `pending` result is uncertain after dispatch. Claude follows the same request automatically under the [waiting contract](plugin_base/README.md#claude-host-operation-waiting-and-evidence-sizes). While the page waits, retain the live waiting reason and elapsed time. Use the manual receipt button only when automatic waiting ends with an unknown result. It queries the existing request id. On Codex, retain the uncertain result and inspect the host because this receipt query is absent. Inspect the uncertain effect before any further action on the same target; continue independent tests within their declared scope.

### Identity, events and local sandbox

Start with `host.getInfo`, `host.getCapabilities` and `host.getContext`. Compare identity with the recorded software layer and the environment with the current session. Claude returns project roots under `data.workspaceRoots`, with `cwd` and `model`; Codex returns declared UI context. The live receipt owns actual fields, including any difference from the page's guidance.

Run `events.subscribe` before the tests that produce events. The lab also has a startup subscription; distinguish its source from the explicit subscription's source. Retain relevant event details separately from the comparison file. Check delivered types against the current host's declaration, and record lifecycle events at the point where their connection can still deliver them.

Use `local.files.read` on the sandbox sample. Start `local.files.watch`, then use `local.files.write` or one controlled editor save and inspect the change event. Compare read-back content and `observed.matchesSent`. Stop the watch with its result-card control. Keep writes inside the granted sandbox. An explicit outside-scope negative test uses an authorized disposable path and must leave its bytes unchanged.

Test `local.system.openExternal` with a safe HTTP/HTTPS page and observe the system browser. Test `local.system.revealInFileManager` on the sandbox sample and observe the system file manager. A launched process or Explorer exit code alone establishes no visible-window result. Treat the host's own `files.revealDirectory` as its separate operation with its current unsupported reason.

### Files, draft, message and context

On Claude, display the current session in a host window before positive file-open, draft and owned-view tests. Record that window attachment. A windowless negative test must retain the host's refusal and raw reply under the [result rules](plugin_base/README.md#results-and-evidence).

For `files.openFile`, use the workspace preset: `<root>/README.md`, line 2, with an editable path. After connection the lab reads `host.getContext` and selects `workspaceRoots[0]`, falling back to `cwd`. Confirm that the file exists inside the working directory or a granted folder before running. Inspect the host's file panel and line position. [The sandbox explanation](PROTOTYPE.md#lab-state-and-comparison-files) identifies the separate scratch target used for local capabilities; Claude's host-file scope is defined in the [file-open reference](plugin_base/README.md#filesopenfile). The directory-reveal preset uses the workspace root and retains its declared host limitation. Codex's supported file-open variant omits `line`; keep the line argument only for its unsupported-variant check.

Before `composer.writeDraft`, record the existing composer content and confirm that no dialog is holding input. Append a unique test marker and verify the draft with no submitted message. On refusal, compare any `data.refusal` with the [composer cause definitions](plugin_base/README.md#composerwritedraft); retain an absent cause as unknown. Exercise replacement only with a disposable draft on a host that declares it. Remove only test-owned content and preserve unrelated draft text.

For `conversation.submitMessage`, first use current settings and a bounded reply request. Record acceptance separately from the actual message and reply. On Claude, a specified model must be valid for that host; use one of the five supported effort strings. Verify the applied settings in the matching `turn.completed` event, including `override.applied` and the values the session would have used. Model self-description alone supplies no setting verification. On Codex, specified/default selections are unsupported and must send nothing. Both hosts currently reject the default-selection variant as unsupported. Preserve these comparisons as declared limits.

For `context.update`, set a distinctive snapshot and verify that the update starts no reply. On Claude, test both delivery paths from the [context reference](plugin_base/README.md#contextupdate):

1. Use the lab's probe submission. Compare the visible inline section with the update's displayed context text and the model's response. Retain the submission's inline-delivery evidence and the matching `context.attached` event.
2. Send a separate prompt from another source, such as the person's composer. Compare its hidden attachment event with the model's response. Record the transcript visibility of each path separately.

For Codex text context, compare the sent text with the context-probe reply. For structured-only context, retain the sent snapshot and the separate boundary of the text-block probe. Clear by passing `{"snapshot":{}}` to `context.update`, then use a separate probe to check the cleared state. A bare `{}` omits the required argument and is an invalid-input test. The probe itself submits a message; record that effect separately. The usage reference owns exact text, evidence fields and clearing semantics.

### Tools, Skills and views

Run `tools.list` before `tools.call`. Use the lab's bounded `lab_echo` target and compare the returned echo with the arguments. On Claude use the live session tool reference and normal permission flow; on Codex use the originating server reference. A model deciding to call a tool after a submitted message is a different effect from a direct call.

Run `skills.list` and `skills.invoke` within the current declarations. On Claude, invocation uses the [slash-command route](plugin_base/README.md#skillsinvoke). Use the lab Skill's `echo` input test, observe its activation in the transcript, and retain the model's one-sentence response and the next `turn.completed` event. Check the submit receipt separately from activation and the business reply. Codex's unconfirmed routes are recorded as unknown/unsupported with their reasons.

For available `views.open`, first confirm that the Claude session is displayed in a window, then use a safe web page and a test-owned reuse key. Repeat with that key to check reuse. Retain the returned `viewId`, then run `views.list` and `views.close` only for that owned view. Preserve unrelated pages and the lab itself. Compare active-tab state, pane visibility and actual focus separately. Codex's generic owned-view operations have unknown routes; record their explicit results. For `views.requestDisplayMode`, use only host-declared modes and compare the returned mode with the actual container. The two observations have separate scope.

## Canvas observation and session lifecycle

After operation tests, exercise normal graph presentation separately with a disposable Graph Skill root. Record the exact displayed root, graph id, selected node, host/version status, current canvas and pre-existing pages. `show_graph` presents the canvas alone. Codex attaches its MCP App view to that call; Claude follows the ordered preview flow. Repeated display must be checked for one current canvas and preserved unrelated pages. The canvas and lab have separate tools and pages.

Make one reversible graph-visible edit through the host and observe natural follow-up. Preserve the first result before diagnostic instructions or manual focus repair. Restore exact fixture bytes. While the canvas is open, test a valid save, an invalid save with runtime diagnostics, and recovery after restoration. Record the graph actually rendered and the retained selected node where applicable. Observe graph refresh separately from host capability refresh. [PROTOTYPE.md](PROTOTYPE.md#graph-skill-canvas-page) owns the expected page behavior.

Use the host's normal end/clear action in an authorized disposable session. Record whether the old page can still issue host actions, any available session-end event and the fresh connection in a new session. If teardown destroys the page, record that fact. A post-teardown click is then unobservable. Graph-credential revocation has a separate open lifecycle item in [the decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md#open-items); page closure alone supplies no credential-revocation evidence.

## Settlement and reporting

Stop explicit event subscriptions and file watches with their result-card controls. Clear the test context, remove test draft markers, restore changed sandbox/business bytes where required, and close only test-owned views. Preserve comparison files and unrelated user pages. Page-client disposal clears local listeners; explicit watch stopping settles the server watch before page closure.

Verify the saved file at `<lab state directory>/records/<host>-<session start>.json` for each host. Its schema must be `plugin-interface-lab.records.v1`. Confirm that every operation has an invocation, evidence, comparison and note. Check receipt lookups and late outcomes before the final report. Retain unresolved effects as not observed.

The page record contains arguments, status, message, evidence, verdict and note. Retain raw result data, relevant event excerpts, screenshots, candidate/build hashes, actual server/Mod paths, host versions and observation times in supplemental evidence. Keep credentials out of shared reports. A record's existence alone does not establish complete coverage or native success.

When comparing source with the release, run `npm run mode:installed`, retain its result and `reload_required`, reload each named host, and verify the actual server/Mod paths against the active release. Use the same fixture and separate fresh sessions. Retain source and installed observations as independent candidate records.

Report, per host:

- exact candidate, loaded process/Mod/page identity and software versions;
- each of the 22 operations: promised effect, actual result, decisive evidence and matches/differs/not observed with its note;
- unsupported or unknown variants with their reasons and the remaining feature gap;
- context consumption, applied settings and visible focus only where separately observed;
- canvas rendering, normal follow-up, view preservation and session boundaries;
- saved comparison-file paths, supplemental evidence, restored resources and unresolved effects.

The acceptance owner reconciles each result against its candidate and the decision's criteria. A demonstrated mismatch needs diagnosis and affected re-testing. Source checks, native effects and release delivery retain separate judgments in the validation ledger.
