# tools.list 独立结果（2026-10-14T02:23:04.464101+00:00）

## 结论与责任

**有条件接通源码路由，真实宿主效果未核验。** 本接口为共同的 `shared-graph-ui-feasibility` 目标贡献“返回可调用工具引用”的独立结果；父级还须合并其余 14 个接口、完整构建和真实 Codex/Claude Desktop 验收。没有声明整个目标完成。

原始问题来自协调者完整 `build/prime-interface-20261013/brief.txt` 所转录的用户“每一个接口，并发启动prime进行接通，每个prime接一个接口”；子任务权责来自 `build/prime-interface-20261013/handoffs/tools_list.md`。这两处是转录或派工，非我所见的原始用户发言。该任务授权本目录和唯一测试文件，禁止改公共接口、宿主安装或同时操作桌面。`src/graph_skill_toolkit/ADAPTER.md:33,43-45` 将请求定义为 `scope=session|originating-server` 的工具引用清单；`src/graph_skill_toolkit/VALIDATION.md:3-46` 保留同一目标、源码通过与真实桌面未验的边界。文件 SHA-256 在交接和验收均为：ADAPTER `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`，ARCHITECTURE `f71b5cd6e11d86df193b3fb2c856ff6b433ca19a111abd51500d5b246da97c08`，VALIDATION `93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6`。这是紧凑 Markdown 目标，goal-contract/v1 只读 JSON 检查器不适用；已实读其内容和必要引用，并按 `task-contract/SKILL.md`、`references/profile.md` 独立审查，未声称 JSON 检查通过。

目标挑战：源支持是明确的一接口派工，但原话靠父级转录；删除本结果会留下用户明确要求的工具列举缺口；只测本接口无法让父目标成功；与 `tools.call` 的直接调用、会话边界及 Graph 专属呈现兼容；源码测试可能全部通过但桌面根本没有加载新代码。因此当前判断只用于受限代码和宿主 API 路径，不能升级为桌面已验收。

目标四维审查：source **0.93**（交接、brief 与项目契约相符；复核原始用户回合可提高）；interpretation **0.91**（两个作用域和完成/不可用边界明确；实际 UI 所需引用形式待宿主核对）；effectiveness **0.81**（若两端真实返回对应清单，本接口问题解决；不替代其他 14 接口和原问题的完整画布）；decomposition **0.85**（本模块+独立测试+父级真实验收是必要分工；桌面加载、权限和工具生命周期仍是父级缺口）。以上不是完成率或权限。若发现新宿主 API 或原始用户源有别，需重审而非固化旧实现。

## 方案取舍与实际 API 依据

- Codex：**有条件接通**。当前 `@modelcontextprotocol/ext-apps` 安装类型 `node_modules/@modelcontextprotocol/ext-apps/dist/src/spec.types.d.ts:368-372` 只声明 `serverTools` 的代理能力，不声明通用宿主工具枚举。`app.d.ts:647-673` 声明 `App.callServerTool`。`server/main.mjs:80-107` 确认本画布服务向 App 暴露 `inspect_graph`、`list_canvas_tools` 两项，后者提供本服务范围内清单；`host_interfaces/tools/list/codex.mjs` 拒绝 session 清单、调用 `list_canvas_tools` 并校验条目及来源作用域。候选信心 **0.82**：源码、SDK 类型和隔离测试支持，但 Desktop 是否广告 `serverTools` 并真正代理该调用未验。替代的“直接枚举宿主整个会话”信心 **0.14**：当前 MCP App SDK 类型没有这条接口，不能冒称拥有权限；若新版官方 SDK 提供会话清单，可重新比较。
- Claude：**有条件接通**。`evidence/native-launch-20261012/claude-code-reference.d.ts:2570-2582,10333-10349` 是 Claude Code **2.1.277** 生成的早期访问类型，`$.tool.list()` 返回当前模型可调用的内建及 MCP 工具 `ToolInfo[]`，字段只有 `name`、`description`、`mcp`，没有输入 schema。`adapters/claude/mod/operations/index.mjs:11-24` 在会话保护和实时 `$.tool.list()` 后才运行本模块，`claude.mjs` 投影该列表，缺少旧式元数据时标 unknown，拒绝畸形条目和超过 Mod `lifecycle/index.mjs:39-43` 六万字节回执限制的结果，避免丢弃数据却标已完成。候选信心 **0.79**：类型和模拟 Mod 测试支持；已知 `VALIDATION.md:44` 的本地 Claude CLI 2.1.273 严格校验器拒绝 `session.end`，并不证明当前 Mod 能加载，实际新版本宿主需再验。替代的静态 MCP 服务清单只能覆盖单服务，无法满足 Claude session 清单；不采用。

两端都只列工具，不提交聊天消息、不执行工具、不证明 business Graph Skill 已运行。`complete` 只针对该作用域的当前回复，不能解释为整个宿主所有工具。Codex 若服务器未声明完整则 `complete=false`；错误/伪造条目不返回已完成。Claude 超回执上限明确报 error，不盲目重试。本任务未改父级当前“Claude 工具清单可用”的适用范围。

## 产物和验收边界

仅改 `src/graph_skill_toolkit/host_interfaces/tools/list/codex.mjs`、`.../claude.mjs`；新建 `src/graph_skill_toolkit/tests/host/interfaces/tools_list.test.mjs`。`index.mjs` 未改。`node --test tests/host/interfaces/tools_list.test.mjs` 在 `src/graph_skill_toolkit` 下 **7/7 通过**；覆盖真实 SDK 形状、来源及 session 范围、能力声明、畸形/错误/部分回执、缺失元数据和超过桥接限制的否定情形。先写回归时 4 例中 3 例失败（虚假元数据、伪造条目、畸形列表）；修复后 7/7。`npm run typecheck` **退出码 0**。

另运行 `node --test tests/host/interfaces/tools_list.test.mjs tests/adapters/codex/driver.test.mjs tests/adapters/claude/operations.test.mjs`：**16 例中 14 通过、2 失败**。两个失败均落在只读公共 `operations.test.mjs`：`conversation.submitMessage` 在 `host_interfaces/conversation/submit_message/claude.mjs:12` 拒绝其假回执，以及 `tools.call` 实际使用原生 `$.tool.call` 平铺参数而该测试预期 `$.mcp.call`。它们不是 tools.list 的失败，且当前并行其他工作会影响共同文件；我未改公共测试或 `tools.call`。父级应核对两处当前实际来源、测试样本/预期和其他负责代理的结论，不应因本报告直接删弱断言。没有运行全套构建或更改 `dist`。

**C16 判断：源码子结果部分达到，当前真实双宿主效果 unverified。** 实际 Codex Desktop 的 App SDK 连接/`serverTools` 广告/两条引用，以及实际 Claude 当前会话 Mod 是否加载、其 `$.tool.list()` 返回与页面回执，均待父级串行获取。最小下一观察：在确认为本次构建字节、当前 session ID 和相应宿主身份的单一连接中，分别发 `tools.list` 两种作用域，留存调用受理、范围、返回引用与错误状态；不同时占用桌面，不把模拟 peer 当原生证据。Native 之后父级按所有 15 结果和原问题验收。无独占进程、桌面控制、全局配置或安装需要清理。
