# Person approval for tool calls a plugin page starts

Date: 2026-11-01.

## Purpose

When a person clicks a control on a plugin page that needs a session tool, the person decides whether it runs, whatever permission mode the session is in.

## Problem

In auto mode the engine sends an unsettled tool call to a classifier. A page's call comes from a click and no model request stands behind it, so the classifier refuses it. Observed on 2026-11-01 for `tools.call` with `lab_echo` and `views.open` with `preview_start`: "The server-side auto mode classifier gave no verdict ... the request that produced this action did not ask for one".

A `tool.check` hook that answers `ask` does not solve this. Observed on 2026-11-01 in a fresh auto-mode session: such a hook left the refusal text unchanged and the page received it within seconds. The engine's type documentation states that a classifier's block still refuses a hook's ask.

A `tool.check` hook of the Mod that answers `allow` does not solve it either. Observed on 2026-11-01 in auto-mode session `28a86b56-fde9-43bc-9092-c1dbc7365b85` (Claude Code 2.1.309): the person chose 允许 in the dialog, the Mod issued `$.tool.call` for `mcp__graph-skill-canvas__lab_echo`, and the page received the same classifier refusal. The likely cause, read from the 2.1.309 binary and not yet observed: when an event's origin is a plugin's code outside any hook frame, the dispatcher leaves out all of that plugin's hooks ("hooks module … skipped: re-entry (the plugin's own code raised it)"); from inside a hook frame it leaves out only the calling hook. The Mod runs page actions from a `$.clock.every` callback, so its `tool.check` hook probably never saw the call. The engine's debug log would show it.

The engine offers one channel on which a plugin's call is itself the grant. Its type documentation for `$.mcp.call` states: "No permission prompt: the plugin's call, seen by the hooks above it, is the grant." Every tool the lab and the Mod's view operations call is an MCP tool (`mcp__graph-skill-canvas__*`, `mcp__Claude_Browser__*`, `mcp__ccd_view__show_pane`).

## Decisions

1. **The Mod asks the person before the call.** `callNative` in `plugin_base/adapters/claude/mod/operations/tools/index.mjs` queries `$.tool.check`. On a verdict of `ask` it opens the engine's own question dialog with `$.ui.ask`, offering 允许 and 拒绝 (gloss: "allow" and "refuse").
2. **An answer of allow runs an MCP tool through `$.mcp.call`.** `mcpReference` in the same file reads the session name `mcp__<server>__<tool>` as the server and tool of that call. The engine runs the call as the plugin's own grant, so no mode decider and no classifier is asked. The result is the server's MCP result (`content`, `isError`), which `nativeData` and `nativeText` already read.
3. **Any other answer refuses the call.** A refusal, a dismissed dialog and a session where nobody can be asked all return a rejected result naming the tool, and no tool runs.
4. **Verdicts of allow and deny stand.** `bypassPermissions`, saved allow rules and deny rules keep their meaning, and no dialog opens for them: such a call goes through `$.tool.call` and the session's own permission decision. Every tool of an action is queried, including those after the answer. A page gains nothing the session's rules deny. The query runs no PreToolUse hook, and `$.mcp.call` is not documented to run one, so a classic PreToolUse hook does not review an approved page call.
5. **One click raises one question.** A page action reads its own tool list, and that list identifies the action. Approval covers the tools of that action only, so `views.open` asks once although it calls several tools. The next click asks again.
6. **The Mod registers no `tool.check` hook.** Calls the model makes are decided by the engine as before, and an approved page call no longer needs a verdict changed. In auto mode, an approved page call is reviewed by the person and not by the classifier.
7. **A native tool a person allowed still meets the mode's decider.** A tool without the `mcp__` prefix (`Read`, `Bash`) has no grant channel of the plugin's own; after the dialog it goes through `$.tool.call`, and in auto mode the classifier refuses it as before. No page action of the lab calls such a tool.

## Application state

Unit tests in `tests/adapters/claude/operations.test.mjs` cover the approval logic with a stand-in engine: one question per action, refusal and dismissal, allow and deny without a question, the MCP grant channel, and `mcpReference`. A session in auto mode must confirm the dialog and the echo with the rebuilt Mod.

## Acceptance

In an auto-mode session displayed in a window, clicking `tools.call` with `lab_echo` opens the question dialog. Allowing returns the echo through `$.mcp.call`; refusing shows the refusal on the page. `views.open` raises one dialog and opens its tab.
