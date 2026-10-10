# Graph Skill toolkit installer

Installs global `graph-skill` and `gskill` commands, shared Skills and the graph canvas integration for Codex Desktop and Claude Code Desktop. The bootstrap requires Node.js 18 or later, npm and network access. The installed toolkit includes private Node.js and Python runtimes.

Version `0.3.4` uses one shared HTML interface and two host adapters. HTML contains the graph's webpage, styling and interactions; an adapter supplies a host's data and permitted actions. Codex displays the page as an MCP App attached to the graph tool result. Claude opens a generated local HTML file in its Browser pane through a Mod, a plugin observing that host's events. The host's normal file tools handle browsing and editing.

At source-document freeze, a staged Windows Claude Desktop `2.31226.1.0` / engine `2.1.295` candidate passed two ordinary-edit observations: its closed Browser pane automatically opened the real changed graph, then reopened the next changed graph from the same file. Final installed-package acceptance, native release builds and GitHub/npm publication remain pending. Actual Codex Desktop acceptance of the new candidate remains unverified; its shared page and bridge passed Chromium checks with a simulated MCP host. The release notes record final artifact identities and public availability. The prior published `0.3.3` package retains its earlier Claude drawing.

Install the latest published version:

```text
npx --yes graph-skill-toolkit@latest install
```

The installer selects Windows x64, Apple Silicon macOS, Linux x64 or Linux ARM64, verifies the matching release ZIP against `SHA256SUMS.txt` and runs its explicit installer. Intel Mac and Windows ARM64 packages are unavailable. Installing this npm package alone leaves host configuration unchanged.

The toolkit uses `~/.local/share/graph-skill` for state, commands and private runtimes on all supported systems. Here `~` means the user's home directory; on Windows the path is `%USERPROFILE%\.local\share\graph-skill`. Its explicit install/update operation automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill`. Run this version's npm entry or ZIP installer to perform that migration. It preserves unrelated configuration, stops on ownership conflicts or edited managed content, and retains old caches for explicit verified cleanup. Keep the migration record in the old root so older installers cannot reclaim it.

When Claude is selected, the installer adds one owned Mod directory to `env.CLAUDE_CODE_PLUGIN_DIRS` in the default Claude user settings. Update replaces that recorded entry and uninstall removes it, preserving other plugin directories and settings. Codex keeps its existing integration. The independent Python runtime remains version `0.1.0a1`.

Installation defaults to `--targets auto`: executable and native-application evidence selects the installed Codex and Claude clients. Configuration folders alone supply no client evidence. Unknown discovery results or no detected clients stop installation before toolkit state creation. An update preserves existing adapters and stops if a previously configured client is missing from detection. Use `--targets codex`, `--targets claude` or `--targets codex,claude` to choose the intended hosts explicitly, and `--dry-run` to preview. Selected hosts must use their default user profiles. Installing an older toolkit version over a newer one is rejected.

The toolkit retains download and installation progress, retry guidance and recovery of demonstrably abandoned installer records. The completion message includes an absolute command for checking the installation immediately. Open a fresh terminal to use commands by name, then restart the selected host to load its Skills and canvas:

```text
graph-skill status
graph-skill detect
graph-skill update
```

Ask the agent to open a Graph Skill folder and show its graph. Confirm the root and visible canvas in the restarted host; installation checks establish local configuration and files.

Claude's [documented Mod prerequisites](https://code.claude.com/docs/en/plugins/mods/overview#turn-mods-on-or-off) are bundled Code engine `2.1.286` or later in Desktop and `2.1.287` or later in the terminal. Check the Desktop engine with `/status` in its local Code session. Host trust, settings and organization policy govern loading. Local HTML additionally requires Browser tools and, for the measured interactive route, a Skill root inside the selected Claude project. Other host platforms, terminal display and interactive files outside the project remain unverified.

Claude's graph call creates a snapshot at `<skill_root>/.gskill/canvas/view-XXXXXX/canvas.html`; a later call updates that file and native preview reloads it. The shared template and executable code stay identical across hosts; only the embedded graph/root data differs. The page does not watch source files. `/graph-skill-canvas` reopens the latest snapshot. Normal server shutdown removes unchanged owned files, while a browser may retain an already rendered snapshot. Externally modified files are preserved. The measured host limits generated HTML to 512 KiB; larger output produces an error without truncation.

Claude's path control copies the Skill root when the preview context provides clipboard access; otherwise it reports the failure and leaves the path selectable. Copying does not open a folder. Native Claude folder opening remains unverified.

`detect` reports client evidence and configuration destinations as JSON without changing toolkit or host state. The npm command uses an existing installed payload that supports detection. Without an installed or complete extracted payload, it reports `not-installed`; first-use preflight discovery runs after the explicit `install` command acquires the complete archive.

Progress and completion messages use standard error. Piped or redirected standard output retains the structured JSON result. Add `--json` for structured output in an interactive terminal. After a failed or interrupted install, resolve the reported problem and retry the same command, retaining any `--targets` and `--dry-run` options. The installer preserves live, inaccessible or unidentified ownership records and reports the condition requiring attention.

Updates download the newest published toolkit release, including previews. `graph-skill update "EXTRACTED_DIR"` uses a downloaded ZIP offline. `graph-skill uninstall` removes managed integration and commands while retaining caches. Close processes using old payloads before `graph-skill cleanup`; use `--dry-run` to preview. Cleanup covers verified inactive caches in the current root and the migrated AppData root, preserves the active and executing installer caches, and skips unknown or modified directories. An active legacy installation must be migrated before this version can clean it up or uninstall it. After uninstall, run the npm entry above with `cleanup` in place of `install`; its report still identifies the executing cache retained.

The npm bootstrap downloads the GitHub release matching its own version. The versioned [toolkit guide](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.4/plugins/graph-skill/README.md) covers offline ZIP installation, configuration ownership, source execution and Desktop acceptance. Its [validation record](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.4/plugins/graph-skill/VALIDATION.md#local-html-source-freeze-acceptance) records the source-freeze boundary; those links become available with the release tag. Publication requires final installed acceptance and verified matching artifacts.
