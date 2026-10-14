# views.close 接口核查结果

核查时间：2026-10-14T02:18:46.113590+00:00。结果：**Codex 未知、Claude 未知；本次未接通关闭功能**。已完善能力说明和禁止误关的聚焦测试。这个结论仅针对当前源码和所查历史证据；真实桌面效果未测。

## 要求与边界

父目标为 `shared-graph-ui-feasibility`，本次独立责任只核查、完善 `views.close`，并向协调者交付证据。来源是 `build/prime-interface-20261013/brief.txt` 的任务所有者转录：“每一个接口，并发启动prime进行接通，每个prime接一个接口”；原始人类对话未在本子会话中独立核验。`src/graph_skill_toolkit/ADAPTER.md:38,43` 将本操作定义为以当前连接的 `viewId` 请求关闭**本模块创建**的视图。`src/graph_skill_toolkit/VALIDATION.md:3,5-46` 的 Markdown 基线负责整体目标；收到时及验收时 SHA-256 均为 `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`。该格式不是 goal-contract/v1；结构化 JSON 检查器不适用，已直接阅读基线、转录 brief、接口与架构。父协调者负责整体集成和验收。本子任务不得编辑共同视图状态、其他接口、宿主全局安装，也不得并行操控桌面。

挑战与处置：① 来源支持这个独立接口核查，但不保证“所有接口均可用”；② 若安全、真实地关闭自有视图，将推进用户要的双宿主反向操作，不能由单项替代整套共享页面；③ 删除本项仍可能完成 Graph 展示，却无法完成所要求的 15 项逐项核查，因此保留；④ `viewId` 归属当前连接且仅自有视图可关闭，不能因宿主提供关闭任意标签的工具而放宽；⑤ 与 Claude 的 `views.list`（列出非自有标签）和 `views.open`（当前无创建回执）同时成立，不能声称列表项均可关闭；⑥ 模拟测试可通过但实际桌面关闭失败，必须将源级保护与原生效果分开。

本责任信心判断：[来源 0.91] 父 brief、ADAPTER 的接口定义及范围清楚，原始用户句子来自任务所有者转录而非本会话直接消息；若原话、当前接口契约发生变化需复核。[解释 0.89] 已覆盖 viewId、所有权、关闭请求与结果边界；原生 API 细节有版本缺口，收到新接口契约将改变。[有效性 0.84] 若在两端确实安全关闭模块拥有的视图，将满足本接口效果，但独立于整体画布展示；观察真实关闭及保留其他标签可提高判断。[分解 0.86] 身份/能力、归属创建回执、安全请求、关闭后宿主清单、真实效果须共同成立；当前创建回执缺失，不能误以局部测试为总体达成。每个数值为有证据的范围判断，不是权限或达成概率。

## 两端证据与状态

- **Codex：未知。** 本地安装 `@modelcontextprotocol/ext-apps` 2.0.3 的 `node_modules/@modelcontextprotocol/ext-apps/dist/src/spec.types.d.ts:361-399` 列出宿主能力，其中 `openLinks` 是外部链接打开能力，没有管理式视图关闭声明。`app.d.ts:975-992,1111-1124` 声明 `openLink` 与容器显示模式请求，二者均不是按自有 viewId 关闭宿主视图的接口。`host_interfaces/views/open/codex.mjs` 亦无创建句柄。SDK 列举不足以证明宿主产品永远没有私有接口；目前不能安全声称可用。
- **Claude：未知。** `evidence/sidebar-reveal-source.json:71` 保留 2026-10-10 安装版 Claude Desktop `2.31226.1.0` 代码摘录：原生 `tabs_close` 接受 `tabId` 并可关闭标签；这是历史版本静态证据，未在当前客户端调用。`evidence/shared-html-pane-tool-schemas.json` 的 `tabs_context` 声明可列 Browser 标签，`tabs_create` 声明返回新 `tabId`。`evidence/native-launch-20261012/claude-code-reference.d.ts:2573-2593` 的 Mod 工具列表/调用接受会话工具并经过权限检查。现有 `adapters/claude/mod/operations/views/index.mjs:10-19` 对每个列出的标签记 `owned:false`，`:27-37` 只允许自有标签调用 `tabs_close`；`views.open/claude.mjs` 尚无通用安全创建路径及连接所有权回执。兄弟 `views_open` 子代理复核后也报告无法满足通用 open 的复用/activate:false 和预存标签归属。直接把 `tabs_context` 可见标签当可关标签会破坏用户页面；不得如此接通。不能从历史工具存在推断目前原生效果或恒久不支持。

两种方案比较：A. 保留 `unknown` 并拒绝关闭（本次采用，候选信心 0.93，静态调用链和聚焦测试支持；代价是本接口尚不可用，当前 Desktop 仍未证实）。B. 启用 Claude `tabs_close` 配合自有创建回执（候选信心 0.43）：须先证明通用 `views.open` 正确返回特定连接的原生 `tabId`、注册归属、复用/activate 语义和跨会话隔离；共同状态 `adapters/claude/mod/operations/views/index.mjs` 需由父协调者集成。只按 origin 或列出标签推断自有的变体不安全。C. 让 Agent 或系统窗口关闭、把容器显示模式当标签关闭不可满足接口，拒绝。新宿主能力和短促、受控的真实桌面创建-关闭观察能提高或推翻 A/B 的判断。

## 改动与验证

- `src/graph_skill_toolkit/host_interfaces/views/close/claude.mjs`：明确即使 `tabs_close` 出现在会话清单，缺少自有创建回执时仍保持 `unknown`。
- `src/graph_skill_toolkit/host_interfaces/views/close/codex.mjs`：明确打开链接/显示模式不能充当关闭句柄。
- `src/graph_skill_toolkit/tests/host/interfaces/views_close.test.mjs`：三项聚焦测试检查入参边界、Claude 已列/伪造标签不会触发 `tabs_close`、Codex 即使声明其他丰富能力也不调用无关宿主操作。
- 在 `src/graph_skill_toolkit` 工作目录执行 `node --test tests/host/interfaces/views_close.test.mjs`：**3/3 通过，退出码 0**。模拟宿主只验证当前能力路由和防误关，不验证真实客户端；父协调者负责合并后的 typecheck、build、完整测试。三个改动文件 SHA-256 依次为 `e78f6eae63ebb0d973da30613deef0a460299bac9764c54f70a31087ef4ae2ed`、`4122aa584651f76bd95db699e29b18c6d7191b6e8d90b7b204647b1df4f4abf0`、`8284efee17cf48e968960ec824c68147a59ec63ef843f832cf39aaad1b2d8fe4`。

接受判断：本子任务的**诚实能力审查和防误关保护已达到**；`views.close` 双宿主实际关闭功能**未达到/当前效果未验证**。无已确认运行时缺陷或命令配置错误。能力差距是**当前连接没有可核验的自有创建回执及 Codex 关闭接口**；对较新宿主版本的相关能力属**未测试**，不称全局不支持。未使用桌面控制，未触碰全局安装、共用文件或发布。父目标仍需其他 14 项与双宿主真实行为的整体核对；单独通过测试不能解除该缺口。

给父协调者的最小下一步：收集当前目标版本两宿主接口清单及一次受控、用户授权的自有视图创建→返回稳定句柄→确认归属→关闭→查询消失且其他标签保留的原生观察。若 Claude 的 `views.open` 实现提出安全回执，父协调者统一修改共享视图状态并做跨连接/会话和丢失回执测试；否则继续显示 `unknown`。Codex 需可管理视图句柄及关闭请求的原生 API 才可重新评估。等待这些外部证据不阻止其他接口工作。
