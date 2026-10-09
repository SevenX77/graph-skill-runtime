import { readFile } from "node:fs/promises";
import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { graph } from "./graph.mjs";
import { loadSkill } from "./skill-files.mjs";
import { projectGraph } from "./project-graph.mjs";
import packageInfo from "../package.json" with { type: "json" };

const resourceUri = "ui://graph-skill/canvas-v2.html";
// The build places this self-contained resource alongside the bundled server.
const html = await readFile(new URL("./canvas.html", import.meta.url), "utf8");
const ui = { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: false };

serveStdio(() => {
  const server = new McpServer({ name: "graph-skill-canvas", version: packageInfo.version });
  registerAppTool(server, "show_graph", {
    title: "Show Graph Skill canvas",
    description: "Display the selected Graph Skill's root nodes and edges. Call after working on a Graph Skill, supplying its absolute skill_root. Omit skill_root only for the labeled three-node demonstration.",
    inputSchema: z.object({ skill_root: z.string().min(1).optional() }).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { resourceUri, visibility: ["model"] } },
  }, async ({ skill_root }) => {
    try {
      if (!skill_root) return {
        content: [{ type: "text", text: "Demonstration canvas. No business Skill selected; pass skill_root for its actual graph and folder shortcut." }],
        structuredContent: { graph: { ...graph, width: 352, height: 548 }, skillRoot: null },
      };
      const skill = await loadSkill(skill_root);
      const projected = projectGraph(skill.data, skill.kinds);
      return {
        content: [{ type: "text", text: `Graph Skill canvas: ${skill.skillRoot} (${projected.nodes.length} nodes).` }],
        structuredContent: { graph: projected, skillRoot: skill.skillRoot },
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: `Cannot display Graph Skill: ${error.message}` }] };
    }
  });
  registerAppResource(server, "Graph Skill canvas", resourceUri, {
    description: "Viewport-filling graph canvas with a host-owned Skill folder shortcut.",
    _meta: { ui },
  }, async () => ({ contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html, _meta: { ui } }] }));
  return server;
}, { onerror: (error) => console.error(error.message) });
