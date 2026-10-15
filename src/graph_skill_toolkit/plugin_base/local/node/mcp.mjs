import { registerAppTool } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { LOCAL_TRANSPORT_OPERATIONS } from "../definitions.mjs";

export const LOCAL_CALL_TOOL = "local_call";
export const LOCAL_EVENTS_TOOL = "local_events";

/** Page-only MCP tools that carry local capabilities for a page whose only
 * route to its plugin process is the MCP App channel (Codex). The model never
 * sees them.
 * @param {any} server an McpServer
 * @param {ReturnType<ReturnType<typeof import('./index.mjs').createLocalCapabilities>['createConnection']>} connection
 */
export function registerLocalCapabilityTools(server, connection) {
  const app = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true };
  registerAppTool(server, LOCAL_CALL_TOOL, {
    title: "Local capability",
    description: "Page channel: run one of this plugin's local capabilities (read, write or watch files in granted directories, open a web URL, reveal a path).",
    inputSchema: z.object({ operation: z.enum(/** @type {[string, ...string[]]} */ ([...LOCAL_TRANSPORT_OPERATIONS])), args: z.record(z.string(), z.unknown()).optional() }).strict(),
    annotations: app,
    _meta: { ui: { visibility: ["app"] } },
  }, async ({ operation, args }) => {
    const value = await connection.call(operation, args ?? {});
    return { content: [{ type: "text", text: value.message }], structuredContent: value };
  });
  registerAppTool(server, LOCAL_EVENTS_TOOL, {
    title: "Local capability events",
    description: "Page channel: wait for local capability events after a cursor.",
    inputSchema: z.object({ after: z.number().int().min(0), timeout_ms: z.number().int().min(0).max(25000).optional() }).strict(),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { visibility: ["app"] } },
  }, async ({ after, timeout_ms }, context) => {
    const value = await connection.wait(after, timeout_ms ?? 20000, context?.mcpReq?.signal);
    return { content: [{ type: "text", text: `${value.events.length} local events.` }], structuredContent: value };
  });
}
