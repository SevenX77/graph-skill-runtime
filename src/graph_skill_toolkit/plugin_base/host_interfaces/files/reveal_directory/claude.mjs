import { unknown } from "../../../adapters/claude/mod/operations/shared.mjs";
// Claude Code 2.1.309: mcp__ccd_view__show_pane with pane "file" accepts only a
// file; a directory path is refused as unresolvable, and the pane needs a path.
export const capability = () => unknown("Claude 的文件面板只打开文件：mcp__ccd_view__show_pane 对目录路径回复“`path` could not be resolved inside this session's working directory or granted folders.”，且不给路径时拒绝；宿主没有定位目录的接口，不会用系统窗口或 Agent 消息代替。");
