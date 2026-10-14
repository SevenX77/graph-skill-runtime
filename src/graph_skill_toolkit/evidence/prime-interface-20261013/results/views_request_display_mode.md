# views.requestDisplayMode：接口接通结果

## 结果和范围

**有条件实现（Codex）；未知（Claude）；真实桌面效果未验。** 本接口只请求当前画布容器的 `inline`、`fullscreen` 或 `pip` 显示模式，不打开/聚焦标签页。父目标 `shared-graph-ui-feasibility` 还需其他接口、真实宿主效果和整体验收；本子结果不能代替父目标验收。

有效来源：协调者给出的 `build/prime-interface-20261013/brief.txt` 引述用户要求“每一个接口，并发启动prime进行接通，每个prime接一个接口”，并要求无法接通给出原因；`src/graph_skill_toolkit/ADAPTER.md` 的接口表定义当前容器显示模式及两端边界；`src/graph_skill_toolkit/VALIDATION.md` 的 2026-10-13 当前基线把模拟 Codex 能力与真实 Desktop 效果分开。原用户 turn 由任务所有者转述，未在本子会话独立见到。交接 `build/prime-interface-20261013/handoffs/views_request_display_mode.md` 规定只写本接口目录、独立测试和本报告，不触碰全局构建、桌面、安装或发布。本报告在 2026-10-14 02:15 UTC 核验 `ADAPTER.md`、`ARCHITECTURE.md`、`VALIDATION.md` 的 SHA-256 分别为 `99b20b5aebf9b5d6db762a52546b0fed5cc9f60ecb0d04e6a32c303e76c6ad3b`、`f71b5cd6e11d86df193b3fb2c856ff6b433ca19a111abd51500d5b246da97c08`、`93ed06deb70c77ec1bc0b49492310e1a262f20f40bb48d647948765f589420e6a`. 父记录为紧凑 Markdown，所提供只读 JSON goal checker 不适用；我直接读取了交接、来源、相关源码与本地 SDK 声明，并作语义核对。

目标审查：来源支持 **0.87**（用户引语为转述，当前 ADAPTER 定义精确）；解释 **0.92**（请求范围与真实可见效果分开，仍缺实际宿主观测）；若两个宿主的模式请求得到真实效果，对原接口问题的有效性 **0.88**（仅覆盖此接口，不替代整幅 Graph 显示）；本子目标的分解充分性 **0.89**（Codex 返回模式与实际可见效果是两个必要观察，Claude 等价接口另须证据）。这些是依据判断，不是完成率或授权。删去本接口的诚实鉴定则 15 接口逐一接通/说明原因的要求缺一项；模拟测试即使全部绿灯仍可能在真实 Desktop 上不显示。当前范围与其他接口共存，不把这次源代码选择变成永久产品要求。

## 已核验宿主协议与实现

- **Codex 有条件。** `node_modules/@modelcontextprotocol/ext-apps` 当前本地版本 `2.0.3` 的 `dist/src/spec.types.d.ts:598-615` 定义 `ui/request-display-mode` 参数及返回的实际 `mode`，并明确返回值可能不同于请求；`dist/src/app-bridge.d.ts:553-571` 说明宿主应检查 `availableDisplayModes`，默认测试桥可原样返回当前模式。`src/graph_skill_toolkit/adapters/codex/connection/index.mjs` 使用官方 App 和 PostMessageTransport；`host_interfaces/views/request_display_mode/codex.mjs:2-12` 只在当前 host context 明示模式时调用 `app.requestDisplayMode({ mode })`。没有声明时为 `unknown`；明示空数组为 `unavailable`；请求未声明的模式为 `unsupported` 且不调用宿主。SDK 回执匹配所请求模式才返回 `completed`；不同的实际模式返回 `rejected` 和实际 `data.mode`，不声称焦点或肉眼可见结果。`rejected` 这里只断言该次模式没有按请求设定，不推断宿主产品永久不支持。
- **Claude 未知。** `host_interfaces/views/request_display_mode/claude.mjs:1-2` 保留 `unknown`。`adapters/claude/mod/lifecycle/index.mjs` 通过 `$.tool.list()` 获取当前工具清单；`adapters/claude/mod/operations/registry.mjs` 映射该接口至上述未知实现。当前 Mod 的预览和浏览标签页工具没有已确认、语义相同的画布容器三模式 API；预览启动、浏览标签选择、页面 CSS 放大都不是替代方案。未检查每个可能的真实宿主私有接口，不能声称 Claude 不具备此能力。

方案评估：采纳已声明模式下的官方 SDK 请求，并以实际返回模式判断是否满足请求，把未声明/无等价接口保持未知或不可用，把真实显示留待桌面观察；把握 **0.86**，依据 SDK 声明与六项本地协议测试，缺口为真实 Codex Desktop 声明及可见效果。备选“只把 SDK 请求完成视为成功”会在 SDK 默认返回当前模式时虚报 fullscreen；备选“让 Claude 预览或 Agent 模仿”作用对象不同，违反接口边界。真实宿主提供模式声明与可视结果、或 Claude 暴露同义原生调用，会增强/改变判断。不做无回执自动重试。

## 改动和验收证据

改动仅在：
- `src/graph_skill_toolkit/host_interfaces/views/request_display_mode/codex.mjs`：区分未声明与空声明，并检查返回实际模式；SHA-256 `d0f85678d04a502d9db96f7d9092859e881223b36aa91278bbd2a92eea10a0f5`。
- `src/graph_skill_toolkit/tests/host/interfaces/views_request_display_mode.test.mjs`：新增实际官方 SDK App ↔ AppBridge 内存传输形状和负面边界测试；SHA-256 `1d59284d00f83d24f3af92e8b579e2f1396dc38bb03e8d0febebbd57fca11bcd`。

在 `src/graph_skill_toolkit` 运行 `node --test tests/host/interfaces/views_request_display_mode.test.mjs`：**6/6 通过，exit 0**。测试涵盖声明模式发出及回执、未经声明不发请求、SDK 默认返回未改变模式不冒充成功、空声明、无声明，以及 Claude 工具清单不冒充同义能力。改动前失败用例观测到返回模式不同仍标 `completed`，属于当前实现缺陷；首次测试还因测试夹具在 SDK 建链前异步设宿主 context 触发关闭后 `Not connected`，改为建链后通知，最终无该异步错误。这是调用夹具问题，不是产品宿主故障。未运行共享构建/完整测试；由父协调者串行整合。

**仍待验：** 真实 Codex Desktop 对此画布是否声明所请求模式，调用后返回及可见容器模式是否一致；真实 Claude Mod 是否有同义的当前容器接口。最小下一观察是由协调者排队打开已授权测试页，读取真实连接的 `availableDisplayModes`，只请求其声明的模式并同时记录回执 `mode` 与可见容器变化；Claude 则检查目标版本官方 Mod API 或真实会话工具清单是否提供容器模式操作。在那之前 Codex 的源级有条件路线不等于真实接通，Claude 保持未知。无桌面进程或子任务需我清理。
