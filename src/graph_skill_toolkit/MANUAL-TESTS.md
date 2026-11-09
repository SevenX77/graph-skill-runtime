# Native observation of the canvas

Native observation establishes what a selected toolkit candidate actually does in each desktop host, so acceptance reflects observed effects and recorded evidence.

This guide owns the procedure for observing the Graph Skill canvas of a loaded toolkit candidate in Claude Code Desktop and Codex Desktop. [VALIDATION.md](VALIDATION.md) owns acceptance status and dated results; historical native measurements retain their candidate scope there. Hostpane's [Claude connection decision](https://github.com/SevenX77/hostpane/blob/main/docs/design/interface-connect-verdicts-2026-10-16.md) owns the current verdict table and the 2026-10-16 native evidence. The Interface Lab is Hostpane's test page, and [Hostpane's `docs/MANUAL-TESTS.md`](https://github.com/SevenX77/hostpane/blob/main/docs/MANUAL-TESTS.md) gives the lab's observation steps for Hostpane's 22 operations and for page triggers.

A **candidate** is the exact selected source/build or installed release being observed. [PROTOTYPE.md](PROTOTYPE.md) owns the canvas's visible behavior, and [Hostpane usage](https://github.com/SevenX77/hostpane/blob/main/README.md) owns the host interfaces the canvas uses; Hostpane is the separately versioned package that provides the toolkit's host integration.

A person performs the comparisons. An agent may prepare the candidate and reconcile evidence within its authorization. Keep normal host permissions and approvals. Use disposable inputs and stop dependent tests when the loaded candidate, root, host identity or connection is wrong.

## Source mode and loaded host check

Source test mode selects a built checkout for the existing installer-owned profiles. Installed mode selects the active release. [The mode command](README.md#switch-the-desktop-source-for-testing) changes configuration. A running host loads the selected server and applicable Mod after reload or restart. A **Claude Mod** is hook code loaded inside the Claude session; it carries host operations and page presentation.

1. From the toolkit source directory, record `npm run mode:status` and ordinary `graph-skill status`. Retain time, installed release identity, `installed_version`, `source_version`, configured targets, source path, mode and reported problems. Record the checkout and built-file hashes separately.
2. Run `npm run build`, then `node bin/graph-skill.mjs mode test --dry-run`. The dry run checks existing assets and skips the build. Review planned paths and changes. Run `npm run mode:test` to build and apply the source selection. Retain the result, `reload_required`, installation manifest selection, server/hook/Skill references and Claude Mod directory. The source-test registrations reference the checkout's `dist/server.mjs`, `dist/after-tool.mjs` and `dist/claude-mod`, and the `graph-skill` and `graph-skill-canvas` Skills.
3. Reload or restart every host named in `reload_required`. Begin a fresh task or session. Identify the live plugin process, the script path it runs and its candidate/build identity. For Claude, establish the loaded Mod path. Establish the loaded page identity as well: a new build or changed configuration does not prove that an already open page has loaded new HTML. Configuration alone leaves loading unverified; keep this gap explicit when the live identity cannot be established.
4. Record the desktop version and any separately reported engine version. The host identity that the canvas's host chip shows, and the host-connection JSON behind its ⓘ toggle (`data-host-info`), may name a different software layer from the desktop About panel. Retain both with their sources. Confirm the page's current connection before graph tests.

For a Codex page reopened from an earlier tool result after an engine update, retain the resource-read engine version, historical tool-result engine version and current UI identity separately. Confirm that a version difference between those Codex `mcp-client` records permits the unchanged UI connection to remain confirmed. The current UI identity and the required host, transport and session checks still govern dispatch under [Hostpane's adapter contract](https://github.com/SevenX77/hostpane/blob/main/docs/ADAPTER.md#connection-and-detection). A source regression establishes this comparison rule; native acceptance requires observing the loaded page.

A managed-file conflict or changed source hash requires diagnosis before testing. Rebuild and repeat source selection when tracked assets change. `mode:status` reports configuration and tracked drift; it leaves loaded process identity to observation. A repeated matching selection may return `unchanged` with no reload request. Keep installer receipts distinct from native effects.

## Canvas observation and session lifecycle

Exercise graph presentation with a disposable Graph Skill root. Record the exact displayed root, graph id, selected node, host/version status, current canvas and pre-existing pages. `show_graph` presents the canvas alone. Codex attaches its MCP App view to that call; Claude follows the ordered preview flow. Repeated display must be checked for one current canvas and preserved unrelated pages.

Make one reversible graph-visible edit through the host and observe natural follow-up. Preserve the first result before diagnostic instructions or manual focus repair. Restore exact fixture bytes. While the canvas is open, test a valid save, an invalid save with runtime diagnostics, and recovery after restoration. Record the graph actually rendered and the retained selected node where applicable. Observe graph refresh separately from host capability refresh. [PROTOTYPE.md](PROTOTYPE.md#graph-skill-canvas-page) owns the expected page behavior.

Use the host's normal end/clear action in an authorized disposable session. Record whether the old page can still issue host actions, any available session-end event and the fresh connection in a new session. If teardown destroys the page, record that fact. A post-teardown click is then unobservable. Graph-credential revocation has a separate open lifecycle item in [the decision record](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md#open-items); page closure alone supplies no credential-revocation evidence.

## Settlement and reporting

Restore changed business bytes, including every fixture edited for the follow-up and save tests, and close only test-owned views. Preserve unrelated user pages.

Retain screenshots, candidate/build hashes, actual server/Mod paths, host versions and observation times as evidence. Keep credentials out of shared reports.

When comparing source with the release, run `npm run mode:installed`, retain its result and `reload_required`, reload each named host, and verify the actual server/Mod paths against the active release. Use the same fixture and separate fresh sessions. Retain source and installed observations as independent candidate records.

Report, per host:

- exact candidate, loaded process/Mod/page identity and software versions;
- canvas rendering, normal follow-up, view preservation and session boundaries;
- valid save, invalid save with its diagnostics, and recovery;
- supplemental evidence, restored resources and unresolved effects.

The acceptance owner reconciles each result against its candidate and the decision's criteria. A demonstrated mismatch needs diagnosis and affected re-testing. Source checks, native effects and release delivery retain separate judgments in the validation ledger.
