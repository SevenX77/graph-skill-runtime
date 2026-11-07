# Claude browser-page host route: withdrawn

Date: 2026-11-01. Status: withdrawn; no such route exists in the toolkit.

## Purpose

A later reader knows why the toolkit has one Claude route, and keeps the host facts that were measured while a second route was tried.

## Decision

The Claude host connects to plugin pages through the Claude Mod alone. The route that used only a web page and the plugin's own server process (tool `open_browser_lab`, transport `http-page`) was built, tested in a fresh session and removed the same day by owner direction.

A comparison in that fresh session explains the outcome. The Mod route reaches the session's tools, the conversation, the composer and the file pane. The page route reached none of these, and it exceeded the Mod route only by calling the plugin's own tool without a host permission check.

Owner record, 2026-11-01: 「放弃html模式，用回mod模式」. Gloss: "Abandon the HTML mode; go back to the Mod mode."

## Observed host facts

Observed on 2026-11-01 in a loopback page in the Browser pane of Claude Desktop `4.4212.0` (Chromium `152.0.7977.167`), with each call started by a click on a page button:

| Page call | Observed result |
| --- | --- |
| `document.documentElement.requestFullscreen()` | The promise had not settled after several seconds; `document.fullscreenElement` stayed null and the page size stayed 829 by 1205. |
| `documentPictureInPicture.requestWindow()` | `InvalidStateError: Failed to execute 'requestWindow' on 'DocumentPictureInPicture': Internal error: no window` |
| `window.open("about:blank", "_blank")` | Returned `null`; the tab inventory gained no tab. |
| `navigator.clipboard.writeText()` | Resolved. |

Claude Desktop refuses screen control of its own window, stating that such control would let the agent operate its own interface and change its own permissions. Toolkit code therefore injects no keystroke into that window. The session environment's messaging socket and token are for Claude's own use and are not a plugin interface.
