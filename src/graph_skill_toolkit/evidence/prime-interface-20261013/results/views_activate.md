# views.activate 接口结果（2026-10-14 UTC）

## 结论与边界

- **Claude：有条件接通源码路径，真实 Desktop 效果未验。** 已在当前会话工具清单同时包含 `mcp__Claude_Browser__tabs_context` 和 `mcp__Claude_Browser__tabs_select` 时，针对本连接先通过 `views.list` 观察的浏览器标签发送一次 `tabs_select({tabId})`；再次查询 `tabs_context`，仅在同一标签 `isActive === true` 的有效原生字段返回后认定接口效果完成。激活浏览器标签不等于把隐藏的 Browser 侧栏展示在屏幕上，也不等于激活独立文件面板。
- **Codex：未知，而非断言不支持。** 当前 MCP App SDK 的 `requestDisplayMode` 管理画布容器模式，未提供可由 `viewId` 定位并激活任意宿主视图的已确认接口。保持原有 `unknown`；没有用显示模式、文件预览或 Agent 消息冒充视图激活。
- 对父目标 `shared-graph-ui-feasibility`，本接口只贡献十五个必要接口之一的真实能力判定和 Claude 条件路径；**不构成父目标或自动画布置前的验收**。源码替身测试只确认派发、范围和结果分类。未在本轮操控桌面、安装、更改公共文件或发布。

## 授权、目标和自检

输入是 `build/prime-interface-20261013/handoffs/views_activate.md` 和 `brief.txt`，均已按 UTF-8 完整读取。后者转录用户“每一个接口，并发启动prime进行接通，每个prime接一个接口”和相关边界；当前子任务只拥有 `views.activate` 目录与对应独立测试。原始用户回合未在本子会话直接核验，因此授权依据为任务拥有者的转录，未将历史测试或选择视作新用户命令。`src/graph_skill_toolkit/ADAPTER.md` 的接口表定义了连接范围内 `viewId` 与两个宿主映射。`VALIDATION.md` 当前基线 ID 为 `shared-graph-ui-feasibility`，文件仍是紧凑 Markdown，非 goal-contract/v1 JSON；适用的 JSON 只读 checker 没有此格式的接口，未声称运行过。交接列出的三个文档 SHA-256 在 2026-10-14 02:16 UTC 再次匹配。已读 task-contract SKILL.md 与共享 profile，并独立审查实际源码和宿主证据。

目标解释：在现有连接与权限下，真实 `viewId` 激活必须可归因于该宿主的目标视图，不能以“调用完成”或隐藏面板的活动标签假装屏幕置前；可证实的支持路径实现并测边界，缺失的宿主能力如实报告。完成条件为各宿主能力声明与协议调用符合这一语义，错误/丢失回执分类安全，真实宿主效果单独核验。停止条件是没有已确认等效接口时保留未知，不发会话消息或触碰桌面。当前环境允许只读源码和本目录内写入，以及 Node.js 聚焦测试；结果整合与原生实测属于 parent。

挑战及处理：来源明确限定到单接口；删掉本接口仍可能做其他十四项，但不能满足用户“每一个接口”的范围。单个 `tabs_select` 只能满足 Browser 标签激活，不解决自动展开隐藏侧栏；因此效果和父目标不能合并。Codex/Claude 两种接口差异保留为不同状态。离线测试可能通过而真实 Desktop 缺权限、未加载 Mod 或无法显示；故本报告不将离线通过升级为原生验收。工作未把本次仅源级的限制变成永久产品要求。

对该子目标的证据式评估（数值不是成功概率或权限）：**来源 0.88**：brief 的用户转录、ADAPTER.md 语义和显式 owner 支持；直接原始用户回合若与转录冲突则推翻。**解释 0.88**：参数与浏览器范围明确，隐藏侧栏反例限制了“激活”解释；一次当前原生视觉结果可缩小歧义。**有效性 0.72**：若十五接口和父级图展示一起达成，此结果解决其中一项；单项激活不保证整体自动置前，需父级集合验收。**分解 0.83**：Codex、Claude 各自能力和调用结果，加错误分类与原生观察，足以核这项；原生证据未取得，父级其它十四项不由本项覆盖。删除任一宿主分支不再覆盖“两 adapter”。

方案审查：Claude 直接工具选择 + 再查标签的路径，条件为同一绑定会话已列出相应工具且目标 handle 来源本连接；方案把工具许可留给宿主。把观察失败作为未知而不重试，避免重复副作用；局限是工具回执无法证明侧栏可见。候选把失败边界包在本接口模块而不更改公共 dispatcher，信心 **0.80**：本地目标调用与模拟原生形状通过，尚欠真实 Mod 负载。另一方案是 parent 改共享 `views/index.mjs` 的通用选择逻辑（信心 **0.78**：代码更集中，但跨越本次 owner，且影响 `views.list`/`views.close`），本轮未选。Codex 把 `requestDisplayMode` 当 `viewId` 激活的方案信心 **0.12**：SDK 模式参数并非任意视图句柄，无法满足指定目标；保留 unknown 并等待真实产品可用接口比猜测能力稳妥。官方 SDK 或 Desktop 原生端到端观察可提高或推翻这些评估。

## 本轮代码与确切证据

1. 修改 `src/graph_skill_toolkit/host_interfaces/views/activate/claude.mjs`：仅该接口包装既有 `executeView`。发送选择前的读取错误仍为 `not-sent`；一旦尝试 `tabs_select`，之后读取失败由 `not-sent` 更正为 `unknown`，交由 Mod 生命周期报告 pending 而不重发。对返回标签的 `tabId`/`isActive` 做严格原生类型检查，以免 `isActive: "false"` 这类真值被共享 `executeView` 算为完成。宿主拒绝仍保持 rejected。代码 SHA-256 `78773387d0fa4dc86cfaac5cef43ef729c3431fe6364f83112db9ea3f69027c3`。
2. 新增 `src/graph_skill_toolkit/tests/host/interfaces/views_activate.test.mjs`，覆盖工具库存门控、原生文本包裹 JSON、准确 `tabId`、先列出目标、跨连接句柄拒绝、选择后读取失败、错误布尔字段、明确拒绝、仅接受未确认状态和发起前读取失败。测试 SHA-256 `91611f4887f37d27204567c9f706cfabf4edd4323c642dc566c58f066e128bf8`。
3. `node --test tests/host/interfaces/views_activate.test.mjs`，在 `src/graph_skill_toolkit` 目录运行：**8 passed, 0 failed**, exit 0。该检查只覆盖替身工具，不是 Desktop 实测。
4. 补充测试 `node --test tests/adapters/claude/operations.test.mjs tests/host/interfaces/views_activate.test.mjs`：**12 passed, 2 failed**, exit 1；失败为共享 `operations.test.mjs:70` 的 submitMessage 空回执期望，以及 `:83` 的 tools.call 路径期望（预期 `$.mcp.call`，观察到 `$.tool.call` 的平铺参数）。失败栈不含本接口，当前只能归为并行源码/测试状态不一致或其它模块行为，未查明根因；已通知 parent。不能用这次部分通过声称整套门禁通过。没有 caller 超时、截断或取消迹象（命令正常退出且有完整失败信息）。

接口证据坐标：`evidence/shared-html-pane-tool-schemas.json` 中 `tabs_context` 声明 `{browserOpen,tabs:[{tabId,origin,isActive}]}` 且独立说明隐藏面板仍可工作；`evidence/shared-html-tabs-select-schema.json` 给出 `tabs_select` 唯一必需字符串 `tabId` 和 “Front the given Browser pane tab”。`evidence/dual-view-candidate/native-session.sanitized.json` 内原始转录在原会话行 97/100（该文件 382–436 附近）显示对 `seed` 的选择回执与之后活动状态；这只是旧真实会话该次行为，不是当前实现的 Mod 实测。`evidence/shared-html-foreground-session.jsonl` 的历史观测（见 `VALIDATION.md` 对应段落）证明选择标签之后侧栏仍可能隐藏。Codex SDK 当前本地 `node_modules/@modelcontextprotocol/ext-apps/dist/src/app.d.ts:1112–1125` 声明的 `requestDisplayMode` 是画布模式请求；`adapters/codex/driver/index.mjs` 及本接口 `codex.mjs` 没有任意 `viewId` 激活。Claude Mod 类型资料 `evidence/native-launch-20261012/claude-code-reference.d.ts:10005–10020` 支持 `$.tool.call` 的 tool 平铺参数结构；本地原生库存存在与当前会话加载并非同一事实。

## 下一步与验收限制

Parent 审阅两处 owned 文件、合并其他接口后运行统一门禁并处理上述两个独立失败。需要真实 Claude Desktop 验收时，在获准且不与其他 worker 并行操控桌面的会话中启动当前代码的 Mod，先 `views.list` 取得 connection-scoped `viewId`，调用一次 `views.activate`，读取紧接的 `tabs_context` 并看目标 `isActive`；另行记录 Browser 侧栏是否 **displayed**，尤其从 hidden 状态开始。对 Codex，仅从真实 MCP App capability 或官方接口取得可按任意 `viewId` 激活的证据后再把 unknown 改为 available。当前未取得这些输入，本接口源码条件路径可供 parent 集成，原生效果仍未核实。
