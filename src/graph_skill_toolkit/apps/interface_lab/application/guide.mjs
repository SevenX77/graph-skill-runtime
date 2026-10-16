// @ts-check
/** What the Interface Lab tells a developer about each Plugin Base operation:
 * its purpose, the visible effect to expect on each host, where to look, and
 * argument presets built from the session workspace or the lab sandbox. Text is for the developer
 * reading the page; host facts mirror the host adapters' capability texts. */

/** @typedef {{stateDirectory:string, sandbox:string, records:string, sampleFile:string}} LabPaths */
/** @typedef {{lab: LabPaths | null, host: string, lastViewId: string | null, workspaceRoot?: string | null}} PresetContext */
/** @typedef {{label:string, args:(context:PresetContext)=>Record<string, unknown>}} Preset */
/** @typedef {{id:string, group:string, kind:"host"|"local", purpose:string, expect:{claude:string, codex:string}, check:string, presets:Preset[], note?:string}} Guide */

const sample = (/** @type {PresetContext} */ { lab }) => lab?.sampleFile ?? "C:/example/sample.txt";
const workspace = (/** @type {PresetContext} */ { workspaceRoot }) => workspaceRoot ?? "C:/workspace";
const workspaceReadme = (/** @type {PresetContext} */ context) => {
  const root = workspace(context).replace(/[\\/]+$/, "");
  return root + (root.includes("\\") ? "\\" : "/") + "README.md";
};
export const CONTEXT_PROBE = "请逐字复述你在这一轮收到的、以“Plugin page context”开头的上下文段落；如果没有收到这样的段落，只回答“未收到页面上下文”。不要调用任何工具。";

/** @type {Guide[]} */
export const GUIDES = [
  { id: "host.getInfo", group: "宿主信息", kind: "host",
    purpose: "读取当前连接确认的宿主身份：宿主名称、版本、会话标识和连接方式。",
    expect: { claude: "返回 Claude Code、版本号和会话 ID；身份来自 Claude Mod 的会话接口。", codex: "返回 MCP 客户端声明的名称和版本；连接方式为 mcp-app。" },
    check: "把返回的名称和版本与宿主“关于”界面或设置里的版本号对照。", presets: [{ label: "读取", args: () => ({}) }] },
  { id: "host.getCapabilities", group: "宿主信息", kind: "host",
    purpose: "读取 17 个宿主接口在当前连接上的可用状态、范围和限制说明。",
    expect: { claude: "大多数接口为 available；宿主文件浏览器定位和显示模式为 unknown。", codex: "依宿主声明而定；Skill、视图管理和宿主目录定位为 unknown。" },
    check: "左侧列表的状态点就来自这份结果；不可用接口的原因写在每个接口的限制说明里。", presets: [{ label: "读取", args: () => ({}) }] },
  { id: "host.getContext", group: "宿主信息", kind: "host",
    purpose: "读取宿主环境：Claude 给出项目目录、工作目录和当前模型；Codex 给出主题、语言和显示模式。",
    expect: { claude: "data 含 workspaceRoots（会话项目目录）、cwd、model；不含主题和语言。", codex: "data 含 theme、locale、displayMode、availableDisplayModes；不含工作区目录。" },
    check: "Claude：与会话标题栏的项目目录和模型选择器对照。Codex：切换浅色/深色主题后再读一次，theme 应随之改变。", presets: [{ label: "读取", args: () => ({}) }] },
  { id: "events.subscribe", group: "事件", kind: "host",
    purpose: "订阅宿主推给页面的事件。本页启动时已订阅全部类型，事件都显示在右侧事件记录里。",
    expect: { claude: "可收到 tool.completed、turn.completed、session.ended、context.attached；经 Mod 心跳转发，最多延迟约 1 秒。", codex: "可收到 tool.completed、host.contextChanged、page.teardown；收不到 turn.completed 和 session.ended。" },
    check: "订阅后在对话里发一条消息或让模型调用一个工具，看右侧事件记录是否出现对应事件，并核对 at 时间。",
    presets: [{ label: "全部类型", args: () => ({ types: ["tool.completed", "turn.completed", "session.ended", "page.teardown", "host.contextChanged", "context.attached"] }) },
      { label: "只要轮次结束", args: () => ({ types: ["turn.completed"] }) }] },
  { id: "files.openFile", group: "宿主文件", kind: "host",
    purpose: "请宿主在它自己的文件面板里打开一个文件。",
    expect: { claude: "会话在窗口中显示时，宿主文件面板打开工作区 README.md 并跳到指定行；无窗口时返回 rejected 和宿主原因。", codex: "宿主经文件扩展打开所选工作区文件；不支持跳到指定行。" },
    check: "看宿主界面里的文件面板。Claude 只允许工作区或已授权目录；实验室 sandbox 是插件状态目录，不能用于宿主文件面板预设。工作区未知时请先编辑路径。", presets: [{ label: "工作区 README.md 第 2 行", args: context => ({ path: workspaceReadme(context), line: 2 }) }] },
  { id: "files.revealDirectory", group: "宿主文件", kind: "host",
    purpose: "请宿主在它自己的文件浏览器里定位一个目录。这与“在系统资源管理器中定位”是两个独立功能。",
    expect: { claude: "当前不可用：Claude Mod 没有开放宿主文件浏览器的目录定位接口。", codex: "当前不可用：宿主文件扩展只声明了打开文件。" },
    check: "预期结果是“当前不可用”并说明原因，宿主界面不应有任何变化。要在系统文件管理器里定位，请用本地能力分组的同名功能。",
    presets: [{ label: "工作区根目录", args: context => ({ path: workspace(context) }) }] },
  { id: "composer.writeDraft", group: "对话", kind: "host",
    purpose: "把文字写进宿主的消息输入框，不发送。",
    expect: { claude: "会话在窗口中显示且无对话框时，输入框出现文字；append 追加、replace 替换；不会发送。拒绝时 refusal 说明无输入框或有对话框。", codex: "输入框末尾追加文字；只支持 append，replace 返回不支持；不会发送。" },
    check: "看宿主的消息输入框；对话里不应出现新消息。",
    presets: [{ label: "追加", args: () => ({ text: "（接口测试草稿）", mode: "append" }) }, { label: "替换", args: () => ({ text: "接口测试草稿：替换", mode: "replace" }) }] },
  { id: "conversation.submitMessage", group: "对话", kind: "host",
    purpose: "以用户身份向当前会话提交一条消息，并选择这条消息用的模型和 effort（推理强度）：沿用当前会话、宿主默认，或明确指定。",
    expect: { claude: "会话空闲后消息出现在对话里，模型开始回复；本页面快照以可见 JSON 段落附在消息后。指定的模型和 effort 只作用于这条消息开启的一轮，实际采用值看 turn.completed 事件里的 override.applied；“宿主默认”返回不支持。",
      codex: "消息出现在对话里，使用当前会话的模型和 effort。Codex 的消息接口只有角色和内容字段，没有模型和 effort 字段，所以“指定”和“宿主默认”都会返回不支持，并且不会发送。" },
    check: "看对话里是否出现这条消息和模型回复。Claude 指定模型时，在事件记录里展开 turn.completed，核对 applied.model 与 sessionWouldUse.model 的差别。",
    presets: [{ label: "沿用当前会话", args: () => ({ text: "请仅回复：接口消息测试成功。", model: { source: "current" }, effort: { source: "current" } }) },
      { label: "指定模型与 effort", args: ({ host }) => ({ text: "请仅回复你此刻使用的模型名称。", model: { source: "specified", value: host === "codex" ? "gpt-5" : "claude-haiku-5-5" }, effort: { source: "specified", value: "low" } }) },
      { label: "宿主默认", args: () => ({ text: "请仅回复：默认配置测试。", model: { source: "default" }, effort: { source: "default" } }) }] },
  { id: "context.update", group: "上下文", kind: "host",
    purpose: "用一份快照替换本页面交给模型的上下文，不触发回复。Claude 的其他来源提交使用隐藏段落，本插件提交把段落附在可见消息后。snapshot 为空对象时清除。",
    expect: { claude: "快照先存在 Mod 里；其他来源的下一条提交附上隐藏段落，本页提交则在消息后内联可见的 JSON 段落；context.attached 的 origin 为 plugin-inline 时表示内联路径。",
      codex: "页面调用宿主的 updateModelContext，宿主在下一轮把内容交给模型；Codex 只确认收到，不回传模型实际读到的内容。" },
    check: "调用后看下方“模型将读到的原文”。点“让模型复述上下文”核对本页消息后的可见段落；再从输入框提交，核对隐藏路径。两条路径都应收到 context.attached。",
    presets: [{ label: "设置样例快照", args: () => ({ snapshot: { selection: "node-a", note: "接口测试上下文", at: new Date().toISOString() } }) }, { label: "清空", args: () => ({ snapshot: {} }) }] },
  { id: "tools.list", group: "工具", kind: "host",
    purpose: "列出页面可以直接调用的工具。",
    expect: { claude: "返回当前会话实际开放的全部原生工具和 MCP 工具。", codex: "只返回本插件 MCP 服务开放给页面的工具（如 lab_echo、inspect_graph），不含宿主其他工具。" },
    check: "核对清单里是否有 lab_echo；Claude 上应能看到 mcp__graph-skill-canvas__lab_echo 这样的完整名称。", presets: [{ label: "列出", args: () => ({}) }] },
  { id: "tools.call", group: "工具", kind: "host",
    purpose: "从页面直接调用一个工具，不经过模型。",
    expect: { claude: "按会话工具名调用，经过宿主权限检查，返回原生结果。", codex: "调用本插件 MCP 服务的工具，返回工具结果。" },
    check: "调用本实验室的 lab_echo：结果里的 echo 应与发送的参数完全一致，at 是服务端时间。",
    presets: [{ label: "调用 lab_echo", args: ({ host }) => host === "claude"
      ? { tool: { name: "lab_echo", server: "graph-skill-canvas", scope: "session" }, arguments: { text: "接口测试 ✓" } }
      : { tool: { name: "lab_echo", scope: "originating-server" }, arguments: { text: "接口测试 ✓" } } }] },
  { id: "skills.list", group: "Skill", kind: "host",
    purpose: "读取当前会话可用的 Skill 名称清单。",
    expect: { claude: "宿主确认清单完整时返回全部名称；被上下文预算截断时返回不支持。", codex: "当前不可用：MCP App 没有 Skill 清单接口。" },
    check: "核对清单里是否有 plugin-interface-lab。", presets: [{ label: "读取", args: () => ({}) }] },
  { id: "skills.invoke", group: "Skill", kind: "host",
    purpose: "让宿主直接激活一个 Skill。",
    expect: { claude: "提交 /plugin-interface-lab echo 接口测试；会话空闲后运行斜杠命令，加载记录和回复在对话中可见。", codex: "当前不可用：MCP App 没有原生 Skill 调用接口。" },
    check: "看对话里是否出现斜杠命令、Skill 加载记录和模型确认；订阅下一次 turn.completed 核对轮次完成。",
    presets: [{ label: "激活本实验室 Skill", args: () => ({ skill: "plugin-interface-lab", input: "echo 接口测试" }) }] },
  { id: "views.open", group: "视图", kind: "host",
    purpose: "在宿主里打开一个由本页面拥有的视图（网页标签），返回它的 viewId。",
    expect: { claude: "会话在窗口中显示时，Browser 面板新开一个标签载入网址；同一 reuseKey 再次打开会复用这个标签。面板隐藏时插件无法替你显示它。", codex: "当前不可用：MCP App 没有返回可管理视图句柄的接口。" },
    check: "看 Browser 面板里的新标签；你原有的标签都应保留。记下返回的 viewId，后面的“列出视图”和“关闭视图”会用到。",
    presets: [{ label: "打开 example.com", args: () => ({ resource: { kind: "web", url: "https://example.com/" }, reuseKey: "lab-web", activate: true }) }] },
  { id: "views.list", group: "视图", kind: "host",
    purpose: "列出本页面打开且仍存在的视图。",
    expect: { claude: "会话在窗口中显示时，只列出本页面用 views.open 打开的标签；无窗口时返回宿主拒绝原因。", codex: "当前不可用。" },
    check: "清单里的 viewId 应与“打开视图”返回的一致；手动关掉那个标签后再列，清单应为空。", presets: [{ label: "列出", args: () => ({}) }] },
  { id: "views.close", group: "视图", kind: "host",
    purpose: "关闭本页面打开的一个视图。",
    expect: { claude: "会话在窗口中显示时，关闭对应标签；无窗口、用户标签或伪造的 viewId 会报告拒绝原因。", codex: "当前不可用。" },
    check: "看 Browser 面板里那个标签是否消失，其余标签保持不变。",
    presets: [{ label: "关闭最近打开的视图", args: ({ lastViewId }) => ({ viewId: lastViewId ?? "先运行“打开视图”" }) }] },
  { id: "views.requestDisplayMode", group: "视图", kind: "host",
    purpose: "请求改变当前页面容器的显示模式（内嵌、全屏、画中画）。",
    expect: { claude: "当前不可用：Claude Mod 没有同等语义的接口。", codex: "本页面声明只支持全屏；请求 fullscreen 时宿主返回实际模式。" },
    check: "看页面容器是否变成全屏，返回的 mode 是否与请求一致。", presets: [{ label: "全屏", args: () => ({ mode: "fullscreen" }) }] },
  { id: "local.files.read", group: "本地能力", kind: "local",
    purpose: "由插件自己的 Node 进程读取一个文件，不经过宿主。只能读插件授权的目录。",
    expect: { claude: "返回文件内容、大小、修改时间和 SHA-256 摘要；页面经本机 HTTP 调用插件进程。", codex: "同左；页面经只对页面可见的 MCP 工具 local_call 调用插件进程。" },
    check: "用编辑器打开样例文件，核对内容一致。读取授权目录以外的文件应被拒绝。", presets: [{ label: "读取样例文件", args: context => ({ path: sample(context) }) }] },
  { id: "local.files.write", group: "本地能力", kind: "local",
    purpose: "由插件进程原子替换一个文件：先写同目录临时文件，再改名覆盖。",
    expect: { claude: "observed.matchesSent 为 true：读回内容的摘要与发送内容一致。", codex: "同左。" },
    check: "再运行“读取本地文件”或用编辑器打开，内容应是刚写入的文字。如果此时在监听这个文件，事件记录会出现 modified。",
    presets: [{ label: "写入样例文件", args: context => ({ path: sample(context), content: `Plugin Interface Lab sample file.\n写入时间：${new Date().toISOString()}\n` }) }] },
  { id: "local.files.watch", group: "本地能力", kind: "local",
    purpose: "监听文件的创建、修改和删除；变化以 local.files.changed 事件送到页面。",
    expect: { claude: "返回 watchId 和初始状态；之后的变化约 300 毫秒内出现在事件记录里。", codex: "同左；事件经 MCP 工具 local_events 长轮询送达。" },
    check: "开始监听后，运行“写入本地文件”或用编辑器保存样例文件，看事件记录里的 local.files.changed。结果卡片上可以停止监听。",
    presets: [{ label: "监听样例文件", args: context => ({ paths: [sample(context)] }) }] },
  { id: "local.system.openExternal", group: "本地能力", kind: "local",
    purpose: "用操作系统默认浏览器打开网址，不是宿主的 Browser 面板。",
    expect: { claude: "系统默认浏览器打开 example.com；插件只能确认进程已启动。", codex: "同左。" },
    check: "看系统默认浏览器是否出现这个网址；宿主界面不应变化。", presets: [{ label: "打开 example.com", args: () => ({ url: "https://example.com/" }) }] },
  { id: "local.system.revealInFileManager", group: "本地能力", kind: "local",
    purpose: "在操作系统的文件管理器里定位一个路径：Windows 资源管理器或 macOS 访达选中它，Linux 打开所在目录。",
    expect: { claude: "系统文件管理器窗口出现并选中样例文件；资源管理器的退出码不表示成败。", codex: "同左。" },
    check: "看系统文件管理器窗口是否选中 sample.txt。", presets: [{ label: "定位样例文件", args: context => ({ path: sample(context) }) }] },
];

export const GROUPS = [...new Set(GUIDES.map(guide => guide.group))];
