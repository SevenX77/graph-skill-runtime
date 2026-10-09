# Graph Skill toolkit

Graph Skill toolkit supplies global runtime commands, shared agent instructions and a graph canvas for Codex Desktop and Claude Code Desktop. It uses the host's normal file tools for source browsing and editing. The canvas is an MCP App: an HTML view attached to a tool result through the Model Context Protocol (MCP). The Python runtime remains independently installable, and business skills stay in the directories the user selects.

Version `0.3.0` adds an npm bootstrap installer, automatic release downloads for updates and explicit cleanup of inactive version caches. It packages Windows x64, Apple Silicon macOS, Linux x64 and Linux ARM64. Intel Mac packaging has been withdrawn at the user's request. The [validation record](VALIDATION.md) owns the current decision, publication gates and historical evidence. At documentation freeze, the new build, downloads and Desktop operation remain unverified; use the release's final evidence to identify published bytes.

## Install

The small npm package downloads the matching complete archive and runs its installer. This entry requires Node.js 18 or later, npm and network access. The installed toolkit uses its private Node.js `24.21.0` and CPython `3.13.16`; it does not rely on the bootstrap interpreter afterward.

After the `0.3.0` GitHub release has been published and verified, run:

```text
npx --yes --package=https://github.com/SevenX77/graph-skill-runtime/releases/download/graph-skill-toolkit-v0.3.0/graph-skill-toolkit-0.3.0.tgz graph-skill install
```

The package resolves its own version's GitHub release, selects the operating system and processor architecture, verifies the archive against `SHA256SUMS.txt`, extracts it and invokes the explicit installer. Downloading the npm package alone performs no host configuration writes. npm registry publication is pending authentication and package-ownership verification; `npx graph-skill-toolkit@latest` is not an available installation promise.

Alternatively, download a complete ZIP from the release assets. This route requires no system Node.js or Python and no dependency downloads during installation:

| Computer | Archive |
| --- | --- |
| Windows x64 | `graph-skill-0.3.0-win32-x64.zip` |
| Mac with Apple Silicon | `graph-skill-0.3.0-darwin-arm64.zip` |
| Linux x64 with glibc | `graph-skill-0.3.0-linux-x64.zip` |
| Linux ARM64 with glibc | `graph-skill-0.3.0-linux-arm64.zip` |

Here `darwin` means macOS, and glibc is the Linux system library used by these binaries. Intel Mac and Windows ARM64 have no `0.3.0` installer. Each ZIP contains private runtimes, the runtime wheel and its locked base dependencies. Optional embedded-provider extras and additional libraries required by business skills need separate deployment.

Extract the matching ZIP, preserving executable permissions on macOS/Linux. On Windows, run `install.cmd`; on macOS/Linux, run `sh install.sh` from the extracted directory. Keep the extracted payload together. An unbuilt source checkout is not an installer archive.

Add `--targets codex` or `--targets claude` to install for one host, and `--dry-run` to preview the operation. First installation defaults to both hosts. An upgrade without `--targets` retains the target list in the existing installation manifest. Only selected hosts' configuration overrides are checked: `CODEX_HOME` for Codex and `CLAUDE_CONFIG_DIR` for Claude must resolve to their respective default user profiles. Custom selected profiles remain unsupported.

If Codex has the earlier `graph-skill-canvas@graph-skill-local` plugin enabled, disable it through Desktop before installation. The installer preserves conflicting configuration and stops. It also preserves unmanaged collisions and edited toolkit-owned resources; resolve the reported conflict before retrying.

After installation, open a fresh terminal for the updated PATH, the command search list. Restart or reload the host to discover the Skills, canvas server and hook. A Skill is a discoverable instruction file that guides the agent; the hook supplies follow-up guidance after tool use. The host retains its normal trust and approval decisions.

The bundled Node.js prerequisites include Windows 10/Server 2016 or later, macOS 13.5 or later, and Linux kernel 4.18 or later with glibc 2.28 and libstdc++ 6.0.25 or later. libstdc++ is the C++ runtime library. Upstream also requires a vendor-supported operating system. These are [Node.js prerequisites](https://github.com/nodejs/node/blob/v24.21.0/BUILDING.md#platform-list); complete toolkit compatibility still needs native evidence.

## Update, inspect and remove

```text
graph-skill update
graph-skill update "EXTRACTED_DIR"
graph-skill status
graph-skill cleanup --dry-run
graph-skill cleanup
graph-skill uninstall
```

`graph-skill update` finds the newest published toolkit release, including toolkit previews, downloads the matching archive, verifies its checksum and runs the incoming installer. Supplying an absolute extracted release directory selects the offline route. Install/update accept `--targets codex,claude` and `--dry-run`. To upgrade an older toolkit that lacks automatic updates, use the new npm entry or the new ZIP's installer.

`cleanup` removes only verified inactive version caches. It preserves the active version and the currently executing installer, and skips unknown or modified directories. Close hosts and other processes that may still use old payloads before cleanup, then restart them against the active installation. `--dry-run` shows the proposed cleanup first. Cleanup is an explicit operation; updating does not broadly delete old directories.

Uninstall removes managed host registrations, Skills, command launchers and PATH integration while retaining version caches. Business files and runtime run state remain user-owned. After uninstall removes the global command, invoke the same npm entry above with `cleanup` in place of `install` to clean verified caches. Its report identifies the executing cache that must remain; this does not promise complete removal of cached payloads. `status` describes recorded ownership; actual host loading must be observed in the host.

| Location | Toolkit-owned content |
| --- | --- |
| Windows `%LOCALAPPDATA%/GraphSkill`; macOS/Linux `~/.local/share/graph-skill` | Product state, `install.json`, commands and `versions/<version>-<digest>` payloads. |
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

The canvas displays root inputs, phases, dependencies and outputs, with each subgraph phase represented as one node. Runtime compilation owns full format validation. Presentation reads do not import business Python; runtime compilation or inspection of trusted skills can load their declared code. Complete property and option editing remains in the [broader design](../../docs/design/graph-skill-agent-plugin.md).

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

The output is `release/graph-skill-0.3.0-TARGET.zip` with an adjacent JSON receipt binding its source, archive, runtime wheel and dependency inputs. Generate the lightweight npm package from the same clean source after the JavaScript build:

```text
npm run pack:installer --prefix plugins/graph-skill
```

The packer derives the package version from the product module and records `sourceCommit`; its output is `release/graph-skill-toolkit-0.3.0.tgz`. The product build module remains private. The generated distribution contains the command entry and bundled installer, with no postinstall host mutation. The release contains the tarball, four ZIPs and `SHA256SUMS.txt`. Final hashes and post-build evidence remain outside packaged documents; changing an input requires rebuilding and verifying the affected artifacts.

## Manual Desktop acceptance

The user owns these observations in Codex Desktop and an authenticated Claude Code Desktop session. Record toolkit and host versions, installation route and selected hosts.

1. For the complete ZIP route, use a fresh launch environment without system Node.js or Python in command search and confirm installation completes without dependency downloads. Keep normal operating-system utilities available. For the npm route, record the bootstrap Node/npm versions and confirm the installed commands bind to private runtimes.
2. In a fresh terminal outside the checkout, inspect `graph-skill status` and `gskill --version`. Confirm rendered Skill, canvas and hook commands use absolute installed paths. Record upgrades separately from pristine installation.
3. Confirm Skill discovery and canvas server connection. Ask the agent to read a known business skill and observe whether it naturally calls `show_graph`. Confirm graph and root identity. If follow-up is absent, test an explicit call and record it separately.
4. Observe the canvas filling its allocated panel and the actual host folder/file view after clicking the path. A delivered tool result, request acknowledgement or fallback message alone does not establish either result.
5. Repeat discovery and display in a new host conversation. Record connection, result delivery, native rendering and natural follow-up separately. Controlled lifecycle checks must also cover conflicts, edited owned files, rollback, target retention, cleanup and uninstall.

Build, CLI and automated checks do not establish Desktop operation. Native Claude Code Desktop rendering, hook discovery and agent follow-through retain their evidence gaps until observed on the delivered version. Keep successful lower-level results while identifying the exact remaining gap in the shared-host workflow.
