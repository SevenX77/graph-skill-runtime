# files.revealDirectory 接口核验（2026-10-14 UTC）

## 结果与边界

**Codex：未知。Claude：未知。** 当前源码没有可确认的宿主内置文件浏览器“定位任意目录”原生调用。两个 adapter 都拒绝分发该请求；本次没有把打开文件、浏览器 URL、操作系统 Explorer 或 Agent 消息替代目录定位。接口接通这一要求**未验收**，不能把“未知”解释为宿主永久不支持。当前具体成果是可重跑的负面边界测试；没有控制真实桌面或改变安装、配置、共享构建。

## 来源、目标与判断

父代理交接 `build/prime-interface-20261013/handoffs/files_reveal_directory.md` 和任务简报 `build/prime-interface-20261013/brief.txt` 转述原要求“每一个接口，并发启动prime进行接通，每个prime接一个接口”，并明确不能接通须给出原因。原用户消息在本子会话不可独立查看，因此该授权是任务所有者转述，不冒称直接对话事实。`src/graph_skill_toolkit/evidence/native-launch-20261012/interface-scope-correction.md:12` 保留更早的用户更正：必须定位于**宿主自己的文件浏览器**，非系统文件管理器。现行 `src/graph_skill_toolkit/ADAPTER.md:27` 定义请求为绝对 `path`，Codex 和 Claude 在未证实目录接口时均为 unknown；`src/graph_skill_toolkit/VALIDATION.md:26` 明确真实接口还待观察。父稳定目标为该文件所述的 `shared-graph-ui-feasibility`；此子结果仅为其中 15 个接口之一，接受权仍属父代理。

本子目标：在当前工作树、各宿主实际提供接口的条件下，给 `files.revealDirectory` 的 `path` 请求建立诚实的能力/请求/效果/结果边界；若缺少已证实原生路径，则保留 unknown 并提供最小后续证据要求。父目标中的图页面、其他 14 个接口、真实桌面和发布均不归本子任务。删除本接口的核验会留下用户明确指定的接口未审；而仅让离线测试通过也可能没有任何宿主目录定位效果。因此源码负面测试只支撑安全边界，不支撑完成接通。该子范围与两宿主及共享 Graph 页面一致，当前单次任务的临时并发安排不是永久产品约束。

判定依据及待推翻信息（值表示证据支持强弱，不是成功概率或授权）：

| 维度 | 判断 | 依据与缺口；改变判断的观察 |
| --- | --- | --- |
| 来源 | 0.93 | 简报、交接、接口合同和更正记录一致；原用户回合只有转述。若用户实际原话不同，须回父代理修正。 |
| 解释 | 0.96 | “宿主自己的文件浏览器定位目录”排除文件打开、网页预览、Explorer、Agent；具体目录 API 尚未知。若用户定义更窄/宽，需用户裁定。 |
| 有效性 | 0.86 | 若两端均能真实定位并验证视效，解决该接口问题；若仅返回请求受理或一方未知，不解决接通。原生可见效果和真实安装身份仍缺。 |
| 分解充分性 | 0.83 | 双端原生证据、能力声明、调用边界与结果回执都必要；父代理仍要把其他 14 个及集成测试联合验收。原生观测可能推翻纯源码结论。 |

选案复核：① `openai/files/open` 给目录路径或 Claude `show_pane` 的 `pane=file` 给目录路径，信心 **0.12**，拒绝：已读协议/工具描述仅保证文件，试错可能接受请求却不定位目录。② 保留未知、拒绝错误代办、加聚焦回归，信心 **0.94**，采用于本次源码边界：现有模块有明确保护，实测后可据证据增加目录路由。③ 真实宿主仅做受控目录路由发现/可见效果观察，现阶段可行性 **未评估**，因为当前子代理不得并发操控桌面且没有这两个实际连接的当前目录工具声明；由父代理顺序协调。若发现已声明专用方法，可在相同身份和许可下实测，不把旧会话/模拟结果升级为新宿主支持。路径①若只返回空对象或文件面板，验收可能假阳性；路径②离线绿灯亦不得替代路径③。

## 核验事实（截至 2026-10-14T02:17Z）

- `src/graph_skill_toolkit/node_modules/@modelcontextprotocol/ext-apps/dist/src/spec.types.d.ts:361-405` 的 `McpUiHostCapabilities` 定义 `experimental?: Record<string, object>` 等能力，无内建目录导航项；这**允许宿主自定义扩展**，所以不是“不可能支持”的证明。安装版本见同目录 `package.json`：`2.0.3`。当前 `host_interfaces/files/open_file/codex.mjs` 用已广告的 `openai/files` 向 `openai/files/open` 发文件路径；`files/reveal_directory/codex.mjs` 保持 unknown，不调用方法。
- 历史保存的 Claude Mod 类型 `src/graph_skill_toolkit/evidence/native-launch-20261012/claude-code-reference.d.ts:1-5,2570-2593` 标为 Claude Code `2.1.277` **early access**；`$.tool.list()` 返回当前模型工具清单，`$.tool.call()` 通过权限检查调用已列工具，未自行声明目录定位函数。它不是当前桌面版本的实时清单。
- `src/graph_skill_toolkit/evidence/shared-html-pane-tool-schemas.json` 保存的 `mcp__ccd_view__show_pane` 描述和 schema：`pane=file` 的 `path` 指定要**打开的文件**，没有目录定位语义；`pane=diff` 的 path 是变更文件。这是历史工具形状，不是本轮真实桌面回执。`host_interfaces/files/open_file/claude.mjs` 正调用 `pane=file`；`files/reveal_directory/claude.mjs` 保持 unknown。
- `src/graph_skill_toolkit/adapters/codex/driver/index.mjs` 在能力不是 available 时返回 unsupported；Claude 的 `adapters/claude/mod/operations/index.mjs` 检查当次 session 身份、工具清单和能力才分发。当前未知能力下两端没有运行 `invoke`。已检查父交接三份文档的 SHA-256，分别是 `ADAPTER.md` `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`、`ARCHITECTURE.md` `f71b5cd6e11d86df193b3fb2c856ff6b433ca19a111abd51500d5b246da97c08`、`VALIDATION.md` `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`，与交接绑定一致。当前基线为 Markdown，JSON goal checker 不支持；已读真实内容并作语义复核，未宣称 checker 成功。

## 产物与验证

- 新增且仅修改归属测试：`src/graph_skill_toolkit/tests/host/interfaces/files_reveal_directory.test.mjs`，SHA-256 `105259aa511bc8a55c36a374adde3b9fd87fb1d4505af90bd4e0bbe6a7b8604e`。三项分别检查绝对路径/无 Graph 绑定、Codex 广告文件打开不变成目录导航、Claude 列出的 file pane 不变成目录导航；假宿主对误发请求或 Agent 消息直接报错。既有三个接口源码文件未修改，因为当前 unknown 判定正确，增加未证实方法反而误报能力。
- 从 `src/graph_skill_toolkit` 执行 `node --test tests/host/interfaces/files_reveal_directory.test.mjs`：退出码 0，`tests 3; pass 3; fail 0; cancelled 0; skipped 0`。这是替身能力和分发测试，不是桌面视效测试。没有运行共享 build / 整套测试，由父代理整合后负责。
- 已观察缺口属于**真实宿主能力与效果未测试**，不是已证明的宿主缺陷；没有命令超时、取消或结果截断。当前保留 unknown；不能接通的具体原因是当前可读能力声明/工具 schema 均不包含这个操作的已确认等价接口。未新增任何后台任务或需要清理的桌面资源。

## 给父代理的最小后续验证

在不与其他代理同时控制真实桌面的受控会话中，先记录**当前加载的** Codex MCP App 初始化 `hostCapabilities.experimental` 和它对目录定位所声明的确切方法/参数；Claude 记录当次 `$.tool.list()` 中可能定位目录的工具描述/schema。仅当发现专用原生路由，向同一宿主会话发一个已授权目录请求，再观察内置文件浏览器确实定位该目录、回执和隔离行为。若无声明，则继续 unknown，不向 `openai/files/open`/`show_pane(file)` 猜测投递目录。父代理负责审查接口结果如何影响 15 项总体目标，不应由此报告宣布全局接通或发布。
