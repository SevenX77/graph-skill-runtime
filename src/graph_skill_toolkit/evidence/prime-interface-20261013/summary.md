# 15 个宿主接口：Prime 并行核查与集成报告

本文件是本次执行报告，不替代 `ADAPTER.md` 或 `VALIDATION.md` 的产品契约。截止：2026-10-14T03:04:39.169119+00:00

## 原问题、来源和范围

收到的用户消息要求完整读取 `build/prime-interface-20261013/brief.txt` 并执行其中已经授权的任务。该简报转录前序用户原话：“每一个接口，并发启动prime进行接通，每个prime接一个接口”；还转录了不能接通须说明原因，以及宿主自己的目录浏览器、草稿只填不发送、直接工具调用与消息发送分开、一份 HTML/两个 adapter 的边界。原始前序 Codex 回合未由本 Prime 会话独立读取，转录者及其边界见简报。当前父目标是 `shared-graph-ui-feasibility`，来源 `src/graph_skill_toolkit/VALIDATION.md` 的 2026-10-13 当前基线；其接受边界包含实际宿主效果和共享画布，不可只靠源码测试。读取时 `brief.txt` SHA-256 `e6316a913c7bb761a196cb1d325a2098c7099e48cef0e8a1c62aef77113119d7`，`VALIDATION.md` SHA-256 `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`，`ADAPTER.md` SHA-256 `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`。这些是接收责任时的 Markdown/文本快照，并非 `goal-contract/v1` JSON publication；已实际读取选定目标与接口表，JSON 检查器不适用。2026-10-14 的后续文档修订由任务负责人另行委派全新空白上下文的 `interface_docs_refresh` 作者撰写，任务负责人报告已审查；协调者重新读取该次改动后，`ADAPTER.md` 为 `9169b542cde3c54244bce218373c242c7010468c2928dfae3d43ef8ad36e5c71`，`VALIDATION.md` 为 `5b2cd95d80475191dbe1fd1a7e68250c49dc7b01e61ff3c9b23c0db5e79f3a46`（独立作者已更新至 168/168 的最终源码测试回执与可跟踪证据链接）。修订更新了源码能力表和证据截止，没有改变用户要求的结果边界。文件哈希标识读取的字节，不认证用户身份或真实宿主效果。

基线：对 15 个接口分别查两端真实可得 API，在保留用户边界的前提下尽可能接通；无等价路由时保持未知并说明下一步最小证据。协调者负责共同代码、完整门禁和两宿主的串行原生验收；子代理每人只拥有一个接口源码目录、唯一测试文件和唯一结果报告。全部 15 个子代理已受理、交付并空闲，没有并发控制桌面。所有更改仍在用户原有大量未提交改动的工作树内；没有清理、提交、推送、安装或发布。

目标挑战与判断：简报和当前接口表支持逐项评估（来源把握 0.89；前序原话仅转录）；“接通”必须同时区分受理、宿主效果、业务结果（解释把握 0.90；真实客户端版本和上下文仍缺）；若 15 项实际满足并与共享画布一起核验，才有助于解决原问题（有效性把握 0.85；未知项及原生验收仍缺）；15 个独立接口结果与共同身份/生命周期/构建/原生观测需要联合成立（分解把握 0.78；源码测试不能取代共同宿主效果）。若删去某一接口核查，用户“每个接口”要求缺一项；若只通过模拟与能力标签，仍可能完全不影响桌面。各子目标四维判断、候选及反例见对应独立报告；分数是证据强弱，不是完成度或授权。当前只接受**已完成 15 项源码审查和受限加固**，父目标仍**部分达到**，双端全部原生接通**未验证**。

## 15 项结果（源码条件；均无本轮桌面视效验证）

| 接口 | Codex | Claude | 原因和验收边界 | 独立证据 |
| --- | --- | --- | --- | --- |
| `files.revealDirectory` | 未知 | 未知 | 缺宿主内置文件浏览器目录定位接口；文件打开、系统 Explorer、Agent 代办均不等价。 | [报告](results/files_reveal_directory.md)；[测试](../../tests/host/interfaces/files_reveal_directory.test.mjs) |
| `files.openFile` | 有条件 | 有条件 | Codex 需声明文件扩展；Claude 需列出文件面板工具；视效与行定位未验。 | [报告](results/files_open_file.md)；[测试](../../tests/host/interfaces/files_open_file.test.mjs) |
| `composer.writeDraft` | 有条件 | 有条件 | Codex 仅 append；Claude append/replace；明确回执与未发送仍待桌面核实。 | [报告](results/composer_write_draft.md)；[测试](../../tests/host/interfaces/composer_write_draft.test.mjs) |
| `conversation.submitMessage` | 有条件 | 有条件 | 受理与后续 Agent 结果分开；Claude 空回执保持未知。 | [报告](results/conversation_submit_message.md)；[测试](../../tests/host/interfaces/conversation_submit_message.test.mjs) |
| `context.set` | 有条件 | 有条件 | Codex 结构化上下文；Claude 本页存储，后续本页提交带数据。 | [报告](results/context_set.md)；[测试](../../tests/host/interfaces/context_set.test.mjs) |
| `context.remove` | 有条件 | 有条件 | 移除仅影响未来本页数据；Codex 回执不明后阻断旧快照继续写入。 | [报告](results/context_remove.md)；[测试](../../tests/host/interfaces/context_remove.test.mjs) |
| `tools.list` | 有条件 | 有条件 | Codex 仅原服务工具；Claude 当前会话工具，非输入 schema 清单。 | [报告](results/tools_list.md)；[测试](../../tests/host/interfaces/tools_list.test.mjs) |
| `tools.call` | 有条件 | 有条件 | Codex 原服务直调；Claude 使用有权限检查的 tool.call，不经无提示 mcp.call。 | [报告](results/tools_call.md)；[测试](../../tests/host/interfaces/tools_call.test.mjs) |
| `views.open` | 未知 | 未知 | 无通用可管理 viewId/重用/前后台/所有权完整路由。 | [报告](results/views_open.md)；[测试](../../tests/host/interfaces/views_open.test.mjs) |
| `views.list` | 未知 | 有条件 | Claude 仅 Browser 标签，可包含隐藏栏；非独立文件面板。 | [报告](results/views_list.md)；[测试](../../tests/host/interfaces/views_list.test.mjs) |
| `views.activate` | 未知 | 有条件 | Claude 需先在本连接观察 viewId；选中标签不等于显示隐藏侧栏。 | [报告](results/views_activate.md)；[测试](../../tests/host/interfaces/views_activate.test.mjs) |
| `views.close` | 未知 | 未知 | 无可证明自有创建回执，不得关闭已存在的用户标签。 | [报告](results/views_close.md)；[测试](../../tests/host/interfaces/views_close.test.mjs) |
| `views.requestDisplayMode` | 有条件 | 未知 | Codex 仅当前容器已声明模式，实际回执模式可能不同；非标签聚焦。 | [报告](results/views_request_display_mode.md)；[测试](../../tests/host/interfaces/views_request_display_mode.test.mjs) |
| `skills.list` | 未知 | 有条件 | Claude 当前 Mod 会话须有 `session.usage`；缺失时不可用，未知时不声称可用；仅完整且未截断才返回名称。 | [报告](results/skills_list.md)；[测试](../../tests/host/interfaces/skills_list.test.mjs) |
| `skills.invoke` | 未知 | 有条件 | Claude 需列出 Skill 工具且确认激活回执；业务工作另验。 | [报告](results/skills_invoke.md)；[测试](../../tests/host/interfaces/skills_invoke.test.mjs) |

“有条件”仅指当前源码可在该宿主明确声明/列出必要接口时尝试直接调用，不等于当前 Desktop 已加载、授权、看见效果或业务完成。“未知”指所查 API 尚未确认等价路由，不是产品永久不支持。代表性模拟会话的源码条件性数量：Codex 8 项、未知 7 项；Claude 在当前会话有 `session.usage` 时 11 项有条件、4 项未知；无此 API 时 `skills.list` 为不可用。Claude `skills.list` 的条件路由是新发现；任务负责人委派的独立作者在本轮后续修订中已将其条件分类写入 `ADAPTER.md` 与 `VALIDATION.md` 的源码表，本文只复述已核验源码范围，不能暗改真实宿主验收。

## 协调者的公共修复与取舍

1. **Codex 上下文回执不明。** `adapters/codex/driver/shared.mjs` 先前在宿主可能收到移除请求却丢失回复时保留旧快照；下一次写入可恢复旧键。受控复现见 `results/context_remove.md`。现将本页标记为不确定并拒绝后续 set/remove，直至新页面连接；明确的已知拒绝仍容许继续。候选信心 0.85：SDK 无已确认读回接口；失去回执后继续写有明显旧值风险。备选权威读回需要新的原生 API 证据；直接重试有重复/恢复风险。测试假宿主模拟了回执丢失及重连，不能证明真实客户端行为。
2. **Claude 浏览标签编号。** `adapters/claude/mod/operations/views/index.mjs` 在生成连接内视图编号前验证非空、唯一字符串原生编号，避免畸形清单导致 `TypeError` 后被误标为待定。候选信心 0.91：定向失败先复现，修复后同用例通过；真实宿主畸形输出是否发生未证实。`views.activate` 自己处理选中后观察丢失，不把已发选择请求误报未发。
3. **Claude 页面上下文隔离。** `adapters/claude/mod/hooks/register.js` 删除把全部页面数据附加到每条普通 `prompt.submit` 的全局钩子，删除 `lifecycle/index.mjs` 已无消费者的 `contextPayload`。本页 `conversation.submitMessage` 仍将本页数据作为可见文本中的数据提交。候选信心 0.82：源码可审计且测试本页/跨页与钩子注册；代价是数据对用户可见，不宣称隐式上下文。如果用户要求隐式且不可见，需用户裁决并设计并发安全的页面关联。保留全局钩子会跨页泄漏，不采用。
4. **共同测试模型。** 把旧空 `prompt.submit` 回执模拟改成参考类型的 `{text}`，把旧 `$.mcp.call` 断言换成带权限检查的 `$.tool.call` 平铺参数，Skill 的模拟回执仅在 Skill 调用时返回激活字段。修改了 `tests/adapters/claude/operations.test.mjs` 和 `tests/host/interfaces/{context_set,context_remove,views_list}.test.mjs` 的已过时预期；未删除或弱化负面测试。

5. **Claude Skill 清单能力判定。** 复核发现原模块无条件报告 `available`，即使真实会话缺少 `$.session.usage`，执行时才返回 `unsupported`。现在共同 registry、操作分发和 Mod 心跳均传入当前会话 API：尚无会话事实为 `unknown`；API 明确缺失为 `unavailable`；仅 `usage` 函数存在时 `available`。候选信心 0.88：类型声明与缺失 API 的受控会话回归支持；当前 Desktop 是否加载并提供该 API 仍未知。备选一律 unknown 会丢失已证实的条件路由，继续一律 available 会误导页面。
6. **Codex 内部错误不能充当拒绝。** 原 `knownHostRejection` 误把 JSON-RPC `-32603` Internal error 当作确定未执行，可能在已应用操作后继续写旧快照。现在只有明确 `outcome=rejected` 或 `-32600/-32601/-32602`（请求/方法/参数在处理前被拒）解锁已确认本地状态；`-32603` 及其他不确定异常使本页 context 写入停下，直至新连接。官方 MCP App SDK 的 `updateModelContext` 明确拒绝会抛错、正常确认返回空对象或 `_meta`；此前测试用工具结果风格的 `{isError:true}` 模拟拒绝，不属于这份确认契约。现在此异常回执也阻断后续写入，已知 `-32602` 明确拒绝仍可后续更正。候选信心 0.90：受控回归覆盖已发送后内部错误、异常回执且无再次写入；真实宿主确认码含义和效果仍待桌面观察。备选继续按“所有数字码明确拒绝”会重现旧键风险。

## 当前源码与测试文件身份

15 份子报告内的源码、测试 SHA-256 属于各子代理撰写报告时的历史字节。协调者在共同集成之后依据仓库 UTF-8/LF 规则，将 36 份本任务拥有的源码和测试文件的 CRLF 行尾机械转换为 LF；文件含义未由此有意改变，但 SHA-256 随之变化，不能再用子报告旧值绑定最终工作树。当前候选的 73 项接口源码、专属与公共测试、相关文档及 `.gitignore` 文件的相对路径、长度和 SHA-256 见 [集成文件身份](integration-file-hashes.json)；该清单绑定当前未提交工作树的具体字节，不是已安装客户端身份或发行档案清单。行尾转换后受影响的 JavaScript/构建门禁已重跑，随后会话能力与内部错误的两处修正又需要最后一次 JavaScript 回归；Python 全套上一次完成的绿色回执属于这两处 JavaScript 专有修正前的候选。只在清单路径、哈希及对应门禁均未再变化的前提下适用。

## 验证、仍缺条件与交接

共同定向测试 `tests/adapters/codex/driver.test.mjs`、`tests/adapters/claude/operations.test.mjs`、`tests/host/interfaces/views_list.test.mjs`、`tests/host/interfaces/context_set.test.mjs`：24/24 通过。`npm run typecheck` 和 `npm run build` 通过；完整 `npm test` 首跑 164/165，仅 `context_remove` 旧假回执失败；修正假宿主正向回执后曾为 165/165。行尾归一化后也为 165/165；再加入 `skills.list` 会话 API 和 Codex `-32603` 的两项回归后，完整 JavaScript 为 167/167、相关定向 14/14；最后把非约定 `{isError:true}` 更新回执归类为结果不明并增加回归后，**本次最终 JavaScript 全套 168/168**、相关定向 **19/19** 通过，`npm run typecheck` 与 `npm run build` 再次退出 0。Ruff、strict mypy（149 files）、lint-imports 已通过。manifest validator 已通过。Python pytest 首轮 1805 通过、8 失败、1 跳过：三项 Windows 临时路径超过常见长度限制，五项导入边界报告因运行器 TERM=dumb 固定 80 列换行而解析失败；换用短临时目录的相关测试 16/16 通过，显式 TERM=xterm-256color 的导入边界测试 29/29 通过。首轮公共修复完成后，使用短临时目录并为该命令显式指定 `TERM=xterm-256color`，全套 Python 复跑 **1813 通过、1 跳过**（退出 0），没有产品代码或测试断言修补。此通过发生在后续 JS 行尾统一与两处 JS 专有修正前；行尾统一后再次启动的 Python 全套由协调者因发现新的 JS 能力前提主动取消，不是目标失败，也不能称该次通过。后续 Ruff、mypy、lint-imports、manifest validator 与文档指针已复跑；任务负责人判断后续三处 JS 专有修正不需要重复无关的 Python 全套。`uv build --no-sources` 退出 0，产出 `dist/graph_skill_runtime-0.1.0a1.tar.gz` 与 `dist/graph_skill_runtime-0.1.0a1-py3-none-any.whl`。`uv run pip-audit` 退出 0，未发现已解析第三方依赖的已知漏洞；未发布的本地 `graph-skill-runtime` 被跳过，此结果不是本仓库源码安全审计。文档修订发生在部分门禁执行期间；随后对当前 `ADAPTER.md`/`VALIDATION.md` 的文档指针测试单独复跑 **15/15** 通过，`git diff --check` 退出 0（仅提示既有部分工作文件的 CRLF→LF 转换）。文档指针测试只验证本工作树当前可读位置；现在权威文档引用可跟踪的 `evidence/` 副本，真正跨工作树可读仍取决于以后保存这些未提交文件。上述自动结果只证明当前本地源码/替身协议，不能证明桌面客户端实际加载或显示。

当前环境只提供 REPL/命令和 Prime 子代理接口，未提供可以操作 Codex/Claude Desktop 的 Computer Use 工具；本轮未申请或占用桌面控制，也没有真实两宿主会话的能力声明、权限提示、按钮视效或安装身份。原生验收必须由有桌面能力的 Codex/用户**串行**操作：先绑定精确源码/构建/已加载会话，再各接口核实能力、一次调用、真实效果和独立业务结果；回执丢失不重试；使用 Computer Use 后立即退出并复核清理。详细每项最小证据见表中的结果报告。来源模式、当前已安装 Mod 与本轮源码是否实际加载仍未验证。

交接时的 `ADAPTER.md` 记 Claude `skills.list` 为未知，`VALIDATION.md` 记 10 可用/5 未知；这些旧快照是各子报告引用的历史绑定。随后，任务负责人按 `authoritative-documents.md` 另行委派全新空白上下文作者 `interface_docs_refresh`，其现存修订把源码表调整为 Claude 11 条件/4 未知，并保留 Desktop 未验的结论。协调者复核了相关表行和公共修复语义；任务负责人报告已审查作者结果。本 Prime 自身仍恰好只有 15 名接口子代理。任务负责人随后要求建立可跟踪证据：现有 `src/graph_skill_toolkit/evidence/prime-interface-20261013/` 内含本报告、15 份内容一致且按仓库规则统一 LF 行尾的结果及简报，表中测试链接在证据副本内已改为相对路径；`src/graph_skill_toolkit/.gitignore` 只放行这一证据目录，其他旧 `evidence/` 仍忽略。原 `build/` 记录保持。权威 `VALIDATION.md` 当前已由独立文档作者改为引用 `evidence/prime-interface-20261013/summary.md`；该路径现可被版本管理跟踪，真正跨工作树可读仍取决于将来保存这些未提交文件。

父目标仍须原生客户端与交付证据；本次本地文档现已指向可跟踪的执行证据副本。本轮未获提交、推送、发布或配置全局安装的授权。结果原件属于构建目录的执行材料，可跟踪副本在 `src/graph_skill_toolkit/evidence/prime-interface-20261013/`；子代理会话与本轮命令均由协调者核对结束后再报告完成。Prime 根会话身份：`01a1382a-221e-70a8-ad20-49f1927b1319`。

## 证据位置与内容对应

本报告和 15 份接口报告的原件保留在 `build/prime-interface-20261013/`。可被版本管理跟踪的副本位于 `src/graph_skill_toolkit/evidence/prime-interface-20261013/`，包含 `brief.txt` 和 15 份报告；15 份报告在归一化 LF 行尾后与原件内容一致。证据简报副本仅将原件中的两个机器本地 checkout 路径改为“本仓库工作树／另一份 checkout”，避免把机器路径写入源码；完整原文与 SHA-256 仍在被忽略的 `build/` 原件及本文开头的绑定中。证据副本的汇总仅把表中的 15 个测试相对链接改为适用其新位置的路径。报告内写作时的 `build/...` 路径是历史坐标。正式源码契约仍由 `ADAPTER.md` 和 `VALIDATION.md` 维护。
