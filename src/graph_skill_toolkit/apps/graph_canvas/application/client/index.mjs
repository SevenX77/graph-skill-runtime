export function validateGraphBackend(value) {
  if (!value || typeof value.url !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(value.token ?? "")) throw new Error("本地画布后端连接信息无效。");
  const url = new URL(value.url);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port || url.pathname !== "/" || url.username || url.password || url.search || url.hash) throw new Error("画布后端必须是本机 loopback 地址。");
  return { url: url.origin, token: value.token };
}

/** Browser composition reads only the App's backend bootstrap, not host identity.
 * @returns {import('../../ports/graph/index').GraphConnection | null}
 */
export function createPageGraphConnection(page = globalThis.document) {
  try {
    const text = page?.querySelector("#graph-skill-snapshot")?.textContent;
    const snapshot = text ? JSON.parse(text) : null;
    if (!snapshot?.graphBackend) return null;
    const connection = createGraphConnection({ backend: snapshot.graphBackend });
    if (snapshot.skillRoot === null || typeof snapshot.skillRoot === "string") connection.selectRoot(snapshot.skillRoot);
    return connection;
  } catch (error) {
    return { connect({ fail }) { fail(error); }, selectRoot() {}, dispose() {} };
  }
}

/** @returns {import('../../ports/graph/index').GraphConnection} */
export function createGraphConnection({ backend, fetch: fetchImpl = globalThis.fetch?.bind(globalThis), retryMs = 750 }) {
  const descriptor = validateGraphBackend(backend);
  let callbacks, root, selected = false, disposed = false, generation = 0, abort, retryTimer, lastFailure = "";
  const stop = () => { clearTimeout(retryTimer); abort?.abort(); };
  async function open() {
    if (!callbacks || !selected || disposed) return;
    const attempt = ++generation;
    stop();
    const controller = new AbortController();
    abort = controller;
    try {
      if (!fetchImpl) throw new Error("页面没有可用的 HTTP 接口。");
      const url = descriptor.url + "/graph/events" + (root === null ? "" : "?root=" + encodeURIComponent(root));
      const response = await fetchImpl(url, { headers: { Authorization: "Bearer " + descriptor.token }, signal: controller.signal, cache: "no-store", credentials: "omit", redirect: "error" });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || "本地画布后端拒绝了连接。");
      }
      if (!response.body) throw new Error("本地画布后端没有返回数据流。");
      const reader = response.body.getReader(), decoder = new TextDecoder();
      let buffer = "";
      try {
        while (!disposed && attempt === generation) {
          const { value, done } = await reader.read();
          if (done) throw new Error("本地画布数据连接已断开。");
          buffer += decoder.decode(value, { stream: true });
          let boundary;
          while ((boundary = buffer.indexOf("\n\n")) >= 0) {
            const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
            if (frame.length > 8 * 1024 * 1024) throw new Error("画布数据帧超过页面输入限制。");
            const data = frame.split("\n").filter(line => line.startsWith("data: ")).map(line => line.slice(6)).join("\n");
            if (!data || disposed || attempt !== generation) continue;
            const event = JSON.parse(data);
            if (event.type === "snapshot") { lastFailure = ""; callbacks.receive(event.data); }
            else if (event.type === "invalid") { lastFailure = ""; callbacks.invalid(event); }
            else if (event.type === "error" && event.message !== lastFailure) { lastFailure = event.message; callbacks.fail(new Error(event.message)); }
          }
          if (buffer.length > 8 * 1024 * 1024) throw new Error("画布数据流超过页面输入限制。");
        }
      } finally { await reader.cancel().catch(() => {}); }
    } catch (error) {
      if (disposed || attempt !== generation || controller.signal.aborted) return;
      const message = error instanceof Error ? error.message : String(error);
      if (message !== lastFailure) { lastFailure = message; callbacks.fail(new Error("本地画布连接失败：" + message)); }
      retryTimer = setTimeout(() => { void open(); }, retryMs);
    }
  }
  return {
    connect(value) {
      if (callbacks || disposed) throw new Error("画布数据连接只能启动一次。");
      callbacks = value;
      void open();
    },
    selectRoot(value) {
      if (disposed) return;
      if (value !== null && (typeof value !== "string" || !value)) throw new Error("无效的 Skill 路径。");
      if (selected && root === value) return;
      selected = true; root = value; lastFailure = "";
      ++generation; stop(); void open();
    },
    dispose() { disposed = true; ++generation; stop(); },
  };
}

/** Long-poll GraphConnection for pages whose only route to the backend is a
 * request/response relay (the Codex MCP App channel). `call(name, args)` sends
 * one originating-server tool call and resolves with its MCP result.
 * @returns {import('../../ports/graph/index').GraphConnection}
 */
export function createRelayGraphConnection({ call, retryMs = 750, timeoutMs = 20000, setTimer = globalThis.setTimeout, clearTimer = globalThis.clearTimeout }) {
  if (typeof call !== "function") throw new Error("画布数据中继缺少调用接口。");
  let callbacks, root, selected = false, disposed = false, generation = 0, revision, retryTimer, lastFailure = "", failures = 0;
  const current = attempt => !disposed && attempt === generation;
  function report(message) {
    // The first failure after a selection is retried silently: the page may ask
    // before the host has finished the show_graph call that selects the root.
    failures += 1;
    if (failures < 2 || message === lastFailure) return;
    lastFailure = message;
    callbacks.fail(new Error("本地画布连接失败：" + message));
  }
  function retry(attempt) { retryTimer = setTimer(() => { if (current(attempt)) void loop(attempt); }, retryMs); }
  async function loop(attempt) {
    while (current(attempt)) {
      let result;
      try {
        result = await call("watch_graph", { skill_root: root, ...(revision === undefined ? {} : { after_revision: revision }), timeout_ms: timeoutMs });
      } catch (error) {
        if (!current(attempt)) return;
        report(error instanceof Error ? error.message : String(error)); retry(attempt); return;
      }
      if (!current(attempt)) return;
      const value = result?.structuredContent;
      if (result?.isError || !value || !Number.isSafeInteger(value.revision)) {
        const text = Array.isArray(result?.content) ? result.content.filter(item => item?.type === "text").map(item => item.text).join("\n") : "";
        report(text || "本地画布后端返回了无法识别的数据。"); retry(attempt); return;
      }
      failures = 0;
      revision = value.revision;
      const event = value.event;
      if (event?.type === "snapshot") { lastFailure = ""; callbacks.receive(event.data); }
      else if (event?.type === "invalid") { lastFailure = ""; callbacks.invalid(event); }
      else if (event?.type === "error" && event.message !== lastFailure) { lastFailure = event.message; callbacks.fail(new Error(event.message)); }
    }
  }
  function start() {
    if (!callbacks || !selected || disposed) return;
    const attempt = ++generation;
    clearTimer(retryTimer);
    revision = undefined; failures = 0;
    void loop(attempt);
  }
  return {
    connect(value) {
      if (callbacks || disposed) throw new Error("画布数据连接只能启动一次。");
      callbacks = value;
      start();
    },
    selectRoot(value) {
      if (disposed) return;
      if (value !== null && (typeof value !== "string" || !value)) throw new Error("无效的 Skill 路径。");
      if (selected && root === value) return;
      selected = true; root = value; lastFailure = "";
      start();
    },
    dispose() { disposed = true; ++generation; clearTimer(retryTimer); },
  };
}
