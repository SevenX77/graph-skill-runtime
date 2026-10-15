import { FILE_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { callNative } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
export const capability = tools => present(has(tools, FILE_TOOL), "调用宿主原生文件面板", { scope: "host-file-view", constraints: { lineNavigation: true } });
export async function invoke($, { tools, args, guard }) {
  await guard();
  const result = await callNative($, tools, FILE_TOOL, { pane: "file", path: args.path, ...(args.line !== undefined ? { line: args.line } : {}) });
  return result.status === "completed" ? { ...result, status: "accepted", message: "宿主文件面板请求已返回；实际显示效果需观察。" } : result;
}
