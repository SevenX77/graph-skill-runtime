# Claude browser-page host route

Date: 2026-11-01.

## Purpose

A plugin page shown in Claude Desktop's Browser pane reaches every host fact and effect that is available to a web page and to the plugin's own server process, and it reports every other interface as unavailable with the observed reason. The route works in a session where the Claude Mod is absent.

## Terms

- **Claude Mod**: the plugin component that the Claude Code engine loads inside a session. It holds the `$` interface, which calls session tools and submits prompts.
- **Browser-page route**: the page, its plugin server process and nothing else. Its transport is named `http-page`.
- **Browser pane**: Claude Desktop's side pane that shows web tabs. The shortcut `Ctrl+Shift+B` and the session tool `mcp__ccd_view__show_pane` with `pane: "preview"` both show it.

## Decisions

1. **A separate tool and transport.** The tool `open_browser_lab` presents the Interface Lab through the `http-page` transport. The existing `open_interface_lab` tool and its Mod route stay in force, because the Mod route carries interfaces that the browser-page route has no means to reach.
2. **Presentation is performed by the agent.** The tool result itself states the ordered steps. A hidden pane is shown with `mcp__ccd_view__show_pane`. When that tool is absent or refused, the person presses the Browser shortcut.
3. **The plugin injects no keystroke into Claude's window.** Claude Desktop refuses screen control of its own window, stating that such control would let the agent operate its own interface and change its own permissions. A script that presses keys in that window would reach the same interface by another route, so the route contains none.
4. **Internal host channels stay closed.** The session environment carries a messaging socket and token for Claude's own use. They are not a plugin interface, so the route does not use them.

## Observed host facts

Observed on 2026-11-01 in a loopback page in the Browser pane of Claude Desktop `4.4212.0` (Chromium `152.0.7977.167`), with each call started by a click on a page button:

| Page call | Observed result |
| --- | --- |
| `document.documentElement.requestFullscreen()` | The promise had not settled after several seconds; `document.fullscreenElement` stayed null and the page size stayed 829 by 1205. |
| `documentPictureInPicture.requestWindow()` | `InvalidStateError: Failed to execute 'requestWindow' on 'DocumentPictureInPicture': Internal error: no window` |
| `window.open("about:blank", "_blank")` | Returned `null`; the tab inventory gained no tab. |
| `navigator.clipboard.writeText()` | Resolved. |

## Interface verdicts on the browser-page route

| Interface | Verdict | Route or reason |
| --- | --- | --- |
| `host.getInfo`, `host.getCapabilities` | Connects | MCP client identity from the tool call; session id from `CLAUDE_CODE_SESSION_ID`. |
| `host.getContext` | Connects | Project root from the tool call and server working directory; theme and language from the page. The model is not reachable. |
| `events.subscribe` | Connects | `tool.completed` and `turn.completed` read from the session transcript file, whose format is private to Claude Code. |
| `context.update` | Connects, pull only | The server stores the snapshot; the model reads it with the tool `read_page_context`. It is not attached to prompts automatically. |
| `tools.list`, `tools.call` | Connects, own tools | The plugin's page tools run in its own process, with no session tool and no host permission check. |
| `skills.list` | Connects, incomplete | Scans the user and project Skill folders; plugin and built-in Skills are not visible, so `complete` is false. |
| `views.requestDisplayMode` | Connected, host refuses | `inline` and `fullscreen` call the page's fullscreen API; `fullscreen` currently returns `rejected`. `pip` is unsupported, per the fact above. |
| `files.openFile`, `files.revealDirectory`, `composer.writeDraft`, `conversation.submitMessage`, `skills.invoke` | Cannot connect | Each needs the session's tools or `$`, which a page and a server process do not hold. |
| `views.open`, `views.list`, `views.close` | Cannot connect | `window.open` is refused and no page API creates a Browser tab. |

The five local capabilities use the existing loopback route, which never depended on the Mod.

## Acceptance

- `npm run build`, `npm test` and `npm run typecheck` pass from `src/graph_skill_toolkit/`.
- A plain MCP client with no Mod starts the built server, calls `open_browser_lab`, and the returned page, loaded in the Browser pane, reports each verdict above when each interface is called.
- Observed on 2026-11-01 with a plain MCP client that declared itself `claude-code` `2.1.309` and held no Mod: the page in the Browser pane of Desktop `4.4212.0` reported transport `http-page` and every verdict above; `tools.call` returned the `lab_echo` echo; `read_page_context` returned the stored snapshot; `tool.completed` events arrived from this session's transcript; and a real click on `views.requestDisplayMode` with `fullscreen` returned `rejected` after 1500 milliseconds with `document.fullscreenElement` null.
- Observed on 2026-11-01 in a fresh Claude session through the real MCP client: the client reports `claude-code` `2.1.309`, and the session id on the page equals that session's `CLAUDE_CODE_SESSION_ID`. The id is null in the result of `open_browser_lab` and present when the page calls `host.getInfo`.
- Open item: `plugin_base/README.md` gains this route's reference once its present uncommitted edits by another session are landed. Until then this document owns the route's contract.
