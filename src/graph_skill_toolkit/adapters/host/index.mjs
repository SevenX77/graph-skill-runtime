// @ts-check
import { HOST_ACTIONS, validateArguments, validateResult, failureResult } from "../../ports/host/contract.mjs";
import { validateCanvas } from "../../ui/canvas/index.mjs";
import { identifyHost, unknownHost, hostIdentityKey, readLaunchHostInfo } from "../detection/index.mjs";
import { launchMatchesConnection } from "../launch/index.mjs";

/** Each instance owns one page connection. It never changes host after selection.
 * @param {() => import('../../ports/host/index').HostConnection} createConnection
 * @param {(info:import('../../ports/host/index').HostInfo, connection:import('../../ports/host/index').HostConnection) => import('../../ports/host/index').HostDriver} selectDriver
 * @param {import('../../ports/host/index').HostInfo} [launchInfo]
 * @returns {import('../../ports/host/index').HostAdapter}
 */
export function hostAdapter(createConnection, selectDriver, launchInfo = unknownHost()) {
  /** @type {import('../../ports/host/index').HostState} */
  let state = "new";
  /** @type {import('../../ports/host/index').HostDriver | undefined} */
  let driver;
  /** @type {import('../../ports/host/index').HostConnection | undefined} */
  let connection;
  let launch = launchInfo, info = launchInfo, pinnedIdentity = "", mismatch = false;
  /** @type {Promise<import('../../ports/host/index').HostInfo>|undefined} */
  let inspecting;
  /** @type {import('../../ui/canvas/types').CanvasSnapshot | null} */
  let snapshot = null;
  let revision = 0;
  /** @type {Promise<void> | undefined} */
  let closing;
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

  return {
    get hostInfo() { return info; },
    get hostId() { return info.id; },
    get hostName() { return info.status === "confirmed" ? info.name ?? info.id : "未知宿主"; },
    get state() { return state; },
    get getResult() { return driver?.getResult ? getResult : undefined; },
    async connect(callbacks) {
      if (state !== "new") throw new Error("每个画布连接只能启动一次。");
      state = "connecting";
      let connectionFailure;
      try {
        connection = createConnection();
        await connection.connect({
          receive(payload) {
            if (!active()) return;
            revision++;
            snapshot = null;
            try {
              // Tool results carry the invocation's identity as well as graph data.
              // Reused resource documents must not overwrite that per-call binding.
              if (payload && typeof payload === "object" && "hostInfo" in payload) {
                const supplied = readLaunchHostInfo(payload.hostInfo);
                if (launch.transport !== "none" && !launchMatchesConnection(launch, supplied)) mismatch = true;
                if (info.status === "confirmed" && !launchMatchesConnection(supplied, info)) mismatch = true;
                launch = supplied;
              }
              snapshot = validateCanvas(payload); callbacks.receive(structuredClone(snapshot));
            }
            catch (error) { callbacks.fail(error); }
          },
          fail(error) {
            if (!active()) return;
            snapshot = null;
            revision++;
            if (state === "connecting") connectionFailure = error instanceof Error ? error : new Error(String(error));
            callbacks.fail(error);
          },
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
    async invoke(action, input) {
      let dispatched = false;
      try {
        requireConnected();
        if (!HOST_ACTIONS.includes(action)) return { status: "unsupported", message: "未知的宿主操作。" };
        const args = validateArguments(action, input, snapshot), expectedRevision = revision;
        const capabilities = await this.capabilities();
        if (revision !== expectedRevision) return { status: "rejected", message: "画布已更新；请基于当前图重新选择操作。" };
        const capability = capabilities[action];
        if (!capability.available) return { status: "unsupported", message: capability.detail };
        dispatched = true;
        const result = validateResult(await execution().invoke(action, args));
        if (state !== "connected") return { status: "pending", message: "操作提交后连接已关闭；请检查宿主中的实际结果。", ...(result.requestId ? { requestId: result.requestId } : {}) };
        return result;
      } catch (error) { return failureResult(error, dispatched); }
    },
    async dispose() {
      state = "disposed";
      info = unknownHost("画布连接已关闭。", info);
      snapshot = null;
      revision++;
      await closeDriver();
    },
  };
}
