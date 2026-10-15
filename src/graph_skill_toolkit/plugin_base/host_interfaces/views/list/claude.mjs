import { CONTEXT_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
import { listViews } from "../../../adapters/claude/mod/operations/views/index.mjs";
export const capability = tools => present(has(tools, CONTEXT_TOOL), "列出本页面用 views.open 打开且仍存在的视图；用户自己的标签不在清单中", { scope: "own-views" });
export function invoke($, context) { return listViews($, context); }
