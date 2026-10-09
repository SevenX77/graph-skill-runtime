# Graph Skill toolkit installer

Installs global `graph-skill` and `gskill` commands, shared Skills and the graph canvas integration for Codex Desktop and Claude Code Desktop. The bootstrap requires Node.js 18 or later, npm and network access. The installed toolkit includes private Node.js and Python runtimes.

After the `0.3.0` GitHub release is published and verified, run:

```text
npx --yes --package=https://github.com/SevenX77/graph-skill-runtime/releases/download/graph-skill-toolkit-v0.3.0/graph-skill-toolkit-0.3.0.tgz graph-skill install
```

The installer selects Windows x64, Apple Silicon macOS, Linux x64 or Linux ARM64, verifies the matching release ZIP against `SHA256SUMS.txt` and runs its explicit installer. Intel Mac and Windows ARM64 packages are unavailable. Add `--targets codex` or `--targets claude` for one host, or `--dry-run` to preview. First installation defaults to both hosts; upgrades retain the installed targets unless explicitly changed. Installing this npm package alone does not modify host configuration.

Open a fresh terminal and restart the selected host after installation:

```text
graph-skill status
graph-skill update
```

Updates download the newest published toolkit release, including previews. `graph-skill update "EXTRACTED_DIR"` uses a downloaded ZIP offline. `graph-skill uninstall` removes managed integration and commands while retaining caches. Close processes using old payloads before `graph-skill cleanup`; use `--dry-run` to preview. Cleanup preserves the active and executing installer caches and skips unknown or modified directories. After uninstall, run the npm entry above with `cleanup` in place of `install`; its report still identifies the executing cache retained.

This package is distributed as a GitHub release asset. npm registry publication is pending authentication and package-ownership verification; no registry `@latest` command is promised. The `0.3.0` URL remains provisional until its release is published and verified.

See the [toolkit guide](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.0/plugins/graph-skill/README.md) for offline ZIP installation, configuration ownership, source execution and manual Desktop acceptance.
