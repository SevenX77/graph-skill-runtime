import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { createLocalHttpServer } from "../backend/http/index.mjs";
import { createHostBridge } from "../adapters/claude/bridge/server.mjs";
import { createLocalCapabilities } from "../local/node/index.mjs";
import { registerLocalCapabilityTools } from "../local/node/mcp.mjs";
import { registerPageToolList } from "./page_tools.mjs";

/** Run one plugin process: a stdio MCP server whose business apps share one
 * loopback listener, one Claude host bridge and the local capabilities.
 *
 * Each app is a factory `({ http, hostBridge, serverInfo }) => owner` called
 * once per process. `owner.register(server, { local })` runs once per MCP
 * session, registers the app's tools and resources and returns the
 * page-callable tools it lists for `tools.list`; `owner.close()` runs at exit.
 * @param {{serverInfo: {name: string, version: string}, apps: Array<(context: any) => {register: (server: any, session: any) => ({name: string, description: string}[] | void), close?: () => unknown}>, onerror?: (error: Error) => void}} options
 */
export async function servePlugin({ serverInfo, apps, onerror = error => console.error(error.message) }) {
  const http = createLocalHttpServer();
  const hostBridge = createHostBridge({ http });
  const local = createLocalCapabilities({ http });
  const owners = apps.map(app => app({ http, hostBridge, serverInfo }));
  await http.open();
  const stdio = serveStdio(() => {
    const server = new McpServer(serverInfo);
    const connection = local.createConnection();
    const pageTools = owners.flatMap(owner => owner.register(server, { local: connection }) ?? []);
    registerLocalCapabilityTools(server, connection);
    registerPageToolList(server, pageTools);
    return server;
  }, { onerror });
  let closing;
  // Normal shutdown releases every owned resource and closes HTTP.
  const cleanup = () => closing ??= (async () => {
    await Promise.all(owners.map(owner => owner.close?.()));
    local.close();
    await hostBridge.close();
    await http.close();
  })();
  process.stdin.once("end", () => void cleanup());
  process.stdin.once("close", () => void cleanup());
  for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, async () => {
    await cleanup();
    await stdio.close();
  });
  return { cleanup };
}
