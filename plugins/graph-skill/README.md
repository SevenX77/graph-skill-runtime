# Graph Skill toolkit

Graph Skill toolkit combines a private Python runtime, a private Node.js runtime, shared agent instructions and a graph canvas in one local package for Codex Desktop and Claude Code Desktop. Version `0.2.0` uses the host's normal file and shell tools for authoring and runtime operations. A shared MCP App provides the canvas. MCP, the Model Context Protocol, connects host tools to external services; an MCP App adds an HTML view to a tool result.

The runtime remains independently installable. The toolkit owns its user-level installation, while business skills stay in the directories the user selects. The current canvas displays root graph nodes and edges, fills its allocated viewport and provides a host folder shortcut. Complete node properties and option editing remain in the [broader design, available in the repository](../../docs/design/graph-skill-agent-plugin.md).

Version `0.2.0` source, builds and archive inspection are attained for the recorded Windows x64, macOS ARM64, Linux x64 and Linux ARM64 candidates. Installation lifecycle and native Desktop behavior remain unverified. The [validation record](VALIDATION.md) owns that scope and preserves earlier canvas, host and `0.1.0` build results as history. Final archive identities belong to their adjacent receipts and external inspection evidence.

## Install the local package

Choose a `0.2.0` archive for the computer's operating system and processor architecture. Target definitions cover Windows x64/ARM64, macOS x64/ARM64 and Linux glibc x64/ARM64. A defined target becomes available only after its archive is built and inspected; [the validation record](VALIDATION.md) identifies the actual outputs. Each archive contains its own Node.js, CPython, runtime wheel and installed base dependencies. Node.js executes the toolkit and canvas; CPython executes the Python runtime. The installer uses these private copies and requires neither a preinstalled Node.js/Python command nor package-index access.

The complete payload covers the engine's locked base dependencies. Optional embedded-provider extras and additional Python libraries required by a business skill need separate deployment planning and validation.

Archive names follow `graph-skill-0.2.0-TARGET.zip`, where `TARGET` is `win32-x64`, `win32-arm64`, `darwin-x64`, `darwin-arm64`, `linux-x64` or `linux-arm64`. Here `darwin` identifies macOS. The extracted directory has the same name without `.zip`.

The assembled candidate targets are `win32-x64`, `darwin-arm64`, `linux-x64` and `linux-arm64`. Their archives live in this module's `release/` directory. Use the adjacent receipt and the external inspection record to identify the final rebuilt bytes.

Windows ARM64 and macOS x64 are unavailable for this candidate: the locked `cryptography==50.0.1` dependency has no compatible binary wheel for either target. Their target definitions remain available for a future reviewed dependency resolution. The [validation record](VALIDATION.md) retains the failed assembly evidence.

The product pins Node.js `24.21.0` and CPython `3.13.16`. Those versions are product build inputs. The operating system and native libraries must satisfy the bundled runtimes and dependencies. Linux targets use glibc, the standard C library used by those selected binary builds. Native compatibility requires operation on the actual target; supported minimum operating-system versions need their own evidence. Connected agents and business operations that use a network retain their own network requirements. The installer uses default host user profiles and requires no Codex or Claude command-line executable.

For the bundled Node.js version, upstream lists Windows 10/Server 2016 or later for x64, macOS 13.5 or later, and Linux kernel 4.18 or later with glibc 2.28 and libstdc++ 6.0.25 or later. libstdc++ is the C++ runtime library used by those Linux binaries. Upstream also requires an operating-system version still supported by its vendor. These are [Node.js prerequisites](https://github.com/nodejs/node/blob/v24.21.0/BUILDING.md#platform-list); full toolkit compatibility requires the separate native observations in the validation record.

Before running the installer, disable an enabled `graph-skill-canvas@graph-skill-local` plugin in Codex Desktop. That earlier installation conflicts with the toolkit's canvas ownership. The installer preserves the conflicting configuration and stops until the user resolves it.

1. Obtain the built archive matching the computer's operating system and architecture, then extract it to a local directory. On macOS or Linux, use an extractor that preserves executable permissions.
2. On Windows, double-click `install.cmd` in that directory. On macOS or Linux, open a terminal in the extracted directory and run `sh install.sh`.
3. Open a new terminal for the updated PATH, the operating system's command search list. Restart or reload the host as needed to discover the installed Skills and canvas connection.
4. Review the installed hooks through the host's normal controls and complete the manual checks below. The host retains its trust and approval decisions.

To preview the installation, run `install.cmd --dry-run` on Windows or `sh install.sh --dry-run` on macOS/Linux. Add `--targets codex` or `--targets claude` to select one host. These flags apply to the incoming installer for both first installation and upgrade.

Both hosts are selected by default. A Skill is a discoverable instruction file that guides the host agent. Each selected host receives `graph-skill` and `graph-skill-canvas`, one `graph-skill-canvas` MCP server connection and a `PostToolUse` hook, a handler that supplies follow-up guidance after tool use.

The installer targets `~/.codex` and `~/.claude` as their default configuration directories. A `CODEX_HOME` or `CLAUDE_CONFIG_DIR` override is accepted only when it resolves to the corresponding default. Other unmanaged collisions or edited toolkit-owned resources are preserved and block the operation; resolve the reported ownership conflict before retrying.

## Commands and installed files

The installed `graph-skill` command manages the toolkit. Replace `EXTRACTED_DIR` with the absolute directory containing an extracted release:

```text
graph-skill install "EXTRACTED_DIR"
graph-skill update "EXTRACTED_DIR"
graph-skill status
graph-skill uninstall
```

`install` accepts an optional bundle path. `update` requires the extracted release directory. Install and update accept `--targets codex,claude` and `--dry-run`; the target list defaults to both hosts. A dry run reports the proposed operation and conflicts before provisioning. The extracted installer is the entry point for first installation and upgrade from `0.1.0`; it runs the incoming archive's private runtimes. Keep its payload together in the extracted directory. The installer validates the target and bound file hashes before writing host configuration.

For an upgrade from `0.1.0`, extract the matching new archive and run its `install.cmd` or `sh install.sh`. The incoming installer reads the existing ownership manifest and applies the new payload only when prior owned resources remain intact. Review any reported conflict before retrying. The new private interpreter binding applies to the new installation; older version directories remain retained for possible existing references and running processes.

The global `gskill` command runs the installed runtime. This command-line interface (CLI) accepts runtime operations and arguments through a shell. `graph-skill <runtime-command> [arguments]` forwards the same runtime command and arguments; for example, `graph-skill compile` invokes runtime compilation. For a verified business skill root:

```text
gskill compile "ABSOLUTE_SKILL_ROOT"
gskill inspect "ABSOLUTE_SKILL_ROOT" --call-graph
graph-skill config resolve "ABSOLUTE_SKILL_ROOT"
```

Runtime commands return structured JSON by default. Calling them from a shell preserves executor selection: the built-in default is host-native, where the host handles Agent phases. Direct execution through vendor CLI processes is a separate explicit `--executor cli` choice. Read the shared [Skill](skills/graph-skill/SKILL.md) and [CLI reference](skills/graph-skill/references/cli.md) for runtime operations and durable Agent result submission. Their source templates contain command placeholders; installation renders absolute private-interpreter, toolkit and reference paths. Python uses `-I -B -X utf8` to isolate module search, suppress bytecode writes and select UTF-8 mode. Windows PowerShell uses `&` before a rendered quoted executable; POSIX shells invoke the rendered command directly.

| Location | Product ownership |
| --- | --- |
| Windows `%LOCALAPPDATA%/GraphSkill`; macOS/Linux `~/.local/share/graph-skill` | Product state, `install.json` ownership manifest, command launchers and immutable `versions/<version>-<digest>` payload/runtime directories. |
| Codex `~/.agents/skills/graph-skill` and `~/.agents/skills/graph-skill-canvas` | Rendered toolkit Skills and references. |
| Codex `~/.codex/config.toml` and `~/.codex/hooks.json` | Marked canvas server block and the owned hook entry. |
| Claude Code `~/.claude/skills/graph-skill` and `~/.claude/skills/graph-skill-canvas` | The same rendered toolkit Skills and references. |
| Claude Code `~/.claude.json` and `~/.claude/settings.json` | Named canvas server selector and the owned hook entry. |
| User command search path | Windows user PATH entry; on POSIX, a marked PATH block in the first existing Bash login profile, or `.profile` when none exists, and in `.zprofile`. |

Every requested target is checked before provisioning. The installer merges only its owned configuration content and preserves unrelated settings and independently installed MoirAI/runtime MCP integrations. Updates require the recorded owned content to remain intact. Rollback restores a touched file only while its bytes match the operation's after-image; a concurrent edit is retained and reported as incomplete rollback. This check coordinates the installer's own writes and does not lock arbitrary host writers.

Uninstall removes owned registrations, Skills, launchers and PATH integration. It retains the version cache explicitly. Business files and runtime run state remain user-owned. `status` reports installation ownership; actual host loading is checked in the host.

## Use the graph canvas

Select a business skill directory containing `SKILL.md` and `graph.yaml`. The host agent resolves its absolute path, uses native file tools for edits and calls the installed runtime as needed. After related authoring, reading, compilation, prediction, execution or inspection, the shared instructions request one normal `show_graph` call with that root. Resume, Agent result submission and golden evaluation receive the same follow-up.

The hook reads path evidence and supplies agent context. The agent performs the tool call, and the host decides whether its app panel opens or receives focus. The shared Skills cover operations whose selected root cannot be inferred from tool path evidence. Guidance from both sources is deduplicated for the same operation and root. An explicit user choice can narrow or disable automatic display.

An explicit canvas call uses the `graph-skill-canvas` server's `show_graph` tool with `skill_root` set to the verified absolute root. The host may namespace the tool name. Omitting that input displays the labeled three-node demonstration. The result carries `structuredContent.graph` and `structuredContent.skillRoot` and links `ui://graph-skill/canvas-v2.html`.

The presentation reader shows root inputs, phases, dependencies and outputs. A subgraph phase remains one node. Full portable-format validation and execution belong to the Python runtime. The canvas reads presentation data without importing business Python; compiling or inspecting a trusted skill can load its declared code.

The top-left path button requests native folder opening. Where the host advertises the OpenAI file capability, the app sends `openai/files/open` with the absolute root. If that route is absent or rejected, it asks the host agent to use native file browsing. A file-only host can show `SKILL.md` and explain the available view. The [OpenAI UI documentation](https://developers.openai.com/plugins/build/chatgpt-ui) describes the file bridge; directory support requires an actual host observation. A submitted request establishes dispatch, while a visible native folder view establishes opening.

## Manual Desktop acceptance

The user performs these checks separately in Codex Desktop and an authenticated Claude Code Desktop session. Record the toolkit version and host version with each result:

1. Use a fresh launch environment in which system Node.js and Python are unavailable through command search. Record that condition without uninstalling or modifying the system runtimes. Keep the operating system's normal shell and native utilities available. Run the matching archive's installer and record whether installation completes without dependency downloads.
2. Open a fresh terminal, confirm `graph-skill status` reports the expected version, and run `gskill --version` from a directory outside the source checkout. Inspect the installed Skill commands and canvas/hook configuration to confirm absolute paths into the toolkit's private version directory.
3. Confirm both Skills are discoverable and the canvas server is connected. Ask the agent to read a known portable business skill. Observe whether it naturally calls `show_graph` afterward, and verify that the displayed graph and top-left root match that skill.
4. If natural follow-up is absent, request `show_graph` explicitly. Record that outcome separately so an explicit repair cannot count as automatic behavior.
5. Confirm the canvas fills the allocated panel, then click the root path and observe the host's actual folder or file view. Record a fallback message separately from successful folder opening.
6. In a fresh host conversation, repeat the relevant discovery and display checks. Record Skill discovery, server connection, tool result delivery and visible panel rendering as separate observations. For an existing `0.1.0` installation, record the new extracted installer's upgrade result separately from a pristine installation.

Native Claude Code Desktop rendering remains unverified. Hook discovery, host trust and agent follow-through each need their own observation. Lifecycle acceptance also needs controlled evidence for collision preservation, edited owned resources, rollback and uninstall. A normal installation result supplies only its observed path. If a required host capability is absent, retain the successful lower-level results and identify the specific remaining workflow gap.

## Deploy the Python runtime independently

Service, developer and headless deployments can install the separately built `graph-skill-runtime` wheel into their chosen Python environment. Its package requirement remains Python `>=3.11`; the toolkit's private CPython pin applies to toolkit delivery. The Python distribution keeps its own programmatic Python interface, CLI and MCP tools. Runtime-only installation is independent of the toolkit's Node.js, canvas assets and host configuration. The runtime is unpublished, so use the supplied local wheel or the repository's documented source workflow.

## Build from source

This directory is one private product module. The runtime wheel and source distribution retain their independent package boundary. The builder requires Node.js 22 or later, Python 3.11 or later, `uv`, and network access to the pinned upstream runtimes and dependency wheels. `uv` is the repository's Python package and build tool. These are build-machine requirements. End users receive the resulting complete archive.

From the repository root, prepare the JavaScript build dependencies and build the canvas:

```powershell
cd plugins/graph-skill
npm ci
npm run build
```

Return to the repository root, build the runtime wheel and assemble a target archive. This example selects Windows x64:

```text
uv build --no-sources --wheel --out-dir plugins/graph-skill/release/runtime-build
python -B plugins/graph-skill/packaging/bundle.py --runtime-wheel plugins/graph-skill/release/runtime-build/graph_skill_runtime-0.1.0a1-py3-none-any.whl --platform win32-x64
```

Here `python` selects the build machine's Python 3.11 or later. Choose another declared target with `--platform`; omission selects the builder's target. The builder writes `release/graph-skill-0.2.0-TARGET.zip` and the adjacent identity receipt `release/graph-skill-0.2.0-TARGET.json`. The receipt binds the archive, runtime wheel, interpreter provenance and dependency-lock hashes. The archive's own hash stays outside the packaged documents.

[`packaging/runtime-lock.json`](packaging/runtime-lock.json) owns upstream runtime identities. The builder exports the repository's `uv.lock` with `uv --locked` and installs binary wheels for the selected interpreter/platform with hash checking. It includes the runtime's base dependencies; optional embedded-provider and development extras remain separate. A target missing a compatible locked wheel stops assembly. [VALIDATION.md](VALIDATION.md) records actual archives and inspection scope. Successful packaging establishes its build properties; installed lifecycle and native Desktop operation require the observations above.
