# Graph Skill toolkit

Graph Skill toolkit supplies global runtime commands, shared agent instructions and one local Graph application for Codex Desktop and Claude Code Desktop. The working `0.3.5` source has a backend on the business Skill's physical filesystem and one React/TypeScript HTML page: a Graph viewer, live host/version status and a laboratory for 15 generic host interfaces. After root selection, the backend observes file saves and the page receives current graph snapshots through its own direct local HTTP connection. The [Host Port](ADAPTER.md) defines native operations independently of Graph business paths; [the architecture map](ARCHITECTURE.md) identifies the data and host-operation owners. Codex's host channel uses the official MCP Apps SDK. Claude uses an authenticated same-origin HTTP page and a Mod, a plugin running inside Claude Code. Its normal Graph display opens or reuses the actual business `SKILL.md` and navigates the HTTP canvas. The Python runtime remains independently installable, and business skills remain in user-selected directories.

Toolkit state, commands and private runtimes live under `~/.local/share/graph-skill` on all supported systems. Here `~` means the current user's home directory. Explicit installation or update automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill` and installs the canvas Mod when Claude is selected. Version `0.3.5` retains client-based integration selection, progress, retry guidance, interrupted-installer recovery, automatic downloads and explicit cleanup. A host installation contains its Skills, canvas-server registration and follow-up hook, plus the Claude Mod where selected. The independently versioned Python runtime remains `0.1.0a1`. Complete archives target Windows x64, Apple Silicon macOS, Linux x64 and Linux ARM64. The [installation decisions](INSTALLATION-DECISIONS.md#toolkit-source-structure-decision-2026-10-10) explain ownership; the [current validation record](VALIDATION.md#current-baseline-unified-host-port-implementation-2026-10-13) owns acceptance conditions.

The source lives at `src/graph_skill_toolkit/`, directly beside the Python runtime. [PROTOTYPE.md](PROTOTYPE.md) explains the current page; [MANUAL-TESTS.md](MANUAL-TESTS.md) separates its native test procedure from the earlier eight-action ledger. The [0.3.4 delivery](release/DELIVERY-0.3.4.md) records a completed earlier public release with bounded installed/native evidence. Installation, actual loading and complete native observations for the reorganized `0.3.5` working source remain unverified; [VALIDATION.md](VALIDATION.md#current-baseline-unified-host-port-implementation-2026-10-13) owns that distinction.

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

Each host receives `detected`, `not-detected` or `unknown`, with evidence, diagnostics and configuration destinations. `not-detected` means the inspected locations supplied no evidence; `unknown` means a diagnostic prevented a conclusion. Positive executable evidence can establish `detected` while retaining diagnostics from another probe. An unknown result or no detected clients stops automatic installation before toolkit state is created. On update, a previously configured client missing from automatic selection also stops the operation and preserves its adapter.

Use `--targets codex`, `--targets claude` or `--targets codex,claude` to choose an explicit set, including a verified nonstandard client location or an intentional target removal. Add `--dry-run` to preview the operation. Only selected hosts' configuration overrides are checked: `CODEX_HOME` for Codex and `CLAUDE_CONFIG_DIR` for Claude must resolve to their respective default user profiles. Custom selected profiles remain unsupported. An incoming toolkit version lower than the installed version is rejected.

If Codex has the earlier `graph-skill-canvas@graph-skill-local` plugin enabled, disable it through Desktop before installation. The installer preserves conflicting configuration and stops. It also preserves unmanaged collisions and edited toolkit-owned resources; resolve the reported conflict before retrying.

The completion message gives an absolute `status` command that works immediately in the current terminal. Open a fresh terminal to use `graph-skill` and `gskill` through the updated PATH. Restart the selected host to discover the Skills, canvas server, hook and applicable Mod. A Skill is a discoverable instruction file that guides the agent; the hook supplies follow-up guidance after tool use. The host retains its normal trust and approval decisions. Ask the agent to open a Graph Skill folder and show its graph, then verify the displayed root and canvas in that host.

Claude Desktop's bundled Code engine must support Mods; the documented minimum is `2.1.286`, while terminal Claude Code requires `2.1.287`. Check the Desktop engine with `/status` in a local Code session, and the terminal engine with `claude --version`. Host settings and organization policy govern Mod loading. These are [upstream prerequisites](https://code.claude.com/docs/en/plugins/mods/overview#turn-mods-on-or-off); actual behavior has separate acceptance evidence. The current route requires native `preview_start`, `navigate`, `tabs_context`, `tabs_select` and the live Mod session-root API. The [attachment evidence](evidence/prototype-preview-attach-source.json) binds the inspected Windows Desktop `2.31226.1.0` / engine `2.1.295` behavior. The manual ledger records the measured native effects for that host; other versions and platforms require their own evidence. An unavailable or rejected preview preserves the graph result and reports the display limitation.

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

`npm run mode:test` builds that checkout before selecting it. `npm run mode:installed` restores the active installed release. `npm run mode:status` reports the configured selection, `installed_version`, `source_version`, source path and any detected change to managed files or recorded source assets. The recorded source hashes cover built canvas/server/hook/Mod assets, the source command and Markdown files in both toolkit Skills. If one of those source files changes, status reports `configuration-changed`; rerun `npm run mode:test` to refresh the selection. Until a release containing this command is installed, use these npm scripts from the updated checkout: the older installed `graph-skill` executable does not contain the mode command.

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

A business root contains `SKILL.md` and `graph.yaml`. The canvas server's `show_graph` and `inspect_graph` are Graph-specific MCP tools, separate from the runtime's MCP tools and from the 15 generic host interfaces. `show_graph` selects an explicit root and returns its presentation diagnostics; omitting the root shows a labeled demonstration. `inspect_graph` is an explicit read of a selected graph. The Graph [source and projection](ARCHITECTURE.md#current-source-map) own these values. The local backend observes relevant files and projects the root topology and phase kinds. The page subscribes directly to that backend and renders changed snapshots after saves, independently of Agent work or host tool refresh. A save that leaves the projected values unchanged retains the current snapshot. Native access to this local connection inside a loaded Codex Desktop page remains to be verified.

The common page shows the graph, selected node, current HostInfo and toolkit version, then lists all 15 operations with editable JSON arguments. A capability is `available`, `unavailable` or `unknown` for the current connection. An operation is sent only when currently available. `accepted` acknowledges the host request, while a visible file, draft or conversation result needs separate observation. The [Port contract](ADAPTER.md#interface-contract) lists every operation and its parameter/result meaning. `application/graph/interface_samples/` supplies optional Graph-specific sample arguments; the generic Port has no Skill-root restriction or fixed `inspect_graph` tool.

Codex uses the official MCP Apps `App` and `PostMessageTransport` and directly calls only host-declared native capabilities. Its Graph canvas presentation is a separate use case: one `show_graph` call attaches the MCP App canvas as the final presentation. Claude's Mod uses actual session and tool facts through the authenticated HTTP bridge. Its Graph presentation uses `preview_start`, tab navigation, tab selection and the owned HTTP page. Generic `files.revealDirectory` is unknown on both hosts; Claude generic `views.open`/`views.close` are unknown. A direct `tools.call` is distinct from submitting an Agent message. Host operation declarations do not promise complete native effects across Desktop versions.

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

`npm start` starts the standard-input/output MCP server and its local HTTP backend. MCP delivers canvas launch tools and the shared HTML; the frontend's HTTP stream delivers live graph data. A Desktop host must actually load that server and, for Claude, the matching Mod under `adapters/claude/mod/`; file paths in configuration alone do not prove loading. The independently installable Python package is not published on PyPI. The current source's complete installed Desktop behavior remains unverified, as recorded in [VALIDATION.md](VALIDATION.md).

## Build and acceptance

The existing [installation decisions](INSTALLATION-DECISIONS.md) and [installer source](installer/) own platform payload and resource-ownership behavior. Release assembly requires an authorized clean source commit, exact candidate-bound archives, required checks and installed native acceptance. The previous `0.3.4` release evidence applies only to its own bytes. The [manual guide](MANUAL-TESTS.md) describes how to observe current host identity, each interface result, actual `SKILL.md` and canvas retention, and session behavior. The old eight-action ledger is explicitly historical. This working source is not claimed as published.
