# conversation.submitMessage 接口结果

**状态：源码范围部分达成；真实 Codex Desktop 与 Claude Code 效果未验证。** Codex 的条件是当前 MCP App 连接确实声明 `message.text`；Claude 的条件是当前会话确实加载有效 Mod 并提供 `$.prompt.submit`。回执仅证明宿主受理，不证明随后 Agent 工作完成。父目标 `shared-graph-ui-feasibility` 的其余 14 接口及宿主集成由协调者验收，本报告不代替父验收。

## 责任、来源及挑战

- 当前 brief `build/prime-interface-20261013/brief.txt` 转述用户原话“每一个接口，并发启动prime进行接通，每个prime接一个接口”，并要求不能接通时给出具体原因。本子任务 handoff `build/prime-interface-20261013/handoffs/conversation_submit_message.md` 划定本接口独占目录、一个独立测试文件及结果文件。用户原始回合在本子会话未独立取得；转述限制保留。
- `src/graph_skill_toolkit/ADAPTER.md:30` 定义：发送非空指定文本到当前会话，Codex 需 `message.text`，Claude 通过 Mod 的 `prompt.submit` 接受/拒绝，page context 作为数据随本页提交。`src/graph_skill_toolkit/VALIDATION.md:3-46` 的当前紧凑 Markdown baseline 是父责任：源级已实现，不等于 Desktop 原生验收。该 Markdown 不属于 goal-contract/v1；按本地 `workflows/goal-management.md` 核对文件、SHA-256 和内容，不声称 JSON 检查器通过。交接时 `ADAPTER.md` SHA-256 `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`，`VALIDATION.md` SHA-256 `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`。
- 采用本接口作为必要子结果有来源：它是独立 15 接口之一；删去它将不能证明“每一个接口”均已评估/接通。它与 `composer.writeDraft`、`tools.call` 的结果边界不同。离线测试即使全部通过，也可因实际 host 未加载插件、会话切换、宿主拒绝或改写而无法达成用户要求。完成本接口仍不能独自完成父目标。
- 四项判断（基于上述转述与实测范围，非完成度）：source **0.87**，原始用户句在 brief 中而非本子会话直接可见；interpretation **0.91**，操作定义清楚，context 可见性有条件；effectiveness **0.79**，若两端实际受理，可贡献一个必要接口，但无法证明父目标联合达成；decomposition **0.82**，本目录/测试 + 父级共享 hook 隔离修复 + 真实两端验收才可能联合充分。若取得原始用户完整上下文、实际 host 事件及多 page 观察，这些判断需重审。

## 协议证据、方案与取舍

- Codex SDK `node_modules/@modelcontextprotocol/ext-apps/dist/src/app.d.ts:817-870` 明示 `App.sendMessage` 添加会话消息，返回可选 `isError`，连接断开/超时会抛错。`spec.types.d.ts:96-116` 定义 `ui/message` 请求 `{role:"user",content:[{type:"text",text}]}` 与拒绝回执。现有 Codex driver 仅在宿主声明 `message.text` 时可用；成功返回 `accepted`，`isError` 返回 `error`，null/非对象回执不能确认为成功。超时/失联异常由上层视为 pending，不自动重发。
- Claude 参考声明 `evidence/native-launch-20261012/claude-code-reference.d.ts` 第一行记录 2.1.277、EARLY ACCESS；`:2504-2519` 声明 `$.prompt.submit` 等空闲后进入用户回合；`:7185-7192` 不允许调用者直接指定隐式 context/origin；`:7262-7304` 声明 `{text,...}` 表示进入或 `{drop}` 表示拒绝，返回不等于 turn.complete。现有 `claude.mjs` 原先将 `{}`/undefined 当 accepted；这与声明不符。现在仅 `{text:string}` 为已受理，`{drop:string}` 为拒绝；其他响应抛未知回执，Mod lifecycle 映射 pending 而不重发。hook 改写的文本返回 accepted + `modified:true` 和提醒，不能声称原文一字不变。
- page context 方案：经父级决定采用最小方案，保留 `claude.mjs` 只附加当前 owner 的 context 到本页提交正文，由父级删除共享 `adapters/claude/mod/hooks/register.js` 的全局 `prompt.submit` hook。该 hook 当前读取 `lifecycle/contextPayload(state)` 中**所有** page 的 context，会注入普通用户消息及别页消息；单独删除本模块附加会扩大泄漏。替代方案需要在 hook 内建立并发安全 page 关联，但 Claude `PromptSubmitArgs` 不允许设置 context/origin，证据不足，不能靠推测放行。正文可见附加数据是当前契约限制；若用户要求隐式且不可见，需要由父级向用户裁决。本文读取时共享 hook 仍存在，父级修复尚待核查。
- 候选把空回执当 accepted：**0.18**，旧共享模拟测试返回 `{}`，但和参考类型冲突，可让测试绿而实际提交未知。采用正向回执：**0.88**，声明与聚焦模拟支持，实际版本/宿主插件执行仍未验。保留本页附加并移除全局 hook 的隔离路径：**0.81**，源码作用域可验证，实际多页与普通消息行为尚待父级共享测试、原生实测；父级已批准此技术路径，未改变用户结果。

## 自有成果与核对

- 修改 `src/graph_skill_toolkit/host_interfaces/conversation/submit_message/codex.mjs`：空或异常结构回执不称成功。SHA-256 `d8cc22cbf08a0ca77476263930abc49a947b91f5da40223e0d4de2528b07e97b`。
- 修改 `src/graph_skill_toolkit/host_interfaces/conversation/submit_message/claude.mjs`：保持 owner 范围 context；校验进入、拒绝、改写与未知回执。SHA-256 `af8517d992c1188feae7bf3d27a2087195c326ec1a1b3aef52317840d3f4422c`。
- 新增 `src/graph_skill_toolkit/tests/host/interfaces/conversation_submit_message.test.mjs`：校验参数、官方 Codex `App`/`AppBridge` 的真实 SDK 协议形状、未广告能力/错误边界、Claude 模拟 Mod 的 owner 隔离/回执/改写/拒绝/会话切换与轮询不重发。SHA-256 `4d998b7141e7dd45c09a5656e8b5e185231dcf7af6494ed5855b9b753baeb2e1`。
- 2026-10-14 UTC，项目根运行 `node --test src/graph_skill_toolkit/tests/host/interfaces/conversation_submit_message.test.mjs`：**7/7 通过**。`npm --prefix src/graph_skill_toolkit run typecheck`：退出 0。均为源码、SDK 本地协议、模拟 Mod 证据；未操控桌面、未做共享构建。受影响共享测试 `tests/adapters/claude/operations.test.mjs` 当前 mock `prompt.submit` 返回 `{}`，需父级改为 `{text: input.text}`，否则新正确判定会使旧断言失败；不是本子任务可写文件。

## 尚需父级与真实宿主证据

1. 父级删除共享全局 prompt hook 后，覆盖普通用户消息、两页不同 context、本页提交只含本页数据、拒绝及失联不重发；修正上述共享 mock，再运行合并门禁。直到此事确认，Claude 多页隔离**未达成**，属已识别的共享源码缺陷，不是环境不可用。
2. 在被授权且相互不重叠的真实 Codex/Claude 会话，记录当前 host 身份/能力/版本、实际消息出现/接受/拒绝和下一回合效果，分别核验 API 调用与宿主视觉效果。当前只能称条件性源码连接，不能称真实 Desktop 接通。Claude Mod 加载还有 `VALIDATION.md:44` 所述旧 CLI validator 与参考类型版本不符，仍未测当前安装/加载。
3. 未改动共享文件、全局安装、真实会话、dist、提交或发布；没有子进程遗留。真实业务 Agent 回复仍未测，不能用提交回执代替。
