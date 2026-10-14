# context.set 接通核查（子任务结果）

**状态：有条件的源码接通；两个当前桌面客户端的实际模型上下文效果未验证。** 本结果只涵盖 `context.set`。父目标 `shared-graph-ui-feasibility` 的 15 接口整合及宿主验收仍由协调者负责。检查时间：2026-10-14 02:16 UTC。

## 权限、问题与判断

原始问题见 `build/prime-interface-20261013/brief.txt`：用户要求 15 个接口逐个并发接通，无法接通须说明原因；本交接 `handoffs/context_set.md` 限定我只写此接口目录、独立测试及本报告。`src/graph_skill_toolkit/ADAPTER.md:31` 将本接口定义为以 `key` 和明确 JSON `content` 设置页面连接拥有的上下文值，不提交消息。成功应由对应宿主的**后续**模型上下文边界观察确认，不由按钮回执确认。用户原话由任务负责人转录，本子会话无法独立核对原始用户轮次；范围与权限因此依据交接和仓库当前契约。

- 源支持 **0.91**：交接、完整简报及 `ADAPTER.md:31` 对接口和权限一致；原始用户轮次未直接可见。若原始记录不同则需修订。
- 解释 **0.87**：页面范围、无消息发送及延迟效果已明确；Claude 的多页面聚合范围及宿主重载后的生存期仍要实测。若用户要求持久化跨会话，则现有解释不足。
- 有效性 **0.82**：若值真实到达两个宿主后续模型输入，将解决本接口问题；源码结果不能替代真实客户端效果。后续模型输入观察可提高此判断。
- 分解 **0.80**：本接口的两个原生映射、参数边界、回执和宿主结果需共同成立；15 个接口及共同画布由父目标整合，本子任务不评价其余接口。若删除本接口结果，则“每一个接口”的原请求没有完整回应。

选择：保留现有源码映射，只增加专属负面边界和协议形状测试；候选可信度 **0.85**（SDK 类型、Mod 类型与现有源码一致；实际客户端尚未测）。另一条路径是直接操作桌面来证实模型所见，证据更强，但交接明确要求避免并发控制真实桌面，故由父协调者排队安排。不能将本地模拟 peer 测试升级为桌面接受结论。没有足够证据支持修改现有调用或冒称无条件可用；一旦真实能力不声明或后续内容丢失，应按实际声明降级并追查，不能自动重发。

## 宿主逐项结果及证据

| 宿主 | 当前源路由和条件 | 已核验 API 与观测 | 缺口 |
| --- | --- | --- | --- |
| Codex | **有条件可用**：只有当前 MCP App 主机声明 `updateModelContext.structuredContent` 时才声明 `available`。`context/set/codex.mjs` 使用 `adapters/codex/driver/shared.mjs` 发布 `{structuredContent:{toolkitContext:{...页面键值}}}` 全量快照；主机返回非错误才提交本地状态，失败不发送消息。 | 安装的 `@modelcontextprotocol/ext-apps/dist/src/spec.types.d.ts:295-311,330-344,387-390` 声明覆盖前次 view 上下文、后续用户回合和结构化内容能力；`dist/src/app.d.ts:892-905,944` 定义确认/拒绝与超时。新测试观察缺失能力拒绝、不发 `sendMessage`、结构化形状、并发序列及宿主错误后不提交状态。 | 未读到本次真实 Desktop 的能力声明，也未验证更新后下次模型输入包含数据；主机不声明时应 `unavailable`。超时或断线后效果未知，不能盲目重发。 |
| Claude Code | **有条件的本地 Mod 路由**：`context/set/claude.mjs` 将 JSON 值保存在当前 bridge owner 的 `state.contexts`；没有调用提交/草稿 API。`mod/hooks/register.js:24-28` 在以后 `prompt.submit` 钩子把 `contextPayload` 附为上下文；模块自己的 `conversation/submit_message/claude.mjs` 提交时还将该值放入消息文本。 | 仓库保留的 Claude 官方类型快照 `evidence/native-launch-20261012/claude-code-reference.d.ts:2503-2544,7220-7234,7262-7269` 定义 `$.prompt.submit`、为以后消息附加 `context` 的钩子及回执不代表 turn 完成；当前测试观察仅存储、页面间隔离、无提交/填草稿和旧会话拒绝。 | 不是立即写入宿主模型上下文的独立原生 API；只有活的已加载 Mod 和以后 prompt 才可能送入。当前版本的 `claude plugin validate --strict` 曾拒绝 `session.end`（`VALIDATION.md:44`），所以不能从源码推断当前 Mod 已加载。需在目标客户端验证钩子和模型实际消费。 |

源码中的 `context/set/claude.mjs` 以**首次设置的请求 ID**填充内部 `scope`，而 `mod/lifecycle/index.mjs:99-102` 把它作为模型上下文的 `scope` 字段。实际页面隔离由 bridge URL/token 的 Map 键承担；该 `scope` 标签并非稳定的页面 ID，容易误导。修复涉及共同 `contextPayload`、`context.remove` 和参数契约，不在此代理可写范围；请父协调者决定是否在共同文件统一为稳定的不敏感连接标签或删去此字段，勿把 token 发给模型。这不推翻当前隔离测试，但限制上下文来源描述。

## 产物和验证

- 新增 `src/graph_skill_toolkit/tests/host/interfaces/context_set.test.mjs`（SHA-256 `bd1a83dbe3817088f4e235c88fbfbbf119c2d8b5c2563f3da9f11482e3e76a27`）；既有接口源码无修改。
- 从 `src/graph_skill_toolkit` 执行 `node --test tests/host/interfaces/context_set.test.mjs`：**4/4 通过、退出码 0**。测试对象是模拟 App/Mod API 和本地源码，并非真实桌面环境；全套构建、类型检查、完整测试和跨接口集成由父协调者执行。
- 核验读取的 `ADAPTER.md` SHA-256 `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`，`ARCHITECTURE.md` SHA-256 `f71b5cd6e11d86df193b3fb2c856ff6b433ca19a111abd51500d5b246da97c08`，`VALIDATION.md` SHA-256 `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`。父记录为 compact Markdown，不适用 `goal-contract/v1` JSON checker；已阅读选定记录和必要引用并做语义核查，未声称检查器执行。

## 最小后续证据及接受限制

父协调者应串行使用真实桌面：先确认当前页面及连接身份和 Codex `structuredContent` 能力或 Claude Mod 加载；再设置一个独特 JSON 值且不提交消息；随后以普通的下一条用户消息触发模型回合，确认模型实际收到值，并测试覆盖旧值和会话结束后的隔离。记录精确宿主版本、源码/构建身份和观察结果。Claude 验证分别区分普通提示钩子和页面 `conversation.submitMessage` 的文本附加路径。以上未验证之前，**本接口未达到原用户要求的真实双宿主接通验收**，但当前本代理范围内的源码映射与聚焦边界验证已完成。没有运行桌面控制、安装、构建、提交或发布；没有待清理的进程。
