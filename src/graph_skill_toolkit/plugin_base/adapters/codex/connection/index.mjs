import { App, PostMessageTransport } from "@modelcontextprotocol/ext-apps";
import { mcpCapabilities } from "../driver/registry.mjs";
export { mcpCapabilities } from "../driver/registry.mjs";

/** @param {{window?:Window & typeof globalThis,transport?:unknown,originatingServer?:string,appInfo:{name:string,version:string}}} options */
export function createMcpConnection({ window: view = globalThis.window, transport, originatingServer, appInfo }) {
  if (typeof appInfo?.name !== "string" || !appInfo.name || typeof appInfo.version !== "string" || !appInfo.version) throw new Error("MCP App connection requires appInfo with name and version.");
  if (!transport && (!view?.parent || view.parent === view)) throw new Error("MCP App requires a host frame.");
  const app = new App({ name: appInfo.name, version: appInfo.version }, {}, { autoResize: false });
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
    async connect({ receive, fail, event = () => {} }) {
      const emit = (type, data) => event({ type, at: new Date().toISOString(), ...(data === undefined ? {} : { data }) });
      // The page owner interprets the presenting tool's arguments.
      app.ontoolinput = input => {
        const args = input?.arguments;
        if (args && typeof args === "object" && !Array.isArray(args)) {
          startupDelivered = true;
          clearTimeout(missingDataTimer);
          receive({ toolInput: args });
        }
      };
      app.ontoolresult = result => {
        emit("tool.completed", { isError: result.isError === true, structuredContent: result.structuredContent ?? null });
        if (result.isError) {
          clearTimeout(missingDataTimer);
          fail(new Error(result.content?.filter(item => item.type === "text").map(item => item.text).join("\n") || "The tool returned an error."));
        } else {
          startupDelivered = true;
          clearTimeout(missingDataTimer);
          receive(result.structuredContent);
        }
      };
      app.onhostcontextchanged = context => emit("host.contextChanged", context);
      app.onteardown = async () => { emit("page.teardown"); return {}; };
      app.onclose = () => { ready = false; clearTimeout(missingDataTimer); };
      try { await app.connect(transport); }
      catch (error) { settleConnected.reject(error); throw error; }
      ready = true;
      settleConnected.resolve();
      missingDataTimer = setTimeout(() => {
        if (!startupDelivered) fail(new Error("宿主没有向页面交付展示工具的输入或结果；请重新打开页面。"));
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
