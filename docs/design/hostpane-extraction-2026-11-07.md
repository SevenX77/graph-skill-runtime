# Extract the Plugin Base into the Hostpane project

Date: 2026-11-07.

## Purpose

Any plugin, the Graph Skill canvas among them, can show its own pages inside Claude Code Desktop and Codex Desktop and call their host interfaces through one independently versioned, independently tested package, while the Graph Skill toolkit keeps only its business apps and composition.

## Terms

- **Plugin Base**: the toolkit's reusable host-integration layer at `src/graph_skill_toolkit/plugin_base/`, 92 files. It owns the 17 host interfaces for both hosts, the 5 local capabilities, page presentation in both hosts, evidence on every call, and the Claude Mod hooks. A host interface is one operation a page asks the host to perform, such as `composer.writeDraft`; a local capability is one operation the plugin's own Node process performs for its page, such as `local.files.read`. [The Plugin Base guide](../../src/graph_skill_toolkit/plugin_base/README.md) is its reference.
- **Hostpane**: the project the Plugin Base becomes. The name joins *host* and *pane*: Hostpane runs one plugin page in each host's pane, the Browser pane in Claude Code Desktop and the MCP App view in Codex Desktop, and calls that host's interfaces. An MCP App is an MCP resource holding an HTML page that the host renders in a sandboxed frame.
- **Toolkit**: `src/graph_skill_toolkit/` in repository `graph-skill-runtime`, branch `claude/toolkit-host-interfaces`. It composes the business apps `apps/graph_canvas` and `apps/interface_lab` in `composition/server.mjs` and `composition/claude_mod/`. A business app is one unit of plugin functionality built on the Plugin Base.
- **Claude Mod** (Mod): a Claude Code plugin module that registers hooks on Claude Code events and calls Claude Code's own APIs; the toolkit's Mod presents its pages in the Browser pane.
- **Closure**: the property that a module's code imports only its own files and a fixed list of outside modules, and that outside code reaches the module only through its named entries.
- **Commit pin**: a dependency declaration that names one exact 40-hexadecimal git commit, so every install of that declaration reads the same bytes.

## Facts

All facts below were observed on 2026-11-07 in the worktree of branch `claude/toolkit-host-interfaces`.

1. **The Plugin Base is closed in both directions.** Code outside it imports only four entry files: `page/index.mjs`, `page/types.ts`, `server/index.mjs` and `claude_mod/index.js`. Code inside it imports only its own files, third-party packages and Node built-ins. `tests/plugin_base/closure.test.mjs` enforces both directions.
2. **The Plugin Base imports three third-party packages**: `@modelcontextprotocol/ext-apps` (including `/server`), `@modelcontextprotocol/server` (including `/stdio`) and `zod`. The toolkit dependencies `react`, `react-dom`, `yaml` and `yauzl` are imported by toolkit code outside the Plugin Base only.
3. **The Plugin Base contains one toolkit-specific literal.** In `plugin_base/adapters/claude/mod/hooks/base.js:93`, the `prompt.submit` hook reads:

   ```js
   if (e.origin?.kind === 'plugin' && e.origin.name === 'graph-skill-canvas-mod') return next(e);
   ```

   This line passes the Mod's own prompts through without attaching stored page context, because those prompts carry the context inline. `registerPluginBase(on, { pages })` is called once, from `composition/claude_mod/hooks/register.js:8`, with `{ pages: [canvasPage, labPage] }`.
4. **Production importers.** Eleven files under `apps/`, plus `composition/server.mjs` and `composition/claude_mod/hooks/register.js`, import the Plugin Base. They use relative paths, for example:

   ```ts
   import type { HostAdapter, HostInfo } from "../../../../plugin_base/page/types";
   ```

5. **Build and typecheck.** esbuild, driven by `scripts/build/main.mjs`, bundles the toolkit into `dist/`: the server, the follow-up hook, the canvas page, the Interface Lab page, the Claude Mod and the installer. `tsconfig.json` uses `moduleResolution: "Bundler"` and includes `plugin_base/**/*.ts`.
6. **Tests.** 28 test files under `tests/plugin_base`, `tests/host` and `tests/adapters` exercise the Plugin Base. Some depend on the Plugin Base alone. Others also import toolkit code:
   - `tests/host/launch.test.mjs` uses the composition Mod, the canvas demonstration graph and the built `dist/server.mjs`;
   - `tests/adapters/claude/operations.test.mjs` and `tests/adapters/claude/presentation.test.mjs` use the composition Mod;
   - `tests/adapters/composition.test.mjs` uses the canvas composition;
   - `tests/adapters/claude/permission_mode.test.mjs` imports `permissionModeLabel` from the Interface Lab;
   - `tests/host/detection.test.mjs` uses the canvas demonstration graph as an arbitrary payload.
7. **Gate baseline.** On commit `9461416a` of branch `claude/toolkit-host-interfaces`, pushed to `origin`, `npm run build`, `npm run typecheck` and `npm test` passed with 255 tests and 0 failures.
8. **Live hosts read this worktree.** The Claude Code and Codex hosts on this machine run the toolkit's `dist/` from this worktree in source test mode, so a toolkit rebuild changes their live behavior.
9. **The npm name is free.** The npm registry returned E404 (unregistered) for `hostpane`; the name `panekit` is registered to another owner.
10. **Documents.** `plugin_base/README.md` links to the toolkit decision records `docs/design/interface-connect-verdicts-2026-10-16.md` and `docs/design/plugin-base-and-interface-lab-2026-10-14.md`. The toolkit's `ADAPTER.md` owns host connection, identity, authority and the per-host route mapping of the 17 host interfaces.

## Decisions

1. **Name and place.** The project is Hostpane. Its `package.json` declares:

   ```json
   {
     "name": "hostpane",
     "version": "0.1.0",
     "private": true,
     "license": "Apache-2.0",
     "engines": { "node": ">=22" }
   }
   ```

   `"private": true` holds until publication is decided separately. The local repository is `D:/coding/hostpane`; its remote is the private GitHub repository `SevenX77/hostpane`.
   Reason: a package that any plugin can depend on and that is versioned on its own needs its own history, version and remote, which the toolkit can then pin like any other dependency.

2. **History is kept.** The repository is created with `git filter-repo` from branch `claude/toolkit-host-interfaces` at `9461416a`, keeping only the Plugin Base source and the tests that move (Decision 6). Source lands under `src/` with its internal layout unchanged; for example `plugin_base/page/index.mjs` becomes `src/page/index.mjs`, and `plugin_base/adapters/claude/mod/hooks/base.js` becomes `src/adapters/claude/mod/hooks/base.js`.
   Reason: each file's earlier commits stay readable in the package that now owns it, so the reasons behind host-interface behavior remain available to anyone maintaining Hostpane for any plugin.

3. **The public entries are the package exports.** `package.json` declares exactly these four exports:

   ```json
   "exports": {
     "./page": { "types": "./types/page/index.d.mts", "default": "./src/page/index.mjs" },
     "./page/types": { "types": "./types/page/types.d.ts", "default": "./src/page/types.ts" },
     "./server": { "types": "./types/server/index.d.mts", "default": "./src/server/index.mjs" },
     "./claude-mod": { "types": "./types/claude_mod/index.d.ts", "default": "./src/claude_mod/index.js" }
   }
   ```

   Each export's `types` condition names a declaration file under `types/`, generated from `src/` by `npm run types` and committed. TypeScript reads no types from JavaScript inside `node_modules`, so without these files a TypeScript plugin would see every Hostpane import as `any`; committing them lets a git installation work without a build step. Generation runs with `--singleThreaded`, because TypeScript 7's parallel checkers order inferred union members differently on each run; Hostpane's `tests/base/types.test.mjs` regenerates and compares.

   The page entry also exports `validateArguments(action, args)` and `validateLocalArguments(operation, args)`, the validators `adapter.invoke` and the local executor apply. A page can validate a form's arguments before it calls, and the toolkit's Interface Lab checks that every preset it offers passes them.

   A consumer imports through these specifiers only. For example, in `composition/server.mjs`:

   ```js
   import { servePlugin } from "../plugin_base/server/index.mjs";
   ```

   becomes

   ```js
   import { servePlugin } from "hostpane/server";
   ```

   and in a page:

   ```ts
   import type { HostAdapter, HostInfo } from "hostpane/page/types";
   ```

   Reason: the four entries are the existing closure boundary (Fact 1); declaring them as the package's only exports lets the package manager enforce that boundary for every consuming plugin.

4. **The Mod's own plugin name is a required registration parameter.** The Mod entry's signature is `registerPluginBase(on, { pluginName, pages })`. `pluginName` is the plugin name the engine reports as `e.origin.name` for that Mod's own prompts. The `prompt.submit` hook compares against it:

   ```js
   if (e.origin?.kind === 'plugin' && e.origin.name === pluginName) return next(e);
   ```

   A missing or empty `pluginName` throws at registration; Hostpane has no built-in default name. The toolkit's `composition/claude_mod/hooks/register.js` passes its own name:

   ```js
   registerPluginBase(on, { pluginName: 'graph-skill-canvas-mod', pages: [canvasPage, labPage] });
   ```

   A Hostpane test registers under another name and shows that only prompts whose origin carries that name pass through without attached page context.
   Reason: the name identifies the consuming plugin, so it is data the consumer supplies; with it, every plugin's own prompts receive the single context delivery that Fact 3 describes for the toolkit.

5. **Dependencies.** Hostpane's `dependencies` list exactly the three packages it imports (Fact 2), at the versions the toolkit pins at `9461416a`, except `zod`, which both projects raise from `4.3.6` to `4.6.7` for advisory GHSA-mrhx-c7xc-m3w5 (memory exhaustion while validating oversized constrained collections); equal versions let npm install one shared copy. Its `devDependencies` list the tools its own tests and typecheck need.
   Reason: a plugin that installs Hostpane receives exactly what Hostpane uses, and Hostpane's tests run in its own repository.

6. **A test moves to Hostpane when its subject is Plugin Base behavior.**
   - A test whose subject is Plugin Base behavior moves. When such a test borrows toolkit data only as an arbitrary fixture, Hostpane's copy uses a neutral inline fixture: `tests/host/detection.test.mjs` uses an inline payload in place of the canvas demonstration graph, and `tests/adapters/claude/permission_mode.test.mjs` uses an inline label function in place of the Interface Lab's `permissionModeLabel`.
   - A test whose subject is the toolkit's own wiring stays in the toolkit as an integration test: tests of the composition Mod, of the canvas composition and of the built `dist/` server. `tests/host/launch.test.mjs`, `tests/adapters/composition.test.mjs`, and the composition-Mod parts of `tests/adapters/claude/operations.test.mjs` and `tests/adapters/claude/presentation.test.mjs` are in this group.
   - A toolkit test reaches Hostpane only through the four public entries, because the package `exports` map refuses any deeper specifier. A toolkit test case whose assertions need a module those entries do not export (for example `codexAdapter` from `adapters/codex/driver/index.mjs`, or the Browser tool names in `adapters/claude/mod/host_tools/index.mjs`) is a Plugin Base test case and moves to Hostpane; the toolkit keeps the cases that the public entries can express. This applies to the toolkit tests outside the three directories as well: `tests/backend/live.test.mjs`, `tests/integration/*.test.mjs`, `tests/interface_lab/guide.test.mjs` and `tests/support/browser.mjs`.
   Reason: Hostpane's own test suite proves Hostpane's behavior for any plugin, and the toolkit's suite proves that the toolkit composes Hostpane correctly.

7. **Closure is enforced on both sides.**
   - In Hostpane, a closure test checks that every file under `src/` imports only files under `src/`, the packages declared in Decision 5, and Node built-in modules.
   - In the toolkit, the closure test checks that production code reaches Hostpane only through the four specifiers `hostpane/page`, `hostpane/page/types`, `hostpane/server` and `hostpane/claude-mod`, and that no `plugin_base/` directory exists.
   Reason: each project proves its own side of the boundary in its own gate, so the package stays reusable and the toolkit keeps only business apps and composition.

8. **The toolkit pins Hostpane by commit.** The toolkit's `package.json` declares:

   ```json
   "hostpane": "git+https://github.com/SevenX77/hostpane.git#<40-hex commit>"
   ```

   A Hostpane change reaches the toolkit only when this pin is updated.
   Reason: a commit pin resolves to the same bytes from every checkout, including worktrees at different directory depths, and it records exactly which Hostpane bytes a toolkit build used; a `file:` path would resolve relative to where each checkout sits.

9. **Documents follow their subject.**
   - `plugin_base/README.md` becomes Hostpane's `README.md`.
   - The host-connection content of the toolkit's `ADAPTER.md` (connection authority, identity, and the per-host route mapping of the 17 host interfaces) becomes Hostpane's `docs/ADAPTER.md`.
   - The decision records whose subject is a host interface, `interface-connect-verdicts-2026-10-16.md` and `page-tool-calls-person-approval-2026-11-01.md`, live in Hostpane's `docs/design/`.
   - The records about the toolkit's own division, `plugin-base-and-interface-lab-2026-10-14.md`, and this record live in the toolkit's `docs/design/`.
   - The toolkit's `ARCHITECTURE.md`, `README.md`, `VALIDATION.md` and `MANUAL-TESTS.md` link to Hostpane where they refer to the host-integration layer.
   Reason: each document sits with the project that owns its subject, so a plugin author reads Hostpane's repository alone to build on it.

## Acceptance

Observed 2026-11-07 on Windows 11 x64, Node.js 24.18.0.

- [x] `D:/coding/hostpane` is a git repository whose history contains the twelve earlier commits that touched the Plugin Base path; its `origin` is the private repository `SevenX77/hostpane`, whose `main` is `2edc5415e2cad55d305fc0f752cb3ab5be8fe371`.
- [x] In Hostpane, `npm ci`, `npm run typecheck` and `npm test` pass: 182 tests, 0 failures. `npm audit` reports 0 vulnerabilities.
- [x] In Hostpane, the closure test (Decision 7), the `pluginName` test (Decision 4) and the declaration freshness test (Decision 3) pass.
- [x] In Hostpane, a search of `src/` for `graph-skill`, `canvas` and `gskill` finds no match.
- [x] In the toolkit, no `plugin_base/` directory exists, and `package.json` pins `hostpane` at `2edc5415e2cad55d305fc0f752cb3ab5be8fe371`.
- [x] In the toolkit, `npm install`, `npm run build`, `npm run typecheck` and `npm test` pass: 81 tests, 0 failures; `npm audit` reports 0 vulnerabilities.
- [x] Test count: 182 + 81 = 263, which is the baseline 255 (Fact 7) plus eight new tests: the `pluginName` test, the validator-export test, the declaration freshness test and the export-map test in Hostpane; one more closure test on each side; the toolkit's commit-pin test; and the toolkit's canvas payload test, which takes over the `graphPayload` assertions from the Claude presentation test. No test case was removed.
- [ ] The rebuilt toolkit loads in a new Claude Code session: the Interface Lab page opens and one host interface call returns a result. Observed so far: the built Mod passes `claude plugin validate` with Claude Code 2.1.309, and a fresh headless `claude -p` session started the rebuilt `dist/server.mjs` and received a result from its `lab_echo` tool. The Interface Lab page in the Browser pane and a host interface call from it are not yet observed; they need an interactive desktop session started after the rebuild.

The bundled canvas and Interface Lab pages grow from 696582 to 818051 bytes and from 767306 to 888799 bytes. The cause is the `zod` upgrade of Decision 5: on the pre-extraction commit `9461416a`, zod's share of the canvas bundle measures 310643 bytes at `4.3.6` and 454152 bytes at `4.6.7`.

## Application state

Decided 2026-11-07 on the owner's request to package the module as a new project and to create its repository under `D:/coding/`. Applied on 2026-11-07: every acceptance item above is observed except native observation of the Interface Lab page in an interactive Claude Code session.

Owner records:

- 「把mcp 插件接口的模块单独打包成一个新的项目， 帮我起一个名字」 (gloss: "Package the MCP plugin interface module separately as a new project, and give it a name.")
- 「我没有异议，d:/coding/ 建新仓库」 (gloss: "I have no objection; create the new repository in d:/coding/.")
