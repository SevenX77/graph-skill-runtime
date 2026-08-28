---
module: graph-skill-runtime
doc: v1-alignment
role: alignment
status: drafted
binds_baseline: ./baseline.md
aligns_with: ../mvp1/INDEX.md
updated: 2026-08-28
---

# Graph Skill Runtime v1 目标设计

本文定义把提取后的 engine 建成独立 Python runtime、SDK 与 CLI 的完整 v1 目标。它与 [`baseline.md`](./baseline.md) 双向绑定。本文整体状态保持 `drafted`：Phase 0、Phase 1、Phase 2 portable 文件格式、Phase 3 中 root DAG 串行可定位 Agent wait point 的 durable host-native handoff、Phase 4 direct vendor CLI executor、Phase 5 的 canonical MoirAI integration，以及 Phase 6 的同候选制品跨平台 package/release acceptance 已经按各自边界验收；Phase 3b 的 host-native 扩展尚未实现，首次发布前命名裁决和真实 release/registry publication 也尚未闭合。因此不能把完整 v1 当作当前能力或已发布产品。Gateway 与 Studio plugin 不属于本轮 release 交付；本文只保留其未来外部 Port/Adapter 所有权边界。

## 0. Implementation status（2026-08-28）

| 设计范围 | 当前状态 | 可观察事实或剩余边界 |
| --- | --- | --- |
| Phase 0：仓库提取与现状冻结 | **已实现** | 独立 GitHub repository 已建立；旧实现与 v0.3 格式已完成提取和 characterization；历史证据保留在 [`baseline.md`](./baseline.md) 与 `docs/mvp0/` |
| Section 2：产品命名 | **已实现于源码与仓库** | distribution/import/command 是 `graph-skill-runtime` / `graph_skill_runtime` / `gskill`，当前版本 `0.1.0a1`；release workflow 已实现单次 build、三平台 acceptance 与 OIDC publish gate，但 PyPI project/publisher 尚未配置，也没有实际发布 |
| Section 3 与 Section 8 的 typed facade、配置、SDK/CLI/MCP 边界 | **已实现并由 Phase 4/5 扩展** | 顶层 77-symbol contract、closed/frozen/versioned runtime 与 integration models、五层 resolver、immutable `RunRequest`、单一 `RuntimeApplication` 已落地；顶层 Python function 为 14 个：`create_application` 加八个 runtime use cases，以及五个 integration functions；MCP 仍只有八个 runtime tools；Phase 4 增加 `AgentResource`，Phase 5 增加 18 个 integration exports |
| Current engine bridge | **已实现于当前范围** | `CurrentEngineAdapter` 已用真实 portable `LOGIC` skill 验证显式 embedded compile/run，并把 bounded host-native run/resume/submit 接入同一 core；provider clients 仍只位于 optional `embedded` extra |
| Section 4 至 Section 5：portable 格式与 flat graph registry | **Phase 2 已实现** | Production compile/run/SDK/CLI/MCP 只接受显式 root `SKILL.md` + `graph.yaml` bundle；内部 agent phase 使用 `AGENT.md`；graph registry 为单层 `graphs/<graph_id>/`；legacy v0.3 读取只存在于显式 converter 边界 |
| Section 6 至 Section 7：host-native durable handoff | **Phase 3 当前范围已实现** | 支持 root DAG 内串行可定位的 Agent wait point：图 checkpoint 与 `AgentTask` 先后持久化后返回 `agent_required`；SDK/MCP/CLI submit 校验结果并继续同一 run；跨进程、非法输出纠正、精确重试、checkpoint-to-task 与 graph-commit-to-response 两个 crash window 均有因果测试 |
| Phase 3b：host-native 扩展 | **drafted；未实现** | registry subgraph、graph/phase iterate、不可比较并行 wait point、普通 human/breakpoint typed resume，以及宿主 dispatched/started acknowledgment 与 capability negotiation 尚未完成 |
| Phase 4：direct vendor CLI executors | **已实现于当前受限范围** | Claude、Codex、Copilot、Cursor、Gemini、OpenCode 的 capability-probed adapter、fresh top-level process、资源 materialization、schema validation、attempt lifecycle 与全进程树清理已落地；仅 Codex CLI `0.144.1` / Windows `10.0.26200` x64 有成功实机 smoke，其他组合不能由 fake tests 或动态 probe 推导为支持 |
| Phase 5：MoirAI canonical assets 与 installer | **已验收于定义范围** | asset version `1.0.0` 的 4 roles、8 Agent Skills、`KB-00..14`、六宿主 renderer、显式 detect/plan/install/uninstall 与 ownership-safe apply 已落地；renderer snapshots、built-wheel inventory/install smoke 与 Claude skill/agent/MCP discovery 加 Codex skill/MCP 交叉实证满足本阶段退出判据，但不证明六个宿主产品均 operational |
| Phase 6：跨平台 package/release acceptance | **已验收于定义范围** | 一个 manifest-bound wheel/sdist 候选已在 Ubuntu、Windows、macOS 分别通过 pip-wheel、uv-wheel、pip-sdist 安装验收；CLI/MCP、host-native reopen/submit、SQLite、路径与 MoirAI lifecycle 的可观察行为一致。该范围是发布前候选验收，不是 registry publication，也不扩大 direct-vendor 支持矩阵 |
| Gateway/Studio integration | **不属于本轮 release** | 只保留未来外部 Port/Adapter 的 owner 边界；不以 plugin、product cutover 或真机旅程作为本轮完成项 |

当前公共 API 的精确事实源是 [`../public-api-contract.md`](../public-api-contract.md) 与 `src/graph_skill_runtime/__init__.py`。当前 MoirAI inventory 的精确事实源是 `src/graph_skill_runtime/integrations/assets/moirai/integration.json`；renderer 与 installer 行为分别由 `integrations/renderers.py` 与 `integrations/installer.py` 拥有。当前文件格式的事实源是状态为 `audited-ready` 的 [`../skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md)；[`../skill-spec/00-FORMAT-GROUND-TRUTH.md`](../skill-spec/00-FORMAT-GROUND-TRUTH.md) 已被取代，只保留为 legacy converter 输入契约与历史证据。本设计后文保留完整 v1 目标；实现存在、验收通过、未来边界与未支持声明必须分开，不能互相替代。

当前 Phase 5 候选已完整重跑本地 required gates：全仓 Ruff green；strict mypy 覆盖 149 个 source files green；contract manifest validator green；完整 pytest 为 `1715 passed, 1 skipped in 83.51s`。`uv build` 成功生成 `0.1.0a1` source distribution 与 wheel，wheel smoke green。`pip-audit` 报告 `No known vulnerabilities found`，同时明确跳过尚未发布的本地 `graph-skill-runtime`；这只说明被解析 distributions 的已知漏洞检查结果，不是本仓源码安全审计或 PyPI publication evidence。

同一 commit `8928d13b32c800a2ad303d02e1bd96551f969ab5` 的 [GitHub Actions run 33140732333](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33140732333) 已通过 `quality-gates`、Python 3.11/3.12/3.13 的 `runtime-tests`、`cross-platform-smoke (windows-latest)` 与 `cross-platform-smoke (macos-latest)`；CodeQL check 与其中的 `Analyze Python` 也通过。这是 Phase 4 的同一 source checkout 远程平台与静态分析证据；它自身没有完成 packaged acceptance，也没有在 macOS/Linux 执行真实 vendor CLI。Phase 6 使用后续独立制品因果链完成三平台 packaged acceptance。

Phase 6 实现提交 `f7d5340d0c822f62786046724473b9005c41f1b1` 的本地证据为 Ruff green、149-source strict mypy green、manifest validator green、`1716 passed, 1 skipped`、7 条 distribution-contract tests、resolved-distribution audit 无已知漏洞且跳过未发布本地包，以及 Windows/Python `3.11.15` 上同一候选的三个安装通道全部通过。[PR #9](https://github.com/SevenX77/graph-skill-runtime/pull/9) head 是 `f7d5340d`；[Actions run 33159834800](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33159834800) 实际检出的 synthetic merge 是 `67703295956350f6453dae24f4f0de50f8d448d9`，因此三份 acceptance evidence 的 `source_commit` 都是后者。Ubuntu、Windows、macOS 的报告具有相同 artifact-manifest digest，并在 Python `3.11.16` 上让 pip-wheel、uv-wheel、pip-sdist 三通道得到相同的 compile、predict/run、durable handoff、integration lifecycle 与零意外宿主状态改动结果。精确制品大小、SHA-256、平台与 job 结果由 [`../CROSS_PLATFORM.md`](../CROSS_PLATFORM.md) 统一记录；这些值标识该次候选，不是版本级常量。

Phase 4 direct vendor CLI 的实机证据来自 Microsoft Windows `10.0.26200` x64、Python `3.11.15`。唯一成功 operational smoke 是 Codex CLI `0.144.1`：`run_id=codex-post-hardening-smoke`、`task_id=68c178f2-f453-510e-b80c-490ee366caab`、`attempt_id=9c8257a3-2e2a-4d16-aa83-7e141b47692e`、vendor `session_id=01a0465f-7593-78e3-acb4-88b3a0a11100`，输出 `echoed_note="post hardening verified"`，trace 顺序为 `agent_required` → `agent_dispatched` → `agent_started` → `agent_completed`，后三者共享同一 attempt id。Claude Code `2.1.222` 的 executable/version/help probe 通过，但 `auth status` exit 1；`gskill` 返回 `GSKILL_EXECUTOR_UNAVAILABLE`、`category=authentication-missing`、process exit 2，且未创建 handoff database。指定不存在的 Copilot executable 时，`gskill` 返回同一 error code、`category=executable-not-found`、process exit 2；immutable request snapshot 已存在，handoff database 不存在。这两条都是 fail-before-handoff 证据，不是成功支持证据。Copilot、Cursor、Gemini 与 OpenCode 未安装，Claude 未登录，macOS/Linux Phase 4 实机仍未验证。Phase 5 的 host projection discovery 是另一条验收边界，详见 Section 13；它不扩大 Phase 4 direct executor 的 operational support matrix。

## 1. 目标、术语与不可变约束

**Graph Skill Runtime** 是读取、编译并执行 graph skill 的 Python runtime。这里的 **graph skill**（下文简称 gSkill）是用户拥有的一组业务指令、机器图定义和 phase 文件；runtime 是解释并执行这些文件的通用软件。

目标产品同时提供三种接口形态：

- **SDK**：Python 调用者使用的强类型接口；
- **CLI**：人在终端或通用自动化中调用的命令行接口；
- **MCP server**：通过 Model Context Protocol（模型上下文协议，一种让 agent 结构化调用工具的协议）提供的工具接口。

PyPI、`pip` 和 `uv` 是 Python 软件的分发与安装方式；SDK 是调用接口形态。二者不是相互竞争的产品类型。v1 首发渠道是 PyPI，不是 npm。

目标由以下不可变约束导出：

1. 用户业务 gSkill 永远由用户拥有。runtime wheel 不捆绑、不注册、不复制业务 gSkill，只发现并读取调用者给出的路径。
2. 业务声明、单次运行输入、机器配置、宿主 UI 状态和秘密具有不同生命周期，必须分别拥有唯一事实源。
3. 编译、预测、执行、恢复、CLI 与 MCP 必须调用同一 application service。application service 是组织用例的应用层入口；适配器只能转换输入输出，不能复制业务规则。
4. 业务图 checkpoint 与 agent 进程/session 是两个正交状态域。更换 agent supervisor 不能替代图状态的 durable resume。
5. Agent Skills 的说明入口与机器拓扑各有一个职责。一个 `SKILL.md` 不能同时成为人类/agent 指令和机器图 manifest 的双重真相源。
6. v1 每种语义只支持一个当前格式。迁移通过显式转换完成，不在 runtime 核心保留 dual reader、legacy alias 或版本猜测。

## 2. 产品命名与发布身份

### 2.1 目标决定

| 对象 | v1 工作名 |
| --- | --- |
| GitHub repository | `graph-skill-runtime` |
| PyPI distribution | `graph-skill-runtime` |
| Display name | Graph Skill Runtime |
| Python import | `graph_skill_runtime` |
| Console command | `gskill` |
| MCP server/tool namespace | `gskill` |

这些工作名已经在当前 repository、distribution metadata、Python import 与 console entry point 中实现。GitHub repository `SevenX77/graph-skill-runtime` 已存在；PyPI 尚未发布，名称也不构成商标许可。repository 的 release workflow 已按 `v<pyproject version>` release tag 分离一次 build、三平台 verify 与 publish：只有 build 和三平台 source/installed-package acceptance 全部成功，publish job 才能下载原始 distributions，并通过 OIDC Trusted Publishing 请求上传。owner 仍须先在 PyPI 建立 project 与 trusted publisher。首次公开 registry 发布前还须完成占名与商标复核，若复核失败，应在发布前一次性裁决新名称，不能增加永久 alias。

选择完整的 `graph-skill-runtime`，而不是 `g-skill-runtime`，理由是 **Graph Skill** 是清楚的开放复合短语，读者不需要先解码缩写；`GSkill` 则是人为缩合，不是自然英文复合词。完整名字也直接说明包的职责是 graph skill 的 runtime，而不是一个泛化的 “G” 工具。

### 2.2 已核验的命名风险

截至 2026-08-27，项目自己的 GitHub repository 已建立；精确的 `graph-skill-runtime`、`g-skill-runtime`、`graphskill-runtime` 在 npm 与 PyPI 均返回 404。这只是时间点观察，不构成 registry 占名或商标许可。

截至 2026-08-28，repository 的 GitHub Release 列表为空，`graph-skill-runtime` 在 PyPI 与 TestPyPI 的 JSON endpoint 均返回 404。这是“尚未发布且 registry project 尚不存在”的时间点证据，不保证名称继续可用，也不能替代首次发布前的占名和商标裁决。

相邻名称已经拥挤：npm 有直接竞品 [gwaghmar/graph 的 `graph-skill`](https://github.com/gwaghmar/graph)，GitHub 另有 [`ouyangyipeng/Graph-Skill`](https://github.com/ouyangyipeng/Graph-Skill)；`gskill` 还会让人联想到 G.SKILL 硬件品牌、GEPA 的 `gskill` 和 Go 生态同名工具。因此，发布前必须完成 PyPI/GitHub 占名、包名混淆检查、域名与商标复核。任何一项失败都应在发布前重新裁决名称，而不是为兼容 drafted 名称留下别名。

## 3. 目标架构与公共契约

### 3.1 模块边界

| 层 | 单一职责 | 允许依赖 |
| --- | --- | --- |
| domain | 编译规则、typed dataflow、checkpoint 语义、预测与 golden 判据 | Python 标准库与明确的领域依赖；不依赖 Studio、Gateway 或某个宿主 |
| application | `compile`、`resolve_run`、`predict`、`run`、`resume`、`submit_agent_result`、`inspect`、`evaluate_golden` 用例 | domain Port 与强类型请求/结果 |
| ports | `AgentExecutor`、checkpoint store、artifact store、event sink、skill source 等稳定协议 | 只包含宿主无关类型 |
| adapters | 本地文件、host-native、vendor CLI、embedded、MCP、console、Python facade | 依赖 ports；可以依赖具体平台或厂商 |
| integrations | MoirAI canonical assets、宿主 renderer 与显式 installer | installer 只拥有 host projection；资产指令通过公开 SDK/CLI/MCP runtime 契约工作，不进入 core |

核心包不提供 HTTP API，也不持有 Studio 文件扫描、Gateway credential truth 或某个宿主的全局配置。Gateway 与 Studio plugin 不属于本轮 release；未来外部集成只能通过公开 SDK/CLI/MCP 与显式 Port/Adapter 边界接入，不能把产品状态或依赖放进 core。本轮 optional distribution extra 只服务已经列入阶段计划且通过验收的能力。

### 3.2 强类型 facade

目标顶层 `graph_skill_runtime` 至少公开以下版本化契约：

- `CompileRequest` / `CompileResult` 与完整 diagnostics；
- `PredictRequest` / `PredictResult`；
- `RunInvocation`、`RunRequest` / `RunResult`；`RunInvocation` 表达调用者本次给出的覆盖与可选 preset id，`RunRequest` 是配置合并后的 immutable 执行快照；
- `ResumeRequest`、`AgentTask`、`AgentResult`、`AgentRequired`；
- `RuntimeProfile`、`RunPreset` 与 resolved immutable profile snapshot；
- 完整 `CallbackEvent` 判别联合类型、error code catalog 和结构化 error payload；
- `AgentExecutor`、checkpoint store、artifact store、event sink 和 skill source Port。

所有会跨进程、落盘或进入 MCP 的对象必须带明确 `schema_version` 和判别字段。公共函数不得让调用者传入未约束的 `Any` 字典来表达 executor、runtime config、checkpointer 或 provider。内部实现可以使用 LangGraph，但公开请求、暂停结果与事件不能暴露 LangGraph `interrupt()` 对象或内部 runnable config。

### 3.3 单一用例出口

Python SDK、`gskill` CLI 与 `gskill` MCP server 均是薄 adapter：

1. 解析各自 transport 的输入；
2. 构造同一个强类型 `RunInvocation`；
3. 通过同一个配置 resolver 生成 `RuntimeProfile` snapshot 与 immutable `RunRequest`；
4. 调用同一个 application service；
5. 将同一个 result/event/error contract 投影为 Python、JSON 或终端输出。

因此，`gskill compile`、MCP `compile` 和 `graph_skill_runtime.compile(...)` 必须返回同源诊断；`run`、`resume` 与 `submit_agent_result` 也不得各自实现状态转换。

**Phase 1/4/5 实现说明**：上述 domain/application/ports/adapters/integrations 分层与七十七个顶层 typed symbols 已实现。顶层 Python function 精确为 14 个：`create_application` 加八个 runtime SDK use cases 构成九个 runtime/application entry points，五个 integration SDK functions 组成其余五个。八个 runtime use cases、`gskill` 的 runtime CLI commands 与八个 MCP runtime tools 共享同一个 `RuntimeApplication`；五个 integration SDK functions 与 `gskill integrations` CLI 共享显式 `IntegrationInstaller`，没有 installer MCP tool。Phase 4 增加公共 `AgentResource`；Phase 5 增加十三个 integration model/installer names 与五个 integration SDK functions，合计 18 个新增顶层 names。Runtime 公共 Pydantic contracts 位于 `domain/models.py`，integration 公共 Pydantic contracts 位于 `integrations/models.py`；两者都是 closed、frozen、带 `schema_version` 与 `kind` 的对象，构造后的嵌套 JSON collection 也不可变。`create_application` 是显式 composition root，每次调用构造独立 application，不持有全局 singleton。

这一实现状态不表示所有目标用例已经具备完整执行语义。Phase 3 已让 `submit_agent_result` 在受支持的 host-native wait point 上完成 durable state transition；`resume(checkpoint_ref)` 只读取当前 durable wait 或 terminal response，普通 human/breakpoint typed resume 仍返回结构化 `GSKILL_NOT_IMPLEMENTED`。`RuntimeEvent.event_type` 已收紧为封闭的四十四值 Literal，并由 contract test 保证与当前全部 concrete `CallbackEvent` discriminator 精确相等。Host-native 有因果发出的 handoff lifecycle 是 `agent_required`、`agent_completed`、task-terminal `agent_failed` 与 `agent_result_rejected`；它仍没有 dispatched/started 宿主 acknowledgment。Phase 4 的 runtime-owned CLI attempt 则可以在 immutable attempt 建成后发 `agent_dispatched`，在 OS process-tree owner 建成后发 `agent_started`，并让成功 `agent_completed` 共享两者的 `attempt_id`。公共预测结果当前统一使用 `RunResult(mode="predict")`；是否另立 `PredictResult` 仍属于完整 v1 设计收敛事项，不能凭本文的目标清单虚构一个当前 export。

## 4. Portable gSkill 格式

**当前实现边界**：Phase 2 已把本节设计落实为 production reader。当前 core 只接受显式 skill root 下的根 `SKILL.md`、`graph.yaml`、phase `LOGIC.md` / `AGENT.md` / `SUBGRAPH.md` 和单层 `graphs/<graph_id>/` registry；没有 dual reader。字段级格式与 converter 的当前权威是 [`../skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md)，本节说明完整 v1 设计中的职责与动机，不另建平行 schema。

### 4.1 目录布局

v1 的一个业务 gSkill 目录采用以下唯一布局：

```text
my-skill/
├── SKILL.md
├── graph.yaml
├── phases/
│   └── <phase_id>/
│       └── LOGIC.md | AGENT.md | SUBGRAPH.md
├── graphs/
│   └── <graph_id>/
│       ├── graph.yaml
│       └── phases/
│           └── <phase_id>/
│               └── LOGIC.md | AGENT.md | SUBGRAPH.md
├── references/
├── examples/
└── .gskill/
```

`.gskill/` 是默认的 skill-local runtime state 目录，必须加入 `.gitignore`；profile 或 `--state-dir` 可以覆盖它。runtime 在真正读写前把所有路径解析成绝对路径，并把解析结果写入本次运行的 immutable snapshot。

### 4.2 `SKILL.md` 是 Agent Skills 入口

Agent Skills 是一种让兼容宿主发现并按需加载技能说明的开放目录约定。其[规范](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx)要求根目录有 `SKILL.md`，最小 frontmatter 使用 `name` 与 `description`，并允许可选 metadata 及 `references/`、`scripts/`、`assets/` 等辅助资源。

目标 `SKILL.md` 只承担两个职责：

1. 让 Claude、Codex、Copilot、Gemini、Cursor、OpenCode 等兼容宿主理解何时使用这个业务 skill；
2. 给当前宿主 agent 一段简洁、跨宿主安全的调用协议，例如优先调用 `gskill` MCP tools，MCP 不可用时调用稳定 `gskill` CLI。

它不保存 node、edge、I/O schema 或 subgraph registry。机器可读拓扑只在 `graph.yaml` 中定义。`SKILL.md` 也不应指令宿主调用 `python -m ...`：宿主当前解释器和虚拟环境不确定，模块命令不能形成稳定、可发现的用户协议。

MCP 是结构化首选，因为 request/result schema 可直接校验；CLI 是任何能启动进程的宿主都能采用的通用 fallback。v1 不是 MCP-only。

### 4.3 `graph.yaml` 与 phase 文件

根 `graph.yaml` 声明 root graph 的 `graph_id`、输入输出 schema、phase registry 和显式 edge。每个 phase 目录必须且只能有一个类型文件：

- `LOGIC.md`：确定性逻辑 phase；
- `AGENT.md`：需要 agent executor 的 phase；
- `SUBGRAPH.md`：调用另一个 graph 的 phase。

Legacy v0.3 的 agent phase `SKILL.md` 在 portable 格式中改名为 `AGENT.md`。Cursor 等宿主会递归发现 `SKILL.md`；把 phase 文件继续叫 `SKILL.md` 会使宿主把内部节点误认成可独立调用的 Agent Skill。

portable declaration 包括根 `SKILL.md`、所有 `graph.yaml` 与 phase 文件，可以提交版本控制。runtime state、credentials、宿主 session 和 UI 扫描投影不属于 portable declaration。

## 5. Subgraph registry 与调用图

### 5.1 目标决定

v1 使用 root `graphs/<graph_id>/` 单层 registry。`graph_id` 在一个业务 gSkill 内全局唯一；phase id 只需在所属 graph 内唯一。root `graph.yaml` 也声明一个不与 registry 冲突的 graph id。

`SUBGRAPH.md` 通过显式引用调用 registry 中的 graph：

```yaml
---
graph: fact-check
---
```

trace 和诊断使用稳定地址 `<graph_id>/<phase_id>`。编译器必须在执行前聚合并拒绝：

- 不存在的 graph 引用；
- 重复 graph id；
- 同一 graph 内重复 phase id；
- 调用环；
- registry 目录名、manifest id 与引用不一致。

`gskill inspect --call-graph` 从显式 call edge 生成面向人的调用拓扑。parent 和 callers 必须从 edge 派生，不能另存 `parent` 真相；同一 graph 可以被多个 caller 复用，单一 parent 字段无法表达这一事实。

目录只表达资产所有权，调用图才表达运行拓扑。v1 不按 caller 在 `subgraph/` 下递归嵌套，也不在具体 phase 目录里套娃。v1 不同时支持嵌套布局与 registry 布局；未来若需要真正 inline scope，应另立作用域、可见性和生命周期语义，而不是复活隐式物理嵌套。

### 5.2 成熟方案的取舍

- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)把 subgraph 作为可独立编译的 graph，再作为 node 使用。我们借用“独立单元 + 明确嵌入点”，不借其 Python graph object 作为公共文件契约。
- [Camunda call activity](https://docs.camunda.io/docs/components/modeler/bpmn/call-activities/)调用可被多个流程复用的外部 process；[embedded subprocess](https://docs.camunda.io/docs/components/modeler/bpmn/embedded-subprocesses/)则是同一 diagram 内的内嵌作用域。我们 v1 选择 reusable call 的语义，不把两类语义混在一个目录形状里。
- [GitHub Actions reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)将可复用 workflow 平铺在 `.github/workflows`，由显式 `uses` 引用。我们借用平铺 registry 与显式引用，不借其 YAML job/runtime 模型。

共同结论是：可复用单元应独立拥有，调用关系应显式表示。物理嵌套无法正确表达动态、多父或共享调用，所以不作为 v1 拓扑真相。

## 6. Agent phase 与 `AgentExecutor` Port

### 6.1 公共 dispatch/result 协议

核心不再拥有唯一的自制 ReAct agent。ReAct 是让模型在“思考—调用工具—观察结果”循环中完成任务的一种 agent 策略；它可以是一个 adapter 的实现，不能定义整个 runtime。

目标 `AgentExecutor` 是窄 Port。直接 executor 消费版本化 `AgentTask` 并产生 `AgentResult`；cooperative host-native adapter 则把同一 task 投影为 durable `AgentRequired`，等待外部提交：

| 对象 | 必须表达的事实 |
| --- | --- |
| `AgentTask` | schema version、task/run id、`graph_id/phase_id`、已渲染指令、typed input、output schema、`AgentResource` references/examples、允许工具/路径/网络策略、deadline 与 capability requirements |
| `AgentRequired` | 完整 `AgentTask`、opaque checkpoint reference 与允许的 wire 提交入口；所需能力在 task 内；它表示任务已持久化等待宿主，不表示 agent 已启动 |
| `AgentResult` | schema version、task id、terminal status、typed output 或结构化 failure、executor identity 与可复核 provenance |
| lifecycle events | `agent_required`、`agent_dispatched`、`agent_started`、`agent_completed`、`agent_failed`、`agent_result_rejected`；每个事件只能在有相应可观察证据时发出 |

runtime 收到结果后先验证 task identity、状态转换和 output schema；completed 结果写入 blackboard 并继续 graph，failed/cancelled 结果不执行该 Agent phase，而是幂等地产生 terminal failed response 并发出 `agent_failed`。错误 task、过期 checkpoint 或 schema 不匹配必须 fail fast。当前实现对完整 immutable `AgentResult` 做 canonical hash：完全相同的重复提交返回第一次提交因果产生的同一 `RunResult`，不同结果冲突，schema 非法结果不消费 task。`FrameworkState.agent_result_hashes` 记录 graph owner 已接收的 hash，用来跨越 graph checkpoint SQLite 与 handoff SQLite 无法共享事务的 result-commit crash window。

当前 closed event catalog 在 Phase 3 的 42 值基础上增加 `agent_dispatched` 与 `agent_started`，共 44 值。每条 handoff/attempt trace event 带确定性 `handoff_event_id`，本地 append 做 best-effort 去重；trace JSONL 与 handoff SQLite 是不同 owner，consumer 必须按 causal at-least-once evidence 处理并用该 id 去重，event 不能充当跨 owner commit proof，也不存在全局 exactly-once delivery 承诺。

两类执行器的证据边界不同。Host-native 仅仅返回 task 不能证明宿主已经派发或启动 agent，所以它的 dispatched/started acknowledgment 仍待 Phase 3b。Direct CLI 的进程由 runtime 自己拥有：adapter 完成 immutable attempt build 后发 `agent_dispatched`，OS process-tree owner 建成后发 `agent_started`，二者都带同一非空 `attempt_id`；成功提交的 `agent_completed` 显式复用该 id。dispatch 后失败发 `agent_failed(status=failed, task_terminal=false)`，携带 attempt id 与 retryable 判定，durable task 保留。Host-native submitted failed/cancelled 仍是 `task_terminal=true`，其 attempt id 可以为空。

### 6.2 Adapter 1：`host-native`，v1 默认

`host-native` 是协作式 adapter：它让当前交互宿主自己的 root agent 创建原生、干净上下文的 subagent，而不是让 runtime 外部进程假装进入当前 session。

**Phase 3 当前实现**：`host-native` 是 `RuntimeProfile` 的默认 executor。没有 Agent phase 的纯 logic graph 在该 profile 下直接完成。存在 Agent phase 时，当前只接受 root DAG 内可按依赖关系串行定位的 wait point，并要求 `SqliteCheckpointStoreConfig`。registry subgraph 内 Agent、包含 Agent 的 graph-level iterate、Agent phase iterate，以及 Agent 与其他 phase 不可比较的并行分支都会在执行前以 `GSKILL_INVALID_REQUEST` 失败，不会落入 embedded 模型路径。

一次 AGENT phase 的完整时序是：

1. `RuntimeApplication.run` 解析并以 create-if-absent 语义保存 immutable `RunRequest`；
2. engine 运行到 root Agent phase 之前，由 LangGraph SQLite checkpoint store 持久化等待状态；
3. host-native adapter 从该 pause 构造并在独立的 `<state_root>/agent-handoffs.sqlite3` 中持久化 `AgentTask`；
4. runtime 返回结构化 `agent_required`。公开 `checkpoint_ref` 固定为 `gskill-handoff-v1:<task-id>`，不泄漏 LangGraph checkpoint id 或 namespace；
5. 当前宿主 root agent 按业务 `SKILL.md` 的协议，用宿主原生 tool 或 instruction 创建新的 clean-context subagent，并把 `AgentTask` 交给它；
6. 宿主通过 Python SDK `submit_agent_result`、同名 MCP tool 或 CLI `gskill submit` 提交 `AgentResult`；
7. runtime 从 immutable request snapshot 恢复调用上下文，先确认 handoff record 仍拥有完全相同的 request，再校验 task/run identity 与 output JSON Schema，把 external phase completion 写入同一 graph state，并继续同一 run。若后续还有受支持的串行 Agent phase，则再次返回新的 durable `agent_required`。

两层持久化都发生在 `agent_required` 对外可见之前，因此宿主崩溃或会话结束后仍能由另一进程提交。若进程在 LangGraph 已提交 Agent breakpoint、handoff row 尚未写入时退出，下一次相同 `run` 通过 `recover_paused_skill` 只读现有 checkpoint，重建 public task，而不调用 graph node 或重放已经完成的 prefix。公开契约是 durable dispatch/result，不是 LangGraph interrupt object。`resume(checkpoint_ref)` 只读取 handoff owner 当前保存的 wait 或 terminal response；它不提交 Agent output，也不推进图。普通 human/breakpoint typed resume 仍待 Phase 3b。

若当前宿主没有 native subagent 能力，宿主必须明确报告不能执行，不能伪造 task completion。当前 runtime 能把 `required_capabilities` 放入 task，但尚无 host-native acknowledgment 来证明 capability、`agent_dispatched` 或 `agent_started`；该协商属于 Phase 3b。无论宿主能力如何，runtime 都不静默选择 fallback executor。显式选择 `embedded` 才进入 embedded，显式选择 `cli` 才进入下一节的 runtime-owned direct vendor process 路径。

### 6.3 Adapter 2：`cli`，第二阶段直接执行

`cli` adapter 从 runtime 启动厂商 headless CLI。**Phase 4 当前实现**包含 Claude、Codex、GitHub Copilot、Cursor、Gemini 与 OpenCode 六个协议 adapter。每个 `AgentTask` 使用一个新进程和新的临时 cwd，不传 resume、continue 或既有 session id；这是 fresh vendor-native top-level session，不是当前交互宿主的 native child/subagent。它也不等于“空白用户配置”：vendor-managed auth/config 仍可能生效，部分 CLI 仍会按 vendor 默认保存 session record。

默认 executor 仍是 `host-native`。只有显式 `executor=cli` 才进入 `CliRuntimeAdapter`；fallback declaration 不会被静默选择。一个纯 `LOGIC` graph 即使 profile 是 `cli`，也直接通过现有 runtime 完成，不构造或 probe vendor executor。存在 Agent phase 时，CLI 复用 Phase 3 的 root-DAG、串行可定位 wait-point 限制；registry subgraph、graph/phase iterate 与不可比较并行分支在业务执行前失败。Portable Agent 声明的 tools、subagents、subgraphs 与 `context_access` 目前也在 handoff 创建前以 non-retryable `task-capability-missing` 拒绝；Phase 4 不假装已经完成 Phase 3b address、human resume、host acknowledgment 或未来工具桥。

`CliExecutorConfig` 的当前字段是：

| 字段 | 当前契约 |
| --- | --- |
| `vendor` | 必填闭集：`claude`、`codex`、`copilot`、`cursor`、`gemini`、`opencode` |
| `agent_profile` | 可选 `Identifier`，只允许 Copilot、Gemini、OpenCode |
| `model_override` | 可选 vendor-native model id；省略时交给 vendor 默认 |
| `executable` | 可选 PATH basename 或 absolute path；含路径分隔符的相对路径 fail fast |
| `timeout_seconds` | 默认 600 秒，必须 `> 0` 且 `<= 86400` |

CLI 同名投影参数是 `--executor cli`、`--vendor`、`--agent-profile`、`--model`、`--executable`、`--timeout-seconds`。Agent profile 不是统一的“从当前会话创建 child”语义：Copilot/OpenCode 使用厂商直接 `--agent`；Gemini 在完整 task stdin 前加 `@<name>`，请求 Gemini 主 agent broker 调用具名 subagent；Claude 在必需的 `--safe-mode` 下不能选 custom agent，Codex `--profile` 是配置 profile 而非 child selector，Cursor 没有文档化 direct selector，所以后三者在 config validation 时拒绝该字段。

[GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) 是 agent/product orchestration，不是一个同名 foundation model。2026-08-27 查验的官方 reference 把 `claude-sonnet-4.6` 列为 general-purpose default，并允许 `--model=auto` 或选择 GPT、Gemini、MAI 等模型；默认会随服务更新。runtime 因此不硬编码“Copilot model”，未给 `model_override` 时完全交给 vendor。

六个 adapter 都执行 executable basename/override lookup、`--version` 与 required help-flag probe。Claude、Codex、Cursor 另有 CLI 暴露的 auth probe；Copilot、Gemini、OpenCode 记录 `auth_probe=not-exposed`，登录问题由真实执行的 structured nonzero-exit 暴露。Probe 证明当前本机 executable 暂时满足这次 adapter 的必需表面，不是所有版本或 OS 的长期支持声明。

| Vendor | 当前 invocation 与收敛表面 | Auth / session provenance | Agent selector |
| --- | --- | --- | --- |
| Claude | `--safe-mode --print --no-session-persistence --tools ''`，完整 task 走 stdin；不超过 12 KiB 的 compact schema 同时传 `--json-schema`，更大 schema 只由 runtime 校验 | auth probe；`session_persistence=disabled` | 不支持 |
| Codex | [`codex exec`](https://developers.openai.com/codex/noninteractive) 使用 `--ephemeral --ignore-user-config --ignore-rules --strict-config`，禁用 `multi_agent`/`multi_agent_v2`，read-only sandbox，task 走 stdin、final response 走 bounded file；只有保守 strict-compatible schema 使用 native `--output-schema` | auth probe；`session_persistence=disabled` | 不支持；`--profile` 不是 agent selector |
| Copilot | fixed short `--prompt` + `--attachment agent-task.md`；关闭 custom instructions、builtin MCP、experimental、remote/export、auto-update、bash-env 等已暴露 customization | `auth_probe=not-exposed`；`session_persistence=vendor-default` | direct `--agent` |
| Cursor | [`--print --output-format json`](https://docs.cursor.com/en/cli/headless)；完整 task 走 stdin，按官方 [output format](https://docs.cursor.com/en/cli/reference/output-format) 解析 | auth probe；`session_persistence=vendor-default` | 不支持 |
| Gemini | stdin context + fixed `--prompt`、JSON output、sandbox、skip trust、extensions none；参见 [headless](https://geminicli.com/docs/cli/headless/)、[stdin automation](https://geminicli.com/docs/cli/tutorials/automation/) | `auth_probe=not-exposed`；`session_persistence=vendor-default` | 按 [subagents](https://geminicli.com/docs/core/subagents/) 以 `@name` 发 brokered request |
| OpenCode | [`--pure run --format json --dir <temp> --file agent-task.md`](https://dev.opencode.ai/docs/cli) | `auth_probe=not-exposed`；`session_persistence=vendor-default` | direct `--agent` |

完整业务 prompt 从不进入 argv：Claude/Codex/Cursor/Gemini 使用 UTF-8 stdin；Copilot/OpenCode 使用退出 temporary directory 时删除的 UTF-8 `agent-task.md`。`AgentResource` 是 top-level public model，字段为 `schema_version=gskill.agent-resource.v1`、`kind=reference|example`、`resource_id`、非空 `path` 与非空 `summary`；`AgentTask.resources` 是 immutable tuple。Host-native task 结构化携带绝对 resource path 给宿主，但 instructions 中的注册表只含 handle/summary，不再复制 path。CLI materializer 只读取 resolve 后位于 `allowed_paths` 的 regular file，将 handle、summary、content 内联 prompt，不把原路径写入 prompt。

当前 byte limits 是：全部 materialized resources 合计 1 MiB、最终 prompt 2 MiB、output schema 1 MiB、process stdout+stderr 合计 4 MiB、Codex final response file 4 MiB。输出始终经过 Draft 2020-12 JSON Schema runtime validation，即使 Claude/Codex 同时做 native schema enforcement。Secret-shaped output/provenance 不能进入 durable `AgentResult`；nonzero exit 或 invalid output 只把 output SHA-256 写入 error details，不持久化原始坏输出。

进程 Port 使用 `shell=False`、显式 temp cwd、最小 allowlisted environment、UTF-8、timeout/cancellation 和 bounded temp-file output。Windows 先启动一个等待 stdin 的 Python supervisor，把它立即加入带 `KILL_ON_JOB_CLOSE` 的 Win32 Job Object，再发送 vendor argv；Job assignment 失败时 fail closed，不降级成只杀 direct child。`AgentStartedEvent.process_id` 在 Windows 是被拥有的 supervisor/process-tree root PID，不保证是 vendor direct child PID。

POSIX 以 `start_new_session` 建立 process group，group-wide `SIGTERM`、固定一秒 grace、再 `SIGKILL` 是 primary cleanup。Hosted Darwin 实证表明 `killpg` 可能按 Apple [`killpg(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/killpg.2.html) 的权限语义返回 `EPERM`。只有遇到 `PermissionError` 时，adapter 才以两秒/1 MiB 上限调用存在的 `/bin/ps` 或 `/usr/bin/ps`，从 `pid/pgid/uid` 三列中选择 PGID 精确等于 attempt group、UID 精确等于 runtime effective UID 的进程，再逐 PID 发送同一 signal；runtime 自身 PID 被排除，结果去重。缺少 `ps`、命令失败、超限、乱码或 malformed row 都使 inspection 失败，不扩大 target。该 narrow fallback 同样用于 `SIGKILL` pass；真实 macOS test 让 descendant 忽略 `SIGTERM`，并证明它被后续 `SIGKILL` 清理。

Timeout、cancel、正常 parent exit 都清理 owned process tree。这里借用 [Win32 Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) 的 `AssignProcessToJobObject`、`TerminateJobObject`、`KILL_ON_JOB_CLOSE`，以及 POSIX process group / Python [`subprocess.start_new_session`](https://docs.python.org/3/library/subprocess.html#popen-constructor) 与 [`os.killpg`](https://docs.python.org/3/library/os.html#os.killpg)；不借 PID file、shell job control 或跨平台 daemon，因为它们不能为本 runtime 证明同一棵 owned tree。

这不是跨 vendor 的统一 OS sandbox。runtime 把资源内联到隔离 temp cwd、过滤环境、关闭 CLI 已暴露的 customization，并在 prompt 禁止额外 filesystem/shell/network/MCP/skill/subagent 工具；vendor-managed auth/config 仍可能生效，CLI 自己的 tool 与 sandbox 强度不同。当前 `allowed_paths` 权威约束的是 runtime resource materialization，不是“vendor 只能读取这些路径”。未来工具桥接必须另立 Port、权限和实机验收，不能从本实现推导。

当前唯一成功支持声明是 Codex CLI `0.144.1` / Windows `10.0.26200` x64 / Python `3.11.15` 的真实 `gskill run`。Claude Code `2.1.222` 只证明 executable/version/help 通过后能因未登录而 fail-before-handoff；不存在 Copilot executable 的实测只证明 `executable-not-found` 同样发生在 handoff 前。六 adapter 的 fake-process tests 证明 contract shape，不证明真实 vendor/OS 支持。Phase 6 的三平台 installed smoke 使用 deterministic host-native result submission，也不执行 vendor CLI；macOS/Linux 以及其他 vendor/version 组合仍须由后续支持矩阵中的真实 smoke 证明。

### 6.4 Adapter 3：`embedded`，可选 fallback

现有 engine 路径已经放到显式 `embedded` executor 后面；provider clients 位于 `graph-skill-runtime[embedded]` optional extra，不在 base dependency 中。它不再是默认 executor。当前实现已用真实 portable `LOGIC` skill 验证 `CurrentEngineAdapter` 的 compile/run；这份证据不等于所有 provider-backed AGENT 行为已经完成 Port parity。

保留它有四个实际价值：

- server 与 CI 即使没有任何厂商 CLI，也可以执行 agent phase；
- runtime 可以完整控制工具、schema、middleware、checkpoint 与 trace；
- predict 与 eval 可以注入确定性模型或 fake；
- 对 executor parity 和错误契约提供可重复的离线基准。

它的保留条件是依赖隔离和 Port parity。host-native/CLI 达到同等 contract coverage 后，再根据真实 server 使用证据决定继续保留或删除；在此之前不让 embedded 的模型、middleware 或 LangGraph 类型泄漏进 core public API。

## 7. Checkpoint、interrupt 与 agent supervisor

checkpoint 保存业务图的 durable state：已完成 phase、blackboard、恢复位置和已经应用的外部结果 hash；handoff store 保存待处理 `AgentTask` 与对外提交响应。ah 或 Prime Agent 这类系统管理 agent session、进程、provider、角色拓扑与 crash recovery。两者解决不同问题，不是二选一。

当前 Phase 3 把两个事实 owner 明确分开。`<state_root>/<SqliteCheckpointStoreConfig.filename>` 由 LangGraph 拥有 graph checkpoint；`<state_root>/agent-handoffs.sqlite3` 拥有跨进程 `AgentTask`、完整 `AgentResult` hash 与对外 `RunResult`。因此要分别收口两个无法共享事务的 crash window：其一，graph pause 已提交而 task row 未写入时，`recover_paused_skill` 从现有 Agent breakpoint 重建 task，不重放 graph prefix；其二，result 已写入 graph 而 handoff response 未提交时，`FrameworkState.agent_result_hashes[task_id]` 作为 crash marker，让完全相同的 submission 从最新 graph state 恢复并缓存 response，而不同 hash 被拒绝。handoff store 用 SQLite `BEGIN IMMEDIATE` 串行化提交，两条恢复路径都不会再次执行 Agent phase。

这项机制借用两个成熟方案的已公开取舍。[SQLite `BEGIN IMMEDIATE`](https://www.sqlite.org/lang_transaction.html) 在 transaction 开始时就申请 write transaction，因此本地 handoff owner 用单写者顺序裁决并发 submission；它没有被扩展成跨两个数据库的伪原子事务。[Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) 保存首次执行结果供同 key 重试，并在同一 identity 携带不同参数时拒绝复用；本实现对应地缓存同一完整 `AgentResult` hash 的 `RunResult`，并拒绝同 task 的不同 hash。Stripe 的时间窗清理不适合直接照搬：当前 runtime 尚未拥有明确的 handoff retention lifecycle，所以 Phase 3 不做基于时间的自动 pruning，避免 task 在宿主离线期间失去唯一 durable owner。

内部实现可以继续用 LangGraph checkpoint。只有人工介入和 cooperative host adapter 需要 interrupt-like pause；普通 CLI executor 可以在一次 application call 内等待子进程完成。无论内部如何实现，SDK/CLI/MCP 只暴露 versioned pause/dispatch/result，不暴露 `interrupt()`、Command 或内部 checkpoint object。

Phase 4 的 process-tree owner 与 checkpoint owner 仍然正交。CLI preflight 在 handoff task 之前完成；成功 preflight 后，runtime 先通过既有 Phase 3 机制建立 durable wait，再为每个 task 建一个 immutable process attempt。`agent_dispatched` 证明 invocation 已建成，`agent_started` 证明 OS tree owner 已建立；它们不替代 graph checkpoint。Dispatch 后的 process failure 保留 handoff task，下一次同一 immutable run 可以对同一 task 建新 attempt id；成功 `AgentResult` 才通过 durable submit transition 推进图。

[ah](https://github.com/SevenX77/ah) 提供 provider CLI、进程监督、tmux workspace、角色编队和 JSON-RPC control plane。v1 借它的 provider adapter、生命周期监督与显式角色拓扑思想；不把它作为核心依赖，因为当前实现依赖 Linux/WSL、systemd/tmux，并以预配置编队为中心，这与 Windows/macOS 原生支持和“装进现有宿主”的目标不一致。

[Prime Agent architecture](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/architecture.md)把 presentation、supervisor、runtime、provider 与 persistence 分层，并用 versioned command/RPC 和 child registry 管理 session tree；其[subagent extension](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/examples/extensions/subagent/README.md)以隔离进程运行 child。v1 借这些边界和 registry 思想；不把 Prime 作为核心依赖，因为它是完整替代型 harness，而本产品要作为兼容现有宿主的 plugin/runtime。

未来可以实现 `AhExecutor` 或 `PrimeExecutor` adapter。v1 先完成直接 CLI adapter 的最小闭环，避免在未证明需要完整 supervisor 前引入第二套控制平面。

## 8. Standalone 配置与状态

### 8.1 五层优先级

同一配置项只能按以下固定优先级解析，高者覆盖低者：

1. `RunInvocation` 中的显式本次覆盖或 CLI flags；
2. 业务项目根 `gskill.toml`，其中 `[runtime]` 是 project `RuntimeProfile` overlay，`[presets.<preset_id>]` 是可选的具名 `RunPreset`；
3. 操作系统标准 config directory 中的 user `RuntimeProfile`；
4. integration 显式传入的 portable `RuntimeProfile` overlay 或 portable `RunPreset` defaults；
5. built-in safe defaults。

具名 `RunPreset` 只来自 project `gskill.toml` 或 integration 显式传入的 portable defaults。user config 只能拥有机器级 `RuntimeProfile`，不能保存具名业务 preset。Phase 1 resolver 已按这五个来源实现逐字段 provenance；其中 project preset 被选中后以 `preset` 标记业务值来源，以区别 project runtime overlay。

`RuntimeProfile` 只承载 executor、checkpoint store、state directory、capability 与权限/失败策略等运行环境选择。`RunPreset` 承载需要跨多次运行复用的**非秘密业务运行默认值**，例如 input/binding defaults、breakpoints、node overrides、compare candidates 和 artifact requests。二者是 `gskill.toml` 中两个独立的强类型 schema；不能为了少一个文件把业务输入、artifact 定义或 UI 扫描状态塞进 `RuntimeProfile`。

调用者可以选择一个具名 preset，再只覆盖本次变化的值，不需要每次重新配置整套运行。resolver 合并上述来源后输出两个 normalized、强类型对象：resolved `RuntimeProfile` snapshot，以及包含实际 inputs/bindings/overrides/artifact requests 的 immutable `RunRequest`。两者记录每个值的来源层；`run` 与 `predict` 会把 `RunRequest` 以 create-if-absent 语义持久化。Phase 3 的 host-native `resume(checkpoint_ref)` 与 `submit_agent_result` 已从该快照恢复，不重新读取变化后的 profile 或 preset；普通 human/breakpoint typed resume 仍待 Phase 3b。

秘密只来自宿主 secret store、环境变量或操作系统 keychain，绝不把 secret value 写入业务 gSkill、`gskill.toml`、run snapshot 或安装 manifest。配置和 snapshot 可以保存 `SecretReference` / `SecretBinding`，不能保存 secret value。Phase 1 对 structurally secret-shaped literal key 做边界拒绝；runtime 无法从任意业务字符串本身可靠推断它是否是秘密，调用者仍须正确分类其他字段。

### 8.2 Executor 所需配置

- `host-native` 不需要 LLM key 或 model provider 配置；当前宿主负责模型与登录。
- `cli` 由厂商 CLI 持有登录和默认模型；runtime profile 选择 vendor、可选 agent profile/model override/executable、bounded timeout 与所需 capabilities。
- 只有 `embedded` extra 需要 provider/model resolver；它的 credential 仍通过环境或 secret provider 注入。

### 8.3 State directory

默认 state directory 是业务 skill 根的 `.gskill/`。`--state-dir` 或 profile 可显式覆盖。runtime 必须在边界解析并验证绝对路径，不允许内部模块各自从 CWD 推导目录。run snapshot、checkpoint、trace 与 artifact manifest 都引用同一 resolved state root，但各自仍有独立 owner 和保留策略。

`LocalRunSnapshotStore` 在 `<state_root>/runs/<run_id>/request.json` 保存 immutable request：第一次写入采用 create-if-absent，同一内容重复保存幂等，不同内容不得覆盖相同 run id。Phase 3 host-native submission 以它恢复调用请求；graph checkpoint 由配置的 LangGraph SQLite 文件拥有，handoff protocol 由固定的 `agent-handoffs.sqlite3` 拥有，三者不能互相替代。

## 9. 从 `studio.runtime_config.v2` 拆分

旧 `.workspace/runtime_config.json` 不能整体迁入 runtime。目标按 owner 与生命周期拆成四类：

1. **Portable declarations**：`SKILL.md`、`graph.yaml`、phase 文件，以及 `graph.yaml` 中具名 artifact declarations；随业务 skill 提交。
2. **Reusable configuration**：project `gskill.toml` 同时容纳彼此独立的强类型 `RuntimeProfile` overlay 与可选 named `RunPreset`；user config 只提供机器/用户级 `RuntimeProfile` 默认值。`RunPreset` 保存可复用、非秘密的运行默认值，不保存 artifact definition。
3. **RunRequest**：由显式 invocation、选中的 preset、profile 与声明默认值合并出的本次 immutable snapshot；包含实际 inputs/bindings、breakpoints、artifact requests、node overrides 与 compare candidates。
4. **Future StudioAdapterState**：Studio 文件 mirror、扫描和 UI 编辑投影；只属于未来外部 Studio adapter，不是本轮 release 交付物。

Artifact declaration 和 artifact request 是两个不同对象。根 `graph.yaml` 以稳定 `artifact_id` 声明 `stem`、`fields`、`mode`、`format`，回答“这个 skill 能产出什么、怎样物化”；`RunPreset` 或 `RunRequest.artifact_requests` 只引用 `artifact_id`，回答“这次要产出哪些”。v1 默认只允许 request 指定输出 destination；若未来确需覆盖其他属性，必须由 declaration 中的强类型 override schema 明确开放，不能让 request 任意改写 `fields`、`mode` 或 `format`。

逐字段映射如下：

| 当前字段 | 新 owner | 转换规则 |
| --- | --- | --- |
| `schema_version` | converter 输入判别；各新对象各自有版本 | 不复制成统一 runtime config version |
| `inputs.import_root` | future `StudioAdapterState.import_root` | 只用于 Studio 导入扫描，不进入 runtime core |
| `inputs.manifest.root` / `.phases` | future `StudioAdapterState.input_manifest` | 保留文件 mirror/scan 事实，不作为运行输入 |
| `inputs.active.root` | named `RunPreset.inputs` → resolved `RunRequest.inputs` | 非秘密、可复用值进入 converter 生成的 project preset；本次覆盖合并后进入 immutable request。秘密或机器临时值不得持久化，converter 必须报告并要求运行时显式提供 |
| `inputs.active.phases` | named `RunPreset.bindings` → resolved `RunRequest.bindings` | 按 `<graph_id>/<phase_id>/<field>` 规范化；同样先保留长期默认，再在每次运行形成最终快照 |
| `inputs.removed.root` / `.phases` | future `StudioAdapterState.removed` | UI 差异状态，不进入 runtime |
| `inputs.conflicts.root` / `.phases` | future `StudioAdapterState.conflicts` | 未来 Studio adapter 在提交 RunRequest 前解决；未解决则边界拒绝 |
| `llm.node_params.nodes` | named `RunPreset.node_overrides` → resolved `RunRequest.node_overrides` | 可复用、非秘密覆盖可进 preset；显式本次覆盖优先，最终值只接受公开 schema |
| `llm.compare_candidates.nodes` | named `RunPreset.compare_candidates` → resolved `RunRequest.compare_candidates` | 经常复用的非秘密候选集可进 preset；一次性候选只进 invocation，二者都在本次 snapshot 固化 |
| `llm.custom_params.nodes` | named `RunPreset.node_overrides.custom_params` → resolved `RunRequest` | 按 executor capability/schema 校验；秘密值禁止进入 preset 与 snapshot |
| `breakpoints` | named `RunPreset.breakpoints` → resolved `RunRequest.breakpoints` | 使用稳定 graph/phase address；可复用默认值进 preset，本次增删在最终 snapshot 固化 |
| `artifacts[].{stem,fields,mode,format}` | `graph.yaml.artifacts[]` + named `RunPreset.artifact_requests` | converter 将每个旧条目提升为 portable declaration，并为其生成稳定 `artifact_id`；为保持旧配置“已启用”的语义，生成的 preset 以 ID 选择这些 declaration。RunRequest 只保存最终选择、destination 与声明允许的本次覆盖 |

portable graph 中声明允许的输入输出、可覆盖点和 artifact definitions，不保存某次运行的实际值。`RuntimeProfile` 不接收表格中的业务运行字段；这些字段只在 named `RunPreset` 与最终 `RunRequest` 之间流动。

新仓不实现 dual reader 或 legacy shim。当前一次性转换入口是 `gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]`：它显式读取旧 Studio skill 与 runtime config，生成 portable 目录、project `gskill.toml`、named migration preset 与确定性迁移报告。它先完成只读 preflight，在 destination 的 sibling temp 目录生成，再以操作系统原生 create-if-absent rename 发布；未知或有冲突字段、无法平铺的 nested subskill、source/destination 冲突或 existing destination 都会在不修改 source、不发布 partial destination的前提下失败。

artifact id 不能使用旧数组位置，因为增删或排序会改变身份。converter 先把 `{stem, fields, mode, format}` 规范化，以合法化后的 `stem` 生成可读候选 ID；若不同定义产生同名候选，则追加规范化定义内容的确定性短 hash。完全相同的重复定义是无法证明意图的重复身份，converter 必须在报告中列出并失败，不能静默合并。迁移报告逐条记录旧数组索引到新 `artifact_id` 的映射。转换完成后，新 runtime 只读新格式，并只按 ID 接受 artifact request。

## 10. MoirAI 随包集成

**实现边界**：Phase 5 已在 canonical bundle、六宿主 renderer、显式 installer 与 scoped discovery 的定义范围内验收。`src/graph_skill_runtime/integrations/assets/moirai/` 只有一份 manifest-closed canonical bundle；`catalog.py` 负责 package-resource 读取与 inventory/UTF-8/LF/frontmatter 校验，`renderers.py` 负责六宿主 native format，`installer.py` 负责 preflight、ownership、apply、因果安全 rollback 与 uninstall。Renderer snapshot、built wheel 与真实宿主证据在 Section 13 分开记录；这些证据不把“六个 renderer 可生成”扩大成“六个宿主产品均 operational”。

### 10.1 资产边界与安装模型

MoirAI 是可选 agentic front door：它帮助当前宿主设计、修复、执行与评估一个**由用户显式提供路径**的业务 gSkill。业务 gSkill 的 root 仍是根 `SKILL.md` + `graph.yaml`，每个 phase 恰有 `LOGIC.md` / `AGENT.md` / `SUBGRAPH.md` 之一；reusable graph 平铺在 `graphs/<graph_id>/`。MoirAI bundle 不含 `graph.yaml`，不安装业务 workflow，不注册全局业务 skill，也不是 core runtime 的必需依赖。

精确 inventory 与 reference subset 的唯一事实源是 `integration.json`，asset version 为 `1.0.0`：

- 四个 role body：`moirai` → host name `moirai`，`clotho` → `moirai-clotho`，`lachesis` → `moirai-lachesis`，`atropos` → `moirai-atropos`；
- 八个 Agent Skills：`moirai`、`moirai-brainstorming`、`moirai-domain-analysis`、`moirai-graph-design`、`moirai-agent-prompt-design`、`moirai-compile-repair`、`moirai-eval-judgement`、`moirai-web-research`；
- 十五个 knowledge files：`KB-00-hub.md` 与 `KB-01..14` 的 manifest-listed exact filenames。每个 renderer 只把 manifest 分配给某个 skill 的 reference subset 复制到该 skill，不创建额外引用。

上述 canonical 与 provider-neutral specialist names 始终使用连字符。Codex adapter 为满足该宿主的 safe identifier surface，单独把 agent projection 正规化为下划线，例如 `.codex/agents/moirai_clotho.toml` 内 `name = "moirai_clotho"`；其他宿主仍投影 manifest 中的连字符名称。该 adapter 变换不改变 canonical inventory 或 delegation 名称。

Canonical skill 的 YAML frontmatter 只含 `name` 与 `description`，其余正文按 progressive disclosure 链接普通相对 Markdown references。Role source 只含 provider-neutral body；renderer 再生成宿主 metadata。Canonical prompt 只调用属于 `gskill` MCP server 的公开 runtime tools，或在 MCP 不可用时调用 installed `gskill` command；不得调用内部 Python module。

安装 distribution、`import graph_skill_runtime`、构造 installer、启动 MCP 与 PATH detection 都不修改宿主或项目。唯一写入授权是显式 `gskill integrations install moirai ...` 或等价 SDK `install_integration(IntegrationRequest(...))`。`detected` 只是 PATH read evidence；只有把它放入显式 install command 后才成为目标选择。Installed-user 流程先 detect、再 dry-run、再 apply：

```text
gskill integrations detect
gskill integrations install moirai --targets codex --scope user --dry-run
gskill integrations install moirai --targets codex --scope user
gskill integrations uninstall moirai --targets codex --scope user --dry-run
gskill integrations uninstall moirai --targets codex --scope user
```

Project scope 要显式给出或由 CLI 从当前目录确定现存 project root；SDK request 必须显式携带该路径。Project manifest 位于 `<project>/.gskill/integrations/moirai/<target>/install-manifest.json`；user scope manifest 位于 runtime user-state root 的同构 `integrations/moirai/<target>/` 下。

Installer 在任何写入前 preflight 全部 requested targets；一个 conflict 阻止全部目标。它不 adopt 或 overwrite unmanaged file/config entry；managed resource 被用户修改后会被保留，并阻止 update/uninstall。Shared JSON 只合并 owned selector；Codex TOML 只维护 marker-delimited owned block。Apply 中途失败后，rollback 只在路径当前内容仍精确等于本次 operation after-image 时恢复 before-image；若另一个进程已改动该路径，installer 保留新内容、报告 incomplete rollback 并抛错，绝不覆盖。Uninstall 只移除 manifest 中 hash 精确匹配的 owned content，并保留 unrelated config。`.opencode/opencode.json` 是 shared config；OpenCode renderer 只 merge/own V2 selector `mcp.servers.gskill` 以及 manifest-owned projected files，不拥有整个 JSON 文件。若 sibling `opencode.jsonc` 已存在，installer fail closed，不 rewrite 或 shadow JSONC。

六个 renderer 按当前 official format references 实现：Codex [skills](https://developers.openai.com/codex/skills)、[subagents](https://developers.openai.com/codex/subagents) 与 [MCP](https://developers.openai.com/codex/mcp)；Claude [skills](https://docs.anthropic.com/en/docs/claude-code/skills) 与 [sub-agents](https://docs.anthropic.com/en/docs/claude-code/sub-agents)；Copilot [custom agents](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/invoke-custom-agents) 与 [MCP](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)；Gemini [subagents](https://geminicli.com/docs/core/subagents/)；Cursor [skills](https://prod.cursor.com/docs/skills) 与 [subagents](https://prod.cursor.com/docs/subagents)；OpenCode V2 [skills](https://opencode.ai/v2/docs/skills/)、[agents](https://opencode.ai/v2/docs/agents)、[config](https://opencode.ai/v2/docs/config) 与 [MCP servers](https://opencode.ai/v2/docs/mcp-servers/)。`tests/integrations/snapshots/moirai_renderers.json` 锁定六者在 project/user scope 的 native paths、profile metadata 与 MCP shape。Official references 证明 format 依据，snapshot 证明 deterministic projection；二者都不单独证明真实产品 discovery 或 operational execution。

### 10.2 Tool ownership

| Tool family | 目标 owner | 原因 |
| --- | --- | --- |
| `compile`、`resolve_run`、`predict`、`run`、`resume`、`submit_agent_result`、`inspect`、`evaluate_golden` | `gskill` portable runtime MCP | 当前 MCP 精确八个 tools；都到达同一 `RuntimeApplication`，没有独立 `trace`、`artifacts`、golden create/promote 或 installer MCP tool |
| LLM credential、role、route、endpoint registry 与 provider probe | future external Gateway adapter | Gateway 是配置真相 owner；秘密与 route 不属于 portable skill。本轮不交付该 adapter |
| create/fork/publish、Studio UI file writing、workspace mirror | future external Studio adapter | 需要 Studio native-fs、router 与产品工作流。本轮不交付该 adapter |
| web fetch/search | 当前宿主能力 | 网络权限、登录和安全策略由宿主拥有，runtime 不重复内置 |

Runtime workflow 先 `compile`。`inspect` 只投影 compiled topology；`predict` 是 deterministic/heuristic stub，不调用真实 model、不持久化 declared artifact outputs，也不证明 quality/golden fitness；`run` 才执行。Golden 只评估现存 `<state_root>/golden/<baseline_id>/baseline.json` 与 cases，没有 public create/promote 操作；`stale` 不算 pass。Artifact 由 root `graph.yaml` 以 stable `artifact_id` 声明，由本次 request 选择；`run` 可以物化选择项，`predict` 不会。

CLI fallback 只使用 installed `gskill` command：`gskill compile SKILL_ROOT`、`gskill predict SKILL_ROOT [--inputs-json JSON]`、`gskill run SKILL_ROOT [--inputs-json JSON]`、`gskill inspect SKILL_ROOT --call-graph`、`gskill golden SKILL_ROOT BASELINE_ID --state-root STATE_ROOT`、`gskill resume SKILL_ROOT RUN_ID --state-root STATE_ROOT --checkpoint-ref REF`、`gskill submit RUN_ID --state-root STATE_ROOT --checkpoint-ref REF --result-json JSON`。Canonical assets 不使用 `uv run`、`python -m` 或 source checkout，也不复制 compile/run 判据。

### 10.3 Specialist 与当前宿主所有权

`moirai` 协调 understand → research → plan → execute → dispatch → close。`moirai-clotho` 负责 domain model、graph topology/dataflow 与 Agent prompt design；`moirai-lachesis` 负责完整 diagnostics、root cause 与最小 authoritative repair；`moirai-atropos` 负责 predict/run/trace/artifact/golden evidence 与 pass/rework verdict。它们是宿主原生 specialist profiles，不替代当前宿主，也不是 runtime executor。

当前宿主始终保留授权、最终裁决与 user-facing response。每次 specialist handoff 必须自包含 objective、scope、paths/typed inputs、已核验 facts、constraints、requested output 与 acceptance evidence。若 runtime 返回 `agent_required`，当前宿主必须创建 fresh native clean-context subagent、交付完整 `AgentTask`、接收一个满足 `output_schema` 的 JSON、封装 `AgentResult` 并调用 `submit_agent_result`；`resume` 只观察 durable wait/terminal state。无法强制 required capabilities 时必须停止并报告，不能伪造输出或通过 shell vendor CLI 冒充当前宿主的 native child。显式 `executor=cli` 是另一条 fresh vendor-native top-level process 路径；它不进入当前 host conversation。Phase 4 direct executor 的真实 operational support 仍只证明 Codex CLI `0.144.1` / Windows `10.0.26200` x64 / Python `3.11.15`；Phase 5 host projection discovery 不改变这条执行矩阵。

## 11. 同类型方案比较

| 方案 | 它解决的核心问题 | v1 借用 | v1 不采用为核心的部分 |
| --- | --- | --- | --- |
| [Agent Skills standard](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx) | 跨宿主发现、说明与渐进加载 skill | 根 `SKILL.md`、安全 frontmatter、references/examples | 它不定义 typed DAG、checkpoint、predict 或 eval；这些由 runtime 补充 |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/) | graph execution、state、checkpoint、subgraph | 内部图执行与 durable checkpoint 的成熟机制 | 不把 Python graph object、interrupt 或 provider agent 变成公开 portable contract |
| [gwaghmar/graph](https://github.com/gwaghmar/graph) | 多宿主的本地 DAG 工程，含 cache、retry、quality gate 与 live report | 显式 DAG、thin host adapters、本地可观察执行 | 其公开能力弱于本项目已有 typed blackboard、聚合 compile、predict/golden 与 durable resume；不以复制其格式替代现有领域能力 |
| [ah](https://github.com/SevenX77/ah) | 多 provider CLI 的 daemon、进程监督与固定角色编队 | provider adapter、进程生命周期、角色拓扑 | Linux/WSL、systemd/tmux 与完整 control plane 不适合作为跨平台 plugin runtime 的 v1 硬依赖 |
| [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/architecture.md) | 完整 coding-agent harness、daemon、session tree 与 provider abstraction | presentation/supervisor/runtime/provider/persistence 分层、versioned RPC、child registry | 它会替代宿主，而 v1 需要接入现有宿主；不把完整 harness 作为核心 |

Graph Skill Runtime 的独特组合是：portable Agent Skill entry、compiled typed dataflow、predict/golden、durable resume、host-native agent execution 与可选 MoirAI front door。相应成本也必须正面承担：六宿主 compatibility matrix、`agent_required`/result 的两步交接协议、installer 的冲突与安全责任，以及 CLI 版本漂移的长期探测测试。

## 12. 安全与失败行为

实现必须在边界 fail fast：

- skill root、state dir、file binding 与 artifact target 在解析绝对路径后检查允许范围；
- vendor CLI adapter 使用明确 executable basename/absolute override、固定 argv 结构、`shell=False`、最小 allowlisted environment 和一次性 working directory；完整业务 prompt 只走 stdin 或临时 UTF-8 attachment，不进入 argv；
- `AgentTask` 只携带该 phase 所需输入、结构化 resources、允许工具与路径，不携带宿主全会话或未声明 secrets；CLI 只 materialize `allowed_paths` 内的声明资源，并从 prompt 中省略原路径；
- 外部 agent 返回值必须先做 Draft 2020-12 schema、task id、checkpoint generation、secret-shaped payload 与大小限制校验；坏输出只持久化 SHA-256，不持久化原文；
- Windows Job Object 与 POSIX process group 负责全 process-tree cleanup，但这不是统一 OS sandbox；vendor auth/config、tools 和 sandbox 强度仍由各 CLI 决定，`allowed_paths` 不得被写成普遍 filesystem confinement；
- MCP 与 installer 遵守宿主权限与信任模型；被动 capability detection 不等于安装授权，只有用户显式执行 `integrations install` 才能写入，即使目标值是 `detected`；
- install/uninstall 以 manifest 和 content hash 证明 ownership，冲突时保留用户文件并失败；apply failure 后也只对仍等于本次 after-image 的路径 rollback，任何并发改动都被保留并作为 incomplete rollback 报错；
- checkpoint 写入、agent result 提交与 resume 必须幂等，重复/过期提交返回结构化错误而不是再次执行 phase。

## 13. 分阶段迁移

每个阶段都必须有独立退出判据和失败出口。Phase 0、Phase 1、Phase 2、下述受限 Phase 3、Phase 4、定义范围内的 Phase 5 与 Phase 6 已验收；当前独立 distribution、portable gSkill v1 格式、bounded host-native protocol、direct vendor CLI protocol、optional MoirAI projection 与同候选三平台 package acceptance 是运行事实。工程阶段中 Phase 3b 仍未实现；完整 v1 还要求首次发布前命名裁决和真实 release/registry publication。不能用 source presence、fake tests、workflow 配置或文档声明替代各阶段要求的因果验收证据。Phase 5 以 source、built artifact 与真实宿主 discovery 三层证据闭合；Phase 6 则以 source gates、manifest-bound built artifact 和三平台隔离安装后的可观察行为闭合。两者都不能扩大 direct vendor CLI 或六宿主 operational support matrix，也不能把可发布候选写成已发布产品。

### Phase 0：契约冻结与 characterization

**当前状态（2026-08-27）**：已实现。repository 提取、命名所需的源迁移、历史冻结与 characterization 已完成。

**工作**：冻结当前 24-export 行为、格式 fixtures、聚合 diagnostics、run/predict/golden/checkpoint/resume/events/errors、`runtime_config.artifacts` 的 `{stem, fields, mode, format}` 物化语义与 Studio 调用样本；记录 Windows/macOS/Linux 安装和路径行为。

**退出判据**：characterization suite 能在当前提交重复运行，并明确区分公开承诺、待收紧的 `Any` 接缝和已知漂移。

**失败出口（Phase 0 当时的规则）**：不拆代码；补齐证据后重跑。当时的 v0.3 format ground truth 保持不变。

### Phase 1：拆出 pure runtime 与 typed facade/config

**当前状态（2026-08-27）**：已实现。distribution/import/command 已切换；Phase 1 的 typed facade、配置 resolver、request snapshot、application/ports/adapters 边界、SDK/CLI/MCP parity 与显式 embedded bridge 已落地。Phase 4 增加 `AgentResource`，Phase 5 再增加 18 个 integration names 后，当前顶层总数为 77。项目尚未发布 PyPI，这不把已完成的源码阶段变成已发布产品。

**工作**：建立独立 repo/package 骨架、domain/application/ports/adapters 边界、版本化 invocation/request/result/event/error，以及将 `RuntimeProfile` 与 named `RunPreset` 分离的五层 config resolver；把 compile/predict/checkpoint 等 pure runtime 能力迁入。现有 embedded executor 只作为显式 optional extra 与 characterization oracle，不成为新包默认 executor。

**退出判据**：clean Python 3.11+ 环境可从 wheel 安装；顶层 contract 不泄露 `Any` 配置；RuntimeProfile 不含业务运行字段，named RunPreset 能提供持久非秘密默认值，RunRequest 是可回放的本次 immutable snapshot；CLI/MCP/SDK 的相同用例通过同一 application service；安装无宿主或项目写入副作用。

**失败出口**：停止发布新包，当前 monorepo package 继续运行；不在旧包旁增加永久兼容 facade。

### Phase 2：切换新 `SKILL.md` / `graph.yaml` / `AGENT.md` / `graphs/` 格式

**当前状态（2026-08-27）**：已实现。Production reader 已原子切换到 portable root `SKILL.md` + `graph.yaml` + phase `AGENT.md` + flat `graphs/`；legacy v0.3 parser 只在显式 converter boundary 中可达。Windows 本地 ruff、mypy strict、1582 passed / 1 skipped、manifest validator、build、isolated-wheel CLI smoke 与第三方依赖 audit 已通过；本 PR 的远程 Ubuntu/Windows/macOS CI 尚未发生。

**已落实工作**：新 parser/compiler、扁平 registry、具名 artifact declarations、call graph 校验与一次性 Studio converter；converter 为旧 artifact definitions 生成稳定 ID，并输出 project preset、flat registry 与确定性 migration report；受控 fixtures 已迁移到 portable 格式。

**退出判据**：新格式 compile/predict 与 typed dataflow characterization 通过；unknown/duplicate/cycle 被同轮聚合拒绝；artifact declaration ID 在重排后稳定，request 只按 ID 选择声明；递归宿主 discovery 只发现根 `SKILL.md`；新 runtime 代码只存在一个 reader。

**失败出口**：丢弃未发布的新格式 build，修正 converter/compiler 后重新生成测试资产；不把旧 reader 加回新 core。

### Phase 3：完成 `host-native` cooperative adapter

**当前状态（2026-08-27）**：当前受限范围已实现。默认 executor 是 `host-native`；纯 logic graph 直接完成，root DAG 内串行可定位的 Agent phase 返回 durable `agent_required`，提交结果后继续同一 run。

**已落实工作**：

- LangGraph SQLite checkpoint 先于 `AgentTask` 持久化，二者又都先于 `agent_required` 可见；
- `AgentTask` 完整携带 run/task id、root graph/phase address、host-neutral instructions、typed inputs、output JSON Schema、allowed tools/paths/network、deadline 与 required capabilities；
- Python SDK、MCP `submit_agent_result` 与 CLI `gskill submit` 到达同一 application service；CLI 把 `agent_required` 当作成功的两步协议状态并返回 exit code 0；
- immutable request 被篡改、output schema 或 identity 非法时 submission 被拒绝；schema 非法不消费 task；完整结果的精确重复提交返回缓存的同一 `RunResult`，不同结果冲突；
- failed/cancelled terminal result 不执行 Agent phase，而是幂等地返回 terminal failure 并发出 `agent_failed`；
- checkpoint-to-task window 由只读 `recover_paused_skill` 重建 public task，graph-commit-to-response window 由 `agent_result_hashes` 恢复；SQLite `BEGIN IMMEDIATE` 串行提交；另一进程可以加载 immutable request snapshot、提交并继续原 run；
- 公开 checkpoint reference 是 `gskill-handoff-v1:<task-id>`，不暴露 LangGraph checkpoint id、namespace、interrupt 或 `Command`；
- 当前 trace 有证据地发出 `agent_required`、`agent_completed`、`agent_failed` 与 `agent_result_rejected`。

**验收证据**：`tests/application/test_host_native_handoff.py` 的 12 条 manifest-targeted tests 覆盖跨进程闭环、多个串行 Agent phase 每次只暴露一个 durable task、非法输出纠正、cancelled terminal failure、篡改 request snapshot 拒绝、graph-commit/handoff-response crash window 与 graph-pause/handoff-row crash window，并另有 durable SQLite、parallel fail-fast、secret-shaped durable result rejection、CLI 两步协议与 MCP 同源提交证据。Ruff green，strict mypy 覆盖 135 个 source files green，manifest validator green，包含全部 12 条 Phase 3 targeted evidence 的本地完整 pytest suite 为 `1604 passed / 1 skipped in 83.88s`。一次人工实测由 `gskill run` 产生 `task_id=c5533e58-abf1-5cfb-ae19-e5f4751e974d`，Codex native clean-context subagent 执行后由 `gskill submit` 让同一 `run_id=real-host-closure` 完成，`executor_id=codex-native-subagent`。这是一条本次人工实测记录，不把机器本地临时 state 路径冒充长期 CI 证据。

**失败出口**：不支持的 graph shape 或非 SQLite Agent handoff 返回结构化 `GSKILL_INVALID_REQUEST`，不执行 Agent phase，也不静默切 executor。宿主没有 native subagent 时必须明确报告无法执行，不能伪造结果。

### Phase 3b：扩展 host-native address 与宿主 acknowledgment

**当前状态（2026-08-27）**：未实现，保持 drafted。

**工作**：为 registry subgraph、graph-level iterate、Agent phase iterate 与不可比较并行分支定义可唯一定位且可重复恢复的 wait-point address；把普通 human/breakpoint resume 接入 standalone typed facade；定义宿主 acknowledgment 与 capability negotiation，使 runtime 只有在宿主确实派发或启动后才能发出 `agent_dispatched` / `agent_started`。

**退出判据**：每种新增地址形状都有跨进程、重复提交和 crash-window 因果测试；human/breakpoint response 与 AgentResult 走彼此不混淆的 typed transition；capability 不满足在派发前明确失败；lifecycle 事件只由宿主回执证明。

**失败出口**：继续保留 Phase 3 的 fail-fast 支持矩阵；不得用 embedded 回退、隐式路径猜测或无证据 lifecycle event 假装覆盖新增形状。

### Phase 4：直接 vendor CLI adapters

**当前状态（2026-08-27）**：当前受限范围已实现。Claude、Codex、GitHub Copilot、Cursor、Gemini 与 OpenCode 的 direct protocol adapter、capability/auth preflight、fresh top-level process、resource materialization、schema validation、attempt lifecycle 和跨平台 process-tree owner 已落地。默认 executor 仍是 `host-native`；显式 `cli` 才进入本路径，纯 `LOGIC` graph 不构造或 probe vendor。

**已落实工作**：

- `CliExecutorConfig` 与 CLI flags 覆盖 vendor、受限 agent profile、model override、executable override 与 bounded timeout；不支持 selector 的 vendor 在 config boundary 拒绝；
- 六 adapter 分别建立固定 command builder、required help flags、JSON/output parser、auth-probe status 与 session-persistence provenance；Claude/Codex 关闭 persistence，其余明确记录 vendor default；
- 全业务 prompt 只走 stdin 或 temporary UTF-8 attachment；结构化 `AgentResource` 在 `allowed_paths` 内 materialize，不把原 path 写进 prompt；资源、prompt、schema、stdout+stderr 与 Codex final file 均有 byte limit；
- 所有 output 都经过 Draft 2020-12 runtime schema validation，secret-shaped durable output/provenance 被拒绝，错误只保留 output SHA-256；
- runtime-owned attempt 按 `required` → `dispatched` → `started` → `completed` 建因果链，后三者显式共享 attempt id；dispatch 后失败发 non-terminal `agent_failed` 并保留 task；preflight 失败不创建 handoff；
- Windows 以 stdin-blocked Python supervisor 消除 Job assignment 抢跑窗口，并用 `AssignProcessToJobObject` / `TerminateJobObject` / `KILL_ON_JOB_CLOSE` 拥有全树；POSIX 以 new session/process group 和 TERM→KILL 为 primary owner，`killpg(EPERM)` 时只对 bounded `ps` 证明为 exact-PGID/effective-UID member 的 PID 逐个发 signal；normal parent success 也清理 lingering descendants；
- 当前 CLI Agent 仍拒绝 portable tools、subagents、subgraphs 与 context access，不宣称 Phase 3b address、human resume、host acknowledgment 或未来工具桥已完成。

**验收证据**：全仓 Ruff green；strict mypy 覆盖 142 source files green；Phase 4 adapter/runtime/process focused tests `43 passed in 4.70s`；完整 pytest 为 `1661 passed / 1 skipped in 116.69s`；contract manifest validator green。`uv build` 产出 `dist/graph_skill_runtime-0.1.0a1.tar.gz` 与 `dist/graph_skill_runtime-0.1.0a1-py3-none-any.whl`。`pip-audit` 对 resolved dependencies 报告无已知漏洞，同时跳过未发布的本地 distribution；这条结果既不是 Graph Skill Runtime 源码审计，也不是 registry publication evidence。

同一 commit `8928d13b32c800a2ad303d02e1bd96551f969ab5` 的 remote source-checkout evidence 是：GitHub Actions run `33140732333` 的 quality gate、Python 3.11/3.12/3.13 runtime tests、Windows smoke 与 macOS smoke 全部通过；CodeQL check 与 `Analyze Python` 通过。macOS 的真实 process test 包含忽略 `SIGTERM` 的 descendant，并验证随后的 `SIGKILL` cleanup。该矩阵证明 source checkout 在这些 runner 上的已测试行为，不证明 real vendor CLI、packaged install 或 release chain。

Windows `10.0.26200` x64 / Python `3.11.15` 上，Codex CLI `0.144.1` 的真实 `gskill run` 以 `run_id=codex-post-hardening-smoke` 完成，task、attempt 与 vendor session id 见本文 Section 0，输出为 `echoed_note="post hardening verified"`。Claude Code `2.1.222` 的 auth-missing 与不存在 Copilot executable 的两次真实负向 smoke 都在 handoff DB 创建前返回结构化 `GSKILL_EXECUTOR_UNAVAILABLE`。它们证明 fail-before-handoff，不证明成功支持。其他四 vendor 未安装，macOS/Linux real vendor execution 未实测。

**退出判据**：本阶段的代码/contract exit 已由六 adapter contract tests、bounded runtime transition、process-tree tests 和唯一已声明 Windows/Codex operational combination 满足。任何新增 OS/vendor/version 支持声明仍须真实 smoke；动态 probe 或 fake test 不会自动扩大矩阵。更丰富 Agent capability、Phase 3b resume/address 和三平台 release acceptance 分别归后续 owner，不反向扩大本阶段承诺。

**失败出口**：缺 executable/version/flag/auth/capability 返回可修复环境对应的 structured `GSKILL_EXECUTOR_UNAVAILABLE`；invalid config/task/schema/resource 与未桥接 capability 不可重试；timeout/cancel/output limit/nonzero/invalid output 返回 structured failure，dispatch 后保留 durable task 供同一 run/task 重试。支持矩阵移除没有实机证据的组合；不伪装成当前宿主 child，不声称 blank config 或 hard sandbox，也不回退到未授权 `embedded`。

### Phase 5：MoirAI canonical assets、installer 与 `gskill` MCP registration

**当前状态（2026-08-27）**：已在 canonical assets、六 renderer、explicit installer 与 scoped host discovery 的定义范围内验收。当前 MCP 仍精确暴露八个 runtime tools：`compile`、`resolve_run`、`predict`、`run`、`resume`、`submit_agent_result`、`inspect`、`evaluate_golden`；installer 只通过 CLI/SDK 暴露。

**已落实工作**：

- `integration.json` 以 integration id `moirai` 和 asset version `1.0.0` 封闭登记 4 roles、8 Agent Skills、15 KB filenames 与每个 skill 的 reference subset；canonical assets 不含 `graph.yaml`；
- 四个 provider-neutral specialist role body、八份仅含 `name` / `description` frontmatter 的 progressive-disclosure `SKILL.md`、`KB-00` routing hub 与 subject-owned `KB-01..14` 已落地；
- Claude、Codex、Copilot、Cursor、Gemini、OpenCode 六个 renderer 把同一份 assets 投影到 native skill/agent directories，并注册现有 `gskill` MCP server；Codex 把 projected agent filename/name 中的 canonical 连字符正规化为下划线，其他宿主保留连字符；OpenCode 只 merge/own shared `.opencode/opencode.json` 中的 V2 selector `mcp.servers.gskill`，遇到 sibling JSONC 时 fail closed；
- `IntegrationInstaller` 与五个 SDK functions、`gskill integrations detect/install/uninstall` 已落地；construction、import、MCP startup 与 detection 零写入，只有 explicit install request 授权 host/project mutation；
- preflight 覆盖全部 requested targets；unmanaged/modified resource 形成全局 conflict；owned JSON selector 与 Codex marker block 独立 merge；apply failure 后只对仍等于本次 after-image 的路径做因果安全 rollback，并对并发改动报告 incomplete rollback；manifest/hash-safe idempotent uninstall 已在实现中闭合；
- Gateway/Studio plugin、dedicated Claude plugin bundle 与 global business-skill registry 均不是本阶段产物，只保留未来 external Port/Adapter owner 边界。

**验收证据（已满足）**：

- **Source candidate**：Ruff green；strict mypy 覆盖 149 个 source files green；contract manifest validator green；完整 pytest 为 `1715 passed, 1 skipped in 83.51s`。`tests/integrations/snapshots/moirai_renderers.json` 锁定 Claude、Codex、Copilot、Cursor、Gemini、OpenCode 六个 renderer 在 project/user 两种 scope 的 native paths、profile metadata 与 MCP shape。Snapshot 是六 renderer 的格式回归证据，不是六个真实产品均 operational 的证据。
- **Built artifact**：`uv build` 成功生成 `0.1.0a1` sdist/wheel，wheel smoke green。Wheel 内 MoirAI closed inventory 精确为 28 members：1 个 `integration.json`、4 个 role bodies、8 个 skills、15 个 KB files；没有 `graph.yaml`，也没有额外 member。Clean Python 3.11 environment 从该 wheel 安装后，`PackagedMoiraiAssets` 读取到 `4/8/15`，并由该 wheel 安装的 `gskill` 完成 temporary project projection。`pip-audit` 报告 `No known vulnerabilities found`，但跳过未发布的本地 `graph-skill-runtime`；这不是源码安全审计或发布证据。
- **Real host observation**：在 Windows `10.0.26200` x64 上，Claude Code `2.1.222` 使用隔离的 `CLAUDE_CONFIG_DIR` 与 temporary project-scope projection。Debug 明确报告 `Loaded 8 unique skills (... project: 8)`；不存在的 `--agent` 对照在认证前列出的 available agents 明确包含 `moirai`、`moirai-atropos`、`moirai-clotho`、`moirai-lachesis`；有效 `--agent moirai-clotho` 越过 profile discovery/selection，只在未登录处失败。`claude mcp get gskill` 发现 project `.mcp.json` entry，debug 随后实际启动并连接 `gskill` stdio MCP，capabilities 为 `hasTools/hasPrompts/hasResources=true`。这些事实证明 skill/agent/MCP discovery 与 MCP startup，不证明 authenticated Claude model execution。
- **Cross-host check and limit**：同一平台的 Codex CLI `0.144.1` 在隔离 temporary project 中供应 project skill `$moirai`，并通过 project MCP 的 `gskill.inspect` 对 `hello-world` 返回 `skill_id=hello-world`。该 tool-backed session 的 spawn tool surface 没有 `agent_type`；生成 child metadata 为 `agent_role=null`，且没有加载 custom `developer_instructions`。因此 Codex custom-agent invocation 尚未验证；这是宿主观察到的限制，不否定 official standalone TOML format。Phase 5 acceptance 依据 Claude 三类 discovery 加 Codex skill/MCP 交叉证据，不把 custom-agent runtime invocation 或其余四宿主扩大为 operational support。

**退出判据（已满足）**：同一候选的 renderer snapshots、built-wheel closed inventory/install projection，以及至少一个真实宿主的 projected skill、agent、`gskill` MCP discovery/startup 均已有 action 与 observed evidence；Codex 再独立交叉验证 skill/MCP。Source、artifact 与 host 三层证据彼此不替代，但已共同闭合本阶段定义范围。

**失败出口**：保留 core runtime 与用户业务 gSkill 的显式路径契约，不让其依赖 MoirAI。未来改动若破坏 snapshot、wheel inventory 或真实 discovery，撤回相应验证声明，修正 canonical asset/renderer/installer 后从同一候选重新验收；不以隐式 projection、覆盖用户文件或新增 core dependency 绕过缺口。

### Phase 6：跨平台 packaging 与 release acceptance

**当前状态（2026-08-28）**：已在“同一 built candidate 的跨平台安装与发布前验收”范围内验收。该状态表示验收 evidence 绑定的 wheel/sdist 候选满足已定义的 package contract，并且 release workflow 只允许已通过三平台验证的原始 bytes 进入 publish job；它不表示已经创建 tag/GitHub Release、配置 PyPI project/trusted publisher，或向 PyPI/TestPyPI 上传。任何后续重建都是新候选，必须生成新 manifest 并重新验收。Phase 4 的成功 direct-vendor operational statement 仍只有 Windows/Codex 一项。

**已落实工作**：

- [`scripts/accept_release_artifacts.py`](../../scripts/accept_release_artifacts.py) 的 `validate` 要求 dist directory 恰好包含一个 wheel 和一个 `.tar.gz` sdist，检查 metadata、`py3-none-any`、`gskill` console entry 与安全 archive path；wheel 明确拒绝 symlink，sdist member 必须是 regular file 或 directory。Wheel 拒绝 `graph_agent/` 与 `graph_skill_runtime/examples/`，sdist 拒绝 `src/graph_agent/` 与 `src/graph_skill_runtime/examples/`；两者都对 MoirAI asset subtree 执行 manifest-owned closed inventory。Sdist 可以保留 repository-level examples/tests 作为源码语料，但这些内容不会进入 installed distribution 或注册到宿主。这不是整个 runtime archive 普通源码 member 的全量白名单。输出 `gskill.release-artifacts.v1` 绑定 supplied source commit、文件名、size 与 SHA-256。
- `accept` 先让当前 wheel/sdist 的 size 与 SHA-256 精确匹配 manifest，重验 archive contract，再要求 `--expected-source-commit` 与 manifest 的 source commit 相等；随后把已验证 bytes 复制到隔离候选目录，分别建立 pip-wheel、uv-wheel、pip-sdist 环境，并输出 `gskill.package-acceptance.v1`。Evidence 记录实际消费的 manifest SHA-256；命令没有另一个外部 `--expected-manifest-hash` 参数，三平台 evidence 的相同 manifest digest 才证明它们消费同一 manifest。
- internal `installed-smoke` 从 site-packages 导入且拒绝 base install 混入 provider extras、`graph_skill_runtime/examples/` 或任何 `graph.yaml`；检查 version、console entry 与只读 host detection；通过真实 stdio 枚举精确八个 MCP tools 并调用 `compile`；通过 installed CLI 运行 compile/inspect/predict/run；覆盖空格与非 ASCII path、Claude/Codex MoirAI project dry-run/install/idempotent/uninstall、host-native run→reopen→submit→duplicate submit→terminal reopen、SQLite integrity/rename/reopen、immutable request/trace、Windows handle release 与零意外宿主配置写入。
- CI 的 `quality-gates` 以 `uv build --no-sources` 一次构建、validate 并上传 distributions+manifest；Ubuntu Python 3.11、Windows Python 3.11 与 macOS Python 3.11 的既有 required-check 路径下载并 accept 同一制品。Ubuntu Python 3.12/3.13 继续运行完整 source suite。Release workflow 同样一次构建并校验 tag/version，三平台同时做 source 和 installed-package verification；只有 build 与三个 verify 全部成功，publish 才下载原始 distributions 并请求 Trusted Publishing。
- 该拓扑采用 [PyPA GitHub Actions publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) 的 build/publish 分离与 immutable artifact handoff，以避免每个平台重建出不同 bytes；采用 [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) 的 named environment 加 `id-token: write`，避免长期 registry token；采用 [uv package guide](https://docs.astral.sh/uv/guides/package/) 的 `uv build --no-sources`，避免本地 workspace source override 掩盖不可发布的依赖关系。精确工程政策由 [`../CROSS_PLATFORM.md`](../CROSS_PLATFORM.md) 拥有。

**验收证据（已满足）**：本地实现提交 `f7d5340d0c822f62786046724473b9005c41f1b1` 通过 Ruff、149-source strict mypy、manifest validator、`1716 passed, 1 skipped`、7 条 distribution-contract tests 与三个 Windows/Python `3.11.15` 安装通道；dependency audit 对 resolved distributions 未发现已知漏洞，但跳过未发布本地包，因此不是源码安全审计或发布证据。PR #9 的 head 为 `f7d5340d`，Actions run `33159834800` 的实际 source checkout/binding 为 synthetic merge `67703295956350f6453dae24f4f0de50f8d448d9`；三平台 evidence 因此记录后者，并具有相同 manifest SHA-256、wheel/sdist size 与 digest。Linux x86_64、Windows 10 AMD64、Darwin arm64 均使用 Python `3.11.16`，三个安装通道均观察到 compile passed、predict/run completed、handoff `[agent_required, agent_required, completed, completed, completed]`、integration `[planned, installed, unchanged, uninstalled]` 与 `unexpected_host_state_changes=[]`。精确 artifact identities 与 job results 见 [`../CROSS_PLATFORM.md`](../CROSS_PLATFORM.md)。

**退出判据（已满足）**：一个 source-bound candidate 在三平台从 built artifact 而非 source tree 安装，并证明 import/console、八工具 MCP surface、portable CLI execution、durable handoff/reopen、SQLite、路径与 integration ownership 行为；wheel 与从 wheel/sdist 构建出的 installed distribution 不含用户业务 gSkill。源码 sdist 可以携带 repository-owned example/test corpus，但安装过程不得投影或注册它。CI 与 release workflow 都阻止未通过全部 verifier 的候选进入 publish job。Installed smoke 使用 deterministic host-native submission，不是 real vendor CLI；因此本阶段不要求也不推导 macOS/Linux vendor operational support。

**失败出口**：任何新候选只要 source binding、archive contract、任一安装通道或任一平台 observable behavior 不一致，就不得发布；修复后必须从新的精确 source commit 重建一对制品并完整重新验收，不能复用旧 manifest/hash 或以较少平台结果代替。Gateway/Studio plugins 不进入该阶段，不得为满足发布验收而把产品专用依赖或状态移入 runtime。实际 registry publish 仍须由 owner 创建 release/tag、完成名称裁决和 PyPI trusted-publisher 配置，并观察上传结果后才能声明。

## 14. v1 总体验收

v1 只有同时满足以下条件才可标记完成。Phase 6 已满足下述 package-candidate 验收项，但 Phase 3b、首次发布前命名裁决和真实 registry publication 尚未闭合，因此本文继续保持 `drafted`：

1. 一个 source-bound candidate wheel 可在 clean Python 3.11+ 环境以 `pip` 和 `uv` 安装，source distribution 可由 `pip` 安装；三者提供 `graph_skill_runtime` 与 `gskill`，且安装本身零宿主配置副作用。实际 PyPI publication 必须上传已验收的同一 distributions，不得重新构建。
2. 一个业务 gSkill 只有根 `SKILL.md` 被宿主发现，机器 topology 和具名 artifact declarations 只有 `graph.yaml` 定义，agent phase 只使用 `AGENT.md`；RunRequest 只按稳定 ID 请求已声明 artifact。
3. 编译聚合报告 graph/phase id、unknown reference、duplicate 和 cycle；`gskill inspect --call-graph` 与实际 call edges 同源。
4. SDK、CLI、MCP 对同一输入返回同源 diagnostics、result、events 与 error code；公开 config/executor/checkpoint 接缝没有未约束 `Any`。
5. `host-native` durable handoff 在真实宿主上完成 crash/reopen/submit/resume；每个声明支持的 CLI vendor/version/OS 组合都有真实 smoke，并明确证明是 fresh top-level session。
6. checkpoint、trace、artifact 与 immutable run snapshot 可由因果证据关联到同一 run；重复 result 提交不会重复执行。
7. config 五层优先级、RuntimeProfile/RunPreset 职责分离、持久非秘密默认值、immutable RunRequest、secret exclusion 与 state-dir 绝对路径在三平台通过测试。
8. `gskill integrations install moirai` 的 dry-run、all-target conflict、manifest、因果安全 rollback、idempotency 与 safe uninstall 通过；六 renderer snapshots、built-wheel canonical inventory 与真实宿主 skill/agent/MCP discovery smoke 均有证据；显式安装前不投影宿主，安装资产也不包含用户业务 gSkill。Phase 5 已在当前定义范围满足本项，完整 v1 仍受其余未满足项约束。
9. wheel/sdist、clean install、CLI/MCP smoke、SQLite reopen 与受支持 handoff 在 Ubuntu、Windows、macOS 的同一候选提交上通过；Gateway/Studio plugins 不是本轮验收依赖，未来只能消费公开 Port/Adapter 边界。Phase 6 已用 manifest-bound 同一候选满足本项。
10. Production runtime 只有 portable reader；旧 v0.3 契约保持 `superseded`，legacy parser 只服务显式 converter。当前 portable 规范处于 `audited-ready`；只有 owner 盖章并建立 SHA-256 哈希锁后才可标记 `FROZEN`。

## 15. 尚待实证的裁决

以下不是 v1 默认事实：

- `embedded` extra 是否在 host/CLI parity 后长期保留，需要真实 server/CI 使用量、维护成本和隔离风险证据；在此之前保持可选，不进入 core default。
- 当前 Windows/Codex `0.144.1` 之外，每个 vendor adapter 首次发布支持的精确 CLI 版本与 OS 组合仍需要 capability probe 和真实 smoke；fake-process contract test、已安装状态或一次动态 help probe 都不能替代 operational evidence。
- 工作名能否最终发布，需要 registry 占位和商标复核；若失败，应在首次公开发布前一次性改名，而不是增加永久 alias。

## 16. 修订记录

| 日期 | 修订 | 依据与边界 |
| --- | --- | --- |
| 2026-08-28 | 将 Phase 6 在 same-candidate cross-platform package/release-candidate acceptance 范围标为 accepted；继续区分可发布候选与已发布产品 | `accept_release_artifacts.py` 建立 source/size/SHA-256 manifest、三安装通道与 installed evidence；本地 gates/Windows exact-candidate 验收通过；PR #9 run `33159834800` 在 Linux x86_64、Windows 10 AMD64、Darwin arm64/Python 3.11.16 消费同一 manifest-bound wheel/sdist，并观察同源 CLI/MCP、handoff、SQLite、path 与 integration 结果。Workflow 采用 PyPA immutable handoff、uv `--no-sources` 与 PyPI OIDC gate。没有 tag release、GitHub Release、PyPI/TestPyPI project/upload 或 trusted-publisher 实证；real vendor support 仍只有 Windows/Codex；全文仍因 Phase 3b 与真实 release/registry publication 为 `drafted` |
| 2026-08-27 | 将 Phase 5 在 canonical assets、六 renderer、explicit installer 与 scoped discovery 范围标为 accepted；收紧 causal rollback、OpenCode shared-config ownership 与 Codex identifier 边界 | Source candidate 通过 Ruff、149-source strict mypy、manifest validator 与 `1715 passed, 1 skipped in 83.51s`，六 renderer 的 project/user snapshot 已锁定；`0.1.0a1` wheel 精确含 28 个 MoirAI members，clean Python 3.11 wheel install/projection smoke 通过；Windows 上 Claude Code `2.1.222` 实证 skill/agent/MCP discovery 与 stdio startup，Codex CLI `0.144.1` 交叉实证 skill/MCP。Claude authenticated model execution 与 Codex custom-agent invocation 均未证明，六宿主 operational claim 不成立；全文仍因 Phase 3b/6 为 `drafted` |
| 2026-08-27 | 将 Phase 4 direct vendor CLI executor 标为当前受限能力，新增 `AgentResource`、六 vendor protocol、attempt lifecycle 与跨平台 process-tree owner，并保持全文 `drafted` | 当前 source/manifest、43 条 Phase 4 focused tests、142-source strict mypy、Ruff、manifest validator 与完整 suite `1661 passed / 1 skipped in 116.69s`；build 同时产出 wheel/sdist，dependency audit 无已知 resolved-dependency 漏洞但跳过未发布的本地 distribution。同一 commit 的 Linux/Windows/macOS source-checkout matrix 与 CodeQL/Analyze Python 已通过，并包含 Darwin `killpg(EPERM)` 后 exact-PGID/effective-UID fallback 的 real macOS SIGKILL cleanup evidence。Windows/Codex `0.144.1` 仍是唯一成功 operational vendor smoke；该行当时的 Phase 5 状态已由上一行验收记录取代，Phase 3b/6 仍未完成，Gateway/Studio plugin 仍不在本 release |
| 2026-08-27 | 将 Phase 6 裁决为跨平台 packaging/release acceptance；Gateway/Studio plugins 移出本轮 release，只保留未来 Port/Adapter owner 边界 | 本轮后续交付顺序固定为 vendor CLI、MoirAI、三平台发布验收；当前无 Gateway/Studio adapter，也不得把产品 plugin 当作 v1 release gate |
| 2026-08-27 | 将 root DAG 串行可定位 wait point 的 durable host-native handoff 标为 Phase 3 当前能力，并把 richer address、普通 typed resume 与 host acknowledgment 留在 Phase 3b | `agent_handoffs.py`、`host_native.py`、`host_native_runtime.py`、`result_mapping.py`、`recover_paused_skill`、external phase completion 与 `agent_result_hashes`；12 条 feature-targeted tests 覆盖跨进程/纠错/cancelled failure/两个 crash window/CLI/MCP，Ruff、135-source strict mypy、manifest validator 与完整 suite `1604 passed / 1 skipped in 83.88s` 通过，并有一次 Codex native clean-context 人工闭环。远程三平台门禁未列为已通过 |
| 2026-08-27 | 将 Phase 2 portable gSkill reader、flat registry、artifact-by-id 与显式 Studio converter 标为当前已实现；把 v0.3 降为 converter/历史证据 | 当前 compiler/loader/converter、portable fixtures 与 Windows 本地门禁；该行只记录 Phase 2 cutover，当时的 Phase 3 判断已由本表上一条修订取代 |
| 2026-08-27 | 初次增加 implementation-status，把 Section 2 源码命名与 Section 3 typed facade/config/SDK-CLI-MCP boundary 标为 Phase 1 已实现 | `pyproject.toml`、`src/graph_skill_runtime/__init__.py`、`domain/models.py`、`application/`、`ports/`、`adapters/`、composition root 与 Phase 1 contract tests；当时的后续阶段判断已由本表第一条 cutover 修订取代，仍未宣称 PyPI 发布 |
| 2026-08-27 | 将配置来源展开为 invocation > project > user > portable > built-in，并澄清 project/portable preset owner、secret reference 与 create-once request snapshot | `ConfigResolver`、`LocalRunSnapshotStore` 与 immutable contract tests；该行当时留下的 durable handoff 缺口已由本表第一条 Phase 3 修订收口 |
| 2026-08-27 | 记录 release workflow 已准备 tag/version check、distribution build、wheel validation 与 OIDC Trusted Publishing | `.github/workflows/release.yml`；PyPI project/trusted publisher 尚未由 owner 配置，也没有实际发布 |
