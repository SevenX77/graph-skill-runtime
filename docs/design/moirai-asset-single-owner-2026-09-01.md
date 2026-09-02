---
module: graph-skill-runtime
doc: moirai-asset-single-owner
role: workflow-record
status: drafted
aligns_with: ./v1-alignment.md
updated: 2026-09-01
---

# 决议:MoirAI 资产单一 owner 收敛(批B′)

## 0. 本文是什么

本文是 **MoirAI 资产的单一 owner 定到本仓** 这件事的落盘正本:它记录八条已裁事项的**结论、依据与落位**,记录**哪些旧资产不迁入以及为什么**,记录**旧 id 到本仓 id 的重定向对照**,并记录**上升后已裁的两项**(一条教义冲突的终局形态、旧映射表的退役步骤)。

本文**不是**:①进度状态(进度的唯一可变载体是发起方仓库的交付台账);②资产内容本身(资产的唯一事实源是 [`integration.json`](../../src/graph_skill_runtime/integrations/assets/moirai/integration.json) 及其声明的闭集);③格式契约(格式的唯一事实源是 [portable gSkill v1 格式规范](../skill-spec/01-PORTABLE-GSKILL-V1.md))。

**术语**(首次出现即解释):

| 术语 | 平白话解释 |
|---|---|
| **资产闭集** | `integration.json` 声明的文件全集。`PackagedMoiraiAssets` 对实际文件清单做双向比对,多一个或少一个文件都直接报错。 |
| **投影(projection)** | renderer 把这一份资产改写成某个宿主(Claude / Codex / Copilot / Cursor / Gemini / OpenCode)自己的 skill、agent 与 MCP 配置格式,写进那个宿主的目录。 |
| **旧 owner** | 迁移前同时持有一份 MoirAI 资产的另一处:`agent-harness` 仓的 `apps/studio/backend/app/agents/`。 |
| **双 owner 漂移** | 同一份资产在两处各有一份且内容已经不同,谁是真相无人可判。 |

## 1. 背景事实(已机械核验)

迁移前两侧共 63 个文件,**没有一对字节相同**,也**没有一对属于"语义相同、措辞漂移"**:27 对可对账的资产里 24 对是语义分叉,另有 15 个文件单侧独有,其中 6 个构成 3 对**编号撞名**(`KB-11`/`KB-12`/`KB-13` 在两侧指三对完全不同主题的文档)。

分叉的根因不是副本走形,而是**两侧各自绑定了不同的 skill 格式**:旧 owner 的资产讲旧格式(`GRAPH.md`、正文 `<phase>` 标签、相位 agent 文件叫 `SKILL.md`、运行时目录 `.workspace/`、Studio 自己的工具面),本仓资产讲当前格式(根 `SKILL.md` + `graph.yaml`、相位 agent 文件叫 `AGENT.md`、状态根 `.gskill/`、`gskill` MCP 八件工具)。发起方决议已裁定当前格式为唯一现行契约,因此"格式层取哪一侧"没有悬念。

## 2. 迁移的语义方向(本文其余各条的判据)

**格式与能力层以本仓为准。** 凡是"文件叫什么、字段长什么样、哪个工具存在、哪条边界当前不支持"这类断言,一律取本仓,旧 owner 的对应断言整条退役。理由:格式契约已裁定,且本仓的断言与本仓代码可逐条对证。

**知识与人格层以旧 owner 的成熟版为准。** 凡是"方法、纪律、反模式、身份叙事"这类不依赖载体形状的内容,旧 owner 那一份是长期迭代出来的成熟文本,本仓对应文件是独立新写的简版;**简版缺的东西是"还没写",不是"裁决删掉"**,因此按成熟版补齐。

**两层交叉时按可对证优先。** 一条旧 owner 的知识断言,只有在本仓代码里能找到同样的机制时才迁入。本次因此**推翻了盘点阶段的一个判断**:盘点把 `[F-v3-*]` 错误码体系与 predict 的 P0–P2 mock 分级当成"旧 owner 独有、属 Studio 事实",实测不成立——本仓 `core/error_registry.py` 注册了 100 个 `[F-v3-*]` 码,`core/_predict_internal/strategy.py` 实现了 P0(golden 回放)/ P1(人工或 copilot 覆盖)/ P2(schema 启发式桩)三档,`middleware/runtime_input.py` 与 `cognitive/prompt.py` 与旧 owner 描述的机制逐条一致。**它们是引擎事实,而引擎就是本仓**,所以这些知识迁入,而不是随 Studio 留下。

## 3. 八条已裁事项的落位

### U1 · 「三名一致」降为「两名一致」

**事实**:旧 owner 两处要求相位 id 在**三处**一致(相位目录名、`GRAPH.md` frontmatter 的 `phases` 注册名、正文 `<phase id>` 标签)。本仓格式下第三处不存在,而**本仓资产此前没有任何相位名一致性条款**——对资产全树检索"consistency / must match / same name"只命中 `KB-05-subgraph.md` 讲 `graph_id`。所以本项不是"改写一条现有规则",是**新增一条本仓缺的规则**。

**落位**:`knowledge/KB-01-skill-anatomy.md` 新增「Two-name phase identity」一节;`skills/moirai-graph-design/SKILL.md` 步骤 3 增一句。

**措辞依据**(不自创,取自本仓格式规范原文):规范第 2 节「每个 `phases/<phase_id>/` 恰好对应所属 `graph.yaml.phases[]` 的一个对象……文件名决定 phase 类型,目录名决定 phase id;phase frontmatter 不重复保存这两个事实」,以及 §10.1「Phase 文件不写 `mode`、`phase_id` 或 graph id;类型和身份由文件系统与 `graph.yaml` 连接」。

### U2 · 三份 Studio / gateway 特有事实知识文件不迁入

**对象**:旧 owner 的 `KB-11-workspace-runtime`(`.workspace/` 布局与 `runtime_config.json`)、`KB-12-llm-roles`(gateway 的 Credential→Endpoint→Route→Role 链、端点健康态、角色写工具)、`KB-13-studio-gates-tools`(Compile→Predict→Run 三道门、Studio MCP 审批工具表、Rust native-fs 唯一写者边界)。

**裁定**:**不进本仓资产闭集**,留在旧 owner 随 Studio 一批处置。本仓 `KB-11`/`KB-12`/`KB-13` 三个编号槽位归本仓现有主题(`runtime-config` / `agent-execution` / `runtime-tools`),不腾位、不改名。

**理由**:决议「知识库归新仓」是在**单体仓层面**成立的归属判断;本仓 AGENTS.md「核心与 application 不得引入 Studio 或 Gateway 模块」是在**包边界层面**成立的约束。两者不冲突:归属说的是"不再有第二份 MoirAI 资产",边界说的是"Studio 的事实不能塞进 SDK 的资产里"。这三份承载的正是 Studio 与 gateway 的宿主表面事实,纯 runtime SDK 不可能拥有它们。

### U3 · 两份宿主表面技能不迁入

**对象**:旧 owner 的 `web-research`(依赖 Studio 专属 `fetch_web_page`,声称能读用户已登录浏览器背后的页面)与 `brainstorming`(新建 skill 向导,交付物是磁盘上一个能编译通过的骨架)。

**裁定**:**不进本仓资产闭集**,理由同 U2——两者的能力前提都是宿主工具面,而本仓运行时既不提供 web/search 工具,也不承担"替用户在磁盘上建骨架"的写入职责。本仓 `skills/moirai-web-research` 与 `skills/moirai-brainstorming` 继续持有这两个槽位。

**边界说明(避免误读)**:本次向这两个本仓技能补入的,只有**与工具无关的方法层**——`moirai-brainstorming` 补的是提问纪律(一次一问、能给具体提案就不做问卷、不用臆测填补沉默),`moirai-web-research` 补的是证据分级纪律(公开可复核 vs 仅本人登录可见、读到不等于测过、遇登录墙报缺而不下结论)。**未**补入任何依赖宿主工具的流程(不写 `fetch_web_page`、不写落盘骨架向导)。

### U4 · 组装层四文件:不为旧载体扩 schema

**对象**:旧 owner 的 `operating-manual.md`(跨角色操作手册)、`contexts/panel.md` 与 `contexts/cli.md`(两个运行位的表面 delta)、`README.md`(组装契约与源文件头模板)。

**裁定**:

1. **不扩 manifest schema**。本仓 `catalog.py` 的资产闭集双向校验(多一个文件即 `unexpected=` 报错)与 `_AssetManifest` 的 `extra="forbid"` + 固定 `schema_version` 是刻意设计;为容纳一个旧载体而新增资产类别、再给六个 renderer 各定一个投影位,是让旧文件的形状反向决定本仓契约。
2. **`README.md` 与 `contexts/*.md` 不迁**。`README.md` 描述的是旧 owner 那套"源文件 + 组装器 + 组装标记"机制,该机制在本仓由 renderer 取代,机制描述随机制退役。`contexts/*.md` 是 Studio 面板与 ah CLI 两个运行位的表面事实,与 U2/U3 同理。
3. **`operating-manual.md` 的跨角色协作准则并入新增知识条目** `knowledge/KB-15-working-discipline.md`。

**落位选择的理由(为什么是新增知识条目,而不是并入 `skills/moirai/SKILL.md`)**:这份纪律是**跨角色**的。旧 owner 的组装记录写明该手册被装进四个角色的规则文件(其文件头声明 `Assembled into: SDK session append; SDK subagent prompts; .ah/rules/master.md`,而 `contexts/cli.md` 声明装进 `master/clotho/lachesis/atropos` 四份)。若只并入协调入口技能,则宿主派出 `moirai-lachesis`(它携带 `moirai-compile-repair` 与 `moirai-graph-design`)时,这份纪律**一次也不会到场**。另一个可选形态是把它抄进四份角色正文,那是同一段文字的四份副本,违反单一事实源。

因此 `KB-15-working-discipline.md` **被全部八个技能声明为 reference**:它是唯一"不分阶段、无条件生效"的条目,任何一个技能被激活时它都必须在场,否则宿主拿到了流程却拿不到约束这个流程的纪律。

**它承载什么**:诊断升级次序(编译 → 预测 → 读源 → 读执行证据)、四条工程纪律(论据先行 / 修权威源 / 渐进披露 / 预测产物永不成为基线)、被拒后的义务(重估充分性 → 换合规路径 → 否则停下并指名缺什么)、知识卫生(引用只在当前技能自己的 `references/` 内解析,别处找到的同名文件属于另一次安装、可能已过期)、回话纪律(跟随用户最近一条消息的语言、结论先行、解释为什么而不是复述 diff、事实/推断/决定/未决分开)。

### U5 · 人格叙事恢复进角色文件

**事实**:旧 owner 四份角色文件是第一人称神话叙事,本仓四份是第二人称契约,叙事整段缺失。

**落位**:四份 `roles/*.md` 各增一段身份说明(MoirAI = 三位命运女神的统一意志;Clotho 纺线 = 设计;Lachesis 量线 = 结构核验;Atropos 断线 = 判定),并保留原有 Inputs / Method / Output 契约各节不动。同时明写「除用户问起,不要叙述神话」——该约束取自旧 owner `skills/moirai-intro/SKILL.md` 的既有条款,防止叙事渗进每次回答。

**不迁的部分**:旧 owner 四份角色文件头部的 HTML 注释编辑纪律块(`English only`、`delta over the base prompt`、`facts belong in knowledge/`、`no tool mechanics`、`edit THIS file, never the assembled outputs`)**不进资产正文**。它是给**编辑这份资产的人**看的,不是给宿主 agent 看的指令;放进角色正文等于把仓库编辑规约当作 agent 指令投影出去。这套纪律改由本文 §6 承载。

### U6 · `moirai-intro` 并入协调入口,不新增第九个技能

**事实**:旧 owner 的 `moirai-intro` 是自我介绍协议(声明身份 → 就地判定工作区事实 → 报三位专家的职责与可达性 → 概述五个阶段能帮什么),且旧 owner 有守卫测试钉住它的**表面中立性**(不得含任何运行位专属的查询动词)。本仓 `skills/moirai/SKILL.md` 是协调入口,不含其中任何一项——**它不冗余**。

**裁定**:**并入**,不新增技能。落位在两处:`roles/moirai.md` 的 Identity 一节(角色正文是宿主 profile 的常驻指令,"你是谁"的答案属于那里)与 `skills/moirai/SKILL.md` 的「Introduce the work, not the myth」一节。表面中立性照旧保留:原文写「依据本会话自身工具面所显示的可达性,**绝不假定一个未被给予的查询动词**」。

**为什么不新增第九个技能**:①这八个技能都是**阶段化**的(设计 / 修复 / 判定 / 研究……),"自我介绍"不是一个阶段,新增会让闭集里出现唯一一个非阶段成员;②技能数是被代码钉住的契约——`scripts/accept_release_artifacts.py` 断言 `(len(role_ids), len(skill_ids)) == (4, 8)`,新增技能要连带改发布验收脚本与多处文档;并入不动这些。

### U7 · 语言纪律缺陷:留在旧 owner 处订正

**事实**:旧 owner `knowledge/KB-12-llm-roles.md` 正文混入非英文碎片(一处中文词、一处韩文词组),与该资产自己声明的 English only 纪律相悖。

**裁定**:该文件按 U2 不迁入本仓,因此**订正动作发生在旧 owner 仓**(与指纹跨 owner 校验同一个 PR)。本仓资产侧无对应缺陷:`catalog.py` 校验 UTF-8 与 LF,但不校验语言,故本仓的 English only 依赖编辑纪律(§6),不依赖门禁。

### U8 · 基线取 `main`,不取未分诊的 WIP

**事实**:本仓资产的最后一次审定改动是 `da39fb8b`(「feat: add explicit MoirAI host integration」),这也是 `origin/main` 上这批文件的当前内容。另有一个提交 `d76f6697`(「wip: snapshot of 113 uncommitted changes (pre-triage)」)改过其中 9 个文件,它**不在 `main` 上**,而在一个被封存的分支上。

**裁定**:本 PR 的基线是 `origin/main`(即审定内容)。理由:①`main` 是唯一承载审定状态的分支,也是唯一的合并目标;②那 113 项改动尚未分诊,以它的字节为基线等于让未审内容从侧门进入 `main`;③"WIP 基线收敛到已裁状态"的收敛动作**就是本 PR 自己撰写的内容**,而不是继承一份 WIP。封存分支的内容在本次只作为**证据**参考(它显示 owner 当时的漂移方向),不作为字节来源。

## 4. 旧 id 到本仓 id 的重定向对照

**这张表是文档记录,不是运行期兼容层。** 资产目录内不留 alias 文件、不留转发页——本仓无向后兼容义务,且资产闭集校验本身就拒绝任何未登记文件。

### 4.1 知识文件

| 旧 owner 文件 | 本仓文件 | 处置 |
|---|---|---|
| `KB-00-hub.md` … `KB-10-golden.md`(11 份)、`KB-14-artifacts-persistence.md` | 同名 | 内容 owner 换人:以本仓为准,并按 §2 补入旧 owner 成熟版中可对证的知识层 |
| `KB-11-workspace-runtime.md` | 无 | 不迁(U2);本仓 `KB-11` 是 `runtime-config` |
| `KB-12-llm-roles.md` | 无 | 不迁(U2);本仓 `KB-12` 是 `agent-execution` |
| `KB-13-studio-gates-tools.md` | 无 | 不迁(U2);本仓 `KB-13` 是 `runtime-tools` |
| —(本次新增) | `KB-15-working-discipline.md` | 承接旧 owner `operating-manual.md` 的跨角色纪律(U4) |

### 4.2 角色

| 旧 owner | 本仓资产 id | 宿主投影名 |
|---|---|---|
| `roles/moirai.md` | `moirai` | `moirai` |
| `roles/clotho.md` | `clotho` | `moirai-clotho` |
| `roles/lachesis.md` | `lachesis` | `moirai-lachesis` |
| `roles/atropos.md` | `atropos` | `moirai-atropos` |

投影名的唯一事实源是 `integration.json` 的 `roles[].host_name`。Codex adapter 是唯一把投影标识符改成下划线的宿主(`moirai_clotho`),其余宿主保留连字符。

### 4.3 技能

| 旧 owner | 本仓资产 id | 处置 |
|---|---|---|
| `graph-design` | `moirai-graph-design` | 内容 owner 换人 + 两名一致新增(U1) |
| `domain-analysis` | `moirai-domain-analysis` | 内容 owner 换人 + 结构化框架与外部交叉核查(工具中立形态) |
| `agent-prompt-design` | `moirai-agent-prompt-design` | 内容 owner 换人 + 槽位职责、简洁纪律、反模式清单整体恢复 |
| `compile-error-repair` | `moirai-compile-repair` | 内容 owner 换人 + 错误码纪律与分类分诊 |
| `eval-judgement` | `moirai-eval-judgement` | 内容 owner 换人 + rework 归属路由(见 §5) |
| `brainstorming` | `moirai-brainstorming` | 旧文件不迁(U3);仅补提问纪律 |
| `web-research` | `moirai-web-research` | 旧文件不迁(U3);仅补证据分级纪律 |
| `moirai-intro` | 并入 `moirai` 与 `roles/moirai.md` | 不新增技能(U6) |

### 4.4 组装层与清单

| 旧 owner | 本仓 | 处置 |
|---|---|---|
| `agent-skill-map.json` | `integration.json` 的 `roles[].skills` | 语义等价,文件退役,**退役分两步走**(见 §4.5)。逐位核对:moirai=[入口技能, 头脑风暴]、clotho=[领域分析, 图设计, agent prompt 设计]、lachesis=[编译修复, 图设计]、atropos=[判定, agent prompt 设计],四条映射的成员与顺序两侧完全一致,只是技能 id 加了 `moirai-` 词缀且入口技能换了对象(`moirai-intro` → `moirai`,该对象按 U6 处置) |
| `operating-manual.md` | `KB-15-working-discipline.md` | 语义并入(U4) |
| `README.md`、`contexts/panel.md`、`contexts/cli.md` | 无 | 不迁(U4) |
| `knowledge/.gitkeep`、`roles/.gitkeep`、`skills/.gitkeep` | 无 | 目录非空,占位无意义 |

### 4.5 已裁:`agent-skill-map.json` 本批降格,cutover 时删除

上一行已用逐位核对证明该文件与本仓 `integration.json` 的 `roles[].skills` 语义等价,因此它作为独立事实源没有存在理由。**但"该退役"不等于"今天就能删"**,这一项已于 2026-09-01 裁定为分两步走。

**裁定**:本批**降格不删除**——该文件不再是一条独立真相,而是被机械钉在本仓 owner 的声明上(发起方仓的关系一致性检查:两侧技能 id 不同,但四个角色的成员与顺序必须一致,任一侧单方面改动即门禁红);**文件本身在批E cutover 时删除**。

**依据**:该文件有**两个读者、两种语言**——发起方仓 Python 侧的 `load_skill_map()`,以及 Rust 侧生成 `ah.toml` 与 `.ah/rules/*` 的 `load_agent_skill_map()`(`apps/studio/tauri/src/lib.rs:1820`、`:2276`)。今天删掉只有两条路:①把这条关系**硬编码两份**(Python 一份、Rust 一份)——那是新造一个第二事实源,与"退役一份重复"正好相反;②让两个读者都去读 owner 自己的 `integration.json`——需要本仓包进发起方的 vendor 快照 + 技能 id cutover,属批E,且本批明令不动 live 资产。降格是这两条之外唯一不制造新分叉的处置。

## 5. 已裁:判定词表定为三值 + 必填归属限定

本次识别出唯一一项"既非格式驱动、也非简版缺失"的教义改写,按纪律上升,已于 2026-09-01 裁定。

**冲突事实**:旧 owner 的判定词表是**四值** `pass` / `design_rework` / `repair_needed` / `needs_user_input`,并把前两种 rework 分流回具名专家(设计缺陷回 Clotho,代码与 prompt 缺陷回 Lachesis)。本仓是**三值** `pass` / `rework` / `blocked`,不做具名分流。两侧都不是格式的后果,本仓那一版也不是简版遗漏——它是独立撰写的审定内容。因此这是一次真实的语义收窄:`design_rework` 与 `repair_needed` 被并成一个 `rework`,归属信息随之丢失;`needs_user_input` 被 `blocked` 覆盖(后者更宽,不丢信息)。

**裁定**:**终局形态是三值枚举 + `rework` 必填归属限定。** 本仓三值 `pass` / `rework` / `blocked` 保持不变,归属信息以限定语的形式补回,不编码进枚举。

**依据两条**:

1. **四值不带来机器可查性。** 两种形态都只是 prompt 层的约定——Atropos 是一个 LLM 角色,本仓**没有任何代码消费这个枚举**(既不解析判定值,也不按值分派)。既然两种写法在机器一侧完全等价,就没有理由为了枚举形状去改一份已审定的资产。
2. **限定形态能表达枚举表达不了的事。** 现实里设计缺陷与修复缺陷常常纠缠,此时需要说清**谁先动**。一个判定值无法同时编码两种 rework,更无法编码它们之间的次序;而"`rework` + 必须说明路由给谁、纠缠时谁先动"这种限定天然容得下。四值反而逼判定者在两个都成立的取值里挑一个,丢掉的正是最该说出的那部分。

**落位(即本 PR 已实现的内容,裁定后无需改动)**:`roles/atropos.md` 与 `skills/moirai-eval-judgement/SKILL.md` 要求:裸 `rework` 不是可用判定,必须说明它路由给设计(`moirai-clotho`)还是权威修复(`moirai-lachesis`),两者纠缠时说明谁先动;`blocked` 必须指名缺失的基线、输入、状态、artifact 请求或宿主能力。旧 owner 的四值词表整条退役。

## 6. 资产编辑纪律(承接旧 owner 的源文件头,落在文档而非资产正文)

编辑 `src/graph_skill_runtime/integrations/assets/moirai/` 下任何文件时:

1. **English only。** 资产正文一律英文。`catalog.py` 校验 UTF-8 与 LF,不校验语言;这一条靠编辑纪律。
2. **只写增量,不复述宿主基础提示。** 角色与技能正文是叠加在宿主自身提示之上的一层,不重述、不与之矛盾。
3. **事实归知识文件,正文只链接。** 不把 schema、字段表、错误码表抄进角色或技能正文——副本必然漂移。
4. **不写工具机制。** 工具边界由代码强制;正文不写"先调 A 再调 B"式的机械流程。
5. **改源文件,不改投影。** 宿主目录下的 `~/.claude/skills/...` 之类是 installer 按安装时刻定格的受管副本,由 installer 自己的 ownership manifest(内容哈希)管辖;它们不随本仓更新自动跟进。资产改动后需重装一次才会刷新。
6. **知识文件之间不互链。** 一个知识文件能否到达宿主,取决于宿主激活了哪个技能、而该技能声明了哪些 reference;知识文件无法知道兄弟文件是否被一起投影,互链因此在部分投影里必然是死链。路由由 `KB-00-hub.md` 与各技能正文承担。**本条已代码化**(见 §7),因为撰写本次内容时正是先犯了这个错才发现它。
7. **改内容就升 `asset_version`。** 该字段是 installer ownership manifest 记录的版本锚;内容变了不升版,"宿主装的是哪一版"就失去判据。

## 7. 本次同批落地的三道资产门禁

前两条属"让非法状态不可表示",而非事后检查:

1. **技能正文的 `references/<file>` 链接必须在该技能的 manifest reference 子集里。** renderer 只把声明过的子集拷到投影的 `references/` 下,所以正文链到别的文件,在**每一个**宿主投影里都是死链。manifest 是该子集的 owner,这道校验让正文无法与它不一致。
2. **知识文件不得链接兄弟知识文件**(理由见 §6-6)。

两条都在 `PackagedMoiraiAssets` 构造时报错,报错文本指名违规的技能/文件与目标文件名。

第三条是**自指纹门禁**,承担的是另一件事——**证明本仓的 bundle 就是它登记的那个**:

3. **bundle 的树 digest、文件数、`asset_version` 与 `roles[].skills` 关系必须等于随仓登记值**(`tests/integrations/moirai-asset-lock.json`)。资产内容一改,门禁即红,必须在**同一次评审**里用 `uv run python scripts/repin_moirai_asset_lock.py` 重钉。

**为什么这道门必须在本仓,而不在下游读者那里。** 下游读者(发起方仓)手上只有一份**出处记录**,它没有 bundle 的副本,因此它**无法验证**自己记的值对不对——"权威侧变动未同批重钉即红"这句话此前没有任何代码编码。能证明"资产现在是什么"的只有资产所在地,所以门禁落在本仓;下游那份记录的作用是让人在评审时看见"当时读的是哪一版",两仓的**版本锚 + digest 互相印证**是人审的对账点。

**形状借自 `go.sum` 与 `package-lock.json` 的 `integrity`**:内容哈希入库,改内容必须在同一次评审里改哈希,于是静默改动不可能发生。**拒掉自动刷新**——记录的全部价值就在于"有人动了它、且被看见";自动重钉会把每次静默改动报成绿。报错文本自带重钉命令,这一点借自发起方仓的 audited-doc 哈希锁。

**登记文件为什么不放在资产目录旁边**:bundle 是闭集,`integration.json` 声明每一个成员、`PackagedMoiraiAssets` 拒绝任何未声明文件——锁文件放进 `assets/moirai/` 会把它本该保护的那个包直接弄坏。所以它放在 `tests/integrations/` 下,它是门禁产物,不是资产。

**digest 算法上的两处跨平台陷阱**(两仓必须逐字节一致,否则两份记录无法由人对照):①排序键必须是 **POSIX 相对路径字符串**,不能是 `Path` 对象——`PurePath` 的比较在 Windows 上不区分大小写、在 POSIX 上区分,同一棵树会得出两个 digest(这一条是实测踩出来的:第一版在 Windows 上算的值,在 Ubuntu 与 macOS 两个 runner 上同时红);②内容先**归一化为 LF** 再哈希,行尾是 checkout 的属性、不是内容的属性。

**`asset_version` 本次不再上调的理由**:内容在 `1.1.0` 之上又改了两处(KB-04 角色解析、KB-09 命名空间),但 `1.1.0` **尚未落 main、也没有任何已合并的下游记录引用过它**——它此刻只存在于本 PR 与发起方仓那个同样未合并的 PR 正文里,两处都在同一批修订中改。若为此跳到 `1.1.1`,main 就会从 `1.0.0` 直接跳到 `1.1.1`,而 `1.1.0` 从未命名过任何东西——一个指向空的版本号比复用一个未发布的版本号更妨碍阅读。规则本身写进门禁的报错文本:**被替换掉的 digest 一旦已发布(已合并,或已被下游记录),就必须同时上调 `asset_version`**,一个锚永不命名两份内容。

## 8. 本次改动清单与验收

**资产**:`integration.json`(`asset_version` 1.0.0 → 1.1.0、知识清单 15 → 16、八个技能各加 KB-15 reference、`moirai-agent-prompt-design` 与 `moirai-compile-repair` 的 reference 子集按新正文补齐)、新增 `knowledge/KB-15-working-discipline.md`、改 `knowledge/{KB-00,KB-01,KB-02,KB-04,KB-07,KB-08,KB-09,KB-10,KB-14}`、改四份 `roles/*.md`、改八份 `skills/*/SKILL.md` 中的七份(`moirai`、`moirai-graph-design`、`moirai-domain-analysis`、`moirai-agent-prompt-design`、`moirai-compile-repair`、`moirai-eval-judgement`、`moirai-web-research`)与 `moirai-brainstorming`。

**代码**:`integrations/catalog.py` 增两道校验(§7-1、§7-2);新增自指纹门禁 `tests/integrations/test_moirai_asset_lock.py` + 登记文件 `tests/integrations/moirai-asset-lock.json` + 重钉脚本 `scripts/repin_moirai_asset_lock.py`(§7-3)。

**测试**:`tests/integrations/test_packaged_assets.py` 更新版本与知识数断言,新增三项——技能正文链到未声明 reference 被拒、技能正文链到不存在的知识文件被拒、知识文件互链被拒。renderer 快照由资产替身驱动,不随真实资产内容变化,故无需重算。

**文档**:本文;并同步各处"当前资产清单"的陈述(asset version 与知识文件数)。**历史证据句不改**——描述已构建 `0.1.0a1` wheel 的那些句子(28 个成员、4/8/15 清单)说的是一个过去的构建产物,它当时确实如此;按本仓纪律,artifact 哈希与清单是证据身份,不是版本常量。**Phase 5 验收证据是在 asset version `1.0.0` 上取得的,本次内容变更之后需要一次新的验收才能主张同等结论。**

## 9. 修订记录

| 日期 | 变更 |
|---|---|
| 2026-09-01 | 初稿。八条已裁事项落位;§4.5 与 §5 两项按纪律**上升待裁**,资产侧按"信息不丢、不预判裁决方向"的临时形态实现。 |
| 2026-09-01 | 上升两项裁定落盘,**资产与代码零改动**——裁定的正是临时形态本身。§5 判定词表定为三值 + `rework` 必填归属限定(依据:两种形态都只是 prompt 层约定、无代码消费该枚举,四值不带来机器可查性;且限定形态能表达"设计与修复纠缠时谁先动",一个判定值编码不了两种 rework);§4.5 `agent-skill-map.json` 定为本批降格、批E cutover 时删除(依据:两个读者两种语言,今天删只能硬编码两份=新造第二事实源)。 |
| 2026-09-01 | 初审 rework 返修。资产两处按代码事实改写:`KB-04-agent-nodes.md` 的角色解析改为"只有相位与所属图两个来源、无宿主 fallback、解析不出即编译期 `[F-v3-agent-llm-role-missing]`"(对齐同批 PR 的终态,并做了全资产同族排查——其余 `fallback` 命中全部指执行器或 CLI 回退,与角色无关,不改);`KB-09-run-trace-checkpoint.md` 的 checkpoint 命名空间由三分法改为"两段可组合",补全实现会生成的 `iter<index>.agent:<phase_id>`。新增 §7-3 自指纹门禁,把"权威侧变动未同批重钉即红"真正编码在真相所在地。 |
