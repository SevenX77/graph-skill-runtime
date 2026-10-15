// @ts-check
import { HOST_ACTIONS, validateArguments, validateResult, failureResult } from "../../ports/host/contract.mjs";
import { FACADE_ACTIONS } from "../../ports/host/catalog.mjs";
import { identifyHost, unknownHost, hostIdentityKey, readLaunchHostInfo } from "../detection/index.mjs";
import { launchMatchesConnection } from "../launch/index.mjs";
import { createLocalClient } from "../../local/page/index.mjs";

/** Each instance owns one page connection. It never changes host after selection.
 * @param {() => import('../../ports/host/index').HostConnection} createConnection
 * @param {(info:import('../../ports/host/index').HostInfo, connection:import('../../ports/host/index').HostConnection) => import('../../ports/host/index').HostDriver} selectDriver
 * @param {import('../../ports/host/index').HostInfo} [launchInfo]
 * @param {{local?: ReturnType<typeof createLocalClient>}} [options]
 * @returns {import('../../ports/host/index').HostAdapter}
 */
export function hostAdapter(createConnection, selectDriver, launchInfo = unknownHost(), { local = createLocalClient(null) } = {}) {
  /** @type {import('../../ports/host/index').HostState} */
  let state = "new";
  /** @type {import('../../ports/host/index').HostDriver | undefined} */
  let driver;
  /** @type {import('../../ports/host/index').HostConnection | undefined} */
  let connection;
  let launch = launchInfo, info = launchInfo, pinnedIdentity = "", mismatch = false;
  /** @type {Promise<import('../../ports/host/index').HostInfo>|undefined} */
  let inspecting;
  /** @type {Promise<void> | undefined} */
  let closing;
  /** @type {Set<{listener:(event:import('../../ports/host/index').HostEvent)=>void, types:Set<string>|null}>} */
  const subscribers = new Set();
  let eventsStarted = false;
  /** @param {import('../../ports/host/index').HostEvent} event */
  const dispatchEvent = event => {
    if (!active()) return;
    for (const item of subscribers) if (!item.types || item.types.has(event.type)) {
      try { item.listener(structuredClone(event)); } catch { /* A listener failure stays with its owner. */ }
    }
  };
  const active = () => state === "connecting" || state === "connected";
  const disposed = () => state === "disposed";
  const requireConnected = () => { if (state !== "connected") throw new Error("宿主尚未连接或连接已关闭。"); };
  const execution = () => { if (!driver) throw new Error("宿主执行器尚未创建。"); return driver; };
  const closeDriver = () => closing ??= Promise.resolve().then(() => connection?.dispose());

  function refreshIdentity() {
    requireConnected();
    return inspecting ??= (async () => {
      try {
        if (!connection) throw new Error("连接未创建。");
        const next = identifyHost(await connection.inspect());
        requireConnected();
        if (launch.transport !== "none" && !launchMatchesConnection(launch, next)) mismatch = true;
        if (next.status === "confirmed") {
          const key = hostIdentityKey(next);
          if (pinnedIdentity && pinnedIdentity !== key) mismatch = true;
          if (!mismatch && !driver) { driver = selectDriver(next, connection); pinnedIdentity = key; }
        }
        info = mismatch ? unknownHost("连接中的宿主身份发生改变；请在当前会话重新打开画布。", next) : next;
      } catch (error) {
        info = unknownHost("无法读取当前宿主连接：" + String(error instanceof Error ? error.message : error), info);
        throw error;
      }
      return info;
    })().finally(() => { inspecting = undefined; });
  }

  /** @param {string} id */
  async function getResult(id) {
    requireConnected();
    if (!id || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error("无效的画布请求编号。");
    // Receipt lookup never resubmits an action. Failed lookup leaves the page's
    // existing unknown result intact, so propagate its diagnostic to the UI.
    const owner = execution();
    if (!owner.getResult) throw new Error("宿主没有请求结果查询接口。");
    const result = validateResult(await owner.getResult(id));
    requireConnected();
    return result;
  }

  /** @type {import('../../ports/host/index').HostAdapter} */
  const adapter = /** @type {any} */ ({
    get hostInfo() { return info; },
    get hostId() { return info.id; },
    get hostName() { return info.status === "confirmed" ? info.id === "codex" ? "ChatGPT(Codex)" : info.name ?? info.id : "未知宿主"; },
    get state() { return state; },
    get getResult() { return driver?.getResult ? getResult : undefined; },
    async connect(/** @type {{receive:(payload:unknown)=>void,fail:(error:unknown)=>void}} */ callbacks) {
      if (state !== "new") throw new Error("每个画布连接只能启动一次。");
      state = "connecting";
      let connectionFailure;
      try {
        connection = createConnection();
        await connection.connect({
          receive(payload) {
            if (!active()) return;
            try {
              // Tool results carry the invocation's identity as well as business data.
              // Reused resource documents must not overwrite that per-call binding.
              if (payload && typeof payload === "object" && "hostInfo" in payload) {
                const supplied = readLaunchHostInfo(payload.hostInfo);
                if (launch.transport !== "none" && !launchMatchesConnection(launch, supplied)) mismatch = true;
                if (info.status === "confirmed" && !launchMatchesConnection(supplied, info)) mismatch = true;
                launch = supplied;
              }
              callbacks.receive(structuredClone(payload));
            }
            catch (error) { callbacks.fail(error); }
          },
          fail(error) {
            if (!active()) return;
            if (state === "connecting") connectionFailure = error instanceof Error ? error : new Error(String(error));
            callbacks.fail(error);
          },
          event: dispatchEvent,
        });
        if (state !== "connecting") throw new Error("连接完成前画布已关闭。");
        if (connectionFailure) throw connectionFailure;
        state = "connected";
        await refreshIdentity();
      } catch (error) {
        if (!disposed()) state = "failed";
        info = unknownHost("宿主连接未成功。", info);
        await closeDriver();
        throw error;
      }
    },
    async capabilities() {
      requireConnected();
      return (await refreshIdentity()).capabilities;
    },
    async invoke(/** @type {import('../../ports/host/index').HostAction} */ action, /** @type {unknown} */ input) {
      let dispatched = false, limits = /** @type {string[]} */ ([]);
      /** @type {import('../../ports/host/index').HostActionArgs | undefined} */
      let args;
      // Every result carries evidence: what was sent and which host limits applied.
      const withEvidence = (/** @type {import('../../ports/host/index').HostResult} */ result) => ({ ...result, evidence: {
        ...(result.evidence ?? {}), sent: result.evidence?.sent ?? args ?? input ?? {},
        limits: [...new Set([...limits, ...(result.evidence?.limits ?? [])])] } });
      try {
        requireConnected();
        if (!HOST_ACTIONS.includes(action)) return withEvidence({ status: "unsupported", message: "未知的宿主操作。" });
        args = validateArguments(action, input);
        const capabilities = await this.capabilities();
        requireConnected();
        if (FACADE_ACTIONS.includes(action)) return withEvidence(facadeAction(action, capabilities));
        const capability = capabilities[action];
        limits = capability.limits ?? [];
        if (capability.state !== "available") return withEvidence({ status: "unsupported", message: capability.detail, data: { capabilityState: capability.state } });
        dispatched = true;
        const result = validateResult(await execution().invoke(action, args));
        if (state !== "connected") return withEvidence({ status: "pending", message: "操作提交后连接已关闭；请检查宿主中的实际结果。", ...(result.requestId ? { requestId: result.requestId } : {}) });
        return withEvidence(result);
      } catch (error) { return withEvidence(failureResult(error, dispatched)); }
    },
    async dispose() {
      state = "disposed";
      subscribers.clear();
      local.dispose();
      info = unknownHost("画布连接已关闭。", info);
      await closeDriver();
    },
  });
  /** @param {string} action @param {import('../../ports/host/index').HostCapabilities} capabilities @returns {import('../../ports/host/index').HostResult} */
  function facadeAction(action, capabilities) {
    if (action === "host.getInfo") return { status: "completed", message: "已读取当前连接的宿主身份。", data: info };
    if (action === "host.getCapabilities") return { status: "completed", message: "已读取当前连接的宿主能力。", data: capabilities };
    return { status: "unsupported", message: "订阅需要监听函数：请调用 adapter.events.subscribe(listener, types)。", data: { capability: capabilities[action] } };
  }
  for (const namespace of ["files", "composer", "conversation", "context", "tools", "views", "skills"]) {
    (/** @type {any} */ (adapter))[namespace] = Object.freeze(Object.fromEntries(HOST_ACTIONS.filter(action => action.startsWith(namespace + ".")).map(action => [action.split(".")[1], /** @param {import('../../ports/host/index').HostActionArgs} [args] */ args => adapter.invoke(/** @type {import('../../ports/host/index').HostAction} */ (action), args ?? {})])));
  }
  (/** @type {any} */ (adapter)).host = Object.freeze({ getInfo: async () => { await refreshIdentity(); return info; }, getCapabilities: () => adapter.capabilities(),
    getContext: () => adapter.invoke("host.getContext", {}) });
  (/** @type {any} */ (adapter)).local = local;
  (/** @type {any} */ (adapter)).events = Object.freeze({
    subscribe(/** @type {(event:import('../../ports/host/index').HostEvent)=>void} */ listener, /** @type {string[]|undefined} */ types) {
      if (typeof listener !== "function") throw new Error("事件订阅需要监听函数。");
      if (types !== undefined) validateArguments("events.subscribe", { types });
      const item = { listener, types: types ? new Set(types) : null };
      subscribers.add(item);
      // Pull-based connections relay host events only once a page listens.
      if (!eventsStarted && connection && "subscribeEvents" in connection) { eventsStarted = true; /** @type {any} */ (connection).subscribeEvents(dispatchEvent); }
      return () => { subscribers.delete(item); };
    },
  });
  return adapter;
}
