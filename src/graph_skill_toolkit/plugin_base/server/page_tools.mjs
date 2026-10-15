import { registerAppTool } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { PAGE_TOOL_LIST_NAME } from "../host_interfaces/tools/list/index.mjs";

/** Register the page-callable tool listing that Codex tools.list reads.
 * @param {any} server an McpServer
 * @param {{name:string, description:string}[]} tools page-callable business tools
 */
export function registerPageToolList(server, tools) {
  const listed = [...tools, { name: PAGE_TOOL_LIST_NAME, description: "List this page's page-callable tools." }]
    .map(({ name, description }) => ({ name, description, reference: { name, scope: "originating-server" } }));
  registerAppTool(server, PAGE_TOOL_LIST_NAME, {
    title: "List page tools",
    description: "Return the tools this plugin's MCP App exposes to its own page. This does not enumerate the host session.",
    inputSchema: z.object({}).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { visibility: ["app"] } },
  }, async () => ({
    content: [{ type: "text", text: `${listed.length} page tools are available.` }],
    structuredContent: { scope: "originating-server", complete: true, tools: listed },
  }));
}
