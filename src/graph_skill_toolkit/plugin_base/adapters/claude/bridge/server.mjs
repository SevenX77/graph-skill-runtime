import { randomBytes } from "node:crypto";
import { createLocalHttpServer } from "../../../backend/http/index.mjs";
import { HOST_ACTIONS, validateArguments } from "../../../ports/host/contract.mjs";
import { identifyHost, hostIdentityKey } from "../../detection/index.mjs";

const actions = new Set(HOST_ACTIONS);
const statuses = new Set(["completed", "accepted", "pending", "unsupported", "rejected", "error"]);
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

function validateAction(input, key) {
  if (!input || typeof input.id !== "string" || !/^[a-zA-Z0-9_-]{1,128}$/.test(input.id) || !actions.has(input.action)) throw new Error("Unknown action or invalid request id.");
  const args = validateArguments(input.action, input.args ?? {});
  return { id: input.id, action: input.action, args, key };
}

// This owner exists only after a plugin tool presents an HTML page. Browser and Mod
// have distinct bearer capabilities; neither token is placed in a URL or a log.
export function createHostBridge({ responseWaitMs = 20000, now = Date.now, http } = {}) {
  const keys = new Map(), credentials = new Map(), pages = new Map();
  const listener = http ?? createLocalHttpServer();
  const paths = new Set(["/capabilities", "/poll", "/disconnect", "/result", "/action", "/events"]);
  listener.mount(path => path === "/" || pages.has(path) || paths.has(path), handle);
  let base, closing, closed = false;
  const connected = view => view.confirmed && !view.disconnected && now() - view.lastPoll < 5000;
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
    base = listener.origin;
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
      if (request.headers["sec-fetch-site"] === "cross-site") return send(403, { error: "Open this page through its host preview." });
      const page = pages.get(url.pathname);
      response.setHeader("Content-Type", "text/html; charset=utf-8");
      response.setHeader("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
      if (page?.disconnected) return response.writeHead(410).end("<!doctype html><meta charset=utf-8><p>This page session has ended.</p>");
      return response.writeHead(200).end(page?.html ?? "<!doctype html><meta charset=utf-8><title>Plugin preview</title><p>Plugin preview is connected. Open the page URL returned by the plugin tool in this tab.</p>");
    }
    if (request.method === "OPTIONS") return send(204, {});
    const credential = credentials.get(request.headers.authorization?.replace(/^Bearer /, ""));
    if (!credential) return send(401, { error: "Unknown view capability." });
    const { view, role } = credential;
    try {
      if (request.method === "GET" && url.pathname === "/capabilities" && role === "browser") {
        return send(200, { connected: connected(view), identity: view.identity, capabilities: connected(view) ? view.capabilities : {}, message: connected(view) ? "Claude Mod 已连接" : "尚未收到当前 Claude Mod 的有效身份和心跳" });
      }
      if (request.method === "POST" && url.pathname === "/poll" && role === "mod") {
        const input = await readJson(request);
        if (view.disconnected) return send(401, { error: "This Claude session has ended." });
        const info = identifyHost({transport:"http-bridge",connected:true,identity:input.identity,capabilities:input.capabilities});
        view.identity = input.identity ?? null;
        view.confirmed = info.status === "confirmed";
        view.lastPoll = now(); view.capabilities = info.capabilities;
        if (!view.confirmed) return send(200, {requests:[]});
        const identityKey = hostIdentityKey(info);
        if (view.identityKey && view.identityKey !== identityKey) {
          view.disconnected = true;
          credentials.delete(view.mod.token);
          for (const entry of view.requests.values()) finish(entry, {status:entry.delivered ? "pending" : "error",message:"会话身份已改变；旧画布操作不会交给新会话。",requestId:entry.request.id});
          return send(409, {error:"The bridge belongs to another host session. Open a new page."});
        }
        view.identityKey = identityKey;
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
      if (request.method === "POST" && url.pathname === "/events" && role === "mod") {
        const input = await readJson(request);
        if (!Array.isArray(input.events) || input.events.some(event => typeof event?.type !== "string" || typeof event.at !== "string")) throw new Error("Invalid event batch.");
        for (const event of input.events) view.events.push({ seq: ++view.eventSeq, type: event.type, at: event.at, ...(event.data === undefined ? {} : { data: event.data }) });
        if (view.events.length > 500) view.events.splice(0, view.events.length - 500);
        for (const resolve of view.eventWaiters) resolve();
        view.eventWaiters.clear();
        return send(200, {});
      }
      if (request.method === "GET" && url.pathname === "/events" && role === "browser") {
        const after = Number(url.searchParams.get("after") ?? 0);
        if (!Number.isSafeInteger(after) || after < 0) throw new Error("Invalid event cursor.");
        if (!view.events.some(event => event.seq > after) && !view.disconnected) {
          await new Promise(resolve => {
            const done = () => { clearTimeout(timer); view.eventWaiters.delete(done); resolve(); };
            const timer = setTimeout(done, Math.min(responseWaitMs, 20000));
            view.eventWaiters.add(done);
          });
        }
        return send(200, { events: view.events.filter(event => event.seq > after), cursor: view.eventSeq, disconnected: view.disconnected });
      }
      if (request.method === "GET" && url.pathname === "/result" && role === "browser") {
        const entry = view.requests.get(url.searchParams.get("id"));
        return entry ? send(200, await wait(entry)) : send(404, { error: "Unknown request." });
      }
      if (request.method === "POST" && url.pathname === "/action" && role === "browser") {
        const action = validateAction(await readJson(request), view.key);
        let entry = view.requests.get(action.id);
        if (entry) {
          if (JSON.stringify(entry.request) !== JSON.stringify(action)) throw new Error("Request id already belongs to a different action.");
        } else {
          if (!connected(view)) return send(200, { status: "unsupported", message: "Claude Mod 未连接；操作未交付。" });
          if (view.capabilities[action.action]?.state !== "available") return send(200, { status: "unsupported", message: view.capabilities[action.action]?.detail || "当前宿主未提供此操作。" });
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
    base = await listener.open();
  }
  return {
    async createView(key, launchInfo) {
      await open();
      if (closed) throw new Error("Bridge is closed.");
      if (typeof key !== "string" || !key || key.length > 4096) throw new Error("A page view needs a nonempty string key.");
      let view = keys.get(key);
      // Bind a native startup session before its first heartbeat. A later
      // explicit launch in another session gets its own page and credentials.
      const launchKey = launchInfo?.identitySource === "claude-mod-session" && launchInfo.status === "confirmed" ? hostIdentityKey(launchInfo) : "";
      if (view && launchKey && view.identityKey && view.identityKey !== launchKey) {
        view.disconnected = true;
        credentials.delete(view.mod.token);
        for (const entry of view.requests.values()) finish(entry, {status:entry.delivered ? "pending" : "error",message:"启动会话已改变；原画布操作不会交给新会话。",requestId:entry.request.id});
      }
      if (!view || view.disconnected) {
        view = { events: [], eventSeq: 0, eventWaiters: new Set(), key, path: `/view/${token()}`, html: null, lastPoll: -Infinity, disconnected: false, identity:null, identityKey:null, confirmed:false, capabilities: {}, requests: new Map(), browser: { url: base, token: token() }, mod: { url: base, token: token(), key } };
        keys.set(key, view);
        pages.set(view.path, view);
        credentials.set(view.browser.token, { view, role: "browser" });
        credentials.set(view.mod.token, { view, role: "mod" });
      }
      if (launchKey) view.identityKey = launchKey;
      return { browser: view.browser, mod: view.mod, url: base + view.path };
    },
    publish(key, html) {
      const view = keys.get(key);
      if (closed || !view || view.disconnected) throw new Error("Create an active view before publishing its HTML.");
      if (typeof html !== "string") throw new Error("Page HTML must be a string.");
      view.html = html;
      return base + view.path;
    },
    close() {
      return closing ??= (async () => {
      closed = true;
      for (const view of keys.values()) for (const entry of view.requests.values()) finish(entry, { status: entry.delivered ? "pending" : "error", message: entry.delivered ? "画布服务已关闭；操作结果未知，不会自动重试。" : "画布服务已关闭，操作未交付。", requestId: entry.request.id });
      credentials.clear(); keys.clear(); pages.clear();
      // Partial HTTP bodies must not hold the MCP process alive at session EOF.
      // Completed/unknown receipts were settled above before retiring sockets.
      if (!http) await listener.close();
      })();
    },
  };
}
