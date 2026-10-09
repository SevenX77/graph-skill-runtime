# Graph Skill toolkit

Graph Skill toolkit supplies global runtime commands, shared agent instructions and a graph canvas for Codex Desktop and Claude Code Desktop. It uses the host's normal file tools for source browsing and editing. The canvas is an MCP App: an HTML view attached to a tool result through the Model Context Protocol (MCP). The Python runtime remains independently installable, and business skills stay in the directories the user selects.

Version `0.3.3` places toolkit state, commands and private runtimes under `~/.local/share/graph-skill` on all supported systems. Here `~` means the current user's home directory. Explicit installation or update automatically migrates an intact toolkit-owned Windows installation from `%LOCALAPPDATA%/GraphSkill`. The toolkit retains client-based adapter selection, progress, retry guidance, interrupted-installer recovery, automatic downloads and explicit cleanup. An adapter supplies the host's Skills, canvas-server registration and follow-up hook. The independently versioned Python runtime remains `0.1.0a1`. Complete archives target Windows x64, Apple Silicon macOS, Linux x64 and Linux ARM64. The [path decision](INSTALLATION-DECISIONS.md#claude-path-repair-decision-2026-10-09) explains the migration; the [current validation record](VALIDATION.md#current-baseline-claude-path-repair-and-automatic-canvas-2026-10-09) owns its acceptance conditions.

The path repair addresses a measured Windows Claude package-context startup failure. Its source implementation is present; real installed migration and automatic canvas display remain pending at this document's source freeze. Publication requires an ordinary Graph Skill edit in real Claude Code to produce the visible correct updated canvas. Final candidate identities and post-build acceptance belong in the [release notes](https://github.com/SevenX77/graph-skill-runtime/releases) and retained receipts. The validation record preserves the earlier AppData failure and its bounded diagnostic evidence.

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

The completion message gives an absolute `status` command that works immediately in the current terminal. Open a fresh terminal to use `graph-skill` and `gskill` through the updated PATH. Restart the selected host to discover the Skills, canvas server and hook. A Skill is a discoverable instruction file that guides the agent; the hook supplies follow-up guidance after tool use. The host retains its normal trust and approval decisions. Ask the agent to open a Graph Skill folder and show its graph, then verify the displayed root and canvas in that host.

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
| Claude `~/.claude.json` and `~/.claude/settings.json` | Named canvas server selector and owned hook entry. |
| User command search path | Windows user PATH entry; marked POSIX PATH blocks in the selected Bash login profile and `.zprofile`. |

The installer preflights every selected host before provisioning, merges only owned configuration content and preserves unrelated settings and independent MoirAI/runtime integrations. Updates require recorded owned content to remain intact. Rollback restores a touched file only while its bytes equal the operation's after-image; a concurrent edit is preserved and reported as incomplete rollback.

## Runtime and canvas

The global `gskill` command exposes runtime operations. `graph-skill <runtime-command> [arguments]` forwards the same operation, for example:

```text
gskill compile "ABSOLUTE_SKILL_ROOT"
gskill inspect "ABSOLUTE_SKILL_ROOT" --call-graph
graph-skill config resolve "ABSOLUTE_SKILL_ROOT"
```

Commands return structured JSON by default. Shell invocation retains the host-native executor default, where the host handles Agent phases. Vendor CLI execution is a separate explicit `--executor cli` choice. The shared [Skill](skills/graph-skill/SKILL.md) and [CLI reference](skills/graph-skill/references/cli.md) describe runtime operations and durable Agent result submission. Installation renders absolute private-interpreter and reference paths into those templates. Python runs with `-I -B -X utf8` for isolated module search, no bytecode writes and UTF-8 output.

Select a business root containing `SKILL.md` and `graph.yaml`. The agent uses native file tools for authoring and calls the runtime as needed. After related authoring, reading, compilation, prediction, execution, inspection, resume, result submission or golden evaluation, the shared instructions request one normal `show_graph` call for that root. The hook supplies path evidence; the agent makes the call, and the host controls panel opening and focus. Explicit user preferences can narrow or disable the follow-up.

An explicit call uses the `graph-skill-canvas` server's `show_graph` tool with the verified absolute `skill_root`. Omitting the root displays a labeled three-node demonstration. The tool returns `structuredContent.graph`, `structuredContent.skillRoot` and `ui://graph-skill/canvas-v2.html`.

The canvas displays root inputs, phases, dependencies and outputs, with each subgraph phase represented as one node. Runtime compilation owns full format validation. Presentation reads do not import business Python; runtime compilation or inspection of trusted skills can load their declared code. Complete property and option editing remains in the [broader design](https://github.com/SevenX77/graph-skill-runtime/blob/graph-skill-toolkit-v0.3.3/docs/design/graph-skill-agent-plugin.md).

The top-left path button requests native folder opening through `openai/files/open` when the host advertises that capability. If the request is absent or rejected, it asks the host agent to browse the root; a file-only host can show `SKILL.md`. The [OpenAI UI contract](https://developers.openai.com/plugins/build/chatgpt-ui) defines the file bridge. Successful dispatch and an actual visible folder view are separate observations.

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

This starts a standard-input/output server for an MCP host; it does not open a graphical application. To use it from Desktop, explicitly register an MCP server that runs Node.js with the absolute path to `plugins/graph-skill/dist/server.mjs`. Its working source tree and Node executable must remain available. Skill installation, template rendering and hook registration are separate setup steps. Downloading or building source does not discover or install those integrations automatically. Use the toolkit installer for the complete global setup.

Runtime-only deployments can use the source command above or install the separately built `graph-skill-runtime` wheel into their own Python environment. The Python package retains Python `>=3.11`, its Python API, CLI and MCP tools. Its installation is independent of toolkit Node.js, canvas assets and host configuration; the runtime is not published on PyPI.

## Build release archives

Release assembly adds pinned-runtime downloads and payload construction to the source workflow. Prepare and commit all source inputs, then build from that clean commit. The builder rejects tracked changes and Git-visible untracked files, records source commit/tree identities and checks them again before completing assembly. Ordinary source execution above does not require a clean Git checkout.

After the JavaScript build, run from the repository root:

```text
uv build --no-sources --wheel --out-dir plugins/graph-skill/release/runtime-build
python -B plugins/graph-skill/packaging/bundle.py --runtime-wheel plugins/graph-skill/release/runtime-build/graph_skill_runtime-0.1.0a1-py3-none-any.whl --platform win32-x64
```

Choose another declared target with `--platform`. [`packaging/runtime-lock.json`](packaging/runtime-lock.json) owns pinned interpreter inputs. The builder exports `uv.lock` with `uv --locked` and installs hash-checked binary wheels for the selected platform. Missing compatible inputs stop assembly. Intel-only native compilation is removed from this release path.

The output is `release/graph-skill-0.3.3-TARGET.zip` with an adjacent JSON receipt binding its source, archive, runtime wheel and dependency inputs. Generate the lightweight npm package from the same clean source after the JavaScript build:

```text
npm run pack:installer --prefix plugins/graph-skill
```

The packer derives the package version from the product module and records `sourceCommit`; its output is `release/graph-skill-toolkit-0.3.3.tgz`. The product build module remains private. The generated distribution contains the command entry and bundled installer, with no postinstall host mutation. The release contains the tarball, four ZIPs and `SHA256SUMS.txt`. Final hashes and post-build evidence remain outside packaged documents; changing an input requires rebuilding and verifying the affected artifacts.

## Manual Desktop acceptance

The release coordinator owns the authorized Windows migration and real Claude Code acceptance before publishing `0.3.3`. The checklist also supports user verification in Codex Desktop and Claude Code. Record toolkit and host versions, installation route, selected hosts and candidate identity.

1. For the complete ZIP route, use a fresh launch environment without system Node.js or Python in command search and confirm installation completes without dependency downloads. Keep normal operating-system utilities available. For the npm route, record the bootstrap Node/npm versions and confirm the installed commands bind to private runtimes.
2. In a fresh terminal outside the checkout, inspect `graph-skill status` and `gskill --version`. Confirm rendered Skill, canvas and hook commands use absolute installed paths. Record upgrades separately from pristine installation.
3. Confirm Skill discovery and canvas server connection. In a fresh Claude Code session, request an ordinary change to a known business Graph Skill without mentioning the canvas or `show_graph`. Verify the changed source, natural canvas tool call and visibly updated graph with the correct root. Preserve the first attempt. An explicit display diagnostic is recorded separately and cannot satisfy automatic follow-up acceptance.
4. Observe the canvas filling its allocated panel and the actual host folder/file view after clicking the path. A delivered tool result, request acknowledgement or fallback message alone does not establish either result.
5. Repeat discovery and display in a new host conversation. Record connection, result delivery, native rendering and natural follow-up separately. Controlled lifecycle checks must also cover conflicts, edited owned files, rollback, target retention, cleanup and uninstall.

Build, CLI and automated checks establish their measured layers. Native Claude Code rendering and agent follow-through require the actual installed-candidate observations above. Missing or failed automatic display blocks publication of the repair. The broader Codex, viewport and folder-opening criteria retain their separately recorded evidence and gaps.
