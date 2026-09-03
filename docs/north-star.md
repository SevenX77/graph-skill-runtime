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

**这棵树怎么来的。** 按决议第 321 行起的盘点方法:域按不变量聚类,现有文件与目录怎么摆不构成判据。2026-08-31 盘点出的七个种子域(旧仓 `docs/design/gskill-restructure-inventory-2026-08-31/domain-reports/MANIFEST.md:9-15`:G1 运行时底座 + 契约基建、G2 gskill 格式 + 编译诊断、G3 模型 + 媒体供给、G4 执行 + 观测、G5 评测 + 工作台、G6 创作、G7 委托 + 发布 + 平台)只作种子,不作答案。本文推导出十个域,与种子的每一处差异都在各域小节里写了理由,汇总在 3.11。

每条 Effect 写四件事:用户能观察到什么、贡献哪条北极星、引擎自己的实现在哪、已知的平行实现是谁。

### 3.1 G-FMT · 格式与编译诊断

**不变量**:一份 gskill 合不合法只由格式规范判定;一次编译返回它当时能查出的全部缺陷,不是第一条。
**贡献**:北极星-2、北极星-1、北极星-3、北极星-4。
**与种子的关系**:等于种子域 G2,不改。

- **E-FMT-1 用文档描述流程就能编译成一张可运行的图。** 用户观察到:写好 `SKILL.md` + `graph.yaml` + 各相位目录,跑一次编译就得到可执行的图,不必写框架代码。贡献北极星-2、北极星-1。引擎实现:格式契约 `docs/skill-spec/01-PORTABLE-GSKILL-V1.md`(`status: FROZEN`),读取与校验 `src/graph_skill_runtime/core/loader.py`、`src/graph_skill_runtime/core/compiler.py`,入口 `gskill compile`。平行实现:工作台的 Compile 按钮。
- **E-FMT-2 一次编译拿到全部缺陷,每条能定位到文件、行、字段。** 用户观察到:一次编译列出这份 gskill 当时能查出的所有缺陷,每条带一个稳定的原因码,而不是修好一个才冒出下一个。贡献北极星-2、北极星-5。引擎实现:`core/compiler.py:47` 的 `CompileIssue` 带 `source_path` / `line` / `field_path` 三个定位轴;原因码表 `core/error_registry.py` 的 `ERROR_REGISTRY`,实测 99 条(`uv run python -c "from graph_skill_runtime.core.error_registry import ERROR_REGISTRY; print(len(ERROR_REGISTRY))"`)。平行实现:工作台把同一份诊断投影到画布徽章、字段提示与 Compile 抽屉。
- **E-FMT-3 可复用的子图按一份扁平注册表引用,图的编号全包唯一。** 用户观察到:一个子图写一次,多个 gskill 按编号引用。贡献北极星-2。引擎实现:`AGENTS.md:16` 定契约,`core/topology_projection.py:42` 与 `:102` 读父子拓扑。平行实现:暂无。
- **E-FMT-4 旧格式一次性转换成当前格式,转换器绝不当兜底。** 用户观察到:一条显式命令把旧 skill 转过来;转换失败就是失败,不会在正常路径上悄悄回落到旧读法。贡献北极星-4、北极星-1。引擎实现:`gskill migrate studio-skill`,`src/graph_skill_runtime/migration/studio_v030.py`;边界由 `AGENTS.md:90` 写死。平行实现:暂无。

### 3.2 G-CFG · 运行请求的解析与快照

**不变量**:一次运行的全部参数在起跑前解析成一份不可变的请求,每个字段说得出它来自哪一层。
**贡献**:北极星-1、北极星-4、北极星-5。
**与种子的关系**:从种子域 G1(运行时底座 + 契约基建)里分出来。理由:G1 把"配置解析"和"图执行底座"混在一起,但两者守的不变量不同——前者守"解析确定且可追溯",后者守"执行忠于图"。按决议第 338 行的反事实检验,把配置解析并进执行,会毁掉"起跑前就能看清这次到底会怎么跑"这个行为区分。

- **E-CFG-1 配置优先级固定,每个字段带出处。** 用户观察到:同一次运行的每个参数,都能查到它来自命令行、项目配置、用户机器配置还是内置默认值。贡献北极星-1、北极星-5。引擎实现:`src/graph_skill_runtime/application/config.py`,优先级顺序写在 `AGENTS.md:50`;出处记在 `ValueOrigin`;入口 `gskill config resolve`。平行实现:工作台的设置界面。
- **E-CFG-2 每次运行先落一份不可变的请求快照,同一个运行编号内容不同绝不覆盖。** 用户观察到:每次运行在状态目录下留一份 `request.json`,事后能照它复现这次运行的输入。贡献北极星-1、北极星-4。引擎实现:Port `ports/runtime.py:66` 的 `RunSnapshotStore`,落盘 `adapters/snapshots.py`,语义写在 `AGENTS.md:54`。平行实现:工作台的运行列表。
- **E-CFG-3 执行者只出现在运行时配置里,永不进可移植源。** 用户观察到:把 gskill 目录拷给别人,里面找不到"用哪个执行者"这种绑死宿主的信息。贡献北极星-4。引擎实现:格式契约里 `executor` 出现 0 次(`grep -c executor docs/skill-spec/01-PORTABLE-GSKILL-V1.md` 返回 `0`);配置侧的执行者联合类型在 `domain/models.py:295`。上位依据:决议 `:221`。平行实现:暂无。
- **E-CFG-4 明文密钥进不了任何契约对象。** 用户观察到:凭据只以引用形式出现在快照和配置里,落盘文件里读不到明文。贡献北极星-4(可移植)与"失败时对用户数据零副作用"这条工程底线。引擎实现:`domain/models.py:239` 的 `SecretBinding` 与它引用的 `SecretReference`,规则写在 `AGENTS.md:52`。平行实现:网关的凭据真相存储。

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
**与种子的关系**:是种子域 G4 的后半,再合入种子域 G3(模型 + 媒体供给)里"把角色解析成模型"这一半。合并理由:AGENT 相位跑不跑得起来,取决于"有没有一个执行者"和"角色能不能变成一个可调用的模型"这两件事同时成立,它们守的是同一个不变量,分开会让缺口落在两个域的缝里。G3 里的"媒体供给"没有并进来,理由见 7.3 的待裁项。

- **E-AGT-1 AGENT 相位能由一个能自主用工具的执行者跑完,结果写回同一次运行。** 用户观察到:流程跑到需要 agent 的那一步不会停死。贡献北极星-1。引擎实现:Port `ports/runtime.py:31` 的 `AgentExecutor`;今天有三种执行者配置——`HostNativeExecutorConfig`(`domain/models.py:248`)、`CliExecutorConfig`(`:253`)、`EmbeddedExecutorConfig`(`:287`)。**已裁定但尚未执行的差异**:决议 `:230` 把执行者闭集裁为 `embedded` 与 `ah` 两个,`:256` 要求删除 `host-native` 本体;而本仓今天的默认执行者仍是 `host-native`(`AGENTS.md:54`)。这是一条未执行的工单,不是本文新裁的事;实施顺序由决议 `:270` 起的 §5.9 给定。平行实现:暂无。
- **E-AGT-2 起跑前逐相位核对执行者的支持面,不支持就以原因码拒绝。** 用户观察到:执行者做不到的能力,在没花任何模型调用钱之前就被告知。贡献北极星-1、北极星-5。引擎实现:**部分缺口**。今天只有命令行执行者路径在创建交接件之前探测可执行文件、版本、必需参数与登录状态(`AGENTS.md:62`);决议 `:242` 起要求的"在 `resolve_run` 阶段逐相位核对"尚未存在。平行实现:暂无。
- **E-AGT-3 AGENT 的输出按 JSON Schema 校验,不合格就不消费这次任务。** 用户观察到:agent 返回的结构不对时,流程报错,而不是把坏数据写进图状态。贡献北极星-1。引擎实现:`AGENTS.md:58` 与 `:68` 定语义;能力条目 `F-finish-task-validation`。平行实现:暂无。
- **E-AGT-4 把一个"角色"解析成一个可调用的模型。** 用户观察到:gskill 里写"这一步用 balanced 角色",运行时就有一个具体模型被调用;某个模型不可用时按声明的顺序退到下一个。贡献北极星-1、北极星-2。引擎自有实现:**缺口**。证据:`grep -rn "ModelResolver" src/graph_skill_runtime --include=*.py` 返回 0 行;`core/graph_assembler.py:213` 的参数是 `model_resolver: Any = None`,由外部注入,`:2427` 处 `if model_resolver is None: return None`——没有注入就没有模型。0 到 1 的参照物:旧仓提交 `c7405b7e` 加入的 `config/llm_roles.yaml` 与 `src/core/graph_agent/config/llm_config.py`(同一提交还加入 `config/multimodal_roles.yaml`),即"一份 YAML 记角色和退让顺序,一个组件读它"。平行实现:网关(旧仓 `packages/graph-agent-gateway`,含 `registry` / `resolve` / `role` / `probing` / `call` / `dialect` / `media` 等模块)是这条 Effect 的 1 到 10。
- **E-AGT-5 没设角色就编译报错,不悄悄套一个默认角色。** 用户观察到:漏配角色时编译红,并被告知去哪里配。贡献北极星-1、北极星-5。引擎实现:已落地——`core/loader.py:381` 抛 `[F-v3-agent-llm-role-missing]`,`core/error_registry.py:113` 登记它为编译期 FATAL;`grep -rn "DEFAULT_LLM_ROLE" src/ --include=*.py` 返回 0 行,说明旧的兜底已删净。平行实现:工作台的角色配置提示。

### 3.5 G-STA · 运行状态的持久与续跑

**不变量**:一次运行的状态只有一个所有者;续跑读的就是那一份,不是复制品。
**贡献**:北极星-1、北极星-4、北极星-5。
**与种子的关系**:从种子域 G1 分出。理由同 3.2:持久化守的是"状态唯一且可恢复",与"配置解析确定"是两回事。

- **E-STA-1 图状态按代落盘。** 用户观察到:流程跑到一半机器断了,状态还在。贡献北极星-1。引擎实现:Port `ports/runtime.py:40` 的 `CheckpointStore`,实现在 `core/checkpointer.py`。平行实现:暂无。
- **E-STA-2 中断之后能从落盘状态续跑同一次运行。** 用户观察到:接着上次的地方继续,而不是从头再来。贡献北极星-1、北极星-4。引擎实现:`gskill resume`,`application/service.py:71`。平行实现:工作台的续跑按钮。
- **E-STA-3 产物落盘并给出稳定引用。** 用户观察到:流程产出的文件有一个固定的引用地址,事后拿得回来。贡献北极星-5。引擎实现:Port `ports/runtime.py:48` 的 `ArtifactStore`,清单构建在 `core/artifacts.py:58`。平行实现:工作台的产物面板。
- **E-STA-4 重复提交同一个结果是幂等的。** 用户观察到:同一份 agent 结果提交两次,拿到同一个答案;换成不同内容则冲突报错,而不是覆盖。贡献北极星-1。引擎实现:语义写在 `AGENTS.md:58`;入口 `gskill submit` 与 MCP 工具 `submit_agent_result`。平行实现:暂无。

### 3.6 G-OBS · 去黑盒:事件、轨迹与检视

**不变量**:发生了的事必须能被外部逐条看到;看不见的环节是缺陷候选。
**贡献**:北极星-5。
**与种子的关系**:是种子域 G4 的后半独立成域,理由见 3.3。

- **E-OBS-1 每个环节发出带类型的事件,并可挂载日志与指标回调。** 用户观察到:能按事件逐条知道流程走到哪、发生了什么;挂上回调不改变执行语义。贡献北极星-5。引擎实现:Port `ports/runtime.py:54` 的 `EventSink`,事件模型 `callbacks/events.py`,契约 `core/event_contracts.py`,现成回调 `callbacks/__init__.py:10` 导出的 `LoggingCallback` / `MetricsCallback` / `TracingCallback`;`spec/features.yaml` 里登记了 54 个不重复的事件类。平行实现:工作台的运行日志面板。
- **E-OBS-2 每次运行留一份可回读的轨迹文件。** 用户观察到:跑完之后有一份文件,能逐步复核每个相位收到什么、模型被怎么提问、返回了什么。贡献北极星-5。引擎实现:结果里的 `trace_path`(`adapters/result_mapping.py:65`),读取与累计在 `callbacks/emit.py:114-135`,步骤模型 `tracing/steps.py`。平行实现:工作台的 trace 视图。
- **E-OBS-3 失败带稳定原因码,并定位到具体相位。** 用户观察到:报错是一个可以被程序断言的编号加位置,不是一句自由文本。贡献北极星-5、北极星-1。引擎实现:`core/error_registry.py` 的 `ERROR_REGISTRY`(99 条,每条带严重级与所属阶段)。平行实现:工作台的错误提示。
- **E-OBS-4 检视编译产物的拓扑与调用关系。** 用户观察到:不跑也能看清这份 gskill 有哪些相位、怎么连、谁调谁。贡献北极星-5、北极星-2。引擎实现:`gskill inspect`,`core/topology_projection.py`;MCP 侧要求以 `cache=false` 编译,查询不得污染编译缓存(`AGENTS.md:42`)。平行实现:工作台的画布。
- **E-OBS-5 正在跑的运行能被实时订阅。** 用户观察到:一次长时间运行跑到哪了,可以边跑边看,而不是等它结束再读文件。贡献北极星-5。引擎自有实现:**缺口**。证据:`grep -rn "def subscribe" src/graph_skill_runtime --include=*.py` 返回 0 行;`ports/runtime.py:54` 的 `EventSink` 只有 `emit` 一个方法,是推出口,外部无法主动订阅。上位要求:决议 `:262` 起的 §5.7——run 是长任务,需要异步任务模型,且它与实时事件订阅必须并为同一个 Port。平行实现:工作台今天用自己的 WebSocket 通道达成同样效果。

### 3.7 G-EVA · 评测

**不变量**:一个 gskill 做得对不对,由可复核的判据说了算,不由一次观感。
**贡献**:北极星-1、北极星-5。
**与种子的关系**:是种子域 G5(评测 + 工作台)的前半。后半"工作台"按 2.2 的规则不是域级 Effect,它是 G-OBS 与 G-ACC 若干条 Effect 下的平行实现,所以从域级表里移出。

- **E-EVA-1 用 golden 基线跑一次评测,得到一个可复核的结论。** 用户观察到:把一次认可的运行存成基线,以后每次改动都能对着它判"变好还是变坏"。贡献北极星-1、北极星-5。引擎实现:`gskill golden`,`application/service.py:90`,实现在 `core/_predict_internal/golden_eval.py:193`;MCP 工具名 `evaluate_golden`。平行实现:工作台的评测面板。
- **E-EVA-2 确定性替身让离线也能跑出可比的结果。** 用户观察到:没有网络、没有模型凭据的机器上也能跑测试,并得到稳定结论。贡献北极星-1。引擎实现:`spec/features.yaml` 的 `F-predict-internal-mocking`,替身在 `core/_predict_internal/stub.py`。平行实现:暂无。

### 3.8 G-AUT · 创作与理解

**不变量**:用户不必先学框架,就能做出一份正确的 gskill,并看懂自己做出来的是什么。
**贡献**:北极星-2。
**与种子的关系**:等于种子域 G6(创作),但内容按用户 2026-09-03 关于层级的原话重排:上级承诺写"能观察节点图、能不手敲代码建出节点图",引擎的实现是 MoirAI 代理人,工作台画布是与它同级的另一种实现。

- **E-AUT-1 有一个代理人带着用户从"想做什么"走到一份能编译的 gskill。** 用户观察到:在自己手边的 agent 工具里,有一个角色会问清领域概念、定出拓扑与数据契约,并给出可编译的源。贡献北极星-2。引擎实现:MoirAI 资产 `integrations/assets/moirai/integration.json` 里的 `moirai` 与 `moirai-clotho` 角色,以及 `moirai-domain-analysis` / `moirai-graph-design` / `moirai-agent-prompt-design` / `moirai-brainstorming` 四个技能。平行实现:工作台的新建向导。
- **E-AUT-2 编译失败时,有人能定位到最小的权威源并修好。** 用户观察到:拿着一份完整诊断,有角色告诉他改哪一处、为什么是那一处。贡献北极星-2、北极星-5。引擎实现:MoirAI 的 `moirai-lachesis` 角色与 `moirai-compile-repair` 技能,知识库 `KB-07-compile-diagnostics.md`。平行实现:工作台把诊断直接标在画布节点上。
- **E-AUT-3 能观察 graph 节点图。** 用户观察到:看得见这份 gskill 长什么样——有哪些节点、怎么连。贡献北极星-2、北极星-5。引擎实现:`gskill inspect`(拓扑投影,与 `E-OBS-4` 同一条实现)加 MoirAI 知识库 `KB-05-subgraph.md`。平行实现:工作台画布。
- **E-AUT-4 不手动敲代码就能把设计好的节点图建出来。** 用户观察到:说清想要的流程,就得到对应的节点与连线,不必逐字写 `graph.yaml`。贡献北极星-2。引擎实现:MoirAI 的 `moirai-clotho` 角色与 `moirai-graph-design` 技能。平行实现:工作台画布的拖拽新建节点——按用户原话,它「是和"用 moirai agent 来实现"的模块同级的模块」。

### 3.9 G-ACC · 接入面

**不变量**:Python SDK、命令行、MCP、宿主投影是同一套用例的四种投影,规则只有一份,不各自实现。
**贡献**:北极星-3、北极星-4、北极星-2。
**与种子的关系**:从种子域 G7(委托 + 发布 + 平台)里分出"怎么被调用"这一半。分开的理由:接入面守"规则只有一份",发货守"别的机器装得出同一份",删掉任一方都会毁掉一个行为区分。

- **E-ACC-1 在 Python 里 import 一个包就能用全部用例。** 用户观察到:一个稳定的、写下来的公开接口清单,不必去读内部实现。贡献北极星-3、北极星-4。引擎实现:门面 `sdk.py`(13 个公开函数),顶层契约 `graph_skill_runtime.__all__` 实测 77 个符号,文档 `docs/public-api-contract.md`(frontmatter `role: contract`,`status: living`)。平行实现:暂无。
- **E-ACC-2 命令行 `gskill` 覆盖同一套用例。** 用户观察到:不写 Python 也能编译、干跑、真跑、续跑、检视、评测、转换、装宿主投影。贡献北极星-2、北极星-4。引擎实现:`adapters/cli.py:166` 起注册的子命令——`compile`、`config resolve`、`predict`、`run`、`resume`、`submit`、`inspect`、`golden`、`migrate studio-skill`、`integrations detect|install|uninstall`、`mcp`。平行实现:工作台的按钮。
- **E-ACC-3 外部 agent 通过 MCP 调用同一套用例。** 用户观察到:在 Claude Code 或 codex 里直接把引擎当工具用。贡献北极星-3、北极星-2。引擎实现:`adapters/mcp.py:31` 起,服务名 `gskill`,恰好 8 个工具——`compile`、`resolve_run`、`predict`、`run`、`resume`、`submit_agent_result`、`inspect`、`evaluate_golden`;每个工具必须声明状态影响标注(`AGENTS.md:42`)。平行实现:工作台的 HTTP 接口。
- **E-ACC-4 把 MoirAI 投影进宿主,是一次显式、冲突即拒、可回滚的操作。** 用户观察到:装之前先体检,任一目标冲突就整体不动;卸载只删自己装的那些、且内容没被改过的那些。贡献北极星-2。引擎实现:`integrations/installer.py`、`integrations/renderers.py`,规则写在 `AGENTS.md:44`;命令 `gskill integrations install moirai --targets ... --scope ...`。平行实现:暂无。

### 3.10 G-SHP · 发货与环境复现

**不变量**:本地做出来的东西,能在别的机器上装出同样的一份。
**贡献**:北极星-4。
**与种子的关系**:种子域 G7 的另一半,理由见 3.9。

- **E-SHP-1 装一个包就有全部能力,用户的业务 gskill 不随包发。** 用户观察到:安装包里没有别人的业务技能,也不会有人偷偷注册或改写他自己的技能目录。贡献北极星-4、北极星-3。引擎实现:边界写在 `AGENTS.md:38`;打包内容由 `scripts/accept_release_artifacts.py` 的 `validate` 逐条断言(`AGENTS.md:78`)。平行实现:暂无。
- **E-SHP-2 打包出来的那一份在三个平台被逐项验收,而不是只在开发模式下绿。** 用户观察到:验收结论出自装好的包,不是出自源码树。贡献北极星-4,以及决议第 143 行"证据环境 = 发货环境"这条行为原则。引擎实现:`scripts/accept_release_artifacts.py` 的 `accept`,验收范围写在 `AGENTS.md:80`;`docs/CROSS_PLATFORM.md` 记具体运行与产物身份。平行实现:暂无。
- **E-SHP-3 锁定版本的引擎加锁定版本的格式,本地做的 gskill 原样在服务端跑。** 用户观察到:同一份 gskill 交给服务端,跑出同一条相位序列。贡献北极星-4。引擎自有实现:**缺口**。证据两处:决议 `:74` 原话「**未实现**」;`AGENTS.md:20`「The project is not published on PyPI or TestPyPI.」——没有发布,"锁定版本"就没有可锁的对象。平行实现:暂无。

### 3.11 与七个种子域的差异汇总

| 种子域 | 本文的归宿 | 理由 |
|---|---|---|
| G1 运行时底座 + 契约基建 | 拆成 G-CFG(解析与快照)与 G-STA(状态与续跑) | 两者守的不变量不同,可以各自单独失败;合在一起会让缺口落进同一个格子看不见 |
| G2 gskill 格式 + 编译诊断 | 原样成为 G-FMT | 不变量一致,无需改动 |
| G3 模型 + 媒体供给 | "角色→模型"并入 G-AGT;"媒体供给"未立域级 Effect | 前者与执行者供给守同一个不变量;后者今天说不出贡献哪条北极星,也没有引擎侧实现,见 7.3 待裁项 |
| G4 执行 + 观测 | 拆成 G-EXE、G-AGT、G-OBS | 忠于图、有人能跑 AGENT、发生的都看得见,是三个可以分别失败的承诺 |
| G5 评测 + 工作台 | 评测成为 G-EVA;工作台移出域级表 | 按 2.2 规则①,工作台不是域,它的每个模块是既有 Effect 下的平行实现 |
| G6 创作 | 成为 G-AUT,并按 2.1 第四段原话重排层级 | 上级承诺是"能观察、能不敲代码建图",MoirAI 与画布是它下面两个同级实现 |
| G7 委托 + 发布 + 平台 | 拆成 G-ACC(接入面)与 G-SHP(发货) | 规则只有一份,与别的机器装得出同一份,是两个不同的承诺 |

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

判据统一是 2.3 那一句:**干净环境里只装引擎这一个包,这条 Effect 能不能达成。** "命令"列写的是达成它要跑什么、看什么文件、或用哪个 MoirAI 技能。状态只有两种取值:**可达成**,或**未覆盖 + 原因**。

| 编号 | 只装引擎怎么达成 | 状态 |
|---|---|---|
| E-FMT-1 | `gskill compile <skill_root>` 返回成功的编译结果 | 可达成 |
| E-FMT-2 | 同上,对一份有多处缺陷的 skill,一次返回全部 `CompileIssue` | 可达成 |
| E-FMT-3 | `graphs/<graph_id>/graph.yaml` 被父图按编号引用后 `gskill compile` 通过 | 可达成 |
| E-FMT-4 | `gskill migrate studio-skill SOURCE DESTINATION` | 可达成 |
| E-CFG-1 | `gskill config resolve` 输出里每个字段带 `value_origins` | 可达成 |
| E-CFG-2 | 跑一次后检查 `<state_root>/runs/<run_id>/request.json` 存在且不被覆盖 | 可达成 |
| E-CFG-3 | `grep -c executor docs/skill-spec/01-PORTABLE-GSKILL-V1.md` 返回 0 | 可达成 |
| E-CFG-4 | 构造带明文密钥形状键的输入,契约对象拒绝它 | 可达成 |
| E-EXE-1 | `gskill predict` 返回相位序列且未发生模型调用 | 可达成 |
| E-EXE-2 | `gskill run` 对一份 LOGIC-only skill 跑到结束并返回结构化结果 | 可达成 |
| E-EXE-3 | 同上,注册的 Python 动作与校验器被执行 | 可达成 |
| E-EXE-4 | 带子图的 skill 跑通,父子输入输出边界被保持 | 可达成 |
| E-EXE-5 | 带 iterate 的 skill 跑通,次数与顺序符合声明 | 可达成 |
| E-AGT-1 | `gskill run` 对带 AGENT 相位的 skill 走到执行者并回写结果 | 可达成(今天靠 `host-native` 与 `cli` 两条路径;它们已被决议 `:230` / `:256` 裁定收敛与删除,替代路径 `embedded` 的 AGENT 侧尚未验证——`AGENTS.md:60` 只承认 LOGIC 路径实测过) |
| E-AGT-2 | `gskill config resolve` 阶段逐相位核对执行者支持面并以原因码拒绝 | 未覆盖 + 原因:只有命令行执行者在创建交接件前探测(`AGENTS.md:62`),决议 `:242` 要求的 `resolve_run` 阶段逐相位 preflight 尚未实现 |
| E-AGT-3 | 提交一份 schema 不合格的 agent 结果,任务不被消费 | 可达成 |
| E-AGT-4 | 只装引擎、不注入任何解析器时跑一个 AGENT 相位 | 未覆盖 + 原因:引擎没有内置的角色到模型解析,`grep -rn "ModelResolver" src/graph_skill_runtime --include=*.py` 返回 0 行,`core/graph_assembler.py:2427` 无注入即返回 `None` |
| E-AGT-5 | 对一份漏配 `llm_role` 的 AGENT skill 编译,得到 `[F-v3-agent-llm-role-missing]` | 可达成 |
| E-STA-1 | 配 SQLite 检查点存储跑一次,检查点文件按代写入 | 可达成 |
| E-STA-2 | `gskill resume` 从落盘状态继续同一次运行 | 可达成 |
| E-STA-3 | 声明产物后跑一次,产物落盘且返回稳定引用 | 可达成 |
| E-STA-4 | `gskill submit` 同一份结果两次,第二次返回同一个结果 | 可达成 |
| E-OBS-1 | 挂 `LoggingCallback` / `MetricsCallback` 跑一次,收到带类型事件 | 可达成 |
| E-OBS-2 | 跑一次后读 `RunResult.trace_path` 指向的文件 | 可达成 |
| E-OBS-3 | 触发一个失败,结果里带 `[F-v3-*]` 原因码与相位位置 | 可达成 |
| E-OBS-4 | `gskill inspect <skill_root> --call-graph` 返回拓扑与调用图 | 可达成 |
| E-OBS-5 | 在运行进行中从外部订阅事件流 | 未覆盖 + 原因:没有订阅接口,`grep -rn "def subscribe" src/graph_skill_runtime --include=*.py` 返回 0 行;`EventSink` 只有 `emit`。决议 `:262` 要求的异步任务模型与订阅同一个 Port 尚未落地 |
| E-EVA-1 | `gskill golden`(MCP 侧 `evaluate_golden`)对一份基线给出结论 | 可达成 |
| E-EVA-2 | 无网络、无模型凭据的机器上跑 `gskill predict` 得到稳定结果 | 可达成 |
| E-AUT-1 | `gskill integrations install moirai` 后,宿主里可用 `moirai` / `moirai-clotho` 角色与 `moirai-domain-analysis`、`moirai-graph-design`、`moirai-agent-prompt-design`、`moirai-brainstorming` 技能 | 可达成 |
| E-AUT-2 | 同上,`moirai-lachesis` 角色与 `moirai-compile-repair` 技能可用 | 可达成 |
| E-AUT-3 | `gskill inspect` 的拓扑输出 + 知识库 `KB-05-subgraph.md` | 可达成 |
| E-AUT-4 | `moirai-graph-design` 技能产出可编译的 `graph.yaml` | 可达成 |
| E-ACC-1 | `import graph_skill_runtime`,`len(graph_skill_runtime.__all__)` 为 77 | 可达成 |
| E-ACC-2 | `gskill --help` 列出 `adapters/cli.py:166` 起注册的全部子命令 | 可达成 |
| E-ACC-3 | 启动 `gskill mcp`,枚举出恰好 8 个带标注的工具 | 可达成 |
| E-ACC-4 | `gskill integrations install moirai --targets ... --scope ...`,冲突时整体不动 | 可达成 |
| E-SHP-1 | 装好的包里没有业务 `graph.yaml`;`scripts/accept_release_artifacts.py validate` 通过 | 可达成 |
| E-SHP-2 | `scripts/accept_release_artifacts.py accept` 在三平台通过 | 可达成 |
| E-SHP-3 | 从公共包仓库按锁定版本装引擎,在服务端跑同一份 gskill | 未覆盖 + 原因:决议 `:74` 记「**未实现**」;`AGENTS.md:20` 记项目未发布到 PyPI 或 TestPyPI,没有可锁定的发布版本 |

**汇总**:40 条域级 Effect 中,36 条可达成,4 条未覆盖(`E-AGT-2`、`E-AGT-4`、`E-OBS-5`、`E-SHP-3`)。4 条缺口全部集中在两处:一是 AGENT 相位的供给链(执行者收敛与角色到模型的解析),二是"长任务 + 实时订阅 + 发布锁版本"这条服务端复现链。它们分别对应决议 §5.3/§5.4(执行模型)与 §5.7(异步任务模型),都是已裁定、待执行的工单,不是本文新提的需求。

---

## 6. 与既有文档的关系

- **本文的上位依据**:旧仓 `docs/design/gskill-restructure-decision-2026-08-31.md` 的 §1(北极星)、§2(权威链)、§3(行为原则)、§5(执行模型)、§7(盘点方法)。本文是它在引擎仓里的落地。
- **该决议的 §4.3(gateway 与 studio 整体迁入本仓、先搬后整、冻结旧引擎随迁)已于 2026-09-03 被用户推翻。** 本文不引用它作依据,也不依赖它成立。本文成立的前提只是 §4.2——引擎的唯一所有权在本仓(决议 `:160-164`)。
- **`AGENTS.md`(仓根)**:本仓的规则入口,今天是自下而上写成的实况描述——它记的是"现在实现成什么样"。按 4.1 的权威链,它应当从本文推导:每条规则说得出自己服务哪条 Effect。**这是一条后续工单,本文只登记,不执行。**
- **`docs/public-api-contract.md`**(`role: contract`,`status: living`):本文的下游,它是 `E-ACC-1` 那条承诺的可执行清单。
- **`docs/skill-spec/01-PORTABLE-GSKILL-V1.md`**(`role: contract`,`status: FROZEN`):本文的下游,是 G-FMT 域的契约载体。同目录的 `00-FORMAT-GROUND-TRUTH.md` 为 `superseded`,只作转换器输入与历史证据(`AGENTS.md:16`)。
- **`docs/design/v1-alignment.md`**(`status: drafted`):本文的下游,是实现阶段的对齐目标,不承载北极星。`docs/design/README.md`(`role: index`,`status: living`)负责路由现况与目标;`docs/design/baseline.md`(`status: drafted`)是抽仓之前的历史证据,不是当前路径地图。
- **`docs/mvp0`(36 份)与 `docs/mvp1`(61 份)**:旧引擎时代的文档,今天仍在仓里(`git ls-files docs | wc -l` 为 119,其中 `docs/skill-spec` 15、`docs/design` 4、根下 3)。它们会把读到的 agent 带偏。同时有三处测试耦合着它们:`tests/contract-seals.yaml` 的 17 条封印里 14 条指向 `docs/mvp0`;`tests/test_doc_hash_lock.py:13` 的 `DOCS_ROOT` 指向 `docs/mvp1`;`tests/test_doc_pointer_liveness.py:54` 的 `CONTRACT_DOC_STATUSES` 只认 `living` 与 `FROZEN`。**清理是独立工单,本文只登记这个事实,不执行。**

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

**问题**:2026-08-31 的种子域 G3 叫"模型 + 媒体供给"。本文把"角色到模型"并进了 G-AGT,但没有为"媒体供给"(多模态输入,例如图片、音频)立任何域级 Effect。理由是两条:它今天说不出自己贡献哪条北极星;引擎侧也找不到实现——`src/graph_skill_runtime/models/` 下只有 `reasoning_patch.py`,多模态角色表 `config/multimodal_roles.yaml` 在旧仓、不在本仓。

**建议**:暂不立为域级 Effect,等出现明确的用户旅程再补;补的时候按 2.2 规则③,先在引擎补这条 Effect 和它的第一个实现,再谈网关那一侧。

**依据**:决议 `:101`——域级 Effect 写不出贡献哪条北极星,就必须显式写"不贡献"并解释为何仍然存在;而"不贡献且引擎无实现"的条目更适合先不立,而不是先立一个空格子。这一条涉及"要不要做这件事",属于目标层,所以呈请用户裁。

---

## 8. 修订记录

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-09-03 | 首版。确立五条北极星的引用基准、核心与辅助的三句规则、十个域共 40 条域级 Effect、四条缺口、五条引擎特有公理。 | 旧仓决议 `docs/design/gskill-restructure-decision-2026-08-31.md` §1/§2/§3/§5/§7;用户 2026-09-03 关于模块化推进、0 到 1 与 1 到 10、MoirAI 归属、层级写法的四段裁定。 |
