// @ts-check
import { discoverConnection } from "./detection/index.mjs";
import { hostAdapter } from "./host/index.mjs";
import { codexAdapter } from "./codex/browser/index.mjs";
import { claudeAdapter } from "./claude/browser/index.mjs";
import { httpConnection } from "./claude/connection/index.mjs";
import { mcpConnection } from "./codex/connection/index.mjs";
import { McpAppTransport } from "./codex/transport/index.mjs";
import packageInfo from "../package.json" with { type: "json" };

/** The browser composition boundary. Environment and drivers can be supplied
 * by an isolated test; normal consumers call this with no host argument.
 * @param {{document?: Pick<Document, 'querySelector'>, window?: Window,
 * connections?: Partial<Record<'mcp-app'|'http-bridge', () => import('../ports/host/index').HostConnection>>,
 * drivers?: Partial<Record<'codex'|'claude', (connection:import('../ports/host/index').HostConnection) => import('../ports/host/index').HostDriver>>}} [options]
 * @returns {import('../ports/host/index').HostAdapter | null}
 */
export function createHostAdapter({ document: page = globalThis.document, window: view = globalThis.window, connections = {}, drivers = {} } = {}) {
  let detected;
  try {
    detected = discoverConnection({ snapshotText: page?.querySelector("#graph-skill-snapshot")?.textContent, framed: Boolean(view?.parent && view.parent !== view) });
  } catch (error) {
    // Render a normal connection error instead of crashing the React entry or
    // interpreting malformed host data as a standalone demonstration.
    return hostAdapter(() => { throw error; }, () => { throw error; });
  }
  if (!detected) return null;
  const { transport, snapshot, hostInfo } = detected;
  const createConnection = connections[transport] ?? (transport === "http-bridge"
    ? () => httpConnection({ snapshot: () => snapshot, pageOrigin: view?.location?.origin })
    : () => mcpConnection(new McpAppTransport({ name: "Graph Skill canvas", version: packageInfo.version }, {}, { window: view })));
  return hostAdapter(createConnection, (info, connection) => {
    // This registry is consulted only after the connection returns identity and
    // capabilities. Unknown hosts have no execution adapter.
    if (info.id === "codex" && info.transport === "mcp-app") return drivers.codex?.(connection) ?? codexAdapter(/** @type {ReturnType<typeof mcpConnection>} */(connection).app);
    if (info.id === "claude" && info.transport === "http-bridge") return drivers.claude?.(connection) ?? claudeAdapter(/** @type {ReturnType<typeof httpConnection>} */(connection));
    throw new Error("当前连接没有匹配的宿主适配器。");
  }, hostInfo);
}
