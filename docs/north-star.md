---
doc: graph-skill-runtime-north-star
role: governance
status: living
updated: 2026-09-03
---

# 引擎的北极星、判据、公理与域级 Effect 树

> **本文是什么**:`graph-skill-runtime` 这个仓库(下称"引擎仓")的最高层依据。它回答三个问题:①这个仓库存在的目的是什么、怎样检验目的达到了;②遇到问题按什么公理与原则推理;③引擎向用户承诺的可观察结果有哪些、每一条今天由哪段代码兑现、哪一条还是空的。
>
> **本文不是什么**:①不是进度状态;②不是任何模块的接口契约本身;③不是实施计划。它只写"目的、判据、承诺清单"。
>
> **怎么读**:先读第 1 节(目的)与第 2 节(核心与辅助的分界),它们决定后面每一条的取舍方向;再读第 3 节(承诺清单)。第 4 节是推理规则,第 5 节是验收清单,第 6 节说明它与仓里其它文档的关系。
>
> **本文的事实基准**:引擎仓 `main` 为提交 `96019595`;上位决议所在的旧仓 `agent-harness` `main` 为提交 `dcb12e40`。文中每个"现在的实现是 X"都给出文件路径与行号,每个"设计意图是 X"都给出权威文件坐标与原句。

---

## 0. 术语

每个词只有一个含义,后文一律用这里的名字,不另起简称。

- **北极星**:最高层的目的判据。任何取舍最终都要回答"它服务哪条北极星、服务到什么程度"。本仓的北极星有五条,见第 1 节。
- **判据**:一句能拿去检验的话,说清"做到什么样才算达到"。没有判据的目标不算目标。
- **gskill**:本项目的技能包格式,以及按这个格式写出来的一个目录。用户在里面用文档描述"这个流程有哪些步骤、步骤之间怎么连、每步读写什么数据"。用户写的就是它,引擎读的也是它。
- **相位(phase)**:流程里的一个步骤节点。一个 gskill 由若干相位和相位之间的连线组成。
- **域**:一组围绕同一批不变量组织的能力。"不变量"指这组能力共同守着的、任何时候都不许被打破的那句话。域不由目录形状决定。
- **域级 Effect**:一个域对用户承诺的可观察结果——做成功时用户能观察到什么。它写的是承诺,不是内部实现。本文用 `E-<域缩写>-<序号>` 给每条承诺一个稳定编号,后续文档一律引这个编号。
- **平行实现**:同一条域级 Effect 的另一种做法,与引擎自己的做法同级,而不是它的上级。网关与工作台的每个模块都是某条域级 Effect 下的平行实现。
- **0 到 1**:把一条承诺从"根本做不到"变成"能做到",哪怕做得笨。这是引擎的责任。
- **1 到 10**:一条承诺已经能做到,再把它做得更好用、更好管。这是辅助模块的责任。
- **Port**:一个稳定的抽象接口,领域逻辑只依赖它,具体外部环境的差异由实现它的适配器承担。本仓的 Port 都在 `src/graph_skill_runtime/ports/runtime.py`。
- **执行者(executor)**:真正去跑一个 AGENT 相位的那一方。AGENT 相位需要一个能自主挑工具、自主行动的 agent 才能完成,执行者就是提供这个 agent 的实现。
- **MoirAI**:引擎自带的一组代理人资产——角色说明、技能说明和知识库文本。它被投影进用户手边的 agent 宿主里,带着用户设计、修复、评测 gskill。它是文本资产,不是四个常驻进程。
- **宿主(host)**:开发者此刻正在用的那个交互式 agent 工具,例如 Claude Code 或 codex。宿主是驾驶员:它调用引擎、读回结果、改源文件。
- **轨迹(trace)**:一次运行留下的逐条记录——每个相位收到什么、模型被怎么提问、返回什么、写回了什么。它落成文件,事后可以逐步复核。
- **编译**:把一个 gskill 目录读成结构化表示、逐条校验、生成可执行的图的那一步。它不调用模型。
- **SDK(软件开发工具包)**:一个供别的程序直接调用的代码库,自己不开网络服务。本仓就是一个 Python SDK。
- **MCP(模型上下文协议)**:一套约定,让外部的 agent 工具把别的程序的能力当成"工具"来调用。引擎按这套约定开一个名叫 `gskill` 的服务。
- **JSON Schema**:用一份 JSON 文档描述"另一份 JSON 应该长什么样"的写法。引擎用它校验相位的输入与输出。
- **preflight(起跑前核对)**:真正开跑之前,先把"这次需要的能力,选中的执行者做不做得到"逐项对一遍,不合就当场拒绝。
- **golden(基线)**:一次被人认可的运行,存下来当尺子;以后每次改动都拿新结果和它比,判断变好还是变坏。
- **SQLite**:一种把整个数据库存成一个文件的轻量数据库。引擎用它存图的检查点。
- **WebSocket**:浏览器与服务端之间一条一直开着的双向通道,用来把"正在发生的事"实时推给界面。
- **ah(agent-hypervisor)**:一个专管"起厂商命令行 agent、盯着它跑、崩了收拾干净"的受监督进程管理器。决议把它定为两个受支持执行者之一。

---

## 1. 引擎的目的:五条北极星

五条并列,不排优先级。原文在旧仓 `docs/design/gskill-restructure-decision-2026-08-31.md` 第 48 至 89 行,以下逐条原样引用。

**北极星-1 · 流程可靠、可重现**
- 要什么(`:54`):「用 langgraph 把流程**钉成一张图**,跑一百次就是同样的一百次。」
- 判据(`:56`):「同一个 gskill、同一份输入,应当走出同一条相位序列;差异只允许出现在相位内部的模型输出,不允许出现在流程结构上。」

**北极星-2 · 比直接写 langgraph 更简单、更不跑偏、更快**
- 要什么(`:60`):「用户用**文档**描述流程即可,不必手写框架代码。」
- 反向判据(`:62`):「任何功能,如果它让用户**比裸写 langgraph 还累**,那这个功能就是错的——不论它多"完备"。」这一条带否决权:新增配置项、新增必填字段、新增要记住的约定,都先过这一问。

**北极星-3 · engine 与 gskill 的 AST 是核心,其余都是提效辅助**
- 要什么(`:66`):「核心资产只有两样——engine(编译与执行)和 gskill 的 AST(格式与它的结构化表示)。」AST 即抽象语法树,是把用户写的 gskill 文本解析成的结构化中间表示。
- 判据(`:68`):「engine 与 AST 权重最高;**studio 迁就 engine,不许反向**。」

**北极星-4 · 本地开发的 gskill 原样复用于服务端**
- 要什么(`:72`):「开发者在本地(桌面应用里)做出来的那个 gskill,**原样**就能在服务端跑,靠的是"锁定版本的 engine SDK"加"锁定版本的 gskill 格式"来编译。」
- 这一条在原文里没有单列"判据",只列了"现状(如实标注)"(`:74`):「**未实现**。」所以它今天的作用是约束设计,不是宣称能力已具备。

**北极星-5 · 去黑盒**
- 要什么(`:78`):「开发者必须能看清 gskill 运行的**每一个细节**。tracing 信息要**完整**(不缺环节)、**准确**(记的就是实际发生的)、**高效**(采集与查看的代价不压垮运行本身)。」
- 判据(`:80`):「凡是"发生了但外部看不见"的环节,都是缺陷候选;修法是把它暴露出来,不是解释它为什么不必看见。」

**两条明确排除项**(`:86-87`):「界面状态必须真实」与「失败时对用户数据零副作用」是要求,但不占北极星席位,它们属于任何严肃工程的底线,由验收清单逐条强制。

**这五条在本仓怎么落地。** 北极星-1 落在"格式把流程钉死、模型只在相位内部发挥"这条实现路线上:相位与连线写在 `graph.yaml` 里,编译期就定死。北极星-2 落在"用户写的是文档,不是框架代码"上:当前格式契约是 `docs/skill-spec/01-PORTABLE-GSKILL-V1.md`(其 frontmatter `status: FROZEN`,即已上机器哈希锁、不可随手改)。北极星-3 落在仓边界上:`AGENTS.md:36` 写死「Core and application code must not import Studio or Gateway modules」——引擎代码里不允许出现工作台或网关的名字。北极星-4 今天只落到"约束设计"这一层,证据见第 3 节 `E-SHP-3`。北极星-5 落在事件、轨迹与检视三件事上,见第 3 节 G-OBS 域;其中"实时看正在跑的运行"这一条今天是空的。

---

## 2. 核心与辅助的分界

### 2.1 用户 2026-09-03 的裁定(逐字)

- 「要遵循模块化推进,一个模块做完就是一个完整的可验证的模块,充分解耦;别把屎山一股脑搬过去,屎上雕花还是屎。runtime 引擎和 gateway 理论上是可以完全解耦互不影响,可以并行推。studio 里面也有很多前端部分也是可以并行推的。当然 runtime 应该先完成,gateway 和 studio 只是 runtime 的辅助功能」
- 「看一下最一开始的 graph-agent 是如何实现 gateway 的,一个 .env 管 api-key,一个 role.yaml 记录角色和 fallback 顺序,一个 llm_manager 组件调用这两个文件,就能满足这个功能。gateway 是能够更好的管理,从 1 到 10,而不是 0 到 1。Studio 也是同理,没有 studio,engine 也要输出 tracing,也要让用户看到这些"去黑盒"的信息,studio 只是把这件事从 1 做到 10,更方便。」
- 关于 MoirAI 算不算引擎的一部分:「算,没有 gateway 和 studio,也需要 moirai,这就是判断原则」
- 关于层级:「"可以直接用 canvas 拖拽、新建节点"也是 studio 的 effect,他的上级模块的 effect 是"可以观察 graph 节点图,可以不手动敲代码建构用户设计的节点图",engine 实现这个 effect 的子模块的 effect 是用 moirai agent 来实现,studio 提供了另一个实现方法,是和"用 moirai agent 来实现"的模块同级的模块。」

### 2.2 由此定下的三句规则

1. **域级 Effect 树只有一份,归引擎所有。** 网关与工作台不得往这棵树上加条目。
2. **引擎对每条域级 Effect 至少提供一个自己的实现。** 这就是"0 到 1"。
3. **网关与工作台的每个模块都是某条既有域级 Effect 下的平行实现**,与引擎自己的实现同级。它的设计文档必须写明自己挂在哪条 Effect 下。找不到父节点只有两种归宿:要么域级表漏了一条(那就先在引擎补上这条和它的第一个实现),要么这个模块不该存在。

### 2.3 完整性判据

**干净环境里只装引擎这一个包,第 3 节列出的每条域级 Effect 都能达成。** "干净环境"指一台没有装工作台、没有装网关、没有本仓源码树的机器。达不成的条目必须在第 5 节写明"未覆盖 + 原因",不允许留白。

### 2.4 MoirAI 的位置

MoirAI 是引擎的一个接入面,与 Python SDK、命令行、MCP 同级——它们是同一套用例的四种投影。判断依据是用户原话:没有网关和工作台,也需要 MoirAI。资产坐标 `src/graph_skill_runtime/integrations/assets/moirai/integration.json`:`asset_version` 为 `1.1.0`,`roles` 4 条、`skills` 8 条、`knowledge` 16 条。

---

## 3. 域级 Effect 树

**这棵树怎么来的。** 按决议第 321 行起的盘点方法:域按不变量聚类,现有文件与目录怎么摆不构成判据。2026-08-31 盘点出的七个种子域(旧仓 `docs/design/gskill-restructure-inventory-2026-08-31/domain-reports/MANIFEST.md:9-15`:G1 运行时底座 + 契约基建、G2 gskill 格式 + 编译诊断、G3 模型 + 媒体供给、G4 执行 + 观测、G5 评测 + 工作台、G6 创作、G7 委托 + 发布 + 平台)只作种子,不作答案。本文推导出十一个域,与种子的每一处差异都在各域小节里写了理由,汇总在 3.12(含一张按旧仓域报告逐条对账的表)。

每条 Effect 写四件事:用户能观察到什么、贡献哪条北极星、引擎自己的实现在哪、已知的平行实现是谁。

### 3.1 G-FMT · 格式与编译诊断

**不变量**:一份 gskill 合不合法只由格式规范判定;一次编译返回它当时能查出的全部缺陷,不是第一条。
**贡献**:北极星-2、北极星-1、北极星-3、北极星-4。
**与种子的关系**:等于种子域 G2,不改。

- **E-FMT-1 用文档描述流程就能编译成一张可运行的图。** 用户观察到:写好 `SKILL.md` + `graph.yaml` + 各相位目录,跑一次编译就得到可执行的图,不必写框架代码。贡献北极星-2、北极星-1。引擎实现:格式契约 `docs/skill-spec/01-PORTABLE-GSKILL-V1.md`(`status: FROZEN`),读取与校验 `src/graph_skill_runtime/core/loader.py`、`src/graph_skill_runtime/core/compiler.py`,入口 `gskill compile`。平行实现:工作台的 Compile 按钮。
- **E-FMT-2 一次编译拿到全部缺陷,每条能定位到文件、行、字段。** 用户观察到:一次编译列出这份 gskill 当时能查出的所有缺陷,每条带一个稳定的原因码,而不是修好一个才冒出下一个。贡献北极星-2、北极星-5。引擎实现:`core/compiler.py:47` 的 `CompileIssue` 带 `source_path` / `line` / `field_path` 三个定位轴;原因码表 `core/error_registry.py` 的 `ERROR_REGISTRY`,实测 99 条(`uv run python -c "from graph_skill_runtime.core.error_registry import ERROR_REGISTRY; print(len(ERROR_REGISTRY))"`)。平行实现:工作台把同一份诊断投影到画布徽章、字段提示与 Compile 抽屉。
- **E-FMT-3 同一份 gskill 里的子图写一次,包内多个调用方复用。** 用户观察到:把一个子图放进 `graphs/<graph_id>/`,这份 gskill 里任何相位都能按编号调它,不必复制一份。**范围到这份 gskill 为止**:注册表属于单个业务 gSkill,跨两份业务 gskill 引用同一个编号不受支持。贡献北极星-2。引擎实现:格式契约 `docs/skill-spec/01-PORTABLE-GSKILL-V1.md:450` 原句「所有 registry graph 都直接位于 skill root 的 `graphs/` 下,且 graph id 在整个业务 gSkill 内唯一」,`:452` 原句「同一 registry graph 可以被多个 caller 复用」;拓扑读取 `core/topology_projection.py:42` 与 `:102`。平行实现:暂无。
- **E-FMT-4 旧格式一次性转换成当前格式,转换器绝不当兜底。** 用户观察到:一条显式命令把旧 skill 转过来;转换失败就是失败,不会在正常路径上悄悄回落到旧读法。贡献北极星-4、北极星-1。引擎实现:`gskill migrate studio-skill`,`src/graph_skill_runtime/migration/studio_v030.py`;边界由 `AGENTS.md:90` 写死。平行实现:暂无。

### 3.2 G-CFG · 运行请求的解析与快照

**不变量**:一次运行的全部参数在起跑前解析成一份不可变的请求,每个字段说得出它来自哪一层。
**贡献**:北极星-1、北极星-4、北极星-5。
**与种子的关系**:从种子域 G1(运行时底座 + 契约基建)里分出来。理由:G1 把"配置解析"和"图执行底座"混在一起,但两者守的不变量不同——前者守"解析确定且可追溯",后者守"执行忠于图"。按决议第 338 行的反事实检验,把配置解析并进执行,会毁掉"起跑前就能看清这次到底会怎么跑"这个行为区分。

- **E-CFG-1 配置优先级固定,每个字段带出处。** 用户观察到:同一次运行的每个参数,都能查到它来自命令行、项目配置、用户机器配置还是内置默认值。贡献北极星-1、北极星-5。引擎实现:`src/graph_skill_runtime/application/config.py`,优先级顺序写在 `AGENTS.md:50`;出处记在 `ValueOrigin`;入口 `gskill config resolve`。平行实现:工作台的设置界面。
- **E-CFG-2 每次运行先落一份不可变的请求快照,同一个运行编号内容不同绝不覆盖。** 用户观察到:每次运行在状态目录下留一份 `request.json`,事后能照它复现这次运行的输入。贡献北极星-1、北极星-4。引擎实现:Port `ports/runtime.py:66` 的 `RunSnapshotStore`,落盘 `adapters/snapshots.py`,语义写在 `AGENTS.md:54`。平行实现:工作台的运行列表。
- **E-CFG-3 执行者只出现在运行时配置里,永不进可移植源。** 用户观察到:把 gskill 目录拷给别人,里面找不到"用哪个执行者"这种绑死宿主的信息。贡献北极星-4。引擎实现:格式契约里 `executor` 一次都没出现;实跑核实——把一行 `executor: cli` 加进 `graph.yaml`,`gskill compile` 从 `passed` 变成 `failed`,诊断是 `[F-v3-graph-schema-unknown-field]`「Extra inputs are not permitted」,定位到 `graph.yaml` 第 20 行、字段 `executor`。配置侧的执行者联合类型在 `domain/models.py:295`。上位依据:决议 `:221`。平行实现:暂无。
- **E-CFG-4 名字一看就是凭据的字段,不许直接写明文值。** 用户观察到:往 `api_key` 这类结构上像密钥的键里写明文,契约当场拒绝,只接受 `SecretReference` 这种引用形式。**边界要说清**:引擎判不出任意一个业务字符串是不是密钥,所以名字看不出来的键(例如 `opaque`)里写什么,由调用方自己负责分类——`AGENTS.md:52` 原句「A runtime cannot infer whether every arbitrary business string is secret, so callers must classify values that do not have secret-shaped keys.」实跑核实:`RunInvocation(inputs={"api_key": "sk-…"})` 构造失败,`RunInvocation(inputs={"opaque": "sk-…"})` 构造成功。贡献北极星-4(可移植)与"失败时对用户数据零副作用"这条工程底线。引擎实现:`domain/models.py:239` 的 `SecretBinding` 与它引用的 `SecretReference`。平行实现:网关的凭据真相存储。

### 3.3 G-EXE · 图执行与流程保真

**不变量**:走哪些相位、按什么顺序,由图决定,不由模型临场决定。
**贡献**:北极星-1、北极星-2。
**与种子的关系**:是种子域 G4(执行 + 观测)的前半。拆开的理由:执行守的是"忠于图",观测守的是"发生的都看得见",两者可以各自单独失败,合在一起会让"跑对了但看不见"和"看得见但跑错了"共用一个格子。

- **E-EXE-1 不调用模型也能看清这次会走哪条相位序列。** 用户观察到:干跑一次(predict),拿到确定性的路径与每步的占位输出,不花模型调用的钱。贡献北极星-1、北极星-2、北极星-5。引擎实现:`gskill predict`,`application/service.py:60`,内部在 `core/_predict_internal/`。平行实现:工作台的 Predict 按钮。
- **E-EXE-2 真跑按编译出来的图执行到底,并返回结构化结果。** 用户观察到:一条命令跑完整个流程,拿到一份可被程序读的结果对象,不是一段自由文本。贡献北极星-1。引擎实现:`gskill run`,`application/service.py:65`,`core/runner.py`。平行实现:工作台的 Run 按钮(同一条路径的界面投影)。
- **E-EXE-3 LOGIC 相位执行注册好的 Python 动作与校验器。** 用户观察到:确定性的步骤由代码做,不交给模型即兴发挥。贡献北极星-1。引擎实现:`core/actions.py`、`core/validators/`;能力条目 `spec/features.yaml` 的 `F-logic-action-execution`。平行实现:暂无。
- **E-EXE-4 子图按声明的父子输入输出边界执行,不串味。** 用户观察到:子图只看得到父图交给它的那部分数据。贡献北极星-1、北极星-2。引擎实现:`spec/features.yaml` 的 `F-subgraph-delegation`,装配在 `core/graph_assembler.py`。平行实现:暂无。
- **E-EXE-5 批量与循环(iterate)按声明执行。** 用户观察到:声明"对这批数据每条跑一次"就真的每条跑一次,次数与顺序可预期。贡献北极星-1。引擎实现:`spec/features.yaml` 的 `F-iterate-runtime`。平行实现:暂无。

### 3.4 G-AGT · AGENT 相位的执行者供给

**不变量**:AGENT 相位交给谁执行,是一次运行的配置;执行者做不到的形状在起跑前就拒绝,不中途炸。
**贡献**:北极星-1、北极星-4、北极星-2。
**与种子的关系**:是种子域 G4(执行 + 观测)里"谁来跑 AGENT 相位"这一支。**不含**"把角色解析成模型":那一支单独立为 3.5 的 G-MDL,理由写在那一节。依据是决议 `:210` 原句「差异**只**落在新仓已有的 `AgentExecutor` Port 上,**不新增任何机制**」——分叉点是执行者,而角色到模型的解析在决议 `:235` 是另一个 Port。

- **E-AGT-1 AGENT 相位能由一个能自主用工具的执行者跑完,结果写回同一次运行。** 用户观察到:流程跑到需要 agent 的那一步不会停死。贡献北极星-1。引擎实现:Port `ports/runtime.py:31` 的 `AgentExecutor`;今天有三种执行者配置——`HostNativeExecutorConfig`(`domain/models.py:248`)、`CliExecutorConfig`(`:253`)、`EmbeddedExecutorConfig`(`:287`)。**已裁定但尚未执行的差异**:决议 `:230` 把执行者闭集裁为 `embedded` 与 `ah` 两个,`:256` 要求删除 `host-native` 本体;而本仓今天的默认执行者仍是 `host-native`(`AGENTS.md:54`)。这是一条未执行的工单,不是本文新裁的事;实施顺序由决议 `:270` 起的 §5.9 给定。**第二处已裁未执行的差异**:决议 `:227-228` 要求执行者的解析链有两级——`RunRequest.executor` 是本次运行的全局默认,`RunPreset.node_overrides[<相位>].executor` 是相位级覆盖;而 `domain/models.py:404-409` 的 `NodeOverride` 今天只有 `address`、`timeout_seconds`、`custom_params` 三个字段,**没有 `executor`**。后果是:一份 gskill 里两个 AGENT 相位要用不同执行者,今天表达不出来。平行实现:暂无。
- **E-AGT-2 起跑前逐相位核对执行者的支持面,不支持就以原因码拒绝。** 用户观察到:执行者做不到的能力,在没花任何模型调用钱之前就被告知。贡献北极星-1、北极星-5。引擎自有实现:**缺口**。今天有一件相邻但不同的事:命令行执行者路径在创建交接件之前探测可执行文件、版本、必需参数与登录状态(`AGENTS.md:62`)——那是"这个工具装没装好",不是"这个相位要的能力它支不支持"。决议 `:242` 起要求的"在 `resolve_run` 阶段逐相位核对工具、子 agent、上下文访问、迭代与并行形状"尚未存在。平行实现:暂无。
- **E-AGT-3 AGENT 的输出按 JSON Schema 校验,不合格就不消费这次任务。** 用户观察到:agent 返回的结构不对时,流程报错,而不是把坏数据写进图状态。贡献北极星-1。引擎实现:`AGENTS.md:58` 与 `:68` 定语义;能力条目 `F-finish-task-validation`。平行实现:暂无。
- **E-AGT-5 没设角色就编译报错,不悄悄套一个默认角色。** 用户观察到:漏配角色时编译红,并被告知去哪里配。贡献北极星-1、北极星-5。引擎实现:已落地——`core/loader.py:381` 抛 `[F-v3-agent-llm-role-missing]`,`core/error_registry.py:113` 登记它为编译期 FATAL;`grep -rn "DEFAULT_LLM_ROLE" src/ --include=*.py` 返回 0 行,说明旧的兜底已删净。平行实现:工作台的角色配置提示。

本域没有 `E-AGT-4`:原先编在这个号下的"角色到模型的解析"已移入 3.5 的 G-MDL,新编号是 `E-MDL-1`。这里不重排其余编号,以免同一条承诺出现两个号。

### 3.5 G-MDL · 角色到模型的解析与凭据

**不变量**:把一个角色名解析成一个可调用的模型,这件事是确定的、按声明顺序回退的,而且凭据一路只以引用形式出现、不落明文。
**贡献**:北极星-1、北极星-2、北极星-4。
**与种子的关系**:等于种子域 G3(模型 + 媒体供给)的前半——"模型供给"。旧仓 G3 报告 `ac08659a6d5b556a3_v1.md:11` 给这一支的一句话 Effect,原文是:把「用户手里的一把 key + 一个 URL」变成「可被角色消费的、带证据的可用模型」,且每一次判定都能说出它凭什么这么判。**它为什么不并进 G-AGT**:两者能各自单独失败——角色解析对了而执行者不支持某项能力,或执行者一切正常而某个角色没有可用模型;合成一个域会让两处缺口互相遮蔽,owner 也说不清。上位依据是决议把它们写成两个 Port:`:210` 原句「差异**只**落在新仓已有的 `AgentExecutor` Port 上,**不新增任何机制**」把执行定为唯一分叉点,而 `:235` 另立一个 Port——「其中"角色 → 模型"的解析经 **`ModelResolver` Port** 完成,**gateway 包是该 Port 的权威实现**」。种子域 G3 的后半"媒体供给"没有并进来,理由见 7.3 的待裁项。

- **E-MDL-1 把一个"角色"解析成一个可调用的模型。**(本文首版编在 `E-AGT-4`,现移到本域,编号以此处为准。)用户观察到:gskill 里写"这一步用 balanced 角色",运行时就有一个具体模型被调用;某个模型不可用时按声明的顺序退到下一个;凭据从头到尾只以引用形式出现。贡献北极星-1、北极星-2。引擎自有实现:**缺口**。三处证据:①`grep -rn "ModelResolver" src/graph_skill_runtime --include=*.py` 返回 0 行;②`core/graph_assembler.py:213` 的参数是 `model_resolver: Any = None`,靠外部注入;③`:2427` 处 `if model_resolver is None: return None`——没有注入就没有模型。**0 到 1 的参照物**:旧仓**历史提交** `c7405b7e` 里的 `config/llm_roles.yaml`、`config/multimodal_roles.yaml` 与 `src/core/graph_agent/config/llm_config.py`,即用户说的"一份 YAML 记角色和退让顺序,一个组件读它"。这三份要按历史提交读:旧仓当前工作树(`main` `dcb12e40`)只还留着 `config/llm_roles.yaml`,另外两份已不在树里。平行实现:网关(旧仓 `packages/graph-agent-gateway`,含 `registry` / `resolve` / `role` / `probing` / `call` / `dialect` / `media` 等模块)是这条 Effect 的 1 到 10;决议 `:235` 已把它定为 `ModelResolver` Port 的权威实现。

### 3.6 G-STA · 运行状态的持久与续跑

**不变量**:一次运行的状态只有一个所有者;续跑读的就是那一份,不是复制品。
**贡献**:北极星-1、北极星-4、北极星-5。
**与种子的关系**:从种子域 G1 分出。理由同 3.2:持久化守的是"状态唯一且可恢复",与"配置解析确定"是两回事。

- **E-STA-1 图状态按代落盘。** 用户观察到:流程跑到一半机器断了,状态还在。贡献北极星-1。引擎实现:Port `ports/runtime.py:40` 的 `CheckpointStore`,实现在 `core/checkpointer.py`。平行实现:暂无。
- **E-STA-2 中断之后,拿得回那次运行的当前等待态。** 用户观察到:`gskill resume` 带上运行编号与检查点引用,把"这次运行停在哪、在等什么"原样再取一次。**这条不等于"接着往下跑"**——`adapters/host_native_runtime.py:266-292` 对一个已有的检查点只返回它已记下的响应,或它正在等的那个请求;不带检查点引用调用则返回 `GSKILL_NOT_IMPLEMENTED`(`:293-298`,消息原句「resume without a host-native checkpoint_ref is not implemented yet」)。真正让运行往前走的入口是 `gskill submit`(MCP 侧 `submit_agent_result`),见 E-STA-4。**另一处缺口**:`AGENTS.md:58` 原句「Standalone typed human/breakpoint resume is not complete.」——独立的人工应答与断点续跑尚未完成。贡献北极星-1、北极星-5。平行实现:工作台的续跑按钮。
- **E-STA-3 运行产物落盘,并在运行结果里给出稳定引用。** 用户观察到:流程产出的文件有固定的引用地址,拿着运行结果就能找回来。贡献北极星-5。引擎自有实现:**缺口**。三处证据:①`ports/runtime.py:48` 的 `ArtifactStore` 只有 Port,包里没有随附实现;②默认组合 `composition.py:14-26` 的 `create_application` 只注入配置解析器、引擎与请求快照存储,不注入 `ArtifactStore`;③`domain/models.py:626-637` 的 `RunResult` 字段是 `status` / `run_id` / `mode` / `request` / `outputs` / `trace_path` / `error` / `agent_required` / `diagnostics`,**没有产物引用**。`core/artifacts.py:58` 的 `build_compiled_artifact_manifest` 建的是**编译期**产物清单,不是运行产物的存储。`core/runner.py:473` 有一个内部的 `artifact_saver` 注入点,公开用例够不着它。平行实现:工作台的产物面板。
- **E-STA-4 重复提交同一个结果是幂等的。** 用户观察到:同一份 agent 结果提交两次,拿到同一个答案;换成不同内容则冲突报错,而不是覆盖。贡献北极星-1。引擎实现:语义写在 `AGENTS.md:58`;入口 `gskill submit` 与 MCP 工具 `submit_agent_result`。平行实现:暂无。

### 3.7 G-OBS · 去黑盒:事件、轨迹与检视

**不变量**:发生了的事必须能被外部逐条看到;看不见的环节是缺陷候选。
**贡献**:北极星-5。
**与种子的关系**:是种子域 G4 的后半独立成域,理由见 3.3。

- **E-OBS-1 每个环节发出带类型的事件,外部能接上自己的接收端。** 用户观察到:能按事件逐条知道流程走到哪、发生了什么;挂上自己的接收端不改变执行语义。贡献北极星-5。引擎实现:**部分**。内部齐备:Port `ports/runtime.py:54` 的 `EventSink`、事件模型 `callbacks/events.py`、契约 `core/event_contracts.py`、现成回调 `callbacks/__init__.py:10` 导出的 `LoggingCallback` / `MetricsCallback` / `TracingCallback`;`spec/features.yaml` 登记了 54 个不重复的事件类;默认跑一次会自动落下 `trace.jsonl` 与 `metrics.json` 两份文件(本次实跑核实)。**公开面没有接线口**:`sdk.py:62` 的 `run(invocation, *, application)` 没有回调或 `EventSink` 参数,默认组合也不注入——`docs/public-api-contract.md:166` 原句「The default composition does not inject an `EventSink`.」;`core/runner.py:472` 的 `event_subscriber` 是内部参数,公开用例够不着。所以"事件被发出并落成文件"成立,"外部挂自己的接收端"不成立。平行实现:工作台的运行日志面板。
- **E-OBS-2 每次进入执行阶段的运行,留一份可回读的轨迹文件。** 用户观察到:跑完之后运行结果里的 `trace_path` 指向一份 `trace.jsonl`,能逐步复核每个相位收到什么、模型被怎么提问、返回了什么。**边界**:编译阶段就失败的运行没有轨迹,只有诊断——本次实跑核实,把 `gskill run` 指向一个没有 `SKILL.md` 的目录,结果是 `status=failed`、`trace_path=None`、错误码 `GSKILL_COMPILE_FAILED`;而正常跑通 `hello-world` 时 `trace_path` 指向 `<state_root>/runs/<run_id>/trace.jsonl`。贡献北极星-5。引擎实现:结果里的 `trace_path`(`adapters/result_mapping.py:65`),读取与累计在 `callbacks/emit.py:114-135`,步骤模型 `tracing/steps.py`。平行实现:工作台的 trace 视图。
- **E-OBS-3 失败带稳定原因码,并给出它能给到的最细位置。** 用户观察到:报错是一个可被程序断言的编号加位置,不是一句自由文本。位置分两档:**编译期**失败定位到文件与行(实跑核实:`[F-v3-graph-schema-unknown-field]`,`graph.yaml` 第 20 行,字段 `executor`);**运行期**失败定位到出事的相位。**边界**:相位还不存在时发生的失败给不出相位——同一次实跑里,编译阶段失败的 `error.phase` 与 `error.source_path` 都是 `None`,只留错误码 `GSKILL_COMPILE_FAILED`,细节在结果的 `diagnostics` 里。贡献北极星-5、北极星-1。引擎实现:`core/error_registry.py` 的 `ERROR_REGISTRY`(99 条,每条带严重级与所属阶段);错误信封 `domain/models.py` 的 `RuntimeErrorPayload`,字段含 `code` / `phase` / `source_path` / `details` / `retryable`。平行实现:工作台的错误提示。
- **E-OBS-4 检视编译产物的拓扑与调用关系。** 用户观察到:不跑也能看清这份 gskill 有哪些相位、怎么连、谁调谁。贡献北极星-5、北极星-2。引擎实现:`gskill inspect`,`core/topology_projection.py`;MCP 侧要求以 `cache=false` 编译,查询不得污染编译缓存(`AGENTS.md:42`)。平行实现:工作台的画布。
- **E-OBS-5 正在跑的运行能被实时订阅。** 用户观察到:一次长时间运行跑到哪了,可以边跑边看,而不是等它结束再读文件。贡献北极星-5。引擎自有实现:**缺口**。证据:`grep -rn "def subscribe" src/graph_skill_runtime --include=*.py` 返回 0 行;`ports/runtime.py:54` 的 `EventSink` 只有 `emit` 一个方法,是推出口,外部无法主动订阅。上位要求:决议 `:262` 起的 §5.7——run 是长任务,需要异步任务模型,且它与实时事件订阅必须并为同一个 Port。平行实现:工作台今天用自己的 WebSocket 通道达成同样效果。

### 3.8 G-EVA · 评测

**不变量**:一个 gskill 做得对不对,由可复核的判据说了算,不由一次观感。
**贡献**:北极星-1、北极星-5。
**与种子的关系**:是种子域 G5(评测 + 工作台)的前半。后半"工作台"按 2.2 的规则不是域级 Effect,它是 G-OBS 与 G-ACC 若干条 Effect 下的平行实现,所以从域级表里移出。

- **E-EVA-1 用 golden 基线跑一次评测,得到一个可复核的结论。** 用户观察到:把一次认可的运行存成基线,以后每次改动都能对着它判"变好还是变坏"。贡献北极星-1、北极星-5。引擎实现:`gskill golden`,`application/service.py:90`,实现在 `core/_predict_internal/golden_eval.py:193`;MCP 工具名 `evaluate_golden`。平行实现:工作台的评测面板。
- **E-EVA-2 确定性替身让离线也能跑出可比的结果。** 用户观察到:没有网络、没有模型凭据的机器上也能跑测试,并得到稳定结论。贡献北极星-1。引擎实现:`spec/features.yaml` 的 `F-predict-internal-mocking`,替身在 `core/_predict_internal/stub.py`。平行实现:暂无。

### 3.9 G-AUT · 创作与理解

**不变量**:用户不必先学框架,就能做出一份正确的 gskill,并看懂自己做出来的是什么。
**贡献**:北极星-2。
**与种子的关系**:等于种子域 G6(创作),但内容按用户 2026-09-03 关于层级的原话重排:上级承诺写"能观察节点图、能不手敲代码建出节点图",引擎的实现是 MoirAI 代理人,工作台画布是与它同级的另一种实现。

- **E-AUT-1 有一个代理人带着用户从"想做什么"走到一份能编译的 gskill。** 用户观察到:在自己手边的 agent 工具里,有一个角色会问清领域概念、定出拓扑与数据契约,并给出可编译的源。贡献北极星-2。引擎实现:MoirAI 资产 `integrations/assets/moirai/integration.json` 里的 `moirai` 与 `moirai-clotho` 角色,以及 `moirai-domain-analysis` / `moirai-graph-design` / `moirai-agent-prompt-design` / `moirai-brainstorming` 四个技能。平行实现:工作台的新建向导。
- **E-AUT-2 编译失败时,有人能定位到最小的权威源并修好。** 用户观察到:拿着一份完整诊断,有角色告诉他改哪一处、为什么是那一处。贡献北极星-2、北极星-5。引擎实现:MoirAI 的 `moirai-lachesis` 角色与 `moirai-compile-repair` 技能,知识库 `KB-07-compile-diagnostics.md`。平行实现:工作台把诊断直接标在画布节点上。
- **E-AUT-3 能观察 graph 节点图。** 用户观察到:看得见这份 gskill 长什么样——有哪些节点、怎么连。贡献北极星-2、北极星-5。引擎实现:**本域不另有实现,复用 `E-OBS-4` 的那一条**——`gskill inspect` 的拓扑投影(`core/topology_projection.py`);MoirAI 知识库 `KB-05-subgraph.md` 只负责教会代理人怎么读它。所以这里是同一处实现的第二个用途,不是第二处实现。平行实现:工作台画布。
- **E-AUT-4 不手动敲代码就能把设计好的节点图建出来。** 用户观察到:说清想要的流程,就得到对应的节点与连线,不必逐字写 `graph.yaml`。贡献北极星-2。引擎实现:MoirAI 的 `moirai-clotho` 角色与 `moirai-graph-design` 技能。平行实现:工作台画布的拖拽新建节点——按用户原话,它「是和"用 moirai agent 来实现"的模块同级的模块」。

### 3.10 G-ACC · 接入面

**不变量**:**同一个用例在各投影里的规则只有一份**——投影只做翻译,不各自实现规则。注意这条**没有**说四种投影覆盖同一套用例:哪个用例出现在哪几个投影里是各自的刻意选择,下面的覆盖矩阵逐格写明。
**贡献**:北极星-3、北极星-4、北极星-2。
**与种子的关系**:从种子域 G7(委托 + 发布 + 平台)里分出"怎么被调用"这一半。分开的理由:接入面守"规则只有一份",发货守"别的机器装得出同一份",删掉任一方都会毁掉一个行为区分。

- **E-ACC-1 在 Python 里 import 一个包,就能用引擎的八个运行用例加宿主投影安装。** 用户观察到:一个稳定的、写下来的公开接口清单,不必去读内部实现。(不含旧格式转换,理由见下面矩阵。)贡献北极星-3、北极星-4。引擎实现:门面 `sdk.py`(13 个公开函数),顶层契约 `graph_skill_runtime.__all__` 实测 77 个符号,文档 `docs/public-api-contract.md`(frontmatter `role: contract`,`status: living`)。平行实现:暂无。
- **E-ACC-2 命令行 `gskill` 是覆盖面最全的那一条投影。** 用户观察到:不写 Python 也能编译、干跑、真跑、取回等待态、检视、评测、转换旧格式、装宿主投影,以及把 MCP 服务起起来。贡献北极星-2、北极星-4。引擎实现:`adapters/cli.py:166` 起注册的子命令——`compile`、`config resolve`、`predict`、`run`、`resume`、`submit`、`inspect`、`golden`、`migrate studio-skill`、`integrations detect|install|uninstall`、`mcp`。平行实现:工作台的按钮。
- **E-ACC-3 外部 agent 通过 MCP 调用引擎的八个运行用例。** 用户观察到:在 Claude Code 或 codex 里直接把引擎当工具用。贡献北极星-3、北极星-2。引擎实现:`adapters/mcp.py:31` 起,服务名 `gskill`,恰好 8 个工具——`compile`、`resolve_run`、`predict`、`run`、`resume`、`submit_agent_result`、`inspect`、`evaluate_golden`;每个工具必须声明状态影响标注(`AGENTS.md:42`)。平行实现:工作台的 HTTP 接口。
- **E-ACC-4 把 MoirAI 投影进宿主,是一次显式、冲突即拒、可回滚的操作。** 用户观察到:装之前先体检,任一目标冲突就整体不动;卸载只删自己装的那些、且内容没被改过的那些。贡献北极星-2。引擎实现:`integrations/installer.py`、`integrations/renderers.py`,规则写在 `AGENTS.md:44`;命令 `gskill integrations install moirai --targets ... --scope ...`。平行实现:暂无。

**用例 × 投影覆盖矩阵。** 空格一律标"刻意"或"缺口",不留白。MoirAI 那一列的依据是:它的宿主投影注册的是同一个 `gskill` stdio MCP 服务(`AGENTS.md:40` 原句「register the same single `gskill` stdio MCP server」),所以 MoirAI 能够到的用例集合**就等于** MCP 那一列。

| 用例 | Python SDK | 命令行 `gskill` | MCP | MoirAI |
|---|---|---|---|---|
| 编译 | 有 | 有(`compile`) | 有 | 有 |
| 解析运行请求 | 有 | 有(`config resolve`) | 有 | 有 |
| 干跑 | 有 | 有(`predict`) | 有 | 有 |
| 真跑 | 有 | 有(`run`) | 有 | 有 |
| 取回等待态 | 有 | 有(`resume`) | 有 | 有 |
| 提交 agent 结果 | 有 | 有(`submit`) | 有 | 有 |
| 检视拓扑 | 有 | 有(`inspect`) | 有 | 有 |
| golden 评测 | 有 | 有(`golden`) | 有 | 有 |
| 旧格式转换 | 刻意无 | 有(`migrate studio-skill`) | 刻意无 | 刻意无 |
| 宿主投影安装 | 有(5 个函数) | 有(`integrations detect/install/uninstall`) | 刻意无 | 刻意无 |
| 启动 MCP 服务 | 不在公开契约内 | 有(`mcp`) | 不适用 | 不适用 |

矩阵里没有一格是遗漏,逐格依据如下:

- **旧格式转换只留在命令行**:`docs/public-api-contract.md:26` 原句「Legacy parsing is confined to the explicit `gskill migrate studio-skill` converter.」旧格式的读法被关进这一个显式边界;少一个入口,就少一处让它变成"编译失败后自动兜底"的机会。这正是 E-FMT-4 那条承诺的另一面。
- **MCP 恰好八个用例**:`AGENTS.md:42` 原句「The `gskill` MCP server exposes exactly `compile`, `resolve_run`, `predict`, `run`, `resume`, `submit_agent_result`, `inspect`, and `evaluate_golden`.」"exactly"是闭集声明,不是当前进度。
- **宿主投影安装不进 MCP**:安装会写用户宿主的配置文件,而 MCP 工具是被外部 agent 自动调起的。`AGENTS.md:44` 原句「Detection is evidence, not authorization.」授权被限定在显式的命令行或 SDK 调用上。
- **"启动 MCP 服务"在 SDK 侧不在公开契约内**:`adapters/mcp.py:26` 有 `create_server`,但它不在 `__all__` 的 77 个符号里。这一格标的是事实,不是刻意与否的判断。

### 3.11 G-SHP · 发货与环境复现

**不变量**:本地做出来的东西,能在别的机器上装出同样的一份。
**贡献**:北极星-4。
**与种子的关系**:种子域 G7 的另一半,理由见 3.10。

- **E-SHP-1 装一个包就有全部能力,用户的业务 gskill 不随包发。** 用户观察到:安装包里没有别人的业务技能,也不会有人偷偷注册或改写他自己的技能目录。贡献北极星-4、北极星-3。引擎实现:边界写在 `AGENTS.md:38`;打包内容由 `scripts/accept_release_artifacts.py` 的 `validate` 逐条断言(`AGENTS.md:78`)。平行实现:暂无。
- **E-SHP-2 我在自己的平台上装得上、跑得起来,而且这份发布随附三平台的验收证据。** 用户观察到:在 Windows、macOS 或 Linux 上装完这个包,`gskill` 命令能用、能编译能跑;同时这份发布带着"同一对产物在三个平台都通过了"的证据,而不是只说"开发机上是绿的"。贡献北极星-4,以及决议第 143 行"证据环境 = 发货环境"这条行为原则。引擎实现:三平台验收由 `scripts/accept_release_artifacts.py` 的 `accept` 执行——它是仓内的**取证手段**,不随包发,所以它本身不是这条承诺;范围写在 `AGENTS.md:80`,具体运行、产物身份与结果记在 `docs/CROSS_PLATFORM.md`。平行实现:暂无。
- **E-SHP-3 锁定版本的引擎加锁定版本的格式,本地做的 gskill 原样在服务端跑。** 用户观察到:同一份 gskill 交给服务端,跑出同一条相位序列。贡献北极星-4。引擎自有实现:**缺口**。证据两处:决议 `:74` 原话「**未实现**」;`AGENTS.md:20`「The project is not published on PyPI or TestPyPI.」——没有发布,"锁定版本"就没有可锁的对象。平行实现:暂无。

### 3.12 与七个种子域的差异汇总

下面两张表回答同一个问题的两个层次:第一张说每个种子**域**去了哪里,第二张说种子域里点过名的每项**能力**去了哪里。第二张之所以必要,是因为 2026-08-31 的域报告里,域的名字和它实际点名的能力并不总是一回事——G1 叫"运行时底座 + 契约基建",但它报告里列的六条 Effect 讲的是桌面应用的 sidecar 生死、横幅、重启预算、错误信封与原因码册。只对着域名对账会漏掉这些。

| 种子域 | 本文的归宿 | 理由 |
|---|---|---|
| G1 运行时底座 + 契约基建 | 这个**域名**下的引擎侧内容拆成 G-CFG(解析与快照)与 G-STA(状态与续跑);而 G1 报告实际点名的六条 Effect 大多是工作台侧能力,逐条归宿见下面第二张表 | 前两者守的不变量不同(解析确定可追溯 / 状态唯一可恢复),可以各自单独失败;而 sidecar 生死、横幅、CORS 这些只在"把引擎包成 HTTP 服务"之后才存在,引擎自己是不开 HTTP 服务的 SDK(决议 `:25` 原句「纯软件开发工具包(SDK,即被别的程序调用的代码库,自己不开 HTTP 服务)」) |
| G2 gskill 格式 + 编译诊断 | 原样成为 G-FMT | 不变量一致,无需改动 |
| G3 模型 + 媒体供给 | "模型供给"单独立为 **G-MDL**;"媒体供给"未立域级 Effect | 模型供给与执行者供给能各自单独失败,合并会让两处缺口互相遮蔽,而决议 `:210` 与 `:235` 本来就把它们写成两个 Port;媒体供给一侧引擎无实现,是否立为域级承诺属目标层,见 7.3 待裁项 |
| G4 执行 + 观测 | 拆成 G-EXE、G-AGT、G-OBS | 忠于图、有人能跑 AGENT、发生的都看得见,是三个可以分别失败的承诺 |
| G5 评测 + 工作台 | 评测成为 G-EVA;工作台移出域级表 | 按 2.2 规则①,工作台不是域,它的每个模块是既有 Effect 下的平行实现 |
| G6 创作 | 成为 G-AUT,并按 2.1 第四段原话重排层级 | 上级承诺是"能观察、能不敲代码建图",MoirAI 与画布是它下面两个同级实现 |
| G7 委托 + 发布 + 平台 | 拆成 G-ACC(接入面)与 G-SHP(发货) | 规则只有一份,与别的机器装得出同一份,是两个不同的承诺 |

**种子能力逐条对账。** 只列种子域报告里点过名的能力;"归工作台平行实现"意思是这条能力真实存在、但它不是引擎对用户的承诺,而是某条既有 Effect 之下工作台那一侧要自己解决的问题。

| 种子域 | 报告里点名的能力 | 本文的归宿 |
|---|---|---|
| G1 (`a2b6b29566a8e3097_v1.md:21-24`) | E1 UI 立即可交互 / E2 sidecar 死活判定与横幅 / E3 自动恢复有上限 / E4 人按 Retry 不被预算拒绝;模块 M1 `SidecarProcess`、M2 `SidecarSupervisor`、M3 `RestartBudget`、M4 `BackendLivenessSignal`、M5 `RuntimeGate`、M8 `CorsOnEveryResponse`、M9 `ReaderFacingMessage`(`:469-470`) | **不立为域级 Effect**,归工作台平行实现。理由:这些问题只在"把引擎包成一个常驻 HTTP 服务"之后才存在,而引擎是不开 HTTP 服务的 SDK。删掉工作台,这些问题一条都不剩;删掉引擎,它们全部失去意义 |
| G1 (`:25`) | E5 任何失败响应都是同一个信封,带机器码 + 结构化 details;模块 M6 `ErrorEnvelope` | 归 **E-OBS-3**。引擎侧的信封是 `RuntimeErrorPayload`(`code` / `phase` / `source_path` / `details` / `retryable`);HTTP 状态码怎么映射是工作台那一侧的事 |
| G1 (`:26`) | E6 每个原因码入册(唯一定义处 + HTTP 投射 + 重试策略 + 读者文案);模块 M7 `ReasonCodeRegistry` | 归 **E-OBS-3**。引擎侧的册子是 `core/error_registry.py` 的 `ERROR_REGISTRY`,99 条;HTTP 投射与读者文案归工作台 |
| G1 (`:454`, `:469`) | M10 `ApiContractCodegen`(从契约生成前端类型并设门禁) | 归 **E-ACC-1**。引擎侧的唯一契约源是 `__all__` 加 `docs/public-api-contract.md`;从它生成别的语言的类型,是消费方的事 |
| G3 域一 (`ac08659a6d5b556a3_v1.md:11,15`) | 把一把 key 加一个 URL 变成可被角色消费、带证据的可用模型;own endpoint 身份与凭据、route、每条 route 最近一次真实询问的证据、role→FallbackChain | 归 **E-MDL-1**(引擎侧是缺口);网关是这条 Effect 的平行实现,并被决议 `:235` 定为 `ModelResolver` Port 的权威实现 |
| G3 域二 (`:249-257`) | 媒体 provider 的凭据、探测、catalog、模型设置 | **未立域级 Effect**,列为待裁项 7.3 |
| G4 域一 (`aeed340fbc0847f26_v1.md:21`) | `predict` 不花钱预演路径;`run` 按图确定性编排 | 归 **E-EXE-1**、**E-EXE-2** |
| G4 域一 (`:21`) | 可暂停 / 断点 / HITL(人工介入应答)/ 续跑 | 归 **E-STA-1**、**E-STA-2**;其中"独立的人工应答与断点续跑"是 E-STA-2 里已登记的缺口(`AGENTS.md:58`) |
| G4 域一 (`:21`) | AGENT 执行者是运行时参数:闭集、相位级可覆盖、preflight 兼容检查、无自动 fallback | 归 **E-AGT-1**(闭集与相位级覆盖两处缺口都已登记)与 **E-AGT-2**(preflight 缺口);"无自动 fallback"对应待裁项 7.1 |
| G4 域一 (`:21`) | 批跑 / 迭代 / 并行受控 | 归 **E-EXE-5** |
| G4 域二 (`:179`) | 运行中每个细节可见;事件完整 / 准确 / 高效 | 归 **E-OBS-1**(公开接线口是缺口) |
| G4 域二 (`:179`) | 投影为 trace、运行报告、实时流 | trace 归 **E-OBS-2**(运行目录里同时落 `result.json` 与 `metrics.json`,这就是引擎侧的"运行报告");实时流归 **E-OBS-5**,是缺口 |
| G7 域一 (`a66fac8a014fefd6b_v1.md:27`) | 用户不必手写 gskill 源文件,让 agent 代写;三工位分工可编排 | 归 **E-AUT-1**、**E-AUT-2**、**E-AUT-4**;引擎侧的实现就是 MoirAI 的四个角色与八个技能 |
| G7 域一 (`:27`) | 落盘前用户看得见改了什么并能否决;关掉重开接着聊 | **不立为域级 Effect**,归宿主与工作台的平行实现。理由:这两条讲的是"人和代理人之间那场对话怎么保存、怎么复核",owner 是宿主的会话层,不是编译与执行的引擎 |
| G7 域二 (`:133`) | 一次 publish 产出内容寻址、版本锁定、可脱离源文件独立运行的资产 | 归 **E-SHP-3**(锁定版本这一半,今天是缺口) |
| G7 域二 (`:133`) | 团队三动作走 Gitea;社区目录上下行 verified 能力事实 | **不立为域级 Effect**,归工作台平行实现。理由:它们是围绕一个团队服务器与一个社区站点的协作能力,删掉工作台就不存在 |
| G7 域三 (`:217`) | 用户装完包看到的行为 = 开发者验过的行为;三个 OS 都能装 | 归 **E-SHP-1**、**E-SHP-2** |
| G7 域三 (`:217`) | 偏好 / 语言 / 主题记得住;升级、卸载、换机器各有说得出的行为 | **不立为域级 Effect**,归工作台平行实现。理由:引擎侧对应的只有配置优先级(E-CFG-1),界面偏好与安装器行为是桌面应用的事 |

---

## 4. 公理与原则

### 4.1 权威链:四层,自上而下

决议 `:95-104` 定的链条是:北极星 → 域级 Effect → 模块级 Effect → 膜契约与实现。说人话:最上面是"我们为什么要有这个东西",往下是"每个域对用户承诺什么",再往下是"每个公开能力成功时承诺什么、失败时暴露什么",最底下才是"函数签名、字段、原因码怎么写"。每一层都必须向上挂钩:一条域级 Effect 说不出它贡献哪条北极星,就必须显式写"不贡献"并解释它为什么还留着(决议 `:101`)。本文第 3 节的每条 Effect 都写了它贡献哪条北极星,没有出现"不贡献"的条目。

### 4.2 三条裁决规则

- **设计有歧义时自上而下裁**(决议 `:110-114`):先问上一层的 Effect 是什么,再看哪种读法服务它;两种读法都不服务时,结论是"设定本身错了",该改的是设定,不是在两个错读法里挑一个。
- **事实有争议时走三道检验**(决议 `:116-124`):先比日期,再找原话(权威文档的修订记录、引入该实现的提交、用户本人的话——不认自己写的旧摘要),最后回第一性原理推一遍;三道同向才动手。
- **自我声明不作证据**(决议 `:126-130`):文档写的"已完成"、注释写的"已支持"、报告写的"已验证",都不算目标已达成。**这条对本文同样生效:本文写下的每一条 Effect 都还只是承诺。**

### 4.3 八条行为原则在引擎仓怎么用

原文在决议 `:134-145`,这里逐条说它在本仓落到哪。

1. **原则高于载体。** 本文、`AGENTS.md`、代码,都只是当下的权威读数。读数与原则冲突,改读数。
2. **修缺陷先问设定是否本来就错。** 例:`E-AGT-5` 那条"没设角色就报错",修的不是某次报错,而是"允许悄悄套默认角色"这个设定。
3. **根因定性到原则,并当场做同族全量排查。** 修完一处,要在同一条原则约束下的全部同类位置扫一遍,而不是只修被报出来的那一处。
4. **门禁量化在封闭域上,不写事故实例补丁。** 例:原因码要针对"全部原因码"这个可枚举集合做断言,不给某一条特判。
5. **约束一律下沉为机器强制。** 能做成持续集成门禁的就做成门禁;不能的就做成交付物里的必填栏。只写在文档里靠人记得的约束,在本项目已被实证证明不成立。
6. **证据环境 = 发货环境。** 见 `E-SHP-2`:验收证据必须出自打包版。
7. **一个概念一处实现一个 owner。** 见 2.2 规则①:域级 Effect 树只有一份。
8. **覆盖按域计量,不按步计量。** 见第 5 节:覆盖不到的格子必须显式写"未覆盖 + 原因",不留白。

### 4.4 引擎仓特有的五条公理

1. **引擎不知道辅助模块的存在。** `AGENTS.md:36` 原句:「Core and application code must not import Studio or Gateway modules」。工作台的界面、原生文件行为、HTTP 路由,网关的凭据与路由真相,宿主会话状态,厂商进程,操作系统集成,网络行为——全部只能待在显式的适配器或集成层后面。
2. **业务 gskill 是用户资产。** `AGENTS.md:38` 原句:「A business gSkill is a user-owned asset.」安装包里可以带运行时自己的资源,但绝不打包、注册、全局发现、复制或改写用户的业务技能;技能路径永远由调用方显式给出。
3. **执行者是运行时配置,永不进可移植源。** 依据决议 `:221`。今天成立,证据见 `E-CFG-3`。
4. **证据环境 = 发货环境。** 依据决议 `:143`。开发模式下的绿只是参考信号。
5. **域级 Effect 树的唯一所有权在引擎。** 依据 2.1 的用户原话与 2.2 规则①。任何辅助模块的设计文档必须写明自己挂在哪条 Effect 下;写不出来就走 2.2 规则③的两种归宿。

---

## 5. 验收判据总表

判据统一是 2.3 那一句:**干净环境里只装引擎这一个包,这条 Effect 能不能达成。** 所以中间那一列只写**装完这个包就有的东西**——`gskill` 命令、Python SDK、MCP 服务、装好的 MoirAI 技能——不写仓内脚本,也不写对仓内文件的检索:`pyproject.toml:59-60` 规定这个包只装 `src/graph_skill_runtime`,拿到包的人手里没有仓库。

状态取三个值:**可达成**、**部分 + 缺口**、**未覆盖 + 原因**。

**这一列今天是按代码坐标判出来的,不是跑出来的。** 首次在干净环境里逐条实跑这张表,是一张独立工单;在那之前,这里的每一行都还只是承诺,不是证据(依据 4.2 第三条"自我声明不作证据")。

| 编号 | 只装引擎怎么达成 | 按坐标判定的状态 |
|---|---|---|
| E-FMT-1 | 自己写一份最小 gskill,`gskill compile <skill_root>` 返回 `status=passed`、诊断为空 | 可达成 |
| E-FMT-2 | 把一份有多处缺陷的 gskill 编译一次,诊断一次列全,每条带原因码、文件、行、字段 | 可达成 |
| E-FMT-3 | 在同一份 gskill 里放一个 `graphs/<graph_id>/`,让包内两个相位都引用它,`gskill compile` 通过 | 可达成 |
| E-FMT-4 | `gskill migrate studio-skill SOURCE DESTINATION` | 可达成 |
| E-CFG-1 | `gskill config resolve <skill_root>` 的输出里每个字段带 `value_origins` | 可达成 |
| E-CFG-2 | 跑一次后 `<state_dir>/runs/<run_id>/request.json` 存在;同一个 run_id 换内容再落,拒绝覆盖 | 可达成 |
| E-CFG-3 | 往自己的 `graph.yaml` 加一行 `executor: cli`,`gskill compile` 报 `[F-v3-graph-schema-unknown-field]` 并指到那一行那个字段 | 可达成 |
| E-CFG-4 | 构造 `RunInvocation(inputs={"api_key": "…"})` 被拒绝;换成 `opaque` 键构造成功——两个结果合起来才是这条承诺的完整真值 | 可达成 |
| E-EXE-1 | `gskill predict <skill_root> --state-dir <dir>` 返回相位序列,且没有发生模型调用 | 可达成 |
| E-EXE-2 | `gskill run <skill_root> --state-dir <dir>` 对一份只有 LOGIC 相位的 gskill 跑到 `status=completed` | 可达成 |
| E-EXE-3 | 同上,自己注册的 Python 动作与校验器被执行 | 可达成 |
| E-EXE-4 | 带子图的 gskill 跑通,父子输入输出边界被保持 | 可达成 |
| E-EXE-5 | 带 iterate 的 gskill 跑通,次数与顺序符合声明 | 可达成 |
| E-AGT-1 | `gskill run --executor host-native`(或 `--executor cli --vendor codex`)对带 AGENT 相位的 gskill 走到执行者并回写结果 | 部分 + 缺口:①决议 `:230` / `:256` 已把闭集裁为 `embedded` 与 `ah` 并要求删除 `host-native`,本仓默认仍是 `host-native`;②`NodeOverride` 没有 `executor` 字段,相位级覆盖(决议 `:227-228`)表达不出来 |
| E-AGT-2 | `gskill config resolve` 时逐相位核对执行者支持面,不支持就以原因码拒绝 | 未覆盖 + 原因:只有命令行执行者在创建交接件之前探测(`AGENTS.md:62`),决议 `:242` 要求的 `resolve_run` 阶段逐相位 preflight 不存在 |
| E-AGT-3 | `gskill submit --result-json` 交一份 schema 不合格的结果,任务不被消费 | 可达成 |
| E-AGT-5 | 对一份漏配 `llm_role` 的 AGENT gskill 编译,得到 `[F-v3-agent-llm-role-missing]` | 可达成 |
| E-MDL-1 | 只装引擎、不注入任何解析器,跑一个 AGENT 相位 | 未覆盖 + 原因:包里没有角色到模型的解析实现,`grep -rn "ModelResolver" src/graph_skill_runtime --include=*.py` 返回 0 行,`core/graph_assembler.py:2427` 无注入即返回 `None` |
| E-STA-1 | 用 SQLite 检查点存储跑一次,检查点按代写入那个文件 | 可达成 |
| E-STA-2 | `gskill resume <skill_root> <run_id> --state-root <dir> --checkpoint-ref <ref>` 取回当前等待态 | 部分 + 缺口:取回等待态可达成;不带检查点引用返回 `GSKILL_NOT_IMPLEMENTED`,且 `AGENTS.md:58` 记独立的人工应答与断点续跑未完成 |
| E-STA-3 | 从运行结果里拿到产物引用并据此取回产物 | 未覆盖 + 原因:包里没有 `ArtifactStore` 的实现,默认组合不注入它,`RunResult` 也没有产物引用字段 |
| E-STA-4 | `gskill submit` 同一份结果两次,第二次返回同一个结果;换内容则冲突报错 | 可达成 |
| E-OBS-1 | 挂上自己的接收端接事件 | 部分 + 缺口:默认落下的 `trace.jsonl` 与 `metrics.json` 可读;但公开 `run` 没有回调或 `EventSink` 参数,默认组合也不注入(`docs/public-api-contract.md:166`),外部接不上自己的接收端 |
| E-OBS-2 | 跑一次后读运行结果里 `trace_path` 指的那份 `trace.jsonl` | 可达成(编译阶段就失败的运行没有轨迹,这是承诺本身的边界,不是缺口) |
| E-OBS-3 | 制造一次编译失败,诊断指到文件与行;制造一次运行期失败,错误指到相位 | 可达成 |
| E-OBS-4 | `gskill inspect <skill_root> --call-graph` 返回拓扑与调用图 | 可达成 |
| E-OBS-5 | 运行进行中从外部订阅事件流 | 未覆盖 + 原因:没有订阅接口,`grep -rn "def subscribe" src/graph_skill_runtime --include=*.py` 返回 0 行,`EventSink` 只有 `emit`;决议 `:262` 要求的异步任务模型与订阅同一个 Port 尚未落地 |
| E-EVA-1 | `gskill golden <skill_root> <baseline_id> --state-root <dir>`(MCP 侧 `evaluate_golden`)给出结论 | 可达成 |
| E-EVA-2 | 在没有网络、没有模型凭据的机器上 `gskill predict` 得到稳定结果 | 可达成 |
| E-AUT-1 | `gskill integrations install moirai --targets <host> --scope project` 后,宿主里可用 `moirai` / `moirai-clotho` 角色与 `moirai-domain-analysis`、`moirai-graph-design`、`moirai-agent-prompt-design`、`moirai-brainstorming` 技能 | 可达成 |
| E-AUT-2 | 同上,`moirai-lachesis` 角色与 `moirai-compile-repair` 技能可用 | 可达成 |
| E-AUT-3 | `gskill inspect` 的拓扑输出,配合装好的知识库 `KB-05-subgraph.md` | 可达成 |
| E-AUT-4 | 用 `moirai-graph-design` 技能产出的 `graph.yaml`,`gskill compile` 通过 | 可达成 |
| E-ACC-1 | `python -c "import graph_skill_runtime as g; print(len(g.__all__))"` 输出 `77` | 可达成 |
| E-ACC-2 | `gskill --help` 列出全部子命令 | 可达成 |
| E-ACC-3 | 起 `gskill mcp`,从客户端枚举出恰好 8 个带标注的工具 | 可达成 |
| E-ACC-4 | `gskill integrations install moirai …` 遇冲突时整体不动;`gskill integrations uninstall` 只删自己装的、且内容未被改过的 | 可达成 |
| E-SHP-1 | 装完后 `python -c "import graph_skill_runtime, pathlib; print(list(pathlib.Path(graph_skill_runtime.__file__).parent.rglob('graph.yaml')))"` 返回空列表 | 可达成 |
| E-SHP-2 | 在自己的 Windows / macOS / Linux 上装完这个包,`gskill compile` 与 `gskill run` 跑通;并能读到这份发布的三平台验收证据 | 部分 + 缺口:装完能跑这一半可达成;"这份发布"这一半还不存在——没有发布,只有一次候选产物的三平台验收记录(`AGENTS.md:78-82`) |
| E-SHP-3 | 从公共包仓库按锁定版本装引擎,在服务端跑同一份 gskill,走出同一条相位序列 | 未覆盖 + 原因:决议 `:74` 记「**未实现**」;`AGENTS.md:20` 记项目未发布到 PyPI 或 TestPyPI,没有可锁定的发布版本 |


**汇总**:40 条域级 Effect 中,31 条可达成、4 条部分达成、5 条未覆盖。**未覆盖的 5 条**是 `E-AGT-2`(起跑前逐相位核对)、`E-MDL-1`(角色到模型的解析)、`E-STA-3`(运行产物的落盘与引用)、`E-OBS-5`(实时订阅)、`E-SHP-3`(锁定版本、服务端复现)。**部分达成的 4 条**是 `E-AGT-1`(执行者闭集未收敛、相位级覆盖缺字段)、`E-STA-2`(只能取回等待态)、`E-OBS-1`(事件发得出但外部接不上)、`E-SHP-2`(装得上跑得起,但还没有一份正式发布)。这 9 条集中在三处:AGENT 相位的供给链、运行侧的产物与实时可观察性、发布与服务端复现。它们分别对应决议 §5.3/§5.4(执行模型)、§5.7(异步任务模型与实时订阅)与北极星-4 的未实现现状,都是已裁定、待执行的工单,不是本文新提的需求。

---

## 6. 与既有文档的关系

- **本文的上位依据**:旧仓 `docs/design/gskill-restructure-decision-2026-08-31.md` 的 §1(北极星)、§2(权威链)、§3(行为原则)、§5(执行模型)、§7(盘点方法)。本文是它在引擎仓里的落地。
- **该决议的 §4.3(gateway 与 studio 整体迁入本仓、先搬后整、冻结旧引擎随迁)已于 2026-09-03 被用户推翻。** 本文不引用它作依据,也不依赖它成立。本文成立的前提只是 §4.2——引擎的唯一所有权在本仓(决议 `:160-164`)。
- **`AGENTS.md`(仓根)**:本仓的规则入口,今天是自下而上写成的实况描述——它记的是"现在实现成什么样"。按 4.1 的权威链,它应当从本文推导:每条规则说得出自己服务哪条 Effect。**这是一条后续工单,本文只登记,不执行。**
- **`docs/public-api-contract.md`**(`role: contract`,`status: living`):本文的下游,它是 `E-ACC-1` 那条承诺的可执行清单。
- **`docs/skill-spec/01-PORTABLE-GSKILL-V1.md`**(`role: contract`,`status: FROZEN`):本文的下游,是 G-FMT 域的契约载体。同目录的 `00-FORMAT-GROUND-TRUTH.md` 为 `superseded`,只作转换器输入与历史证据(`AGENTS.md:16`)。
- **`docs/design/v1-alignment.md`**(`status: drafted`):本文的下游,是实现阶段的对齐目标,不承载北极星。`docs/design/README.md`(`role: index`,`status: living`)负责路由现况与目标;`docs/design/baseline.md`(`status: drafted`)是抽仓之前的历史证据,不是当前路径地图。
- **`docs/mvp0`(36 份)与 `docs/mvp1`(61 份)**:旧引擎时代的文档,今天仍在仓里。按本 PR 的 head 实测:`git ls-files docs | wc -l` 为 **120**,其中 `docs/mvp0` 36、`docs/mvp1` 61、`docs/skill-spec` 15、`docs/design` 4、根下 **4**(`CROSS_PLATFORM.md`、`feature-compliance-checklist.md`、`public-api-contract.md`,加上本文自己)。它们会把读到的 agent 带偏。同时有三处测试耦合着它们:`tests/contract-seals.yaml` 的 17 条封印里 14 条指向 `docs/mvp0`;`tests/test_doc_hash_lock.py:13` 的 `DOCS_ROOT` 指向 `docs/mvp1`;`tests/test_doc_pointer_liveness.py:54` 的 `CONTRACT_DOC_STATUSES` 只认 `living` 与 `FROZEN`。**清理是独立工单,本文只登记这个事实,不执行。**

---

## 7. 待裁项

以下三条本文不替用户裁,只写清问题、建议与依据。

### 7.1 `fallback_executors` 是一个没有消费者的公开字段

**问题**:配置与契约里可以声明"主执行者不可用时退到哪些执行者"(`application/config.py:96`、`domain/models.py:337` 与 `:357`,并有校验拒绝重复项),但全仓没有任何地方读它来真的换执行者——`grep -rn "fallback_executors" src/graph_skill_runtime --include=*.py` 的 12 处命中全部落在配置搬运与校验里。而决议 `:248` 已明确「**绝不静默换执行者**:**没有自动 executor fallback**」,`AGENTS.md:50` 也只说它是一个"声明"。

**建议**:删掉这个字段及其校验,同一次变更删净,不留双路径。

**依据**:决议 `:248`(没有自动 fallback)+ 行为原则第七条"一个概念一处实现一个 owner"(决议 `:144`)+ 本仓无向后兼容义务(`AGENTS.md:88`)。它今天是一个用户能填、填了没有任何效果的旋钮,按北极星-2 的反向判据,这类旋钮本身就是负担。

### 7.2 六个直连厂商命令行执行者的删除代价

**问题**:决议 `:274` 要求「删除六个直连厂商命令行 adapter」,由 `ah` 统一承担进程监督;而本仓的 Phase 4 刚把这六个(Claude、Codex、GitHub Copilot、Cursor、Gemini、OpenCode)做完并写进已验收范围(`AGENTS.md:64`),其中 Codex CLI `0.144.1` 在 Windows 上有真实操作证据(`AGENTS.md:72`)。按决议执行等于把这批已验收的能力与证据一并作废。

**建议**:按决议删。理由是进程监督、沙箱、崩溃恢复不该在引擎里重造第二份(决议 `:240`),而"少一条执行者路径"直接服务北极星-1(可重现)与北极星-4(服务端也成立)。但因为代价是可见的已交付能力作废,呈请用户确认这个代价仍然接受。

**依据**:决议 `:274`(实施顺序第三步)与 `:240`(ah 承担监督层);代价一侧的事实是 `AGENTS.md:64` 与 `:72`。

### 7.3 "媒体供给"要不要成为一条域级 Effect

**问题**:2026-08-31 的种子域 G3 叫"模型 + 媒体供给"。本文把它的前半"模型供给"立成了 G-MDL,但没有为后半"媒体供给"(用模型生成图片、视频这类媒体)立任何域级 Effect。

**必须先纠正本文首版的一个假前提。** 首版在这里写的理由是"它今天说不出自己贡献哪条北极星",这句话**不成立**:旧仓 G3 报告 `ac08659a6d5b556a3_v1.md:249` 已经给出了它的 Effect——「媒体生成 provider 的凭据、探测、模型设置,与模型供给域**同等诚实** —— 即:录入凭据 → 真实、可解释的可用性判定 → 可用模型物化为可消费能力;判定失败钉到真因;不误伤用户数据」;`:256` 还逐条挂了北极星——「*流程可靠可重现*:媒体生成是图流程的一等公民;*去黑盒*:花钱前知道花多少、参数合不合法;*本地=服务端*:同一 catalog」。所以待裁的不是"它有没有理由",而是下面这个。

**真正的问题**:这三条挂钩成立的前提是"媒体生成是图流程的一等公民"。这个前提今天在引擎里**不成立**——`src/graph_skill_runtime/models/` 下只有 `reasoning_patch.py`,没有任何媒体供给的实现;`spec/features.yaml` 的 45 条 feature 里也没有一条讲媒体。按 2.2 规则②,引擎要为每条域级 Effect 提供第一个实现,所以立这条 Effect 等于同时决定"引擎要做媒体生成的 0 到 1"。这是一项要不要做的决定,属目标层。

**建议**:暂不立为域级 Effect,理由**不是**它没有价值,而是它今天没有对应的用户旅程压着——种子报告里那三条北极星挂钩描述的是"如果媒体生成是一等公民会怎样",而不是"今天有用户在这条路上被卡住"。等出现明确的用户旅程再补;补的时候按 2.2 规则③,先在引擎补这条 Effect 与它的第一个实现,再谈网关那一侧。

**依据**:2.2 规则②(每条域级 Effect 引擎都要有自己的实现)加决议 `:353` 的执行顺序规则(执行顺序从依赖序推导,问题密度只用于同层平票裁决)——一条今天没有旅程压着、且要从零起一个 0 到 1 的承诺,排不进当前这一轮。呈请用户裁的正是这一句:媒体生成现在算不算引擎必须承诺的能力。

---

## 8. 修订记录

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-09-03 | 首版(本 PR 的第一个提交)。确立五条北极星的引用基准、核心与辅助的三句规则、十个域共 40 条域级 Effect、四条缺口、五条引擎特有公理。 | 旧仓决议 `docs/design/gskill-restructure-decision-2026-08-31.md` §1/§2/§3/§5/§7;用户 2026-09-03 关于模块化推进、0 到 1 与 1 到 10、MoirAI 归属、层级写法的四段裁定。 |
| 2026-09-03 | 交叉审 r1 返修。①把五条写宽了的承诺按真实契约收窄(E-FMT-3 注册表范围、E-CFG-4 只拒结构上像密钥的键、E-OBS-2 只有进入执行阶段的运行有轨迹、E-OBS-3 位置分编译期与运行期两档、E-STA-2 只取回等待态);②三条从"有实现"改判为缺口或部分(E-STA-3 产物、E-OBS-1 公开接线口、E-AGT-1 相位级执行者);③从 G-AGT 拆出新域 **G-MDL**,原 E-AGT-4 改编号 E-MDL-1;④G-ACC 不变量改为"同一用例的规则只有一份",新增用例 × 投影覆盖矩阵;⑤E-SHP-2 改写为用户可观察的结果;⑥第 5 节只准写装完包就有的检验,列名改"按坐标判定的状态"并声明它尚未实跑;⑦3.12 新增按旧仓域报告逐条对账的种子能力表;⑧7.3 的依据推翻重写——原写"媒体供给说不出贡献哪条北极星"是假前提。 | 交叉审 r1 的 13 条 P1 + 3 条 P2(每条附实跑证据),加协调方两条;逐条坐标已由执笔席重新打开核实。 |
