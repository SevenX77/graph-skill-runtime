import { HOST_ACTIONS as ACTIONS } from "../../../ports/host/contract.mjs";

/** @returns {import('../../../ports/host/index').HostDriver} */
export function claudeAdapter(connection, { requestId = () => globalThis.crypto.randomUUID() } = {}) {
  return {
    async invoke(action, args = {}) {
      if (!ACTIONS.includes(action)) return { status: "unsupported", message: "未知的画布测试操作。" };
      const id = requestId();
      try { return await connection.request("/action", { id, action, args }); }
      catch (error) {
        if (error.requestRejected) return {status:"rejected",message:error.message};
        // A lost HTTP response cannot tell us whether the Mod already acted.
        // Keep the identity so the UI queries this operation instead of resending.
        return {status:"pending",message:"提交结果未确认；请查询这次请求，避免重复执行。",requestId:id};
      }
    },
    async getResult(id) {
      if (typeof id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error("无效的画布请求编号。");
      return connection.request("/result?id=" + encodeURIComponent(id));
    },
  };
}
