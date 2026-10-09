# Graph Skill toolkit installer

Installs global `graph-skill` and `gskill` commands, shared Skills and the graph canvas integration for Codex Desktop and Claude Code Desktop. The bootstrap requires Node.js 18 or later, npm and network access. The installed toolkit includes private Node.js and Python runtimes.

Install the latest published version:

```text
npx --yes graph-skill-toolkit@latest install
```

The installer selects Windows x64, Apple Silicon macOS, Linux x64 or Linux ARM64, verifies the matching release ZIP against `SHA256SUMS.txt` and runs its explicit installer. Intel Mac and Windows ARM64 packages are unavailable. Installing this npm package alone leaves host configuration unchanged.

Version `0.3.3` uses `~/.local/share/graph-skill` for toolkit state, commands and private runtimes on all supported systems. Here `~` means the user's home directory; on Windows the path is `%USERPROFILE%\.local\share\graph-skill`. Its explicit install/update operation automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill`. Run this version's npm entry or ZIP installer to perform that migration. It preserves unrelated configuration, stops on ownership conflicts or edited managed content, and retains old caches for explicit verified cleanup. Keep the migration record in the old root so older installers cannot reclaim it.

Installation defaults to `--targets auto`: executable and native-application evidence selects the installed Codex and Claude clients. Configuration folders alone supply no client evidence. Unknown discovery results or no detected clients stop installation before toolkit state creation. An update preserves existing adapters and stops if a previously configured client is missing from detection. Use `--targets codex`, `--targets claude` or `--targets codex,claude` to choose the intended hosts explicitly, and `--dry-run` to preview. Selected hosts must use their default user profiles. Installing an older toolkit version over a newer one is rejected.

The release retains `0.3.1` download and installation progress, retry guidance and recovery of demonstrably abandoned installer records. The completion message includes an absolute command for checking the installation immediately. Open a fresh terminal to use commands by name, then restart the selected host to load its Skills and canvas:

```text
graph-skill status
graph-skill detect
graph-skill update
```

Ask the agent to open a Graph Skill folder and show its graph. Confirm the root and visible canvas in the restarted host; installation checks establish local configuration and files.

The path repair is implemented in source. Real installed migration and automatic canvas display remain pending at this document's source freeze. Before publishing `0.3.3`, the release coordinator must observe an ordinary Graph Skill edit in real Claude Code naturally producing the visible correct updated canvas. An explicit request to show the graph is a separate diagnostic. Final candidate acceptance is recorded in the [release notes](https://github.com/SevenX77/graph-skill-runtime/releases) and retained receipts.

`detect` reports client evidence and configuration destinations as JSON without changing toolkit or host state. The npm command uses an existing installed payload that supports detection. Without an installed or complete extracted payload, it reports `not-installed`; first-use preflight discovery runs after the explicit `install` command acquires the complete archive.

Progress and completion messages use standard error. Piped or redirected standard output retains the structured JSON result. Add `--json` for structured output in an interactive terminal. After a failed or interrupted install, resolve the reported problem and retry the same command, retaining any `--targets` and `--dry-run` options. The installer preserves live, inaccessible or unidentified ownership records and reports the condition requiring attention.

Updates download the newest published toolkit release, including previews. `graph-skill update "EXTRACTED_DIR"` uses a downloaded ZIP offline. `graph-skill uninstall` removes managed integration and commands while retaining caches. Close processes using old payloads before `graph-skill cleanup`; use `--dry-run` to preview. Cleanup covers verified inactive caches in the current root and the migrated AppData root, preserves the active and executing installer caches, and skips unknown or modified directories. An active legacy installation must be migrated before this version can clean it up or uninstall it. After uninstall, run the npm entry above with `cleanup` in place of `install`; its report still identifies the executing cache retained.

The npm bootstrap downloads the GitHub release matching its own version. See the [toolkit guide](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.3/plugins/graph-skill/README.md) for offline ZIP installation, configuration ownership, source execution and Desktop acceptance. The [validation record](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.3/plugins/graph-skill/VALIDATION.md#current-baseline-claude-path-repair-and-automatic-canvas-2026-10-09) records the candidate's acceptance boundary.
