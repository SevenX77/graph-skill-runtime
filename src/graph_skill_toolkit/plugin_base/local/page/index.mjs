// @ts-check
/** Page side of the local capabilities: one client over whichever route the
 * page has to its own plugin process. */
import { LOCAL_ACTIONS, validateLocalArguments } from "../definitions.mjs";
import { validateResult, failureResult } from "../../ports/host/contract.mjs";

/** @typedef {import('../../ports/host/index').HostResult} HostResult */
/** @typedef {{ call(operation:string, args:Record<string, unknown>): Promise<unknown>, wait(after:number, timeoutMs:number): Promise<{cursor:number, events:any[], closed?:boolean}> }} LocalTransport */

/** Same-origin HTTP route for a page served by the plugin's loopback listener.
 * @param {{url:string, token:string}} descriptor @param {typeof globalThis.fetch} [fetchImpl] @returns {LocalTransport} */
export function httpLocalTransport(descriptor, fetchImpl = globalThis.fetch?.bind(globalThis)) {
  if (!descriptor || typeof descriptor.url !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(descriptor.token ?? "")) throw new Error("本地能力连接信息无效。");
  const url = new URL(descriptor.url);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1") throw new Error("本地能力必须经本机 loopback 地址访问。");
  const headers = { Authorization: "Bearer " + descriptor.token };
  /** @param {Response} response */
  const body = async response => {
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.error || `本地能力服务返回 HTTP ${response.status}。`);
    return value;
  };
  return {
    call: async (operation, args) => body(await fetchImpl(url.origin + "/local/call", { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ operation, args }), cache: "no-store", credentials: "omit", redirect: "error" })),
    wait: async (after, timeoutMs) => body(await fetchImpl(`${url.origin}/local/events?after=${after}&timeout_ms=${timeoutMs}`, { headers, cache: "no-store", credentials: "omit", redirect: "error" })),
  };
}

/** Page-only MCP tools on the originating server (Codex MCP App channel).
 * @param {(name:string, args:Record<string, unknown>) => Promise<any>} callTool @returns {LocalTransport} */
export function mcpLocalTransport(callTool) {
  /** @param {any} value */
  const structured = value => {
    if (value?.isError || !value?.structuredContent) throw new Error(value?.content?.find?.((/** @type {any} */ item) => item?.type === "text")?.text || "本地能力工具返回了无法识别的数据。");
    return value.structuredContent;
  };
  return {
    call: async (operation, args) => structured(await callTool("local_call", { operation, args })),
    wait: async (after, timeoutMs) => structured(await callTool("local_events", { after, timeout_ms: timeoutMs })),
  };
}

const READS = ["local.files.read", "local.files.watch"];

/** @param {LocalTransport | null} transport */
export function createLocalClient(transport, { retryMs = 2000 } = {}) {
  /** @type {Map<string, (event:any) => void>} */
  const listeners = new Map();
  let cursor = 0, polling = false, disposed = false;

  /** @param {string} operation @param {unknown} input @returns {Promise<HostResult>} */
  async function call(operation, input = {}) {
    let args, dispatched = false;
    try {
      args = validateLocalArguments(operation, input);
      if (disposed) return { status: "error", message: "本地能力连接已关闭。", evidence: { sent: args, limits: [] } };
      if (!transport) return { status: "unsupported", message: "此插件服务没有为页面提供本地能力。", evidence: { sent: args, limits: [] } };
      dispatched = !READS.includes(operation);
      const result = validateResult(await transport.call(operation, args));
      return { ...result, evidence: { sent: args, limits: [], ...(result.evidence ?? {}) } };
    } catch (error) {
      return { ...failureResult(error, dispatched), evidence: { sent: args ?? input, limits: [] } };
    }
  }

  async function poll() {
    if (polling) return;
    polling = true;
    while (listeners.size && !disposed && transport) {
      try {
        const answer = await transport.wait(cursor, 20000);
        cursor = Math.max(cursor, answer.cursor);
        for (const event of answer.events ?? []) listeners.get(event?.data?.watchId)?.(structuredClone(event));
        if (answer.closed) break;
      } catch { await new Promise(done => setTimeout(done, retryMs)); }
    }
    polling = false;
  }

  /** @param {{paths:string[]}} args @param {(event:{type:string, at:string, data:any}) => void} listener */
  async function watch(args, listener) {
    if (typeof listener !== "function") throw new Error("监听文件变化需要监听函数。");
    const result = await call("local.files.watch", args);
    const watchId = /** @type {any} */ (result.data)?.watchId;
    if (result.status !== "completed" || typeof watchId !== "string") return { ...result, stop: async () => result };
    listeners.set(watchId, listener);
    void poll();
    return { ...result, stop: async () => { listeners.delete(watchId); return call("local.files.unwatch", { watchId }); } };
  }

  return Object.freeze({
    available: Boolean(transport),
    operations: LOCAL_ACTIONS,
    call,
    files: Object.freeze({
      /** @param {{path:string, encoding?:"utf8"|"base64", maxBytes?:number}} args */
      read: args => call("local.files.read", args),
      /** @param {{path:string, content:string, encoding?:"utf8"|"base64"}} args */
      write: args => call("local.files.write", args),
      watch,
    }),
    system: Object.freeze({
      /** @param {{url:string}} args */
      openExternal: args => call("local.system.openExternal", args),
      /** @param {{path:string}} args */
      revealInFileManager: args => call("local.system.revealInFileManager", args),
    }),
    dispose() { disposed = true; listeners.clear(); },
  });
}
