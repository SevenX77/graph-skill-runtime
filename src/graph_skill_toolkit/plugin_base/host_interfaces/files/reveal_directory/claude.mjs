import { REVEAL_PATH_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { callNative, nativeText } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
// Claude Code 2.1.309: the host's own reveal tool selects a file or folder of the
// session in the system file manager. The host resolves the path inside the
// session's folders and asks the person on a card where its permission mode asks.
// This is the host's route; local.system.revealInFileManager is the plugin
// process's own route and follows the plugin's directory grants instead.
const SCOPE_LIMIT = "路径须在本会话的工作目录或已授权目录内；通过 SSH 运行的远程会话没有这个工具。";
const APPROVAL_LIMIT = "默认权限模式下宿主为每次定位弹出卡片请用户批准；Windows 上自动模式也由用户批准；跳过确认模式直接执行。";
export const capability = tools => present(has(tools, REVEAL_PATH_TOOL), "调用宿主定位工具 " + REVEAL_PATH_TOOL + "：由宿主在系统文件管理器中选中该目录",
  { scope: "session-folders", limits: [SCOPE_LIMIT, APPROVAL_LIMIT] });
export async function invoke($, { tools, args, guard }) {
  await guard();
  const result = await callNative($, tools, REVEAL_PATH_TOOL, { path: args.path });
  const reply = nativeText(result.data);
  if (result.status !== "completed") return { ...result, message: reply || result.message, evidence: { receipt: result.data } };
  return { status: "accepted", message: reply ? "宿主回复：" + reply + " 请在系统文件管理器中观察。" : "宿主定位请求已返回；请在系统文件管理器中观察。",
    data: { reply }, evidence: { receipt: result.data, limits: [SCOPE_LIMIT, APPROVAL_LIMIT] } };
}
