# Graph Skill toolkit

Graph Skill toolkit supplies global runtime commands, shared agent instructions and a graph canvas for Codex Desktop and Claude Code Desktop. It uses the host's normal file tools for source browsing and editing. Both hosts receive graph data through the Model Context Protocol (MCP), the interface through which the agent calls the canvas tool. The current `0.3.4` source contains a minimum React/TypeScript prototype: one HTML interface, node selection and a row of host-operation test buttons. React composes the page from reusable components; TypeScript checks its data and operation shapes during development. HTML is the webpage containing the canvas, styling and interactions, and an adapter supplies data and permitted host actions to it. Codex uses an MCP App, the webpage attached to a tool result. Claude attaches its normal HTTP preview and opens or reuses the actual business `SKILL.md` to reveal its file view and sidebar. It then selects the separate interactive canvas at the local HTTP origin. Both useful views remain open, with the current canvas active. A Mod, a plugin that observes Claude Code events, supplies host presentation guidance and operations. The Python runtime remains independently installable, and business skills stay in the directories the user selects.

Toolkit state, commands and private runtimes live under `~/.local/share/graph-skill` on all supported systems. Here `~` means the current user's home directory. Explicit installation or update automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill` and installs the canvas Mod when Claude is selected. Version `0.3.4` retains client-based integration selection, progress, retry guidance, interrupted-installer recovery, automatic downloads and explicit cleanup. A host installation contains its Skills, canvas-server registration and follow-up hook, plus the Claude Mod where selected. The independently versioned Python runtime remains `0.1.0a1`. Complete archives target Windows x64, Apple Silicon macOS, Linux x64 and Linux ARM64. The [installation decisions](INSTALLATION-DECISIONS.md#toolkit-source-structure-decision-2026-10-10) explain ownership; the [current validation record](VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) owns acceptance conditions.

The source lives at `src/graph_skill_toolkit/`, directly beside the Python runtime, with one directory per executable responsibility and no inner `src/` layer. The [architecture map](ARCHITECTURE.md) locates each owner. [PROTOTYPE.md](PROTOTYPE.md) explains the nine controls; [MANUAL-TESTS.md](MANUAL-TESTS.md) gives their procedures and individual results. The user may perform native tests; agents may use Computer Use when needed and must release it immediately afterward. The native phase is attained within the recorded Claude and Codex candidates: actual controls, retained document/current canvas, ordinary-edit activation and session isolation have scoped observations. The recorded installed payload remains `0.3.3`; current `0.3.4` source, staged candidates and actual host sessions have separate identities. Final release gates, artifact binding, installed acceptance and public delivery remain open. The [current validation record](VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) owns those bounds and the applicability of reused observations.

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

Select a business root containing `SKILL.md` and `graph.yaml`. The agent uses native file tools for authoring and calls the runtime as needed. After related authoring, reading, compilation, prediction, execution, inspection, resume, result submission or golden evaluation, the shared instructions request the actual document and one normal `show_graph` call for that root. In Codex, issue a standalone `open_in_codex` file call with the exact `SKILL.md` path and `line=1`; after its response, call `show_graph` in a separate tool invocation as the final presentation. These calls occupy distinct tool batches. The hook supplies path evidence, and the host controls panel opening and focus. Existing views are reused and other pages remain open. Explicit user preferences can narrow or disable the follow-up.

An explicit call uses the `graph-skill-canvas` server's `show_graph` tool with the verified absolute `skill_root`. Its optional `presentation` value is `mcp-app` or `html`; omission uses the MCP App route. The tool returns the graph and its resolved root. HTML presentation requires `preview_project_root`, which the Claude Mod obtains from the actual host session; it may differ from the business Skill root. That request starts the owned HTTP view, merges one temporary URL-only entry into the host project's `.claude/launch.json`, and returns the entry name and view URL. The displayed root is the server's resolved business path. Omitting the root returns a labeled three-node demonstration; Claude HTTP presentation requires both explicit roots.

The canvas displays root inputs, phases, dependencies and outputs, with each subgraph phase represented as one node. Runtime compilation owns full format validation. Graph presentation does not import business Python; runtime compilation or inspection of trusted skills can load their declared code. HTML presentation starts a service and changes its owned project preview entry, so `show_graph` declares that it is not read-only. Complete property and option editing remains in the [broader design](../../docs/design/graph-skill-agent-plugin.md).

The shared [graph renderer](ui/canvas/view.tsx) draws validated presentation data. The [workbench](ui/workbench/index.tsx) owns root display, selection, test controls and operation results; [the HTML template](ui/template/canvas.html) owns the shell and styling. The build embeds both browser adapters into one `dist/canvas.html`. Codex receives that template through MCP; Claude receives it with current graph/root and connection JSON in one data slot. The executable UI and template are shared. The canvas shows the graph name, resolved root, node and edge counts, and topology. Invalid data clears the drawing and reports the condition. The prototype does not implement a full editor; use the host's file tools to edit the selected root.

Select a node by clicking it or using Tab and Enter/Space. The side panel shows the selected node and the context available for delivery. The nine controls inspect capabilities, request root/file opening, fill a draft, send a prompt, supply selected context, list available tools, perform read-only graph inspection, and request that the host read the selected Skill. Edit the test prompt before using draft or send. Selection alone does not send context or start a host action. Unavailable controls display their reason. The page distinguishes completed interface operations, accepted requests, pending results, rejection and errors; an accepted request does not prove a finished conversation, open file or used skill.

Read-only inspection calls the canvas server's `inspect_graph` for an exact canonical root already selected by `show_graph` in that connection. It reads current graph presentation data without executing business code or writing a preview. This tool is distinct from runtime inspection. Codex calls the originating canvas server when the host declares that capability. Draft filling uses its advertised draft-message extension and appends without submission; host-wide tool enumeration is explicitly unavailable. Claude uses the Mod's host APIs through a per-root, authenticated loopback connection owned by the canvas server. Its fixed inspection submits one normal host prompt, and the conversation contains the actual tool call and graph result. The [prototype contract](PROTOTYPE.md) defines the allowed operations and their result semantics.

Claude's [Mod](adapters/claude/mod/hooks/register.js) detects native preview tools, obtains the live session project root and requests HTML presentation during the normal graph call. It validates configuration ownership, the actual business-document identity and the same-origin view URL. Normal follow-up inventories tabs, attaches HTTP and retains its returned tab ID, then opens or reuses the exact `SKILL.md` when absent or when the pane is hidden. It navigates the retained HTTP tab and selects that same tab. A separate final `tabs_context` call must establish the active current canvas, displayed pane, retained exact document and preserved prior pages. The sequence retains both useful views and reuses their identities. The [manual guide](MANUAL-TESTS.md) defines native acceptance. `/graph-skill-canvas` supplies the latest view and the same guidance. Missing APIs, wrong identity or refusal produce a diagnostic. The Mod also polls for explicit page operations and leaves graph rendering to the shared page.

Claude draft filling appends to the host input and reports a refusal while preserving the existing draft. Sending submits a new prompt and reports acceptance; observe the conversation for its actual response. Root/file and Skill controls submit explicit requests to open the selected path or read `SKILL.md`, preserving the distinction between request and effect. Saved same-root selection accompanies canvas-submitted text as labeled data, and the ordinary prompt hook supplies it to normal submissions. If an operation is pending, the page initially blocks another host action. Use its result-check button to read the same Claude receipt without resending the action. After observing the host, “已查看宿主，继续测试” allows other tests while retaining the unknown result. Session end disconnects the view; a new graph call creates the current connection and restarts Mod polling when needed.

The HTTP service owns an in-memory page at a random per-view URL. Repeated graph calls replace that root's active snapshot; normal navigation loads it again. The page does not watch business files. A failed graph read replaces an existing owned view with an error snapshot, so reloading clears the stale graph. Session end invalidates the view; a new graph display creates the next connection. The origin landing page contains no graph or credentials. Graph pages contain only their browser credential, and page actions remain at the same origin.

The [preview configuration owner](adapters/claude/preview_configuration/index.mjs) preserves unrelated launch entries, rejects redirected or hardlinked resources and serializes writes to the actual host project's configuration. Normal MCP shutdown closes HTTP sockets and removes only unchanged owned configuration; externally edited content is preserved. Startup alone creates none of these resources. Claude's file preview checks the actual `SKILL.md` against its 512 KiB limit and reports an explicit oversize error while preserving the source. HTTP graph delivery has no such file-loader bound. Business source remains user-owned.

Codex's file control requests `openai/files/open` when the host advertises that extension. If it explicitly rejects the request and messaging is available, the adapter reports that boundary and asks the host agent to open the same file. The folder control directly asks the host agent to open the selected root. Its observed successful effect displays the exact contents in Windows Explorer; the embedded directory-preview attempt failed. An unknown request outcome remains pending for observation. Claude's root/file controls submit their corresponding host prompts. Native visible opening requires its own observation; a message or file-request acknowledgment establishes only acceptance.

Codex resource metadata advertises the sidebar's `fullscreen` mode as its sole mode. One opaque view identifier per canonical root and server connection permits host-owned reuse; Codex also scopes it to the conversation, server and resource. Closing hides that retained mode, and a later explicit display reopens the canvas. The [resource and session owners](ARCHITECTURE.md#shared-view-and-host-delivery) keep these host concerns outside the shared page. Page loading performs no file-opening or focus action.

## Run from source

A cloned repository or downloaded source archive can run without building a release ZIP. Install Python 3.11 or later, `uv`, Node.js 22 or later and npm, then run these commands from the repository root:

```text
uv sync
npm ci --prefix src/graph_skill_toolkit
npm run typecheck --prefix src/graph_skill_toolkit
npm run build --prefix src/graph_skill_toolkit
uv run gskill compile examples/hello-world
```

The last command exercises the Python runtime. To launch the canvas MCP server:

```text
npm start --prefix src/graph_skill_toolkit
```

This starts a standard-input/output server for an MCP host. The host opens the graphical view after a graph call. To use source from Desktop, explicitly register an MCP server that runs Node.js with the absolute path to `src/graph_skill_toolkit/dist/server.mjs`. Its source tree and Node executable must remain available. Claude also needs the source candidate's `src/graph_skill_toolkit/adapters/claude/mod` directory selected by its actual Mod loader and Browser tools enabled. Verify the loaded Mod identity separately from the connected MCP server identity; they can come from different candidates. A temporary development selection must preserve and restore any installer-owned setting. Skill installation, template rendering and hook registration remain separate setup steps. The published toolkit installer supplies the complete released setup described above.

Runtime-only deployments can use the source command above or install the separately built `graph-skill-runtime` wheel into their own Python environment. The Python package retains Python `>=3.11`, its Python API, CLI and MCP tools. Its installation is independent of toolkit Node.js, canvas assets and host configuration; the runtime is not published on PyPI.

## Build release archives

Release assembly adds pinned-runtime downloads and payload construction to the source workflow. Use this procedure after a release version and publication work are authorized. Prepare and commit all source inputs, then build from that clean commit. The builder rejects tracked changes and Git-visible untracked files, records source commit/tree identities and checks them again before completing assembly. Ordinary source execution above can use a working checkout.

After the JavaScript build, run from the repository root:

```text
uv build --no-sources --wheel --out-dir src/graph_skill_toolkit/release/runtime-build
python -B src/graph_skill_toolkit/installer/bundle/__main__.py --runtime-wheel src/graph_skill_toolkit/release/runtime-build/graph_skill_runtime-0.1.0a1-py3-none-any.whl --platform win32-x64
```

Choose another declared target with `--platform`. [`installer/runtime_payload/runtime-lock.json`](installer/runtime_payload/runtime-lock.json) owns pinned interpreter inputs. The builder exports `uv.lock` with `uv --locked` and installs hash-checked binary wheels for the selected platform. Missing compatible inputs stop assembly. Intel-only native compilation is removed from this release path.

The output is `release/graph-skill-0.3.4-TARGET.zip` with an adjacent JSON receipt binding its source, archive, runtime wheel and dependency inputs. Generate the lightweight npm package from the same clean source after the JavaScript build:

```text
npm run pack:installer --prefix src/graph_skill_toolkit
```

The packer derives the package version from the product module and records `sourceCommit`; its output is `release/graph-skill-toolkit-0.3.4.tgz`. The product build module remains private. The generated distribution contains the command entry and bundled installer, with no postinstall host mutation. The release requires the tarball, four ZIPs and `SHA256SUMS.txt`. Final hashes and post-build evidence remain outside packaged documents; changing an input requires rebuilding and verifying the affected artifacts.

## Human native acceptance

Native acceptance follows [MANUAL-TESTS.md](MANUAL-TESTS.md). It supplies host preparation, opening and tab-preservation checks, nine button tests (T01–T09), ordinary-edit automatic display (T10), and real session isolation (T11). Codex also has closed-canvas redisplay and repeated-reuse observations. Agents prepare source and reconcile observed effects. Computer Use is permitted when needed and must be released immediately after use. The ledger records the actual passed effects, explicit unavailable capability and remaining limits.

The Claude project uses the isolated `graph-skill-prototype` server and project Mod. Codex user and project configurations point to the immutable current stage, whose actual native loading was separately observed. The [current validation record](VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) binds both hosts' applicable candidates and explains the scoped reuse of unchanged button/isolation evidence after the Codex resource-mode change. These stages remain separate from the installed `0.3.3` payload. Record the actual host version, session, displayed root and candidate identity. Request acceptance establishes its acknowledged request; replies, visible files, consumed context and Skill reads require their observed effects.

Eventual release acceptance retains additional requirements. The complete ZIP must install in a fresh environment without system Node/Python or dependency downloads; the npm route must bind the installed commands to private runtimes. Fresh-terminal status, absolute installed Skill/canvas/hook paths, pristine installation versus upgrade, and actual server/Mod loading require separate evidence. Installed ordinary-edit display must visibly open the current graph without an opening click, repeat after closing the pane and repeat in a new conversation. Lifecycle acceptance covers conflicts, edited owned resources, rollback, target retention, cleanup and uninstall. The HTTP source stage does not replace these installed-artifact checks.

Build, command-line and simulated-host checks establish their measured layers. The [validation record](VALIDATION.md#current-baseline-retained-skillmd-and-http-canvas-2026-10-10) retains current results and gaps. Native stage acceptance is attained within the recorded scope, while the parent delivery goal remains partially attained. Publication remains conditional on the final candidate's applicable checks, installed natural-display acceptance and public artifact read-back. Evidence links under `evidence/` identify locally retained review materials; those ignored files may be absent from a public source checkout.
