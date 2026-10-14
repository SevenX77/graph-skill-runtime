import { App, PostMessageTransport } from "@modelcontextprotocol/ext-apps";
import { mcpCapabilities } from "../driver/registry.mjs";
export { mcpCapabilities } from "../driver/registry.mjs";
import packageInfo from "../../../package.json" with { type: "json" };

/** @param {{window?:Window & typeof globalThis,transport?:unknown,originatingServer?:string}} [options] */
export function createMcpConnection({ window: view = globalThis.window, transport, originatingServer } = {}) {
  if (!transport && (!view?.parent || view.parent === view)) throw new Error("MCP App requires a host frame.");
  const app = new App({ name: "Graph Skill canvas", version: packageInfo.version }, {}, { autoResize: false });
  return mcpConnection(app, { transport: transport ?? new PostMessageTransport(view.parent, view.parent), originatingServer });
}

/** SDK owns handshake, framing, request correlation, schema validation and teardown. */
export function mcpConnection(app, { transport, originatingServer, missingDataTimeoutMs = 12000 } = {}) {
  let ready = false;
  let startupDelivered = false;
  let missingDataTimer;
  let settleConnected;
  const connected = new Promise((resolve, reject) => { settleConnected = { resolve, reject }; });
  connected.catch(() => {});
  return {
    app, originatingServer,
    /** Call one of the originating server's tools once the App handshake completes. */
    async callTool(name, args) {
      await connected;
      return app.callServerTool({ name, arguments: args });
    },
    async connect({ receive, fail }) {
      app.ontoolinput = input => {
        const root = input?.arguments?.skill_root;
        if (typeof root === "string" && root.length > 0) {
          startupDelivered = true;
          clearTimeout(missingDataTimer);
          receive({ skillRoot: root });
        }
      };
      app.ontoolresult = result => {
        if (result.isError) {
          clearTimeout(missingDataTimer);
          fail(new Error(result.content?.filter(item => item.type === "text").map(item => item.text).join("\n") || "The tool returned an error."));
        } else {
          startupDelivered = true;
          clearTimeout(missingDataTimer);
          receive(result.structuredContent);
        }
      };
      app.onclose = () => { ready = false; clearTimeout(missingDataTimer); };
      try { await app.connect(transport); }
      catch (error) { settleConnected.reject(error); throw error; }
      ready = true;
      settleConnected.resolve();
      missingDataTimer = setTimeout(() => {
        if (!startupDelivered) fail(new Error("宿主没有向画布交付 show_graph 的 Skill 路径；请重新打开画布。"));
      }, missingDataTimeoutMs);
    },
    /** @returns {Promise<import('../../../ports/host/index').HostEvidence>} */
    async inspect() {
      let capabilities = null;
      try { capabilities = mcpCapabilities(app.getHostCapabilities(), app.getHostContext?.()); } catch { /* Keep identity facts when capabilities are invalid. */ }
      return { transport: "mcp-app", connected: ready, identity: app.getHostVersion(), capabilities };
    },
    async dispose() { ready = false; clearTimeout(missingDataTimer); await app.close(); },
  };
}
