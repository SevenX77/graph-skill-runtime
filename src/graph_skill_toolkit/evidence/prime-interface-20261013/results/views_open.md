# views.open 独立结果（2026-10-14）

## 状态与验收边界

- **功能接通：Codex 未证实；Claude 未证实。** 两端维持 `unknown`，当前源码不会调起宿主操作。这个状态不等于产品绝对不支持。
- **本轮有界结果：源码核查与拒绝冒充路径的回归测试已达到；真实桌面效果未验。** 用户要求“每一个接口，并发启动prime进行接通，每个prime接一个接口”，来源为 `build/prime-interface-20261013/brief.txt` 对前序用户话语的转录，本子任务只负责其中 `views.open`。其目标是对 `resource`（文件或 HTTP(S) URL）、`reuseKey`、`activate` 请求取得可管理的视图，或报告不能接通的实际原因，不降低为仅打开 URL、文件或特制 Graph 画布。
- 此结果对父目标 `shared-graph-ui-feasibility` 的贡献是给出该接口的诚实能力边界；若删掉该接口评估，15 个接口各自处理的用户要求便缺一项。父目标仍需其他接口、公共集成及加载后的桌面验收，由协调者判断，不能由此子报告验收。现有 `VALIDATION.md:3-46` 是紧凑 Markdown 基线，不是 `goal-contract/v1`；JSON 只读检查器不适用于该文件，本轮独立核对其 SHA-256 `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6` 及 `ADAPTER.md` SHA-256 `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`。源断言来自任务所有者转录，不冒充本会话亲见的用户原话。

## 实际 API 与缺口

| 宿主 | 已核对事实 | 为什么尚不能声称 `views.open` 已接通 |
| --- | --- | --- |
| Codex | 本地 `@modelcontextprotocol/ext-apps` 版本 `2.0.3` 的 `dist/src/app.d.ts:962-990` 明说 `App.openLink` 打开**默认浏览器**，可能被拒绝，仅返回错误标志等结果；`:1124` 的 `requestDisplayMode` 只作用于当前容器；`host_interfaces/files/open_file/codex.mjs` 的文件入口是另一个操作。 | 上述路径没有承诺为任意文件/网页创建可复用、可列举/激活/关闭且有 `viewId` 的宿主内部视图。`openLink` 不是同义替代；当前 SDK 声明和实现没有查到满足整项契约的路径，实际 Codex Desktop 另有私有能力与否未经验证。 |
| Claude | `evidence/shared-html-pane-tool-schemas.json:28-72` 的当时宿主清单声明 `preview_start.url`、`tabs_context`（仅 origin）、`tabs_create`（返回 `tabId`），文件面板由 `show_pane` 负责。历史桌面 `evidence/shared-html-final-natural.json:22-44` 的 HTTP URL `preview_start` 返回 `tabId=seed`，但随后 `tabs_context` 报 Browser pane **hidden**。另一历史桌面 `evidence/dual-view-candidate/native-session.sanitized.json:274-328` 的文件 `preview_start` 返回“opened”文本，后续 `tabs_context` 才看到 `file:///.../SKILL.md` 标签。 | 这些历史调用证明部分开页能力，**不是当前 Mod 的主动调用效果**，且未证明 `reuseKey`、`activate=false`、返回 ID 与新建页的所有权及不改写用户原有标签。`views.close` 只可关本模块确实创建的标签；凭目录清单中已有标签不得标 `owned=true`。网页调用受理、标签身份、侧栏可见、页面加载及可安全管理是不同结果。Graph 专用 `preview_start(name)` 后导航不具备通用请求语义，不能冒充。 |

`ADAPTER.md:45-55` 与 `ports/host/index.ts` 定义共同请求；`VALIDATION.md:18-46` 的 87 个整体测试含模拟宿主，仅证明当时工作树的源码路径。Codex 的可用路径若只链接到默认浏览器，将违反“宿主内部可管理视图”；Claude 若把任何观察到的 tab ID 标为 owned，会有误关用户页面的风险。当前版本宿主是否公开了另一接口，以及当前加载的 Mod 能否使用浏览器工具，均未测；不存在经确认的运行时故障或环境缺失，不能把未测试写成不支持。

## 方案审查与决定

- **候选：直接用 Codex `openLink` / Claude `preview_start` 后报告接通。** 方案把打开动作与 `reuseKey`、不抢焦点、owned `viewId` 混为一谈。判断把握 Codex `0.15`、Claude `0.45`：历史工具结果支持开页但不支持完整语义；测试回传 `tabId` 也无法证明没有复用用户标签。能推翻此判断的是一条能按两个资源类型处理、实现重用键和背景创建并可安全回收的当前宿主原生接口及桌面实测。
- **采用：维持 `unknown`，仅细化能力说明和拒绝替代路径测试。** 源码安全性判断把握 `0.9`：现有 Port 校验和驱动先查能力再调用；缺口是当前桌面私有 API 未知，不以有限源码枚举证明宿主不存在能力。该选择不会使接口功能达成，但避免错误写入、意外切换或误关页。下一步证据到位后可在本接口模块实现有条件映射，不能把暂时未知固化为永久禁令。
- **另一可行候选：Claude `tabs_create(foreground:false)` → 按返回 `tabId` 原位 `navigate` → `tabs_context` 确认；文件路径另测 `preview_start` 前后身份。** 判断把握 `0.55`：清单声明返回 ID，历史导航示例支持按 `tabId` 指向页面；缺少当前宿主中该组合的权限、背景态、文件导航支持、失败遗留空页清理及重复 `reuseKey` 证据。不开并发真实桌面操作；由协调者串行安排自然测试，完成前不写一个看似可用但可能篡改现有标签的映射。

挑战结论：本接口直接来自任务清单第 9 项，作用于跨两端通用操作；不是临时 Graph 展示方案。两端状态可以不同，单端开页不会掩盖另一端缺口。离线测试即使通过也不能说明页面实际显示或被管理；因此将真实效果列为独立验收依赖。没有新的用户范围取舍需要请示，若要放宽为仅 web/只支持前台，须由父协调者确认是否仍满足已定义契约或返回用户裁决。

评估（[0,1] 为当前证据判断，不是完成率）：本子目标的**来源** `0.88`（完整任务简报及 ADAPTER 明确指向，原用户 turn 仅由所有者转录）；**解释** `0.88`（两个资源、重用、激活、可管理 ID 已列出，`reuseKey` 冲突的细节尚未定义）；**效果** `0.82`（真正实现两端可管理视图将解决该接口，但不足以单独解决共享画布父目标）；**分解** `0.83`（本结果核对宿主、守住副作用与测试，同时需父端集成及真实桌面证据）。提升或推翻各项的证据分别是原用户 turn、精确重用规则、真实双宿主页面效果、父协调者完整 15 接口集成验收。

## 改动、验证与后续

- 仅修改 `src/graph_skill_toolkit/host_interfaces/views/open/codex.mjs` 和 `claude.mjs` 的能力说明，澄清相似 API 不是通用受控视图。`index.mjs` 未修改。
- 新增 `src/graph_skill_toolkit/tests/host/interfaces/views_open.test.mjs`：覆盖合法文件/HTTP(S) 输入，拒绝非法协议、嵌入凭据、相对路径和多余字段；模拟 Codex 宣告文件/显示能力仍不调用 `openLink`；模拟 Claude Browser 工具清单仍不调用 `preview_start` 或擅自占有标签。
- 在 `src/graph_skill_toolkit` 运行 `node --test tests/host/interfaces/views_open.test.mjs`：**3 测试通过，0 失败**（最后执行耗时约 207 ms）。该测试不启动真实桌面，不证明原生用户界面效果；全量构建与测试属于父协调者的整合责任。
- 最小新证据：协调者在**一个**授权的、版本和加载来源可核对的 Claude Desktop 会话中，先记录标签及活动/可见状态，再分别测试 Browser 工具直接文件、HTTP(S)、`tabs_create` 后指定标签导航、重复/不同资源和原有标签保留；保存工具输入、返回、后续标签清单与视觉状态，不自动重试无回执调用。Codex 需先查实际桌面已加载的 MCP App 能力/官方 SDK 或宿主文档是否提供返回可管理 ID 的视图创建接口；仅见 `openLink` 不足以接通。协调者随后决定是否改 `ADAPTER.md` 和旧公共测试的 `unknown` 预期；本子任务未改共用文件。
- 本任务没有启动浏览器、Mod、系统窗口、安装或构建；没有待清理的子进程/桌面资源。以上文件仍是脏工作树的一部分，未提交、未发布。
