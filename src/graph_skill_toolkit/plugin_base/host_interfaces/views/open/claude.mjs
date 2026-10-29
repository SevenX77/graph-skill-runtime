import { PREVIEW_TOOL, CONTEXT_TOOL, SELECT_TOOL, NAVIGATE_TOOL, SHOW_PANE_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
import { openView, HIDDEN_PANE_LIMIT, NO_SHOW_PANE_LIMIT } from "../../../adapters/claude/mod/operations/views/index.mjs";
export const capability = tools => present([PREVIEW_TOOL, CONTEXT_TOOL, SELECT_TOOL, NAVIGATE_TOOL].every(name => has(tools, name)),
  "在 Claude Browser 面板为本页面打开或复用一个网页标签，返回本页面拥有的 viewId", { scope: "own-views", constraints: { kinds: ["web"] },
    limits: [has(tools, SHOW_PANE_TOOL) ? HIDDEN_PANE_LIMIT : NO_SHOW_PANE_LIMIT, "文件视图不返回句柄：文件请用 files.openFile。"] });
export function invoke($, context) { return openView($, context); }
