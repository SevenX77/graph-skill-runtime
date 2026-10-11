import { createServer } from "node:http";
import { randomBytes } from "node:crypto";

const actions = new Set(["open-root", "open-file", "fill-prompt", "send-prompt", "update-context", "list-tools", "call-tool", "request-skill"]);
const statuses = new Set(["completed", "accepted", "unsupported", "rejected", "error"]);
const token = () => randomBytes(32).toString("hex");
const pending = id => ({ status: "pending", message: "宿主仍未返回结果；查询此请求不会重复执行。", requestId: id });

async function readJson(request) {
  const chunks = []; let length = 0;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 65536) throw new Error("Bridge request exceeds 64 KiB.");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function validateAction(input, root) {
  if (!input || typeof input.id !== "string" || !/^[a-zA-Z0-9-]{1,80}$/.test(input.id) || !actions.has(input.action)) throw new Error("Unknown action or invalid request id.");
  const args = input.args ?? {};
  if (typeof args !== "object" || Array.isArray(args)) throw new Error("Action arguments must be an object.");
  if (Object.keys(args).some(key => !["skillRoot", "text", "context"].includes(key))) throw new Error("Unknown action argument.");
  if (args.skillRoot !== undefined && args.skillRoot !== root) throw new Error("Skill root differs from the displayed view.");
  if (["fill-prompt", "send-prompt"].includes(input.action) && (typeof args.text !== "string" || !args.text.trim() || args.text.length > 8000)) throw new Error("Prompt must contain 1–8000 characters.");
  if (args.context !== undefined) {
    const value = args.context;
    if (!value || value.skillRoot !== root || typeof value.graphId !== "string" || value.graphId.length > 256 ||
      (value.nodeId !== undefined && (typeof value.nodeId !== "string" || value.nodeId.length > 256)) ||
      Object.keys(value).some(key => !["skillRoot", "graphId", "nodeId"].includes(key))) throw new Error("Invalid selected-node context.");
  }
  if (input.action === "update-context" && !args.context) throw new Error("Node context is required.");
  return { id: input.id, action: input.action, args: { ...args, skillRoot: root }, skillRoot: root };
}

// This owner exists only after an explicit HTML show_graph call. Browser and Mod
// have distinct bearer capabilities; neither token is placed in a URL or a log.
export function createHostBridge({ responseWaitMs = 20000, now = Date.now } = {}) {
  const roots = new Map(), credentials = new Map(), pages = new Map();
  let server, base, opening, closing, closed = false;
  const connected = view => !view.disconnected && now() - view.lastPoll < 5000;
  function finish(entry, result) {
    if (entry.result) return;
    entry.result = result;
    for (const resolve of entry.waiters) resolve(result);
    entry.waiters.clear();
  }
  function wait(entry) {
    if (entry.result) return Promise.resolve(entry.result);
    return new Promise(resolve => {
      const done = result => { clearTimeout(timer); entry.waiters.delete(done); resolve(result); };
      const timer = setTimeout(() => done(pending(entry.request.id)), responseWaitMs);
      entry.waiters.add(done);
    });
  }
  async function handle(request, response) {
    // The normal host preview attaches this actual loopback origin. Documents
    // and actions share that origin; no cross-origin page may read credentials.
    response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type");
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.setHeader("X-Content-Type-Options", "nosniff");
    response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
    response.setHeader("Referrer-Policy", "no-referrer");
    const send = (code, data) => { if (!response.destroyed) response.writeHead(code).end(JSON.stringify(data)); };
    if (request.headers.host !== new URL(base).host) return send(403, { error: "Invalid loopback host." });
    if (request.headers.origin && request.headers.origin !== base) return send(403, { error: "Cross-origin preview requests are not accepted." });
    if (request.headers.origin === base) response.setHeader("Access-Control-Allow-Origin", base);
    const url = new URL(request.url, base);
    if (request.method === "GET" && (url.pathname === "/" || pages.has(url.pathname))) {
      if (request.headers["sec-fetch-site"] === "cross-site") return send(403, { error: "Open this canvas through its host preview." });
      const page = pages.get(url.pathname);
      response.setHeader("Content-Type", "text/html; charset=utf-8");
      response.setHeader("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
      if (page?.disconnected) return response.writeHead(410).end("<!doctype html><meta charset=utf-8><p>This canvas session has ended.</p>");
      return response.writeHead(200).end(page?.html ?? "<!doctype html><meta charset=utf-8><title>Graph Skill preview</title><p>Graph Skill preview is connected. Open the canvas URL returned by show_graph in this tab.</p>");
    }
    if (request.method === "OPTIONS") return send(204, {});
    const credential = credentials.get(request.headers.authorization?.replace(/^Bearer /, ""));
    if (!credential) return send(401, { error: "Unknown view capability." });
    const { view, role } = credential;
    try {
      if (request.method === "GET" && url.pathname === "/capabilities" && role === "browser") {
        return send(200, { connected: connected(view), capabilities: connected(view) ? view.capabilities : {}, message: connected(view) ? "Claude Mod 已连接" : "尚未收到当前 Claude Mod 的心跳" });
      }
      if (request.method === "POST" && url.pathname === "/poll" && role === "mod") {
        const input = await readJson(request);
        if (!input.capabilities || typeof input.capabilities !== "object" || Array.isArray(input.capabilities)) throw new Error("Missing Mod capabilities.");
        if (view.disconnected) return send(401, { error: "This Claude session has ended." });
        view.lastPoll = now(); view.capabilities = input.capabilities;
        const requests = [];
        for (const entry of view.requests.values()) if (!entry.delivered && !entry.result) {
          entry.delivered = true; requests.push(entry.request);
        }
        return send(200, { requests });
      }
      if (request.method === "POST" && url.pathname === "/disconnect" && role === "mod") {
        view.disconnected = true;
        for (const entry of view.requests.values()) finish(entry, { status: entry.delivered ? "pending" : "error", message: entry.delivered ? "Claude 会话已断开；操作结果未知，不会自动重试。" : "Claude 会话已断开，操作未交付。", requestId: entry.request.id });
        credentials.delete(view.mod.token);
        return send(200, {});
      }
      if (request.method === "POST" && url.pathname === "/result" && role === "mod") {
        const input = await readJson(request), entry = view.requests.get(input.id);
        if (!entry?.delivered || !statuses.has(input.result?.status) || typeof input.result?.message !== "string") throw new Error("Invalid result receipt.");
        if (entry.result && JSON.stringify(entry.result) !== JSON.stringify(input.result)) throw new Error("Conflicting result receipt.");
        finish(entry, input.result); return send(200, {});
      }
      if (request.method === "GET" && url.pathname === "/result" && role === "browser") {
        const entry = view.requests.get(url.searchParams.get("id"));
        return entry ? send(200, await wait(entry)) : send(404, { error: "Unknown request." });
      }
      if (request.method === "POST" && url.pathname === "/action" && role === "browser") {
        const action = validateAction(await readJson(request), view.root);
        let entry = view.requests.get(action.id);
        if (entry) {
          if (JSON.stringify(entry.request) !== JSON.stringify(action)) throw new Error("Request id already belongs to a different action.");
        } else {
          if (!connected(view)) return send(200, { status: "unsupported", message: "Claude Mod 未连接；操作未交付。" });
          if (view.capabilities[action.action]?.available !== true) return send(200, { status: "unsupported", message: view.capabilities[action.action]?.detail || "当前宿主未提供此操作。" });
          if ([...view.requests.values()].filter(item => !item.result).length >= 32) return send(429, { error: "32 host operations are still pending; inspect their results first." });
          while (view.requests.size >= 256) {
            const completed = [...view.requests].find(([, item]) => item.result);
            if (!completed) break;
            view.requests.delete(completed[0]);
          }
          entry = { request: action, delivered: false, result: null, waiters: new Set() };
          view.requests.set(action.id, entry);
        }
        return send(200, await wait(entry));
      }
      send(404, { error: "Route is not available to this capability." });
    } catch (error) { send(400, { error: error.message }); }
  }
  async function open() {
    if (closed) throw new Error("Bridge is closed.");
    return opening ??= new Promise((resolve, reject) => {
      server = createServer((request, response) => { void handle(request, response).catch(() => response.destroy()); });
      server.once("error", reject);
      server.listen(0, "127.0.0.1", () => { base = `http://127.0.0.1:${server.address().port}`; resolve(); });
    });
  }
  return {
    async createView(root) {
      await open();
      if (closed) throw new Error("Bridge is closed.");
      let view = roots.get(root);
      if (!view || view.disconnected) {
        view = { root, path: `/view/${token()}`, html: null, lastPoll: -Infinity, disconnected: false, capabilities: {}, requests: new Map(), browser: { url: base, token: token() }, mod: { url: base, token: token() } };
        roots.set(root, view);
        pages.set(view.path, view);
        credentials.set(view.browser.token, { view, role: "browser" });
        credentials.set(view.mod.token, { view, role: "mod" });
      }
      return { browser: view.browser, mod: view.mod, url: base + view.path };
    },
    publish(root, html) {
      const view = roots.get(root);
      if (closed || !view || view.disconnected) throw new Error("Create an active view before publishing its HTML.");
      if (typeof html !== "string") throw new Error("Canvas HTML must be a string.");
      view.html = html;
      return base + view.path;
    },
    close() {
      return closing ??= (async () => {
      closed = true;
      if (opening) await opening;
      for (const view of roots.values()) for (const entry of view.requests.values()) finish(entry, { status: entry.delivered ? "pending" : "error", message: entry.delivered ? "画布服务已关闭；操作结果未知，不会自动重试。" : "画布服务已关闭，操作未交付。", requestId: entry.request.id });
      credentials.clear(); roots.clear(); pages.clear();
      // Partial HTTP bodies must not hold the MCP process alive at session EOF.
      // Completed/unknown receipts were settled above before retiring sockets.
      if (server?.listening) await new Promise(resolve => { server.close(resolve); server.closeAllConnections(); });
      })();
    },
  };
}
