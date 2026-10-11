# Graph Skill toolkit installer

Installs global `graph-skill` and `gskill` commands, shared Skills and the graph canvas integration for Codex Desktop and Claude Code Desktop. Skills are instruction files the host agent discovers and follows. The npm bootstrap requires Node.js 18 or later, npm and network access. The installed toolkit includes private Node.js and Python runtimes.

The canvas uses one shared React/TypeScript HTML interface and two host adapters. React builds the webpage from components; TypeScript checks its data and operation shapes; each adapter connects that page to its host. Codex displays it as an MCP App, an interactive webpage attached to a tool result through the Model Context Protocol. Claude uses its normal HTTP preview, a webpage served by the local canvas process, with a Mod that connects explicit page actions to the Claude session. A Mod is an event-handling plugin inside Claude Code. The host's normal file tools handle browsing and editing.

The [native acceptance record](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) owns measured host versions, candidate identities, observed effects and remaining limits. It distinguishes staged native observations from installed-release acceptance. The [operation contract](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/PROTOTYPE.md) defines the shared interface and each host's capability boundaries.

Install the latest published version:

```text
npx --yes graph-skill-toolkit@latest install
```

The installer selects Windows x64, Apple Silicon macOS, Linux x64 or Linux ARM64, verifies the matching release ZIP against `SHA256SUMS.txt` and runs its explicit installer. Intel Mac and Windows ARM64 packages are unavailable. Installing this npm package alone leaves host configuration unchanged.

The toolkit uses `~/.local/share/graph-skill` for state, commands and private runtimes on all supported systems. Here `~` means the user's home directory; on Windows the path is `%USERPROFILE%\.local\share\graph-skill`. Its explicit install/update operation automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill`. Run this version's npm entry or ZIP installer to perform that migration. It preserves unrelated configuration, stops on ownership conflicts or edited managed content, and retains old caches for explicit verified cleanup. Keep the migration record in the old root so older installers cannot reclaim it.

When Claude is selected, the installer adds one owned Mod directory to `env.CLAUDE_CODE_PLUGIN_DIRS` in the default Claude user settings. Update replaces that recorded entry and uninstall removes it, preserving other plugin directories and settings. Codex receives shared Skills, a canvas-server registration and a follow-up hook, which supplies guidance after relevant tool use. The independent Python runtime remains version `0.1.0a1`.

Installation defaults to `--targets auto`: executable and native-application evidence selects the installed Codex and Claude clients. Configuration folders alone supply no client evidence. Unknown discovery results or no detected clients stop installation before toolkit state creation. An update preserves existing adapters and stops if a previously configured client is missing from detection. Use `--targets codex`, `--targets claude` or `--targets codex,claude` to choose the intended hosts explicitly, and `--dry-run` to preview. Selected hosts must use their default user profiles. Installing an older toolkit version over a newer one is rejected.

The toolkit retains download and installation progress, retry guidance and recovery of demonstrably abandoned installer records. The completion message includes an absolute command for checking the installation immediately. Open a fresh terminal to use commands by name, then restart the selected host to load its Skills and canvas:

```text
graph-skill status
graph-skill detect
graph-skill update
```

Select a Graph Skill folder containing `SKILL.md` and `graph.yaml`, then ask naturally: “Open the canvas for this Graph Skill.” The shared instructions retain the actual `SKILL.md` beside the current canvas, reuse both views, preserve other pages and leave the canvas active after relevant graph work. Confirm the displayed root and graph in the restarted host. Installation checks establish local configuration and files; the visible result establishes presentation.

Host trust, settings and organization policy govern loading and actions. Claude requires Mod support, native Browser preview tools and access to its live session project. Check the bundled Code engine with `/status` in a local Code session; the [source guide](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/README.md#install) records prerequisites. The business Skill root may differ from that preview project. Missing host capabilities produce a diagnostic and leave their dependent controls unavailable.

Each graph call supplies current presentation data. Claude's local HTTP service refreshes its in-memory page, and the host navigates to that current canvas while retaining the actual document. `/graph-skill-canvas` requests the latest view; source changes become visible through the next graph call. Normal server shutdown closes the service and removes only unchanged owned preview configuration, preserving external edits and business files. Claude's 512 KiB file-preview bound applies to the actual `SKILL.md`; its HTTP canvas has no corresponding file-loader bound.

Nine test controls inspect capabilities, request folder opening, open `SKILL.md`, append a draft, send a prompt, synchronize selected-node context, list callable tools, inspect the graph and request Skill reading with a summary. Draft filling preserves existing text without submitting it. Skill reading requests the selected files and a purpose/node summary without business execution. Folder opening requests a host action; its actual view and completion depend on that host. Selecting a node alone starts no host action.

Codex draft filling requires its advertised draft extension, and its host-wide tool list is unavailable. Its fixed graph inspection calls the originating canvas server directly. Claude lists only the live permitted inspection tool and requests that query through a normal host conversation, where the actual graph result appears. An accepted request establishes acknowledgment; visible files, replies and summaries require their observed effects. The [manual ledger](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/MANUAL-TESTS.md) records these controls, ordinary-edit display, view reuse and session isolation. The canvas supplies presentation and these bounded controls; full graph editing uses the host's file tools.

`detect` reports client evidence and configuration destinations as JSON without changing toolkit or host state. The npm command uses an existing installed payload that supports detection. Without an installed or complete extracted payload, it reports `not-installed`; first-use preflight discovery runs after the explicit `install` command acquires the complete archive.

Progress and completion messages use standard error. Piped or redirected standard output retains the structured JSON result. Add `--json` for structured output in an interactive terminal. After a failed or interrupted install, resolve the reported problem and retry the same command, retaining any `--targets` and `--dry-run` options. The installer preserves live, inaccessible or unidentified ownership records and reports the condition requiring attention.

Updates download the newest published toolkit release, including previews. `graph-skill update "EXTRACTED_DIR"` uses a downloaded ZIP offline. `graph-skill uninstall` removes managed integration and commands while retaining caches. Close processes using old payloads before `graph-skill cleanup`; use `--dry-run` to preview. Cleanup covers verified inactive caches in the current root and the migrated AppData root, preserves the active and executing installer caches, and skips unknown or modified directories. An active legacy installation must be migrated before this version can clean it up or uninstall it. After uninstall, run the npm entry above with `cleanup` in place of `install`; its report still identifies the executing cache retained.

The npm bootstrap downloads the GitHub release matching its own version. The [toolkit source guide](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/README.md) supplies source commands and offline ZIP guidance. The [architecture map](https://github.com/SevenX77/graph-skill-runtime/blob/41c111b3fa1eb3a38b2f621df556d5f2f4a7d80d/src/graph_skill_toolkit/ARCHITECTURE.md) locates each responsibility beside the independent Python runtime. These links identify the reviewed source revision; published release metadata identifies shipped artifacts and their source. Release acceptance requires matching artifacts and verified installed behavior.
