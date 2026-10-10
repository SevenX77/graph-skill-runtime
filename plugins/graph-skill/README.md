# Graph Skill toolkit

Graph Skill toolkit supplies global runtime commands, shared agent instructions and a graph canvas for Codex Desktop and Claude Code Desktop. It uses the host's normal file tools for source browsing and editing. Both hosts receive graph data through the Model Context Protocol (MCP), the interface through which the agent calls the canvas tool. Toolkit `0.3.4` implements one complete HTML interface with two host adapters. HTML is the webpage containing the canvas, styling and interactions; an adapter supplies data and permitted host actions to that shared page. Codex uses an MCP App, the webpage attached to the graph tool result. Claude opens a generated local HTML file in its Browser preview pane, with presentation prepared by a Mod, a plugin that observes Claude Code events. The Python runtime remains independently installable, and business skills stay in the directories the user selects.

Toolkit state, commands and private runtimes live under `~/.local/share/graph-skill` on all supported systems. Here `~` means the current user's home directory. Explicit installation or update automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill` and installs the canvas Mod when Claude is selected. Version `0.3.4` retains client-based integration selection, progress, retry guidance, interrupted-installer recovery, automatic downloads and explicit cleanup. A host installation contains its Skills, canvas-server registration and follow-up hook, plus the Claude Mod where selected. The independently versioned Python runtime remains `0.1.0a1`. Complete archives target Windows x64, Apple Silicon macOS, Linux x64 and Linux ARM64. The [installation decisions](INSTALLATION-DECISIONS.md#local-html-preview-decision-2026-10-09) explain ownership; the [current validation record](VALIDATION.md#current-baseline-local-html-preview-and-conditional-034-release-2026-10-09) owns acceptance conditions.

At this source-document freeze, `0.3.4` implementation and local checks are complete, and a staged Windows Claude Desktop `2.31226.1.0` / engine `2.1.295` candidate has passed two ordinary-edit observations: a closed Browser pane automatically opened the actual updated graph, including a second edit that refreshed the same file. Final installed-package acceptance, clean-source native builds and GitHub/npm publication remain pending. Actual Codex Desktop acceptance of the new candidate remains unverified; Chromium checks use a simulated MCP host. The [source-freeze acceptance](VALIDATION.md#local-html-source-freeze-acceptance) records exact evidence and limits. The prior [`0.3.3` release](https://github.com/SevenX77/graph-skill-runtime/releases/tag/graph-skill-toolkit-v0.3.3) retains its earlier Claude drawing. Check the published version before assuming that an npm or ZIP download contains `0.3.4`.

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

Claude Desktop's bundled Code engine must support Mods; the documented minimum is `2.1.286`, while terminal Claude Code requires `2.1.287`. Check the Desktop engine with `/status` in a local Code session, and the terminal engine with `claude --version`. Host settings and organization policy govern Mod loading. These are [upstream prerequisites](https://code.claude.com/docs/en/plugins/mods/overview#turn-mods-on-or-off). The local HTML path was measured on Windows Desktop `2.31226.1.0` and engine `2.1.295`, with Browser tools available and the selected Skill root inside the Claude project. Other platforms, terminal display and interactive HTML outside the project remain unverified. An unavailable or rejected preview leaves the graph result available and requires truthful reporting of the display outcome.

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

On Windows, use the `0.3.3` npm entry or its ZIP's `install.cmd` to migrate an existing AppData installation. The incoming installer checks both installation roots and the owned host resources, updates the Skills, canvas server, hook and launchers, replaces only its owned old PATH entry, and records the new installation owner. A second active installation, an edited owned resource or a changed owned PATH entry stops migration and preserves the reported content. The old root retains its version caches and a migration record; leave that record in place so an older installer cannot reclaim it. Open a fresh terminal and restart the selected hosts after migration.

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

Claude's Mod lives in the active version's `claude-mod` directory. The installer records its exact absolute directory alongside the owned hook in one settings resource. Update replaces that entry, and uninstall removes it while retaining other plugin directories and settings. An edited owned entry or an unmanaged equivalent entry stops the operation with a diagnostic. An explicit update from an earlier manifest adds the new Mod ownership.

## Runtime and canvas

The global `gskill` command exposes runtime operations. `graph-skill <runtime-command> [arguments]` forwards the same operation, for example:

```text
gskill compile "ABSOLUTE_SKILL_ROOT"
gskill inspect "ABSOLUTE_SKILL_ROOT" --call-graph
graph-skill config resolve "ABSOLUTE_SKILL_ROOT"
```

Commands return structured JSON by default. Shell invocation retains the host-native executor default, where the host handles Agent phases. Vendor CLI execution is a separate explicit `--executor cli` choice. The shared [Skill](skills/graph-skill/SKILL.md) and [CLI reference](skills/graph-skill/references/cli.md) describe runtime operations and durable Agent result submission. Installation renders absolute private-interpreter and reference paths into those templates. Python runs with `-I -B -X utf8` for isolated module search, no bytecode writes and UTF-8 output.

Select a business root containing `SKILL.md` and `graph.yaml`. The agent uses native file tools for authoring and calls the runtime as needed. After related authoring, reading, compilation, prediction, execution, inspection, resume, result submission or golden evaluation, the shared instructions request one normal `show_graph` call for that root. The hook supplies path evidence; the agent makes the call, and the host controls panel opening and focus. Explicit user preferences can narrow or disable the follow-up.

An explicit call uses the `graph-skill-canvas` server's `show_graph` tool with the verified absolute `skill_root`. Its optional `presentation` value is `mcp-app` or `html`; omission uses the MCP App route. The tool returns the graph and its resolved root. An HTML request also writes an owned preview file and returns its absolute path. The displayed root is the server's resolved path, which may differ from a symbolic-link input. Omitting the root returns a labeled three-node demonstration; automatic Claude presentation requires an explicit business root.

The canvas displays root inputs, phases, dependencies and outputs, with each subgraph phase represented as one node. Runtime compilation owns full format validation. Graph presentation does not import business Python; runtime compilation or inspection of trusted skills can load their declared code. HTML presentation writes a generated file, so `show_graph` declares that it is not read-only. Complete property and option editing remains in the [broader design](../../docs/design/graph-skill-agent-plugin.md).

The shared [`canvas module`](src/ui/canvas.mjs) owns graph validation, drawing, root display and interaction state. [`src/canvas.html`](src/canvas.html) owns the page structure and styling. The build embeds both browser adapters into one `dist/canvas.html` template. Codex receives that template through MCP; Claude receives it with the current graph/root JSON filled into one data slot. The executable UI and template are shared. The canvas shows the graph name, resolved root, node and edge counts, and topology. Invalid data clears the drawing and reports the condition. Use the host's file tools to edit the selected root.

Claude's [`Mod launcher`](claude-mod/hooks/register.js) detects the native Browser preview and visibility tools and requests HTML presentation during the normal graph call. It executes that call once, validates the owned local file path and appends a host-supported reminder asking the model to use `preview_start` with that path after receiving the graph result. After opening, the model calls `tabs_context` when available and reports its displayed/hidden result. A tool's opening acknowledgement alone supplies no visible-graph guarantee. The graph result, core reference, text and prior reminders remain preserved. The reminder and model calls pass through normal host review and permissions. `/graph-skill-canvas` supplies the latest available file path and the same presentation instruction; it reopens the current snapshot without reading a new graph. Missing visibility tools leave visibility unverified, and an unavailable preview or invalid path produces a diagnostic. This launcher draws no separate graph.

An HTML request generates `<resolved skill_root>/.gskill/canvas/view-XXXXXX/canvas.html`, where the final directory is private to that root and canvas-server process. Repeated calls update the same file; the next native preview call reloads its current snapshot. The page does not poll or watch business files. A failed graph read writes an error snapshot when the publisher still owns the file; reloading it clears the drawing. An already open preview can retain its last snapshot after the server closes. Start a new graph call to display current source.

The file publisher rejects redirected cache directories, preserves externally changed preview files and checks ownership before replacement or cleanup. Normal standard-input/output shutdown removes unchanged owned previews and empty owned directories. Startup alone creates no preview files. The measured Claude reader limits a document to 512 KiB, including the shared UI and snapshot; larger output returns an error without truncation. Keep the selected Skill inside the Claude project for the verified interactive local-preview route. Preview artifacts are generated state; business source remains under the user's control.

The Codex adapter's top-left path button requests native folder opening through `openai/files/open` when the host advertises that capability. If the request is absent or rejected, it asks the host agent to browse the root; a file-only host can show `SKILL.md`. The [OpenAI UI contract](https://developers.openai.com/plugins/build/chatgpt-ui) defines the file bridge. The Claude adapter labels the same control as copying the Skill folder path. Clipboard availability depends on the preview context; a failure is reported and the root text remains selectable. This action copies a path and does not open a folder. Claude native folder opening remains unverified. A successful request and a visibly opened folder are separate observations.

## Run from source

A cloned repository or downloaded source archive can run without building a release ZIP. Install Python 3.11 or later, `uv`, Node.js 22 or later and npm, then run these commands from the repository root:

```text
uv sync
npm ci --prefix plugins/graph-skill
npm run build --prefix plugins/graph-skill
uv run gskill compile examples/hello-world
```

The last command exercises the Python runtime. To launch the canvas MCP server:

```text
npm start --prefix plugins/graph-skill
```

This starts a standard-input/output server for an MCP host. The host opens the graphical view after a graph call. To use source from Desktop, explicitly register an MCP server that runs Node.js with the absolute path to `plugins/graph-skill/dist/server.mjs`. Its source tree and Node executable must remain available. Claude also needs the source candidate's `plugins/graph-skill/claude-mod` directory selected by its actual Mod loader and Browser tools enabled. Verify the loaded Mod identity separately from the connected MCP server identity; they can come from different candidates. A temporary development selection must preserve and restore any installer-owned setting. Skill installation, template rendering and hook registration remain separate setup steps. The published toolkit installer supplies the complete released setup described above.

Runtime-only deployments can use the source command above or install the separately built `graph-skill-runtime` wheel into their own Python environment. The Python package retains Python `>=3.11`, its Python API, CLI and MCP tools. Its installation is independent of toolkit Node.js, canvas assets and host configuration; the runtime is not published on PyPI.

## Build release archives

Release assembly adds pinned-runtime downloads and payload construction to the source workflow. Use this procedure after a release version and publication work are authorized. Prepare and commit all source inputs, then build from that clean commit. The builder rejects tracked changes and Git-visible untracked files, records source commit/tree identities and checks them again before completing assembly. Ordinary source execution above can use a working checkout.

After the JavaScript build, run from the repository root:

```text
uv build --no-sources --wheel --out-dir plugins/graph-skill/release/runtime-build
python -B plugins/graph-skill/packaging/bundle.py --runtime-wheel plugins/graph-skill/release/runtime-build/graph_skill_runtime-0.1.0a1-py3-none-any.whl --platform win32-x64
```

Choose another declared target with `--platform`. [`packaging/runtime-lock.json`](packaging/runtime-lock.json) owns pinned interpreter inputs. The builder exports `uv.lock` with `uv --locked` and installs hash-checked binary wheels for the selected platform. Missing compatible inputs stop assembly. Intel-only native compilation is removed from this release path.

The output is `release/graph-skill-0.3.4-TARGET.zip` with an adjacent JSON receipt binding its source, archive, runtime wheel and dependency inputs. Generate the lightweight npm package from the same clean source after the JavaScript build:

```text
npm run pack:installer --prefix plugins/graph-skill
```

The packer derives the package version from the product module and records `sourceCommit`; its output is `release/graph-skill-toolkit-0.3.4.tgz`. The product build module remains private. The generated distribution contains the command entry and bundled installer, with no postinstall host mutation. The release requires the tarball, four ZIPs and `SHA256SUMS.txt`. Final hashes and post-build evidence remain outside packaged documents; changing an input requires rebuilding and verifying the affected artifacts.

## Manual Desktop acceptance

The coordinator owns acceptance of the current source candidate. The checklist also supports user verification in Codex Desktop and Claude Code. Record toolkit and host versions, installation or development route, selected hosts and the actual server, HTML and Mod identities. Published `0.3.3` evidence belongs to its recorded native-drawing candidate.

1. For the complete ZIP route, use a fresh launch environment without system Node.js or Python in command search and confirm installation completes without dependency downloads. Keep normal operating-system utilities available. For the npm route, record the bootstrap Node/npm versions and confirm the installed commands bind to private runtimes.
2. In a fresh terminal outside the checkout, inspect `graph-skill status` and `gskill --version`. Confirm rendered Skill, canvas and hook commands use absolute installed paths. Record upgrades separately from pristine installation.
3. Confirm Skill discovery, canvas server connection and the actual candidate Mod loading. In a fresh Claude Code session, request an ordinary change to an isolated Graph Skill fixture without mentioning the canvas or `show_graph`. Verify the changed source, natural graph call, native Browser launch and visibly updated shared HTML with the correct root. Preserve the first attempt. Record explicit display diagnostics separately from automatic follow-up.
4. Start with Claude's Browser pane closed and confirm it visibly opens without an opening click. Close it again, make a second ordinary edit, and verify the new graph appears from the same owned file. Check shared HTML, clipboard behavior and `/graph-skill-canvas` guidance. In Codex, observe the canvas filling its allocated panel and the visible folder/file view after clicking the path. Check that invalid snapshots clear the graph on reload and that normal server shutdown removes unchanged owned files. A previously open local preview can retain its rendered snapshot; a navigation acknowledgement alone cannot establish current visible content.
5. Repeat discovery and display in a new host conversation. Record connection, result delivery, native rendering and natural follow-up separately. Controlled lifecycle checks must also cover conflicts, edited owned files, rollback, target retention, cleanup and uninstall.

Build, command-line and automated checks establish their measured layers. A browser with a simulated MCP host verifies the page and bridge behavior. Real Codex and Claude observations establish their corresponding native-host claims. The [validation record](VALIDATION.md#local-html-source-freeze-acceptance) retains current results and gaps. Publication remains conditional on the final candidate's applicable checks, installed natural-display acceptance and public artifact read-back.
