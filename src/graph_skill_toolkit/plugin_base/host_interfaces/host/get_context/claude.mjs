import { capability as displayModeCapability, readDisplayMode, MODES } from "../../views/request_display_mode/claude.mjs";
const LIMIT = "Claude Mod 不提供界面主题和语言；返回会话项目目录、工作目录和当前模型。";
const MODE_LIMIT = "显示模式按 views.requestDisplayMode 的定义从宿主布局读出：inline 为 Browser 面板显示、侧边栏展开，fullscreen 为面板显示、侧边栏折叠；面板未显示时为空。";
export const capability = () => ({ state: "available", detail: "读取当前 Claude 会话的项目目录、工作目录、当前模型和页面容器的显示模式", limits: [LIMIT, MODE_LIMIT] });
export async function invoke($, { tools, guard }) {
  await guard();
  const [root, cwd, model] = await Promise.all([$.session.root(), $.session.cwd(), $.session.model()]);
  const modes = displayModeCapability(tools).state === "available";
  // The layout is read through the host's own tools; a failed read leaves the mode unknown rather than guessed.
  let display = null;
  if (modes) { try { display = await readDisplayMode($, tools, guard); } catch { display = null; } }
  const data = { workspaceRoots: [root], cwd, model, theme: null, locale: null, displayMode: display?.mode ?? null, availableDisplayModes: modes ? [...MODES] : null };
  return { status: "completed", message: "已读取宿主环境。", data, evidence: { receipt: { root, cwd, model, ...(display ? { layout: display.layout } : {}) }, limits: [LIMIT, MODE_LIMIT] } };
}
