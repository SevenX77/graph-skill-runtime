import { CONTEXT_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
import { executeView } from "../../../adapters/claude/mod/operations/views/index.mjs";
export const capability = tools => present(has(tools, CONTEXT_TOOL), "查询当前宿主浏览器标签，包括隐藏面板中的标签；不含独立文件面板", { scope: "browser-tabs" });

export async function invoke($, { state, owner, request, tools, guard }) {
  const result = await executeView($, state, owner, request, tools, guard);
  if (result.status !== "completed") return result;
  // A malformed native inventory must not become a successful list with
  // missing or duplicated connection-scoped handles.
  const views = result.data?.views;
  const ids = new Set();
  if (!Array.isArray(views) || views.some(view => {
    if (typeof view?.viewId !== "string" || !view.viewId || ids.has(view.viewId)) return true;
    ids.add(view.viewId);
    return false;
  })) return { status: "error", message: "宿主标签清单包含无效或重复标识；无法确认查询结果。" };
  return result;
}
