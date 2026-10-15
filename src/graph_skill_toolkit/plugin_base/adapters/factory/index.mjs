// @ts-check
import { discoverConnection } from "../detection/index.mjs";
import { hostAdapter } from "../facade/index.mjs";
import { codexAdapter } from "../codex/driver/index.mjs";
import { claudeAdapter } from "../claude/driver/index.mjs";
import { httpConnection } from "../claude/connection/index.mjs";
import { createMcpConnection } from "../codex/connection/index.mjs";
import { SNAPSHOT_ELEMENT_ID } from "../../template/publisher.mjs";
import { createLocalClient, httpLocalTransport, mcpLocalTransport } from "../../local/page/index.mjs";

/** The browser composition boundary. Environment and drivers can be supplied
 * by an isolated test; normal consumers pass only their own appInfo.
 * @param {{appInfo?: {name:string, version:string}, document?: Pick<Document, 'querySelector'>, window?: Window,
 * connections?: Partial<Record<'mcp-app'|'http-bridge', () => import('../../ports/host/index').HostConnection>>,
 * drivers?: Partial<Record<'codex'|'claude', (connection:import('../../ports/host/index').HostConnection) => import('../../ports/host/index').HostDriver>>}} [options]
 * @returns {import('../../ports/host/index').HostAdapter | null}
 */
export function createHostAdapter({ appInfo, document: page = globalThis.document, window: view = globalThis.window, connections = {}, drivers = {} } = {}) {
  let detected;
  try {
    detected = discoverConnection({ snapshotText: page?.querySelector("#" + SNAPSHOT_ELEMENT_ID)?.textContent, framed: Boolean(view?.parent && view.parent !== view) });
  } catch (error) {
    // Render a normal connection error instead of crashing the React entry or
    // interpreting malformed host data as a standalone demonstration.
    return hostAdapter(() => { throw error; }, () => { throw error; });
  }
  if (!detected) return null;
  const { transport, snapshot, hostInfo } = detected;
  const baseConnection = connections[transport] ?? (transport === "http-bridge"
    ? () => httpConnection({ snapshot: () => snapshot, pageOrigin: view?.location?.origin })
    : () => createMcpConnection({ window: /** @type {any} */ (view), originatingServer: /** @type {any} */ (snapshot)?.serverInfo?.name, appInfo: /** @type {any} */ (appInfo) }));
  /** @type {any} */ let current;
  const createConnection = () => (current = baseConnection());
  return hostAdapter(createConnection, (info, connection) => {
    // This registry is consulted only after the connection returns identity and
    // capabilities. Unknown hosts have no execution adapter.
    if (info.id === "codex" && info.transport === "mcp-app") return drivers.codex?.(connection) ?? codexAdapter((/** @type {any} */ (connection)).app, { originatingServer: (/** @type {any} */ (connection)).originatingServer });
    if (info.id === "claude" && info.transport === "http-bridge") return drivers.claude?.(connection) ?? claudeAdapter(/** @type {ReturnType<typeof httpConnection>} */(connection));
    throw new Error("当前连接没有匹配的宿主适配器。");
  }, hostInfo, { local: createLocalClient(localTransport(transport, /** @type {any} */ (snapshot)?.local, () => current)) });
}

/** The page's route to its plugin process's local capabilities, from the
 * server's bootstrap: an HTTP credential for a loopback page, page-only MCP
 * tools for an MCP App page, or nothing.
 * @param {string} transport @param {any} declared @param {() => any} connection */
function localTransport(transport, declared, connection) {
  try {
    if (transport === "http-bridge" && declared?.transport === "http") return httpLocalTransport(declared);
    if (transport === "mcp-app" && declared?.transport === "mcp-tools") return mcpLocalTransport((name, args) => {
      const owner = connection();
      if (!owner?.callTool) throw new Error("宿主尚未连接。");
      return owner.callTool(name, args);
    });
  } catch { /* An invalid declaration leaves the page without local capabilities. */ }
  return null;
}
