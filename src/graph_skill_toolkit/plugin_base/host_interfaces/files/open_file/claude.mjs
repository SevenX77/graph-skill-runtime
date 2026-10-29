import { SHOW_PANE_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { callNative, nativeData, nativeText, noWindowMessage } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
export const capability = tools => present(has(tools, SHOW_PANE_TOOL), "调用宿主原生文件面板", { scope: "host-file-view", constraints: { lineNavigation: true } });
export async function invoke($, { tools, args, guard }) {
  await guard();
  const result = await callNative($, tools, SHOW_PANE_TOOL, { pane: "file", path: args.path, ...(args.line !== undefined ? { line: args.line } : {}) });
  if (result.status !== "completed") return result;
  const data = nativeData(result.data), noWindow = noWindowMessage(result.data);
  if ((Array.isArray(data?.views) && data.views.length === 0) || noWindow) return {
    status: "rejected", message: noWindow ?? (nativeText(result.data) || "宿主没有改变文件视图（views 为空）。"),
    data, evidence: { receipt: result.data },
  };
  return { ...result, status: "accepted", message: "宿主文件面板请求已返回；实际显示效果需观察。", evidence: { receipt: result.data } };
}
