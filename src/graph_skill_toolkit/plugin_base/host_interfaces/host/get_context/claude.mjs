const LIMIT = "Claude Mod 不提供界面主题和语言；返回会话项目目录、工作目录和当前模型。";
export const capability = () => ({ state: "available", detail: "读取当前 Claude 会话的项目目录、工作目录和当前模型", limits: [LIMIT] });
export async function invoke($, { guard }) {
  await guard();
  const [root, cwd, model] = await Promise.all([$.session.root(), $.session.cwd(), $.session.model()]);
  const data = { workspaceRoots: [root], cwd, model, theme: null, locale: null, displayMode: null, availableDisplayModes: null };
  return { status: "completed", message: "已读取宿主环境。", data, evidence: { receipt: { root, cwd, model }, limits: [LIMIT] } };
}
