import { readFile } from "node:fs/promises";
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { describeDiagnostics, readGraphState } from "../application/service/index.mjs";
import { selectSkillRoot } from "../application/source/files.mjs";
import { createRuntimeCompiler } from "../backend/runtime/index.mjs";
import { createGraphBackend } from "../backend/graph/index.mjs";
import { createGraphRelay } from "../backend/relay/index.mjs";
import { createLiveGraphSource } from "../application/live_source/index.mjs";
import { snapshotHtml, createPreviewConfiguration, pageResourceUri, codexResourceMetadata, createCodexPageSessions, launchHostInfo, requestClientInfo } from "../../../plugin_base/server/index.mjs";

// The build places this self-contained resource alongside the bundled server.
const html = await readFile(new URL("./canvas.html", import.meta.url), "utf8");

// Tool-facing graph state: the drawable graph when the runtime accepts the
// skill, otherwise no graph plus the runtime's compile diagnostics.
function canvasState(event) {
  if (event?.type === "snapshot") return { ...event.data, compile: { status: "passed", diagnostics: [] } };
  if (event?.type === "invalid") return { graph: null, skillRoot: event.skillRoot, compile: { status: "failed", diagnostics: event.diagnostics } };
  throw new Error(event?.message ?? "Graph state is unavailable.");
}
const invalidText = state => `The graph is currently invalid. Runtime compile reported ${state.compile.diagnostics.length} diagnostic(s); the canvas lists them and redraws once the files compile again:\n${describeDiagnostics(state.compile.diagnostics)}`;

/** The Graph Skill canvas app: show_graph, inspect_graph and watch_graph. */
export function graphCanvasApp({ http, hostBridge, serverInfo }) {
  // One live source per root serves both page transports: SSE for the Claude
  // HTTP page and long poll (watch_graph) for the sandboxed Codex MCP App page.
  // The runtime compiler is the only validity authority behind that source.
  const compiler = createRuntimeCompiler();
  const liveSource = createLiveGraphSource({ read: root => readGraphState(root, { compiler }) });
  const graphBackend = createGraphBackend({ http, source: liveSource });
  const graphRelay = createGraphRelay({ source: liveSource });
  const previewConfiguration = createPreviewConfiguration({ namePrefix: "graph-skill" });
  return { register, close };

  function register(server, { local }) {
  const graphConnection = graphBackend.createConnection();
  const bootstrap = { graphBackend: graphConnection.descriptor, serverInfo, local: { transport: "mcp-tools" } };
  const resourceUri = pageResourceUri("graph-skill", "canvas", snapshotHtml(html, bootstrap));
  const ui = { csp: { connectDomains: [http.origin], resourceDomains: [] }, prefersBorder: false };
  const selectedRoots = new Map();
  const codexSessions = createCodexPageSessions();
  registerAppTool(server, "show_graph", {
    title: "Show Graph Skill canvas",
    description: "Display the selected Graph Skill's actual root graph on the shared canvas. The canvas is the only view this presentation opens, selects and verifies: in Codex it is the MCP App view attached to this result, requested once as the final presentation; in Claude Code it is the owned loopback HTTP page shown in the Browser pane. HTML presentation requires preview_project_root from the actual Claude session root; it starts an owned loopback preview and merges one temporary attach entry into that project's .claude/launch.json. Record existing tabs, attach the returned preview name, retain the actual HTTP tabId, navigate only that tab to the canvas URL, select it, and verify the canvas is active with every prior user page preserved. If the Browser pane stays hidden, ask the user to open it manually; open no file or other page to reveal it. Repeated display reuses the same canvas view. Omit skill_root only for the explicitly requested demonstration, which has no business root.",
    inputSchema: z.object({ skill_root: z.string().min(1).optional(), presentation: z.enum(["mcp-app", "html"]).optional(), preview_project_root: z.string().min(1).optional(),
      native_host: z.object({name:z.literal("Claude Code"),version:z.string().min(1).max(256),client_type:z.literal("claude_code"),
        sessionId:z.string().min(1).max(256),source:z.literal("claude-mod-session")}).strict().optional().describe("Supplied by the Claude Mod from native session APIs; the Mod overwrites caller values. Omit in ordinary calls.") }).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { resourceUri, visibility: ["model"] } },
  }, async ({ skill_root, presentation, preview_project_root, native_host }, context) => {
    try {
      const hostInfo = launchHostInfo({clientInfo:requestClientInfo(server.server, context),presentation,nativeHost:native_host});
      if (presentation === "html" && (!skill_root || !preview_project_root)) throw new Error("HTML preview requires skill_root and the actual host session's preview_project_root.");
      if (presentation !== "html" && preview_project_root !== undefined) throw new Error("preview_project_root applies only to HTML presentation.");
      if (!skill_root) {
        graphConnection.select(null);
        return {
        content: [{ type: "text", text: "Demonstration canvas. No business Skill selected; pass skill_root for its actual graph and folder shortcut." }],
        structuredContent: { ...canvasState(await liveSource.current(null)), hostInfo, serverInfo },
        _meta: codexSessions.metadata(null),
        };
      }
      // An invalid graph still opens the canvas: the page shows the runtime's
      // diagnostics and redraws when a later save compiles.
      const presentationData = canvasState(await liveSource.current(await selectSkillRoot(skill_root)));
      selectedRoots.set(skill_root, presentationData.skillRoot);
      await local.allow(presentationData.skillRoot);
      graphConnection.select(skill_root, presentationData.skillRoot);
      const payload = { ...presentationData, hostInfo, serverInfo };
      const projected = presentationData.graph;
      const bridge = presentation === "html" ? await hostBridge.createView(payload.skillRoot, hostInfo) : undefined;
      let httpPresentation;
      if (bridge) {
        const document = snapshotHtml(html, { ...payload, ...bootstrap, hostBridge: bridge.browser, local: { transport: "http", ...local.descriptor } });
        const preview = await previewConfiguration.ensure(preview_project_root, bridge.browser.url);
        const url = hostBridge.publish(payload.skillRoot, document);
        httpPresentation = { kind: "http", url, preview, bridge: bridge.mod };
      }
      return {
        content: [{ type: "text", text: projected ? `Graph Skill canvas: ${payload.skillRoot} (${projected.nodes.length} nodes).` : `Graph Skill canvas: ${payload.skillRoot}. ${invalidText(payload)}` }],
        structuredContent: { ...payload, ...(httpPresentation ? { presentation: httpPresentation } : {}) },
        ...(presentation !== "html" ? { _meta: codexSessions.metadata(payload.skillRoot) } : {}),
      };
    } catch (error) {
      // Keep an existing App bootstrap intact. Its filesystem subscription
      // reports invalid saves and can recover without replacing the page.
      return { isError: true, content: [{ type: "text", text: `Cannot display Graph Skill: ${error.message}` }], ...(presentation !== "html" ? { _meta: codexSessions.existingMetadata(selectedRoots.get(skill_root)) } : {}) };
    }
  });
  registerAppTool(server, "inspect_graph", {
    title: "Inspect the displayed graph",
    description: "Read the current graph of a Skill previously selected with show_graph in this connection: the drawable graph when the runtime compiles it, otherwise the runtime compile diagnostics. Compiles without cache writes; never executes business code.",
    inputSchema: z.object({ skill_root: z.string().min(1) }).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    // Reading current graph data must not instantiate a second canvas.
    _meta: { ui: { visibility: ["app", "model"] } },
  }, async ({ skill_root }) => {
    try {
      const selectedRoot = selectedRoots.get(skill_root) ?? ([...selectedRoots.values()].includes(skill_root) ? skill_root : undefined);
      if (!selectedRoot) throw new Error("Select this Skill with show_graph before inspecting it.");
      const presentationData = canvasState(await liveSource.current(selectedRoot));
      return { content: [{ type: "text", text: presentationData.graph ? `Read graph ${presentationData.graph.id}` : invalidText(presentationData) }], structuredContent: { ...presentationData, serverInfo }, _meta: codexSessions.metadata(presentationData.skillRoot) };
    } catch (error) { return { isError: true, content: [{ type: "text", text: error.message }], _meta: codexSessions.existingMetadata(skill_root) }; }
  });
  registerAppTool(server, "watch_graph", {
    title: "Watch the displayed graph",
    description: "Canvas page channel: wait for the next change of a Skill graph selected with show_graph in this connection, then return its current graph, runtime compile diagnostics or file error. Never executes business code.",
    inputSchema: z.object({ skill_root: z.string().min(1).nullable(), after_revision: z.number().int().min(0).optional(), timeout_ms: z.number().int().min(0).max(25000).optional() }).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    // Page-only long poll: hidden from the model and attaches no canvas.
    _meta: { ui: { visibility: ["app"] } },
  }, async ({ skill_root, after_revision, timeout_ms }, context) => {
    try {
      const selectedRoot = skill_root === null ? null : selectedRoots.get(skill_root) ?? ([...selectedRoots.values()].includes(skill_root) ? skill_root : undefined);
      if (selectedRoot === undefined) throw new Error("Select this Skill with show_graph before watching it.");
      const result = await graphRelay.wait(selectedRoot, after_revision ?? -1, timeout_ms ?? 20000, context?.mcpReq?.signal);
      return {
        content: [{ type: "text", text: result.event ? `Graph revision ${result.revision}.` : `No graph change after revision ${result.revision}.` }],
        structuredContent: { revision: result.revision, event: result.event },
      };
    } catch (error) { return { isError: true, content: [{ type: "text", text: error instanceof Error ? error.message : String(error) }] }; }
  });
  registerAppResource(server, "Graph Skill canvas", resourceUri, {
    description: "Viewport-filling graph canvas with a host-owned Skill folder shortcut.",
    _meta: { ui, ...codexResourceMetadata },
  }, async (_uri, context) => ({ contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE,
    text: snapshotHtml(html, {...bootstrap,hostInfo:launchHostInfo({clientInfo:requestClientInfo(server.server, context)})}),
    _meta: { ui, ...codexResourceMetadata } }] }));
  return [
    { name: "inspect_graph", description: "Read the selected graph without executing it." },
    { name: "watch_graph", description: "Wait for the selected graph's next change." },
  ];
  }

  async function close() {
    graphRelay.close();
    graphBackend.close();
    await previewConfiguration.close();
  }
}
