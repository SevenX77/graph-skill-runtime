// The browser needs only this MCP Apps 2026-01-26 subset. The full official
// AppBridge remains the interoperability oracle in tests/mcp-transport.test.mjs.
// Keeping protocol transport here avoids bundling the SDK's server/auth/schema
// machinery into the shared document alongside React and the graph snapshot.
export const MCP_APPS_PROTOCOL_VERSION = "2026-01-26";

const record = value => value !== null && typeof value === "object" && !Array.isArray(value);
const identifier = value => typeof value === "string" || (typeof value === "number" && Number.isFinite(value));
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const methods = new Set([
  "ui/initialize", "ui/message", "ui/update-model-context", "ui/open-link",
  "ui/request-display-mode", "tools/call", "resources/read", "openai/files/open",
]);

function failure(message, code, outcome = "unknown") {
  return Object.assign(new Error(message), { code, outcome });
}

/** A bounded standards transport, not a replacement for the full Apps SDK. */
export class McpAppTransport {
  constructor(appInfo, appCapabilities = {}, options = {}) {
    this.appInfo = appInfo;
    this.appCapabilities = appCapabilities;
    this.window = options.window ?? globalThis.window;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    if (!this.window?.parent || this.window.parent === this.window) {
      throw failure("MCP App requires a host frame", "HOST_UNAVAILABLE", "not-sent");
    }
    if (!Number.isFinite(this.timeoutMs) || this.timeoutMs <= 0) throw new TypeError("Invalid response timeout");
    this.parent = this.window.parent;
    this.state = "new";
    this.pending = new Map();
    this.nextId = 0;
    this.origin = undefined;
    this.listener = event => this.receive(event);
  }

  getHostCapabilities() { return this.hostCapabilities; }
  getHostContext() { return this.hostContext; }
  getHostVersion() { return this.hostInfo; }

  async connect() {
    if (this.state !== "new") throw failure("Transport already started", "HOST_STATE", "not-sent");
    this.state = "connecting";
    this.window.addEventListener("message", this.listener);
    try {
      const result = await this.request({ method: "ui/initialize", params: {
        appInfo: this.appInfo, appCapabilities: this.appCapabilities,
        protocolVersion: MCP_APPS_PROTOCOL_VERSION,
      } });
      if (result.protocolVersion !== MCP_APPS_PROTOCOL_VERSION || !record(result.hostCapabilities)
          || !record(result.hostInfo) || typeof result.hostInfo.name !== "string"
          || typeof result.hostInfo.version !== "string" || !record(result.hostContext)) {
        throw failure("Host returned an unsupported MCP Apps initialization", "HOST_PROTOCOL", "rejected");
      }
      this.hostCapabilities = result.hostCapabilities;
      this.hostContext = result.hostContext;
      this.hostInfo = result.hostInfo;
      this.state = "ready";
      this.send({ jsonrpc: "2.0", method: "ui/notifications/initialized" });
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  request({ method, params }, schema) {
    if (!methods.has(method)) return Promise.reject(failure(`Unsupported app request: ${method}`, "HOST_METHOD", "not-sent"));
    if (this.state !== "ready" && !(this.state === "connecting" && method === "ui/initialize")) {
      return Promise.reject(failure("MCP App is not connected", "HOST_UNAVAILABLE", "not-sent"));
    }
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(failure(`No host response to ${method}; its outcome is unknown`, "HOST_TIMEOUT"));
      }, this.timeoutMs);
      this.pending.set(id, { method, schema, resolve, reject, timer });
      try { this.send({ jsonrpc: "2.0", id, method, ...(params === undefined ? {} : { params }) }); }
      catch (error) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(failure(error.message, "HOST_SEND", "not-sent"));
      }
    });
  }

  sendMessage(params) { return this.request({ method: "ui/message", params }); }
  updateModelContext(params) { return this.request({ method: "ui/update-model-context", params }); }
  callServerTool(params) { return this.request({ method: "tools/call", params }); }
  readServerResource(params) { return this.request({ method: "resources/read", params }); }
  openLink(params) { return this.request({ method: "ui/open-link", params }); }
  requestDisplayMode(params) { return this.request({ method: "ui/request-display-mode", params }); }

  send(message) {
    // Sandboxed parents can have an opaque "null" origin, which cannot be used
    // as targetOrigin. The exact WindowProxy source is still mandatory on reads.
    this.parent.postMessage(message, this.origin && this.origin !== "null" ? this.origin : "*");
  }

  receive(event) {
    if (event.source !== this.parent || (this.origin !== undefined && event.origin !== this.origin)) return;
    const message = event.data;
    if (!record(message) || message.jsonrpc !== "2.0") return;
    if (typeof message.method === "string") {
      if (own(message, "id")) {
        if (!identifier(message.id)) return;
        if (message.method === "ping") this.send({ jsonrpc: "2.0", id: message.id, result: {} });
        else if (message.method === "ui/resource-teardown") {
          this.send({ jsonrpc: "2.0", id: message.id, result: {} });
          void this.close();
        } else this.send({ jsonrpc: "2.0", id: message.id, error: { code: -32601, message: "Method not supported by this app" } });
      } else if (this.state === "ready" && record(message.params)) {
        try {
          if (message.method === "ui/notifications/tool-result") this.ontoolresult?.(message.params);
          if (message.method === "ui/notifications/host-context-changed") {
            this.hostContext = { ...this.hostContext, ...message.params };
            this.onhostcontextchanged?.(message.params);
          }
        } catch (error) { this.onerror?.(error); }
      }
      return;
    }
    if (!identifier(message.id)) return;
    const pending = this.pending.get(message.id);
    if (!pending || own(message, "result") === own(message, "error")) return;
    if (own(message, "result") && !record(message.result)) return;
    if (own(message, "error") && (!record(message.error) || !Number.isInteger(message.error.code) || typeof message.error.message !== "string")) return;
    clearTimeout(pending.timer);
    this.pending.delete(message.id);
    if (own(message, "error")) {
      pending.reject(Object.assign(failure(message.error.message, message.error.code, "rejected"), { data: message.error.data }));
      return;
    }
    if (pending.method === "ui/initialize") this.origin = event.origin;
    try { pending.resolve(pending.schema?.parse ? pending.schema.parse(message.result) : message.result); }
    catch (error) { pending.reject(failure(`Invalid host result: ${error.message}`, "HOST_PROTOCOL")); }
  }

  async close() {
    if (this.state === "closed") return;
    this.window.removeEventListener("message", this.listener);
    this.state = "closed";
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(failure(`Host connection closed during ${pending.method}; its outcome is unknown`, "HOST_CLOSED"));
    }
    this.pending.clear();
  }
}
