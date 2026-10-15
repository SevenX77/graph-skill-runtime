# Graph Skill toolkit

Graph Skill toolkit supplies local runtime commands, shared agent instructions and a Graph Skill canvas for Codex Desktop and Claude Code Desktop. A **Graph Skill** is a user-owned directory containing `SKILL.md`, `graph.yaml` and phase definitions. The working source is version `0.3.5`; the independent Python runtime is `0.1.0a1`. Business skills remain in user-selected directories.

The toolkit has one **Plugin Base**, the reusable foundation for pages that interact with an agent host, and two separate apps. The canvas shows the graph, selected node and host/version status. The developer **Plugin Interface Lab** exercises the 17 host interfaces and 5 local capabilities. Host interfaces ask the desktop host for information or actions. Local capabilities execute file and operating-system actions in the plugin's own process. The lab is available in source test mode.

## Documentation

| Question | Owner |
| --- | --- |
| How do I build a plugin and call all 22 operations? | [Plugin Base usage](plugin_base/README.md) |
| How does a page connect and gain operation authority in each host? | [Host Port and adapters](ADAPTER.md) |
| Where do modules, processes, routes and graph data belong? | [Architecture map](ARCHITECTURE.md) |
| What does each page show? | [Visible page behavior](PROTOTYPE.md) |
| How do I observe native effects and save comparisons? | [Manual tests](MANUAL-TESTS.md) |
| What design and acceptance boundaries apply? | [Plugin Base decision](../../docs/design/plugin-base-and-interface-lab-2026-10-14.md) |
| What has been measured? | [Current validation baseline](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) |

The current baseline records source, build and installer checks and a configured source-mode switch. Native acceptance of all 22 operations in both hosts is pending. Historical release and native results retain their own candidate scope in [VALIDATION.md](VALIDATION.md).


## Install

The small npm package downloads the matching complete archive and runs its installer. This entry requires Node.js 18 or later, npm and network access. The installed toolkit uses its private Node.js `24.21.0` and CPython `3.13.16`; it does not rely on the bootstrap interpreter afterward.

Install the latest published npm version:

```text
npx --yes graph-skill-toolkit@latest install
```

The package resolves its own version's GitHub release, selects the operating system and processor architecture, verifies the archive against `SHA256SUMS.txt`, extracts it and invokes the explicit installer. The command reports platform selection, download percentage and size, checksum verification, extraction, local file checks and host configuration. Host configuration changes start only through the explicit `install` command.

Alternatively, download a complete ZIP from the release assets. This route requires no system Node.js or Python and no dependency downloads during installation:

| Computer | Archive |
| --- | --- |
| Windows x64 | `graph-skill-VERSION-win32-x64.zip` |
| Mac with Apple Silicon | `graph-skill-VERSION-darwin-arm64.zip` |
| Linux x64 with glibc | `graph-skill-VERSION-linux-x64.zip` |
| Linux ARM64 with glibc | `graph-skill-VERSION-linux-arm64.zip` |

Use the version shown on the [published toolkit release](https://github.com/SevenX77/graph-skill-runtime/releases). Here `darwin` means macOS, and glibc is the Linux system library used by these binaries. Available prebuilt targets are the four rows above. Each ZIP contains private runtimes, the runtime wheel and its locked base dependencies. Optional embedded-provider extras and additional libraries required by business skills need separate deployment.

Extract the matching ZIP, preserving executable permissions on macOS/Linux. On Windows, run `install.cmd`; on macOS/Linux, run `sh install.sh` from the extracted directory. Keep the extracted payload together. An unbuilt source checkout is not an installer archive.

Installation and update default to `--targets auto`, which selects detected clients. Discovery checks executable commands in PATH, the command search list, and supported native installation locations. On Windows it also checks exact registered package families and their manifest-listed, visible application executables. On macOS it checks application metadata and executable files in `/Applications` and `~/Applications`. Configuration folders alone supply no client evidence.

Each host receives `detected`, `not-detected` or `unknown`, with evidence, diagnostics and configuration destinations. `not-detected` means the inspected locations supplied no evidence; `unknown` means a diagnostic prevented a conclusion. Positive executable evidence can establish `detected` while retaining diagnostics from another probe. An unknown result or no detected clients stops automatic installation before toolkit state is created. On update, an already configured client missing from automatic selection also stops the operation and preserves its adapter.

Use `--targets codex`, `--targets claude` or `--targets codex,claude` to choose an explicit set, including a verified nonstandard client location or an intentional target removal. Add `--dry-run` to preview the operation. Only selected hosts' configuration overrides are checked: `CODEX_HOME` for Codex and `CLAUDE_CONFIG_DIR` for Claude must resolve to their respective default user profiles. Custom selected profiles remain unsupported. An incoming toolkit version lower than the installed version is rejected.

If Codex has the earlier `graph-skill-canvas@graph-skill-local` plugin enabled, disable it through Desktop before installation. The installer preserves conflicting configuration and stops. It also preserves unmanaged collisions and edited toolkit-owned resources; resolve the reported conflict before retrying.

The completion message gives an absolute `status` command that works immediately in the current terminal. Open a fresh terminal to use `graph-skill` and `gskill` through the updated PATH. Restart the selected host to discover the Skills, canvas server, hook and applicable Mod. A Skill is a discoverable instruction file that guides the agent; the hook supplies follow-up guidance after tool use. The host retains its normal trust and approval decisions. Ask the agent to open a Graph Skill folder and show its graph, then verify the displayed root and canvas in that host.

Claude Desktop's bundled Code engine must support Mods; the documented minimum is `2.1.286`, while terminal Claude Code requires `2.1.287`. Check the Desktop engine with `/status` in a local Code session, and the terminal engine with `claude --version`. Host settings and organization policy govern Mod loading. These are [upstream prerequisites](https://code.claude.com/docs/en/plugins/mods/overview#turn-mods-on-or-off); actual behavior has separate acceptance evidence. The current route requires native `preview_start`, `navigate`, `tabs_context`, `tabs_select` and the live Mod session-root API. The [validation ledger](VALIDATION.md) retains version-bound host observations. The [manual procedure](MANUAL-TESTS.md) establishes native effects for each selected candidate and host. An unavailable or rejected preview preserves the graph result and reports the display limitation.

If installation fails or is interrupted, resolve the reported problem and retry the same command, retaining any `--targets` and `--dry-run` options. The installer recovers an abandoned process record only after confirming that its process has exited. A running or inaccessible process, or an unreadable ownership record, keeps installation blocked with a diagnostic. Leave the lock files in place and follow that diagnostic; file age is not a recovery criterion.

The bundled Node.js prerequisites include Windows 10/Server 2016 or later, macOS 13.5 or later, and Linux kernel 4.18 or later with glibc 2.28 and libstdc++ 6.0.25 or later. libstdc++ is the C++ runtime library. Upstream also requires a vendor-supported operating system. These are [Node.js prerequisites](https://github.com/nodejs/node/blob/v24.21.0/BUILDING.md#platform-list); complete toolkit compatibility still needs native evidence.

## Update, inspect and remove

```text
graph-skill update
graph-skill update "EXTRACTED_DIR"
graph-skill detect
graph-skill status
graph-skill cleanup --dry-run
graph-skill cleanup
graph-skill uninstall
```

`graph-skill update` finds the newest published toolkit release, including toolkit previews, downloads the matching archive, verifies its checksum and runs the incoming installer. Supplying an absolute extracted release directory selects the offline route. Install/update accept `--targets auto|codex|claude|codex,claude` and `--dry-run`; choose one value after `--targets`. To upgrade an older toolkit that lacks automatic updates, use the new npm entry or the new ZIP's installer.

On Windows, use the latest published npm entry or its ZIP's `install.cmd` to migrate an existing AppData installation. The incoming installer checks both installation roots and the owned host resources, updates the Skills, canvas server, hook and launchers, replaces only its owned old PATH entry, and records the new installation owner. A second active installation, an edited owned resource or a changed owned PATH entry stops migration and preserves the reported content. The old root retains its version caches and a migration record; leave that record in place so an older installer cannot reclaim it. Open a fresh terminal and restart the selected hosts after migration.

`graph-skill detect` reads client evidence and reports configuration destinations without creating toolkit state, changing host configuration or launching clients. It always prints JSON, including in an interactive terminal. The npm entry delegates detection to an existing installed payload; that payload must support the command. On first use without an installed or complete extracted payload, npm `detect` returns `not-installed`. Run the explicit `install` command to acquire the complete payload and perform its preflight discovery.

Lifecycle commands show concise progress and results on standard error, the terminal's diagnostic stream. Redirected or piped standard output retains the structured JSON result for scripts. Add `--json` to display that result in an interactive terminal, including the detailed plan from `--dry-run`.

`cleanup` removes only verified inactive version caches, including caches in the migrated Windows AppData root. It preserves the active version and the currently executing installer, and skips unknown or modified directories. Close hosts and other processes that may still use old payloads before cleanup, then restart them against the active installation. `--dry-run` shows the proposed cleanup first. Cleanup is an explicit operation; updating does not broadly delete old directories. An active legacy installation requires install/update migration before the new toolkit can clean it up or uninstall it.

Uninstall removes managed host registrations, Skills, command launchers and PATH integration while retaining version caches. Business files and runtime run state remain user-owned. After uninstall removes the global command, invoke the same npm entry above with `cleanup` in place of `install` to clean verified caches. Its report identifies the executing cache that must remain; this does not promise complete removal of cached payloads. `status` describes recorded ownership; actual host loading must be observed in the host.

| Location | Toolkit-owned content |
| --- | --- |
| All systems: `~/.local/share/graph-skill` | Product state, `install.json`, commands and `versions/<version>-<digest>` payloads. On Windows this is `%USERPROFILE%\.local\share\graph-skill`. |
| Migrated Windows `%LOCALAPPDATA%/GraphSkill` | Migration record and retained version caches eligible for explicit verified cleanup. |
| Codex `~/.agents/skills/{graph-skill,graph-skill-canvas}` | Rendered Skills and references. |
| Codex `~/.codex/config.toml` and `~/.codex/hooks.json` | Marked canvas server block and owned hook entry. |
| Claude `~/.claude/skills/{graph-skill,graph-skill-canvas}` | Rendered Skills and references. |
| Claude `~/.claude.json` and `~/.claude/settings.json` | Named canvas server selector, owned hook entry and one owned Mod path in `env.CLAUDE_CODE_PLUGIN_DIRS`. |
| User command search path | Windows user PATH entry; marked POSIX PATH blocks in the selected Bash login profile and `.zprofile`. |

The installer preflights every selected host before provisioning, merges only owned configuration content and preserves unrelated settings and independent MoirAI/runtime integrations. Updates require recorded owned content to remain intact. Rollback restores a touched file only while its bytes equal the operation's after-image; a concurrent edit is preserved and reported as incomplete rollback.

In installed mode, Claude's Mod lives in the active version's `claude-mod` directory. In source test mode, the owned settings entry points to the checkout's built `dist/claude-mod` directory. The installer records the exact absolute directory alongside the owned hook in one settings resource. Update replaces that entry, and uninstall removes it while retaining other plugin directories and settings. An edited owned entry or an unmanaged equivalent entry stops the operation with a diagnostic. An explicit update from an earlier manifest adds the Mod ownership.

## Switch the Desktop source for testing

An existing toolkit installation can select either its active immutable release or a built toolkit source checkout for the Codex and Claude user profiles already owned by that installation. This selection changes the canvas server, follow-up hook, rendered Skills and, for Claude, the Mod path. Both modes continue to use the installed release's private Node.js and Python runtimes. The global `gskill` command and the installed release bytes remain bound to that release. Business Skill directories and unrelated host configuration remain under their existing owners.

Run these commands from `src/graph_skill_toolkit/` in the checkout you want to test:

```text
npm run mode:status
npm run mode:test
npm run mode:status
npm run mode:installed
```

`npm run mode:test` builds that checkout before selecting it. `npm run mode:installed` restores the active installed release. `npm run mode:status` reports the configured selection, `installed_version`, `source_version`, source path and any detected change to managed files or recorded source assets. The recorded source hashes cover the selected build assets, source command and Skill Markdown. Source test mode also registers the Interface Lab and its Skill; [ARCHITECTURE.md](ARCHITECTURE.md#installation-and-source-selection) owns this mode-specific projection. If one of those source files changes, status reports `configuration-changed`; rerun `npm run mode:test` to refresh the selection. Until a release containing this command is installed, use these npm scripts from the updated checkout: the older installed `graph-skill` executable does not contain the mode command.

The direct source command also accepts an explicit checkout and a preview:

```text
node bin/graph-skill.mjs mode test [TOOLKIT_SOURCE_DIR] [--dry-run]
node bin/graph-skill.mjs mode installed [--dry-run]
node bin/graph-skill.mjs mode status
```

The source directory defaults to the checkout containing this command. `--dry-run` reports the planned changes without applying them; for test mode it checks an already built source and skips the build. Switching requires a valid installed release and unmodified installer-owned resources. The installer checks the selected source and release, applies the host configuration and installation manifest as one owned transaction, and preserves unrelated user settings. A preflight conflict stops the switch before configuration changes. Selecting an already configured mode with matching source hashes and owned resources returns `unchanged`, makes no writes and has an empty `reload_required` list. An installed-mode dry run from that same configured state has `changes: []`.

After a change, the result's `reload_required` names the configured hosts. Reload or restart those hosts, then verify the live server and, for Claude, Mod in a new host session. `mode:status` checks the recorded configuration and tracked file drift; it does not prove what a running Desktop process has loaded. [The manual acceptance procedure](MANUAL-TESTS.md#source-mode-and-loaded-host-check) separates the configured mode from actual host loading.

## Runtime and canvas

The global `gskill` command runs the independent Python runtime. `graph-skill <runtime-command> [arguments]` forwards the same operation:

```text
gskill compile "ABSOLUTE_SKILL_ROOT"
gskill inspect "ABSOLUTE_SKILL_ROOT" --call-graph
graph-skill config resolve "ABSOLUTE_SKILL_ROOT"
```

The canvas server exposes Graph-specific tools over **MCP (Model Context Protocol)**, the protocol through which a host calls plugin tools and reads resources. `show_graph` selects an explicit skill root and presents the canvas. Codex can also show a labeled rootless demonstration when explicitly requested. `inspect_graph` reads an already selected root. `watch_graph` is the page-only change channel for Codex. These business tools are separate from the host-interface contract and the Python runtime's own tools.

Graph changes reach Claude pages over a local HTTP event stream and Codex pages through `watch_graph`. The runtime compiler owns graph validity. [ARCHITECTURE.md](ARCHITECTURE.md#local-graph-data-and-authorization) owns those paths and credentials. [PROTOTYPE.md](PROTOTYPE.md#graph-skill-canvas-page) describes selection, current graph display and compile diagnostics.

To test host and local operations, use the separate [plugin-interface-lab Skill](skills/plugin-interface-lab/SKILL.md) or `open_interface_lab` in source test mode. Opening the lab presents its page; the developer starts each operation. [MANUAL-TESTS.md](MANUAL-TESTS.md) gives the comparison procedure and saved-record checks.

## Run from source

Run these commands from the repository root with Python 3.11+, `uv`, Node.js 22+ and npm:

```text
uv sync
npm ci --prefix src/graph_skill_toolkit
npm run typecheck --prefix src/graph_skill_toolkit
npm run build --prefix src/graph_skill_toolkit
npm test --prefix src/graph_skill_toolkit
uv run gskill compile examples/hello-world
npm start --prefix src/graph_skill_toolkit
```

`npm start` starts the built stdio MCP server from `composition/server.mjs` and its loopback listener. The canvas app lives under `apps/graph_canvas/`; the separate lab app lives under `apps/interface_lab/`; reusable host integration lives under `plugin_base/`. The built Claude Mod comes from `composition/claude_mod/`. The [architecture map](ARCHITECTURE.md#build-outputs) owns output paths and page transports. A desktop host must load the selected server and matching Mod before native results can be attributed to that source. The Python package remains independently installable and unpublished on PyPI. [VALIDATION.md](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) records source checks and pending loaded-host acceptance.

## Build and acceptance

[Installation decisions](INSTALLATION-DECISIONS.md) and [installer source](installer/) own payload and resource-ownership behavior. [ARCHITECTURE.md](ARCHITECTURE.md#build-outputs) owns the build outputs. [VALIDATION.md](VALIDATION.md#current-baseline-plugin-base-local-capabilities-and-interface-lab-2026-10-14) owns measured checks and remaining acceptance. [MANUAL-TESTS.md](MANUAL-TESTS.md) binds each loaded host to the selected candidate and compares actual effects with the operation contract. The working source has its own delivery boundary; historical publication evidence applies to the bytes recorded there.
