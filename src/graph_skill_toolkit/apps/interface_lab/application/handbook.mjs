// @ts-check
/** The guide mode's quick start: how a plugin uses Hostpane, in four steps,
 * plus the result statuses and evidence slots every call returns. Field
 * tables come from Hostpane's own definitions (INTERFACES, LOCAL_DEFINITIONS);
 * per-host behaviour comes from GUIDES. Links point at Hostpane's README,
 * which owns the full reference. */

export const README = "https://github.com/SevenX77/hostpane/blob/main/README.md";

/** README anchor of an operation's reference section: GitHub drops the dots. */
export const operationAnchor = (/** @type {string} */ id) => id.toLowerCase().replace(/[^a-z0-9]/g, "");

export const QUICKSTART = Object.freeze({
  summary: "Hostpane 让插件把网页显示在 Claude Code 桌面版的 Browser 面板或 Codex 的 MCP App 视图里，网页再直接请宿主做事：写草稿、发消息、调工具、开文件，或让插件进程读写本地文件。",
  parts: [
    { name: "插件服务", entry: "hostpane/server", text: "一个 Node 进程。宿主把它当 MCP 服务启动，它提供页面和工具。" },
    { name: "页面", entry: "hostpane/page", text: "一个自包含的 HTML。通过一个 adapter 对象调用 17 个宿主接口和 5 个本地能力。" },
    { name: "Claude Mod", entry: "hostpane/claude-mod", text: "Claude Code 的钩子模块。负责在 Browser 面板显示页面，并代页面执行宿主操作。Codex 不需要它。" },
  ],
  steps: [
    { title: "启动插件服务", anchor: "the-plugin-server-serveplugin-and-app-factories",
      code: 'import { servePlugin } from "hostpane/server";\n\nawait servePlugin({\n  serverInfo: { name: "my-plugin", version: "1.0.0" },\n  apps: [myPageApp],\n});' },
    { title: "在 Claude Mod 里注册页面", anchor: "registering-the-page-with-the-claude-mod",
      code: 'import { registerPluginBase } from "hostpane/claude-mod";\n\nexport function register(on) {\n  registerPluginBase(on, { pluginName: "my-plugin-mod", pages: [myPage] });\n}' },
    { title: "页面连接宿主", anchor: "the-page-adapter-connection-and-calls",
      code: 'import { createHostAdapter } from "hostpane/page";\n\nconst adapter = createHostAdapter({ appInfo: { name: "My page", version: "1.0.0" } });\nawait adapter.connect({ receive: render, fail: showError });' },
    { title: "调用接口，读结果", anchor: "results-and-evidence",
      code: 'const result = await adapter.composer.writeDraft({ text: "Hello", mode: "append" });\n// 同 adapter.invoke("composer.writeDraft", { text: "Hello", mode: "append" })\nif (result.status === "completed") { /* 效果已确立 */ }' },
  ],
  statuses: [
    { id: "completed", tone: "completed", text: "效果已确立，例如数据已读到、上下文已存下。" },
    { id: "accepted", tone: "accepted", text: "宿主已受理，效果要另外观察。" },
    { id: "pending", tone: "pending", text: "已发出但结果未知。Claude 会按 requestId 自动跟进。" },
    { id: "unsupported", tone: "unsupported", text: "当前宿主做不到；data.capabilityState 给出原因。" },
    { id: "rejected", tone: "rejected", text: "宿主、范围规则或目标拒绝了请求。" },
    { id: "error", tone: "error", text: "参数无效或执行失败。" },
  ],
  evidence: [
    { id: "sent", text: "实际发出的参数。" },
    { id: "receipt", text: "宿主或系统的原始回执。" },
    { id: "observed", text: "读回的实际效果。" },
    { id: "limits", text: "这次调用适用的宿主限制。" },
  ],
  envelope: "{ status, message, data?, requestId?, evidence: { sent, receipt, observed, limits } }",
});
