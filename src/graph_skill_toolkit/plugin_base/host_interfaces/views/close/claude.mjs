import { CONTEXT_TOOL, CLOSE_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
import { closeView } from "../../../adapters/claude/mod/operations/views/index.mjs";
export const capability = tools => present(has(tools, CONTEXT_TOOL) && has(tools, CLOSE_TOOL), "关闭本页面用 views.open 打开的一个视图；用户自己的标签不能关闭", { scope: "own-views" });
export function invoke($, context) { return closeView($, context); }
