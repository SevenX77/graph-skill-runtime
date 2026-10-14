// @ts-check
import { createHostAdapter } from "../adapters/factory/index.mjs";
import { discoverConnection } from "../adapters/detection/index.mjs";
import { createMcpConnection } from "../adapters/codex/connection/index.mjs";
import { createPageGraphConnection, createRelayGraphConnection } from "../application/graph/client/index.mjs";

/** Browser composition root: pairs the host adapter with the graph transport
 * its page may use. A Codex MCP App page cannot reach loopback HTTP (its CSP
 * admits only https/wss), so it long-polls the backend through the same MCP
 * connection the adapter uses; every other page reads the backend's SSE.
 * @param {Parameters<typeof createHostAdapter>[0]} [options]
 * @returns {{ adapter: import('../ports/host/index').HostAdapter | null, source: import('../ports/graph/index').GraphConnection | null }}
 */
export function createCanvasComposition(options = {}) {
  const page = options.document ?? globalThis.document, view = options.window ?? globalThis.window;
  let detected = null;
  try { detected = discoverConnection({ snapshotText: page?.querySelector("#graph-skill-snapshot")?.textContent, framed: Boolean(view?.parent && view.parent !== view) }); }
  catch { detected = null; }
  if (detected?.transport !== "mcp-app") return { adapter: createHostAdapter(options), source: createPageGraphConnection(/** @type {any} */ (page)) };
  const create = options.connections?.["mcp-app"] ?? (() => createMcpConnection({ window: /** @type {any} */ (view), originatingServer: /** @type {any} */ (detected?.snapshot)?.serverInfo?.name }));
  /** @type {any} */ let shared;
  const connection = () => (shared ??= create());
  const adapter = createHostAdapter({ ...options, connections: { ...options.connections, "mcp-app": connection } });
  const source = createRelayGraphConnection({ call: (/** @type {string} */ name, /** @type {Record<string, unknown>} */ args) => connection().callTool(name, args) });
  return { adapter, source };
}
