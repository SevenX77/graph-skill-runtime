import { readFile, stat } from "node:fs/promises";
import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { graph } from "../demo/graph.mjs";
import { loadSkill } from "../skill_source/files.mjs";
import { projectGraph } from "../projection/graph.mjs";
import { snapshotHtml } from "../adapters/claude/preview/publisher.mjs";
import { createHostBridge } from "../adapters/claude/bridge/server.mjs";
import { createPreviewConfiguration } from "../adapters/claude/preview_configuration/index.mjs";
import { skillDocument } from "../presentation/index.mjs";
import { codexResourceMetadata } from "../adapters/codex/resource/index.mjs";
import { createCodexCanvasSessions } from "../adapters/codex/session/index.mjs";
import packageInfo from "../package.json" with { type: "json" };

const resourceUri = "ui://graph-skill/canvas-v2.html";
// The build places this self-contained resource alongside the bundled server.
const html = await readFile(new URL("./canvas.html", import.meta.url), "utf8");
const ui = { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: false };
const previewConfiguration = createPreviewConfiguration();
const hostBridge = createHostBridge();
const selectedRoots = new Map();

const stdio = serveStdio(() => {
  const server = new McpServer({ name: "graph-skill-canvas", version: packageInfo.version });
  const codexSessions = createCodexCanvasSessions();
  registerAppTool(server, "show_graph", {
    title: "Show Graph Skill canvas",
    description: "Display the selected Graph Skill's actual root graph together with its SKILL.md. In Codex, first open the verified SKILL.md with open_in_codex target type=file and line=1 in a standalone host invocation. After that invocation returns, call this tool in a separate invocation as the final presentation. Keep file opening and this tool in distinct tool batches, including when orchestrating calls; queued file delivery is not UI completion. Retain and reuse both views, with the canvas active. HTML presentation requires preview_project_root from the actual Claude session root; it starts an owned loopback preview and merges one temporary attach entry into that project's .claude/launch.json. Record existing tabs, attach the returned preview name and retain the actual HTTP tabId. Open or reuse document.path with normal file preview to show SKILL.md and reveal the sidebar. Navigate only the retained HTTP tab to the canvas URL, select it, and verify both views remain with the pane displayed. Preserve all prior user pages. Omit skill_root only for the explicitly requested demonstration, which has no business document.",
    inputSchema: z.object({ skill_root: z.string().min(1).optional(), presentation: z.enum(["mcp-app", "html"]).optional(), preview_project_root: z.string().min(1).optional() }).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { resourceUri, visibility: ["model"] } },
  }, async ({ skill_root, presentation, preview_project_root }) => {
    try {
      if (presentation === "html" && (!skill_root || !preview_project_root)) throw new Error("HTML preview requires skill_root and the actual host session's preview_project_root.");
      if (presentation !== "html" && preview_project_root !== undefined) throw new Error("preview_project_root applies only to HTML presentation.");
      if (!skill_root) return {
        content: [{ type: "text", text: "Demonstration canvas. No business Skill selected; pass skill_root for its actual graph and folder shortcut." }],
        structuredContent: { graph: { ...graph, width: 352, height: 548 }, skillRoot: null },
        _meta: codexSessions.metadata(null),
      };
      const skill = await loadSkill(skill_root);
      selectedRoots.set(skill_root, skill.skillRoot);
      const projected = projectGraph(skill.data, skill.kinds);
      const payload = { graph: projected, skillRoot: skill.skillRoot, document: skillDocument(skill.skillRoot) };
      if (presentation === "html" && (await stat(payload.document.path)).size > 524288) throw new Error("SKILL.md exceeds the host file preview's 512 KiB limit.");
      const bridge = presentation === "html" ? await hostBridge.createView(skill.skillRoot) : undefined;
      let httpPresentation;
      if (bridge) {
        const document = snapshotHtml(html, { ...payload, hostBridge: bridge.browser });
        const preview = await previewConfiguration.ensure(preview_project_root, bridge.browser.url);
        const url = hostBridge.publish(skill.skillRoot, document);
        httpPresentation = { kind: "http", url, preview, bridge: bridge.mod };
      }
      return {
        content: [{ type: "text", text: `Graph Skill canvas: ${skill.skillRoot} (${projected.nodes.length} nodes).` }],
        structuredContent: { ...payload, ...(httpPresentation ? { presentation: httpPresentation } : {}) },
        ...(presentation !== "html" ? { _meta: codexSessions.metadata(skill.skillRoot) } : {}),
      };
    } catch (error) {
      try { hostBridge.publish(selectedRoots.get(skill_root) ?? skill_root, snapshotHtml(html, { error: error.message })); } catch { /* No previous HTTP view for this root. */ }
      return { isError: true, content: [{ type: "text", text: `Cannot display Graph Skill: ${error.message}` }], ...(presentation !== "html" ? { _meta: codexSessions.existingMetadata(selectedRoots.get(skill_root)) } : {}) };
    }
  });
  registerAppTool(server, "inspect_graph", {
    title: "Inspect the displayed graph",
    description: "Read current graph presentation data for a Skill previously selected with show_graph in this connection. Reads files only; does not compile or execute business code.",
    inputSchema: z.object({ skill_root: z.string().min(1) }).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { resourceUri, visibility: ["app", "model"] } },
  }, async ({ skill_root }) => {
    try {
      if (![...selectedRoots.values()].includes(skill_root)) throw new Error("Select this Skill with show_graph before inspecting it.");
      const skill = await loadSkill(skill_root);
      return { content: [{ type: "text", text: `Read graph ${skill.data.graph_id}` }], structuredContent: { graph: projectGraph(skill.data, skill.kinds), skillRoot: skill.skillRoot, document: skillDocument(skill.skillRoot) }, _meta: codexSessions.metadata(skill.skillRoot) };
    } catch (error) { return { isError: true, content: [{ type: "text", text: error.message }], _meta: codexSessions.existingMetadata(skill_root) }; }
  });
  registerAppResource(server, "Graph Skill canvas", resourceUri, {
    description: "Viewport-filling graph canvas with a host-owned Skill folder shortcut.",
    _meta: { ui, ...codexResourceMetadata },
  }, async () => ({ contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html, _meta: { ui, ...codexResourceMetadata } }] }));
  return server;
}, { onerror: (error) => console.error(error.message) });

// Normal shutdown removes only exact owned attach entries and closes HTTP.
const cleanup = () => Promise.all([previewConfiguration.close(), hostBridge.close()]);
process.stdin.once("end", () => void cleanup());
process.stdin.once("close", () => void cleanup());
for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, async () => {
  await cleanup();
  await stdio.close();
});
