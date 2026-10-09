# Graph Skill toolkit installer

Installs global `graph-skill` and `gskill` commands, shared Skills and the graph canvas integration for Codex Desktop and Claude Code Desktop. The bootstrap requires Node.js 18 or later, npm and network access. The installed toolkit includes private Node.js and Python runtimes.

Install the latest published version:

```text
npx --yes graph-skill-toolkit@latest install
```

The installer selects Windows x64, Apple Silicon macOS, Linux x64 or Linux ARM64, verifies the matching release ZIP against `SHA256SUMS.txt` and runs its explicit installer. Intel Mac and Windows ARM64 packages are unavailable. Add `--targets codex` or `--targets claude` for one host, or `--dry-run` to preview. First installation defaults to both hosts; upgrades retain the installed targets unless explicitly changed. Installing this npm package alone does not modify host configuration.

Version `0.3.1` adds visible download and installation stages, recovery of demonstrably abandoned installer records and actionable completion guidance. The completion message includes an absolute command for checking the installation immediately. Open a fresh terminal to use commands by name, then restart the selected host to load its Skills and canvas:

```text
graph-skill status
graph-skill update
```

Ask the agent to open a Graph Skill folder and show its graph. Confirm the root and visible canvas in the restarted host; installation checks establish local configuration and files.

Progress and completion messages use standard error. Piped or redirected standard output retains the structured JSON result. Add `--json` for structured output in an interactive terminal. After a failed or interrupted install, resolve the reported problem and retry the same command, retaining any `--targets` and `--dry-run` options. The installer preserves live, inaccessible or unidentified ownership records and reports the condition requiring attention.

Updates download the newest published toolkit release, including previews. `graph-skill update "EXTRACTED_DIR"` uses a downloaded ZIP offline. `graph-skill uninstall` removes managed integration and commands while retaining caches. Close processes using old payloads before `graph-skill cleanup`; use `--dry-run` to preview. Cleanup preserves the active and executing installer caches and skips unknown or modified directories. After uninstall, run the npm entry above with `cleanup` in place of `install`; its report still identifies the executing cache retained.

The npm bootstrap downloads the GitHub release matching its own version. See the [toolkit guide](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.1/plugins/graph-skill/README.md) for offline ZIP installation, configuration ownership, source execution and manual Desktop acceptance. The [validation record](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.1/plugins/graph-skill/VALIDATION.md#version-031-installation-patch-evidence-2026-10-09) records the scope of the patch's checks.
