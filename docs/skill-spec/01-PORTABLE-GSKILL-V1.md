---
module: graph-skill-runtime
doc: portable-gskill-v1
role: contract
status: FROZEN
ssot: graph_skill_format_templates
aligns_with: ../design/v1-alignment.md
updated: 2026-09-01
---

# Portable gSkill v1 格式规范

本文定义 Graph Skill Runtime 当前实现的 portable 文件格式、bundle 编译边界和一次性迁移契约。Phase 2 已完成原子切换：production compile、predict、run、inspect、SDK、CLI 与 MCP 只读取本文格式；legacy v0.3 parser 只在显式 `gskill migrate studio-skill` converter 边界可达。[`00-FORMAT-GROUND-TRUTH.md`](./00-FORMAT-GROUND-TRUTH.md) 已是 `superseded` 的 converter 输入契约与历史证据。

**本文状态是 `FROZEN`。** 这个状态词由两个同时成立的条件定义：契约语义已完成审校并由 owner 盖章；本文全文的 SHA-256 摘要（先把 CRLF 与 CR 归一化成 LF，再对 UTF-8 字节求摘要）已作为一条 seal 记录落入 [`tests/contract-seals.yaml`](../../tests/contract-seals.yaml)。前者是人读的背书，后者是机器强制，两个载体缺一不可——只改状态词而不落记录不构成 `FROZEN`，这正是本文在 2026-09-01 之前处于 `audited-ready`（语义已审、机器锁未接上）的原因。

`FROZEN` 是审计通过的背书，不是禁止改动。它保证的是：本文不会被静默改写，任何一个字节的变化都必须是一次显式的、留下书面痕迹的决定。

**之后如何修订本文——只有一条路。** 改正文，并在同一个 pull request 内往 [`tests/contract-seals.yaml`](../../tests/contract-seals.yaml) **追加**一条带 `pm_approval` 的 seal 记录（`exemption_id` / `file` / `sha256` / `reason` / `pr` / `pm_approval`）；同一文件的**最后一条**记录即当前钉值，旧记录原样保留作为审计轨迹。**没有记录的改动会被锁拦下**——这就是主仓状态机 §1.2「`FROZEN` ──改动需 exemption（否则哈希锁拦）」与 §1.3「改动触发测试，须 exemption」在本仓的落地形态。

新摘要由锁的失败信息直接打印；**失败信息里那条命令就是权威命令**，可原样粘贴执行（单行、无 here-document，Windows PowerShell 与 bash 同样可跑）：

```
uv run python -c "import hashlib,pathlib;p=pathlib.Path('docs/skill-spec/01-PORTABLE-GSKILL-V1.md');print(hashlib.sha256(p.read_text(encoding='utf-8').replace(chr(13)+chr(10),chr(10)).replace(chr(13),chr(10)).encode('utf-8')).hexdigest())"
```

**不存在第二条路。** 把状态词降回 `audited-ready`，或删掉本文的 seal 记录，都不是修订而是撤销背书。`FROZEN` 的唯一合法去向是被新版契约取代后转 `superseded`，而那要求新版契约先存在并通过同样的审计。

本文使用“必须”“不得”“可以”表达强制要求、禁止行为和允许行为。目标设计的架构依据见 [`v1-alignment.md`](../design/v1-alignment.md)，Agent Skills 入口遵守 [Agent Skills specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx)。

## 1. 目标、范围与术语

Portable gSkill v1 把宿主可发现的使用说明、机器可读的图拓扑和运行时配置分成独立事实源：

1. 根 `SKILL.md` 说明何时以及怎样调用这个业务 skill；
2. `graph.yaml` 声明机器可读的 graph、phase、边、输入输出和 artifact；
3. phase Markdown 文件声明一个节点的行为；
4. `gskill.toml` 可以声明项目级运行配置和具名 `RunPreset`，但不声明 topology；
5. `.gskill/` 保存运行快照、checkpoint、trace 和物化 artifact，不属于 portable source。

本文使用以下术语：

- **业务 gSkill**：用户拥有并显式交给 runtime 的一个目录。安装 runtime 或导入 Python package 不会注册、复制或全局发现该目录。
- **skill root**：业务 gSkill 的顶层目录，也是唯一根 `SKILL.md` 和根 `graph.yaml` 所在目录。
- **root graph**：skill root 的 `graph.yaml` 所声明的入口 graph。
- **registry graph**：`graphs/<graph_id>/graph.yaml` 所声明的可复用 graph。
- **graph directory**：root graph 的 skill root，或 registry graph 的 `graphs/<graph_id>/` 目录。
- **phase**：graph 中一个有稳定 id 的节点；其行为由同名 phase 目录中的一个类型文件声明。
- **graph call edge**：`SUBGRAPH.md` 或 `AGENT.md` 的显式 graph 引用形成的调用关系。
- **bundle compile**：以一个 skill root 为输入，一次发现、解析并交叉校验根入口、所有 graph 和所有 phase 的编译过程。
- **artifact declaration**：root graph 声明的可物化输出定义。
- **artifact request**：`RunPreset` 或某次 `RunRequest` 对一个 declaration 的选择。

Runtime、SDK、CLI 和 MCP 都按调用者显式提供的 skill root 工作。Portable source 不保存 credential、宿主 session、Studio 扫描投影或一次运行的实际输入值。

## 2. 唯一目录布局

一个 v1 bundle 使用以下布局：

```text
<skill-name>/
├── SKILL.md
├── graph.yaml
├── gskill.toml                         # optional project runtime/preset config
├── phases/
│   └── <phase_id>/
│       ├── LOGIC.md | AGENT.md | SUBGRAPH.md
│       ├── actions/                    # LOGIC-local code, when declared
│       ├── tools/                      # AGENT-local tools, visible only here
│       └── validator.py                # optional, when validator: true
├── graphs/
│   └── <graph_id>/
│       ├── graph.yaml
│       └── phases/
│           └── <phase_id>/
│               ├── LOGIC.md | AGENT.md | SUBGRAPH.md
│               ├── actions/
│               ├── tools/
│               └── validator.py
├── tools/                              # skill-root tools, visible to every AGENT
├── references/                         # skill-root reference resources
├── examples/                           # skill-root example resources
├── scripts/                            # skill-root host-callable scripts
├── assets/                             # skill-root static assets
└── .gskill/                            # runtime state; not portable source
```

`graphs/` 是单层 registry。一个 registry graph 的目录直接位于 `graphs/<graph_id>/`；graph directory 内没有第二个 registry。Root graph 和 registry graph 都使用本文第 4 节的同一 `graph.yaml` schema。

每个 `phases/<phase_id>/` 恰好对应所属 `graph.yaml.phases[]` 的一个对象，并恰好包含 `LOGIC.md`、`AGENT.md`、`SUBGRAPH.md` 之一。文件名决定 phase 类型，目录名决定 phase id；phase frontmatter 不重复保存这两个事实。

仓库内作者编写的文本使用 UTF-8 与 LF。Portable path 使用 `/` 分隔，并以 skill root 或本文明确指定的 graph directory 为解析基准。

## 3. 根 `SKILL.md`：Agent Skills 入口

根 `SKILL.md` 是标准 Agent Skill 文件：YAML frontmatter 后接 Markdown 指令正文。它负责宿主发现、激活说明和调用协议，不负责 graph topology。

### 3.1 Frontmatter

根 frontmatter 的字段如下：

| 字段 | 必需 | 类型与约束 | 含义 |
| --- | --- | --- | --- |
| `name` | 是 | 1–64 个字符；只含 ASCII 小写字母、数字、`-`；不能以 `-` 开头或结尾，不能有连续 `--` | Agent Skill 的稳定名称，必须与 skill root 的目录 basename 完全相等 |
| `description` | 是 | 1–1024 个字符 | 同时说明该 skill 做什么、在什么请求下应激活 |
| `license` | 否 | 非空字符串 | license 名称或 skill 内 license 文件引用 |
| `compatibility` | 否 | 1–500 个字符 | 必要的产品、系统包、网络或运行环境要求 |
| `metadata` | 否 | `string -> string` map | Agent Skills 未定义的附加元数据 |
| `allowed-tools` | 否 | 以空格分隔的字符串 | Agent Skills 的实验性预授权工具提示；宿主支持程度可能不同 |

顶层字段集合以本表为准；需要附加 metadata 时放入 `metadata` 的字符串映射，不增加平行的自定义顶层字段。

Root `allowed-tools` 是 Agent Skills 宿主的实验性预授权提示，不是 runtime 内部 AGENT phase 的业务 tool registry；后者由第 5.2 节的 `tools` 字段与第 6 节的两级 `tools/` scope 共同定义。

最小入口示例：

```markdown
---
name: story-analysis
description: Compile and run the story-analysis graph skill. Use for structured story analysis, comparison, or golden evaluation requests.
---

# Story analysis

Use the installed `gskill` interface with this directory as the explicit skill root.
```

### 3.2 Body 与生成协议

Body 是宿主激活该 skill 后加载的说明。作者可以写步骤、输入示例、边界条件和资源链接。Body 不使用 graph 或 phase schema，也不复制 `graph.yaml` 中的 node、edge、I/O、artifact 或 graph registry。

脚手架和迁移器生成的 body 必须表达以下调用协议：

1. 每次调用都把当前目录作为显式 skill root；
2. 优先使用 `gskill` MCP server 的同名结构化用例，例如 `compile`、`predict`、`run`、`resume` 或 `submit_agent_result`；
3. MCP 不可用时，调用已安装的 `gskill` console command 及等价 subcommand；CLI fallback 不使用 `python -m graph_skill_runtime` 或其他依赖宿主当前解释器的模块入口；
4. 两种入口都把同一 skill root 传给 runtime，并消费结构化 result、diagnostic 和 error；
5. 协议不假定 package 安装或 Python import 已注册业务 skill。

## 4. `graph.yaml`：唯一机器拓扑

`graph.yaml` 是一个 YAML mapping，不使用 Markdown frontmatter 或 XML body。Root graph 与 registry graph 使用同一闭合字段集合；唯一的上下文差异是 `artifacts` 只允许出现在 root graph。

### 4.1 Graph 字段

```yaml
schema_version: gskill.graph.v1
graph_id: main
description: Analyze source material and produce a report.
llm_role: analyst

io:
  inputs:
    type: object
    required: [source]
    properties:
      source: {type: string}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}

phases:
  - id: collect
    depends_on: [input]
    output: false
  - id: synthesize
    depends_on: [collect]
    output: true

artifacts:
  - artifact_id: report
    stem: report
    fields: [report]
    mode: single
    format: md
```

| 字段 | 必需 | 类型与约束 | 含义 |
| --- | --- | --- | --- |
| `schema_version` | 是 | string，精确等于 `gskill.graph.v1` | graph 文件 schema |
| `graph_id` | 是 | 1–64 个字符，匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$` | bundle 内全局唯一 graph id |
| `description` | 是 | 非空字符串 | 该 graph 的职责说明 |
| `llm_role` | 否 | 非空字符串 | graph 内 AGENT phase 的默认 LLM role |
| `io` | 是 | `inputs` 与 `outputs` 两个 JSON Schema object | graph 调用边界 |
| `phases` | 是 | 非空 `GraphPhase` object list | phase 注册表和 phase DAG 的唯一真相源 |
| `iterate` | 否 | `IterateSpec` | graph 级迭代 |
| `artifacts` | 否，仅 root graph | `ArtifactDeclaration` list | 该业务 skill 可以物化的具名 artifact |

Root `graph_id` 不需要等于根 `SKILL.md.name`。Registry graph 的 `graph_id` 必须与其 `graphs/<graph_id>/` 目录名完全相等。Root 与所有 registry graph 的 `graph_id` 在整个 bundle 内共享一个唯一命名空间。

### 4.2 `GraphPhase`

`phases` 中每个对象具有三个必需字段：

| 字段 | 类型与约束 | 含义 |
| --- | --- | --- |
| `id` | 匹配 `^[A-Za-z][A-Za-z0-9_-]*$`，且不能是保留字 `input` | graph 内唯一 phase id，并与 phase 目录名完全相等 |
| `depends_on` | 非空、无重复的 string list | 本 phase 的全部直接上游 |
| `output` | boolean | 本 phase 是否是 graph 输出节点 |

`depends_on` 是显式 list，不接受逗号拼接字符串。`input` 是当前 graph 输入边界的 sentinel，不是 phase id；入口 phase 写 `depends_on: [input]`。`input` 作为依赖时单独出现，其他 phase 只引用同一 graph 的已注册 phase id。同一 graph 的 phase id 在大小写不敏感比较下也必须唯一，避免同一 bundle 在不同文件系统上表示成不同目录集合。

一个 graph 可以有多个入口 phase 和多个输出 phase。每个 phase 都必须从 `input` 可达；每个 `output: true` phase 是 DAG terminal，并且 graph 至少有一个输出 phase。编译后的稳定 phase 地址是 `<graph_id>/<phase_id>`。

### 4.3 I/O schema 与静态数据流

每个 graph 和 phase 的 `io.inputs`、`io.outputs` 都是 Draft 2020-12 JSON Schema object：

```yaml
io:
  inputs:
    type: object
    required: [field_a]
    properties:
      field_a: {type: string}
  outputs:
    type: object
    required: [field_b]
    properties:
      field_b: {type: string}
```

顶层 `type` 精确为 `object`，`properties` 必须存在，`required` 只能列出同一 schema 的 `properties` key。Graph input 初始化当前 graph 的 blackboard；phase 只读取其 `io.inputs` slice，只能把其 `io.outputs` 声明的 key 写回 blackboard。Graph 输出由 `output: true` terminal phase 可提供的值组成，并满足 graph `io.outputs`。

静态数据流校验继续适用：每个必需 phase input 必须由 graph input、上游 phase output、显式运行绑定或 iterator 注入提供；每个必需 graph output 必须能在输出 phase 处取得。

### 4.4 `IterateSpec`

`iterate` 可以出现在 graph 或任一 phase 声明中。它只有 `batch` 和 `loop` 两种模式。

```yaml
iterate:
  mode: batch
  over: chapters
  item_var: chapter
  range: [1, 10]
  concurrency: 4
```

```yaml
iterate:
  mode: loop
  over: chapters
  item_var: chapter
  range: [1, 10]
  accumulate:
    var: previous_results
    init: []
    from: result
    merge: append
```

| 字段 | 必需 | 类型与约束 | 含义 |
| --- | --- | --- | --- |
| `mode` | 是 | `batch` 或 `loop` | 并发 map 或顺序累积 |
| `over` | 是 | 非空字段路径 | 被迭代的 array |
| `item_var` | 是 | 非空字符串 | 每轮注入当前 item 的字段名 |
| `range` | 否 | 两个 integer 组成的闭区间 | 选择迭代范围 |
| `concurrency` | `batch` 可选 | integer，至少 1 | batch 并发上限 |
| `accumulate` | `loop` 必需 | object | loop 累积规则 |

`accumulate` 必须包含 `var`、`init`、`from` 和 `merge`；`merge` 为 `append`、`extend`、`merge`、`replace` 之一。

### 4.5 Root-only artifact declarations

Root `graph.yaml.artifacts` 的每个对象具有以下字段：

| 字段 | 必需 | 类型与约束 | 含义 |
| --- | --- | --- | --- |
| `artifact_id` | 是 | 匹配 `^[A-Za-z][A-Za-z0-9_-]*$`；root 内唯一 | declaration 的稳定身份 |
| `stem` | 是 | 匹配 `^[A-Za-z0-9][A-Za-z0-9._-]*$` | runtime 物化名称的可移植 stem，不含目录分隔符 |
| `fields` | 是 | 非空、无重复的 output field name list | 从 graph 输出选择的字段 |
| `mode` | 是 | `single` 或 `per-item` | 单个产物或逐项产物 |
| `format` | 是 | `json` 或 `md` | 物化格式 |

`fields` 中每个名称都必须存在于 root graph 的 `io.outputs.properties`。数组位置不是 artifact 身份；重新排列 declarations 不改变任何 `artifact_id`。

`single` 把所选字段作为一个逻辑产物物化。`per-item` 把 list-valued 所选字段按 item 位置物化。`format` 选择 JSON 或 Markdown materializer；request 只能选择 declaration，不能改变 materializer 所消费的字段集合。

## 5. Phase 文件

Phase 类型文件使用 YAML frontmatter 和可选 Markdown body。`name` 是面向人的显示名；phase identity 始终来自目录名和 `graph.yaml.phases[].id`。

三个 phase 类型共享以下声明语义：

- `io` 是第 4.3 节定义的输入输出边界；
- `validator` 是可选 boolean，默认 `false`；
- `allow_sequential_overwrite` 是可选 output field name list，默认 `[]`；
- `iterate` 是可选的第 4.4 节 `IterateSpec`。

### 5.1 `LOGIC.md`

`LOGIC.md` 定义确定性 action chain：

```markdown
---
name: normalize text
io:
  inputs:
    type: object
    required: [raw_text]
    properties:
      raw_text: {type: string}
  outputs:
    type: object
    required: [normalized_text]
    properties:
      normalized_text: {type: string}
actions: [strip_noise, normalize_whitespace]
validator: false
---

<action>strip_noise</action>
<action>normalize_whitespace</action>
```

合法 frontmatter 字段是 `name`、`io`、`actions`、`validator`、`allow_sequential_overwrite` 和 `iterate`。`name`、`io` 和非空、无重复的 `actions` 必需。Body 的 `<action>` 序列与 `actions` registry 包含完全相同的名称，并决定执行顺序。

每个本地 action 位于所属 graph directory 的 `phases/<phase_id>/actions/<action_name>.py`，导出 `def <action_name>(inputs) -> dict`。`inputs` 是只读 phase-local snapshot；返回 dict 是 action 写出业务值的唯一通道，返回 key 属于 phase `io.outputs.properties`。

### 5.2 `AGENT.md`

`AGENT.md` 定义 runtime 内部的 agent node。它不是一个可被宿主独立发现的 Agent Skill。

```markdown
---
name: review chapter
llm_role: analyst
use_graph_llm_role: false
validator: false
max_iterations: 10
context_access: [working_memory]

io:
  inputs:
    type: object
    required: [chapter]
    properties:
      chapter: {type: object}
  outputs:
    type: object
    required: [review]
    properties:
      review: {type: string}

tools: [lookup_style_rule]
subgraphs:
  - name: evidence_pipeline
    graph: evidence-pipeline
    description: Extract evidence before review.
references:
  - id: R1
    path: references/style.md
    summary: Style and scoring rules.
examples:
  - id: E1
    path: examples/review.md
    summary: A complete review example.
---

<role>You review one chapter.</role>
<goal>Return a grounded review.</goal>
<step id="S1" name="read">Read the chapter and relevant references.</step>
<protocol id="P1">Cite input evidence for each conclusion.</protocol>
<example id="E2">State uncertainty when evidence is incomplete.</example>
```

合法 frontmatter 字段如下：

| 字段 | 必需 | 类型与含义 |
| --- | --- | --- |
| `name` | 是 | 非空显示名 |
| `io` | 是 | phase 输入输出 schema |
| `llm_role` | 否 | phase 自己的 LLM role |
| `use_graph_llm_role` | 否 | boolean，默认 `false`；为 `true` 时只取 graph role，保留但不选择 phase role |
| `validator` | 否 | boolean，默认 `false` |
| `max_iterations` | 否 | integer，范围 1..50；默认 10 |
| `tools` | 否 | 无重复的业务 tool name list；每项必须从 skill-root 或本 phase 的 tool registry 解析 |
| `context_access` | 否 | 无重复的 `working_memory` / `artifact` list；默认 `[]` |
| `subagents` | 否 | `{name, target_skill, description}` list；`target_skill` 是显式解析的外部 Agent Skill 名称 |
| `subgraphs` | 否 | `{name, graph, description}` list；`graph` 是本 bundle 的 registry graph id |
| `references` | 否 | `{id, path, summary}` list；path 从 skill root 解析 |
| `examples` | 否 | `{id, path, summary}` list；path 从 skill root 解析 |
| `allow_sequential_overwrite` | 否 | 允许本 phase 覆盖祖先输出的字段名 list |
| `iterate` | 否 | `IterateSpec` |

有效 LLM role 的选择顺序是：`use_graph_llm_role: true` 时只使用所属 graph 的 `llm_role`，phase 自己的 `llm_role` 保留但不参与本次选择；`use_graph_llm_role: false` 时依次使用 phase role、所属 graph 的 `llm_role`。

该链条必须解析出一个显式声明的 role 名。**Runtime 不发明兜底 role 名，也没有默认 role**：链条解析不到任何名字时该 phase 未设置 role，属于缺陷而不是一种默认状态。

关于 role 的两个问题分属两层，判定条件不同：

1. **有没有名字**——只由 portable source 决定，与宿主无关，因此**任何编译路径无条件判定**（SDK、CLI、MCP、`inspect`、`predict` 一律适用）：解析不到名字即编译期 `[F-v3-agent-llm-role-missing]`。
2. **这个名字在本宿主能不能路由**——只有宿主答得出，因此由注入的 role resolver 在严格 compile/run preflight 判定（`[F-v3-agent-llm-role-unknown]`），未注入 role 权威时不判定。Portable source 不自建 registry。

Registry graph 各自声明自己的 `llm_role` 默认值；调用方 graph 的默认值不进入被调用 registry graph 内部。

> **修订记录（2026-08-31 用户裁决，本节 role 选择链）**：本节此前规定链条末端为“宿主 fallback”，即 phase 与 graph 都未声明 role 时由 runtime 取一个约定角色名交给宿主解析。该设计被 2026-08-31 用户裁决推翻——“默认角色应该是空，必须要设置，不设置 compile 报错”。推翻依据是实证：runtime 约定的那个名字在任何宿主的种子 role 表里都不存在，于是未设置 role 的 skill 编译全绿、运行期才死在无可用路由上，缺陷位置与报错位置相隔一整个阶段。现行契约把“未设置”定为编译期缺陷，由 `[F-v3-agent-llm-role-missing]` 承载，且该判定不依赖宿主注入 role 权威——否则规则会落在生产编译入口到不了的地方，等于没有生效。

`context_access` 是 framework context capability 的显式门。`working_memory` 挂载读取既有 working memory 的能力，`artifact` 挂载读取 runtime artifact 的能力；未列出的能力不挂载。它不把 framework builtin 改写成业务 tool，也不由 `tools` 重复声明。

Body 顶层标签为：恰一个 `<role>`、恰一个 `<goal>`，以及零到多个 `<step id name>`、`<protocol id>`、`<example id>`。Agent 通过 runtime 提供的完成协议写出 `io.outputs`。

Compiler 从结构化 body、资源 registry、I/O schema 和 runtime cognitive template 派生最终 `system_prompt`。`system_prompt` 是 compiled AST 值，不是 `AGENT.md` authoring 字段，也不由作者在 frontmatter 或 body 顶层标签中直接提供。

Body mention 按声明解析：`@tool:<name>`、`@subagent:<name>`、`@subgraph:<name>`、`@reference:<id>`、`@example:<id>` 和 `@protocol:<id>` 分别引用对应 registry；inline `<example id>` 也可以满足 `@example`。

### 5.3 `SUBGRAPH.md`

`SUBGRAPH.md` 定义一个调用 registry graph 的普通 phase：

```markdown
---
name: evidence pipeline
graph: evidence-pipeline
io:
  inputs:
    type: object
    required: [chapter]
    properties:
      chapter: {type: object}
  outputs:
    type: object
    required: [evidence]
    properties:
      evidence: {type: array}
validator: false
---
```

合法 frontmatter 字段是 `name`、`graph`、`io`、`validator`、`allow_sequential_overwrite` 和 `iterate`；`name`、`graph` 与 `io` 必需。`graph` 是 registry `graph_id`，由 compiler 解析为 `graphs/<graph_id>/graph.yaml`。父 phase 和被调用 graph 通过各自的 `io` 形成显式数据边界。文件不需要 Markdown body。

### 5.4 Validator 与顺序覆盖

当 `validator: true` 时，同一 phase 目录的 `validator.py` 导出：

```python
def validate(output: dict, state_slice: dict, **kwargs) -> None | dict:
    ...
```

返回 `None` 表示保持输出；返回 dict 表示以该 dict 作为校验后的输出，并再次通过 phase `io.outputs` schema。Validator 的异常或其他返回类型形成结构化 phase failure。

`allow_sequential_overwrite` 只列当前 phase 的 `io.outputs.properties` 字段。若当前 phase 与任一传递祖先 phase 输出同名字段，该名称必须出现在当前 phase 的列表中；这表示作者明确允许沿同一 DAG 路径覆盖。并行且互非祖先的 phase 不使用这项授权来解决写冲突，仍由 blackboard/dataflow contract 判定。

## 6. Flat graph registry、调用图与资源

所有 registry graph 都直接位于 skill root 的 `graphs/` 下，且 graph id 在整个业务 gSkill 内唯一。`SUBGRAPH.md.graph` 和 `AGENT.md.subgraphs[].graph` 是 graph call edge 的唯一声明来源。

Compiler 由这些 edge 生成 call graph、`callers` 和面向人的 parent view。Portable source 不保存 `parent` 或 `callers` 字段；同一 registry graph 可以被多个 caller 复用。`gskill inspect --call-graph` 必须投影同一组 edge，不能维护第二份 topology。

资源与可执行实现按 owner 分三类：

1. `references/`、`examples/`、`scripts/`、`assets/` 是 skill-root resources。根 `SKILL.md` 链接和 `AGENT.md` 的 resource path 都从 skill root 解析。`scripts/` 是 Agent Skills 宿主资源，不自动进入 runtime tool registry。
2. Skill-root `tools/` 是整个 bundle 的业务 tool owner。它注册的 tool 对 root graph 和所有 registry graph 的 AGENT phase 可见。
3. Phase 行为实现属于 graph。Root phase 的 action、validator 和 phase-local tool 位于 `<skill_root>/phases/<phase_id>/`；registry phase 的同类文件位于 `<skill_root>/graphs/<graph_id>/phases/<phase_id>/`。Phase-local `tools/` 只允许属于 `AGENT.md` 的 phase，并且只对该 AGENT 可见；`actions/` 只允许属于 `LOGIC.md` 的 phase。

两个 `tools/` scope 都通过目录内一级 `.py` 模块注册业务 tool；模块定义的可调用函数以函数名形成 tool registry entry。`AGENT.md.tools` 是显式调用清单：每个名称必须解析到一个 skill-root tool 或当前 phase-local tool，只有列出的业务 tool 才挂载到该 AGENT。Root 与当前 phase 出现同名 tool 属于歧义，不采用 shadowing；不同 phase 的 local tool 可以同名，因为其可见域不相交。Framework builtin 由 runtime contract 挂载，`context_access` 控制的 builtin 由该字段授权，两类 builtin 都不通过业务 `tools/` 目录或 `AGENT.md.tools` 重复注册。

资源路径是 POSIX-style 相对路径，只使用 `A-Z`、`a-z`、`0-9`、`.`、`_`、`-`、`/`，解析真实路径后仍位于 skill root。Graph-local code 还必须位于所属 graph directory。`scripts/` 中存在文件不会自动把它注册为 LOGIC action 或 AGENT tool；声明与实现仍通过各自显式 registry 连接。

## 7. Artifact declaration 与 request

Declaration 回答“这个业务 skill 能产出什么以及怎样物化”，唯一 owner 是 root `graph.yaml.artifacts`。Request 回答“这次选择哪些 declaration”，owner 是具名 `RunPreset`、`RunInvocation` 合并后的 immutable `RunRequest`。

`ArtifactRequest` 的业务字段只有：

| 字段 | 必需 | 含义 |
| --- | --- | --- |
| `artifact_id` | 是 | 引用 root declaration 的稳定 id |
| `destination` | 否 | 本次运行的输出 destination，由 runtime/host 边界解析和校验 |

例如 project `gskill.toml` 可以选择 declaration：

```toml
schema_version = "gskill.config.v1"

[[presets.default.artifact_requests]]
artifact_id = "report"
```

同一次解析后的 request 中，每个 `artifact_id` 最多出现一次。Compiler/RunRequest boundary 在执行前把 request id 连接到 root declaration；destination 只改变这次写到哪里，不改变 `stem`、`fields`、`mode` 或 `format`。

## 8. Bundle compile

Bundle compile 的输入是一个显式 skill root，输出是一个 normalized bundle 或一组完整结构化 diagnostics。Compiler 先建立文件 inventory，再解析独立文档，最后做 graph 内和 graph 间交叉校验；只有没有 fatal diagnostic 时才装配或执行 graph。

一次 compile 至少执行以下步骤：

1. 发现根 `SKILL.md`、根 `graph.yaml`、flat registry graph 和各 graph 的 phase 目录；
2. 校验 Agent Skills metadata、所有 `graph.yaml` 与 phase 文档的闭合 schema；
3. 连接 graph id、registry directory、phase registry、phase directory 与 phase 类型文件；
4. 对每个 graph 校验 phase DAG、I/O dataflow、output reachability 和顺序覆盖；
5. 解析全部 graph reference，建立 call graph 并检测调用环；
6. 校验 resource path、action、tool scope/显式注册、validator、mention 和 artifact declaration；
7. 如提供 `RunPreset` 或 `RunRequest`，按 root declarations 校验 artifact requests。

Compiler 必须在同一轮聚合所有能够独立确认的缺陷。至少以下类别不能采用“修一个后下次才看到另一个”的 first-error 行为：

| 类别 | 同轮必须报告的事实 |
| --- | --- |
| Root inventory | 缺少根 `SKILL.md`、缺少根 `graph.yaml`；二者同时缺失时报告两项 |
| Agent Skills metadata | YAML、必需字段、name/description 约束和 name/目录不一致 |
| Graph inventory | 非法或重复 graph id、root/registry 冲突、registry 目录与 id 不一致 |
| Phase inventory | 非法或重复 phase id、注册 phase 缺目录、目录无注册项、目录/id 不一致、零个或多个类型文件 |
| Phase DAG | 未知 dependency、重复 dependency、`input` sentinel 误用、不可达节点、无输出、非 terminal 输出和 graph 内 cycle |
| Graph call | 未知 graph reference 和 graph call cycle |
| Agent capability | 未知或重复业务 tool、tool scope 歧义、非法 `context_access` capability |
| Artifact | declaration 字段、重复 id、未知 output field、未知 request id 和重复 request |

一个文档无法解析时，compiler 仍继续检查其他独立文件和目录；依赖该文档成功解析才能得出的二级结论不伪造。每条 diagnostic 至少携带稳定 code、相对 skill root 的 source path、能确定时的 field/line location 和完整 message。

递归 Agent Skills discovery 对一个合格 bundle 只能得到 `<skill_root>/SKILL.md`。Compiler 的 inventory 因此也检查 bundle 内的其他 `SKILL.md`；内部 agent node 使用 `AGENT.md`，registry graph 不拥有自己的 Agent Skills 入口。

## 9. 一次性 Studio skill converter

Legacy 读取只存在于显式的一次性转换命令：

```text
gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]
```

`SOURCE` 是待转换的 legacy v0.3 Studio skill root，`DESTINATION` 是全新 v1 skill root。`--runtime-config` 显式选择旧 `studio.runtime_config.v2` 文件；省略时，converter 在存在的情况下读取 `SOURCE/.workspace/runtime_config.json`，不存在则只转换 portable source。`--preset-id` 为生成的 project preset 命名，默认 `migrated`。

Converter 先完成只读 preflight，再在同一 filesystem 的临时 sibling 目录生成完整输出，最后以 create-if-absent 方式发布到 `DESTINATION`。它不修改 `SOURCE`，也不以覆盖方式发布任何 destination 文件。

### 9.1 Source 到 target 的转换

| Legacy source | v1 target |
| --- | --- |
| 根 `GRAPH.md` metadata | 根 `SKILL.md` 的 Agent Skills metadata，以及根 `graph.yaml` 的 graph metadata |
| `GRAPH.md` phase registry 和 body `<phase>` edge/output 标记 | `graph.yaml.phases[]` 的 `{id, depends_on, output}` objects |
| `phases/<id>/LOGIC.md` | 同一 graph 的 `phases/<id>/LOGIC.md` |
| `phases/<id>/SKILL.md` | 同一 graph 的 `phases/<id>/AGENT.md` |
| `phases/<id>/SUBGRAPH.md` path | `SUBGRAPH.md.graph` registry id |
| Agent `subgraphs[].path` | `AGENT.md.subgraphs[].graph` registry id |
| 本地、被引用的旧 subskill root | `graphs/<graph_id>/graph.yaml` 与该 graph 的 `phases/` |
| 旧 runtime artifact definitions | 根 `graph.yaml.artifacts` declarations |
| 旧配置中已启用的 artifacts | `gskill.toml` 生成 preset 的 `artifact_requests` |

目标根 basename 必须是有效 Agent Skills `name`，生成的 `SKILL.md.name` 精确使用该 basename。Converter 从旧 description 生成合格的 activation description；旧 description 为空时使用确定性的用途说明。生成 body 使用第 3.2 节的 MCP-first、installed-CLI-fallback 协议。

旧 graph name 或目录 basename 规范化为小写 kebab graph id；所有旧引用重写成 id reference。迁移报告保存 source-relative graph/phase 路径到 destination-relative graph/phase 路径及 graph id 的映射。直接本地引用的 graph 被移动到 flat registry；物理 parent 不进入输出事实。

### 9.2 Runtime config 拆分

Converter 按 owner 拆分旧配置：

| 旧数据 | 输出 owner |
| --- | --- |
| `inputs.active.root` | generated `RunPreset.inputs` |
| `inputs.active.phases` | generated `RunPreset.bindings`，地址规范化为 `<graph_id>/<phase_id>/<field>` |
| node params/custom params | generated `RunPreset.node_overrides` |
| compare candidates | generated `RunPreset.compare_candidates` |
| breakpoints | generated `RunPreset.breakpoints`，使用稳定 graph/phase address |
| `{stem, fields, mode, format}` artifacts | root `graph.yaml.artifacts` |
| 已启用 artifact entries | generated `RunPreset.artifact_requests` |
| import manifest、removed/conflict 和 Studio mirror state | Studio adapter state 或迁移报告，不进入 portable/runtime declaration |

Preset 只保存可复用、非秘密的业务默认值和 secret reference，不保存 secret value。Artifact definition 不进入 preset；preset 仅用生成的 `artifact_id` 选择 declaration。

### 9.3 确定性 artifact id

Converter 用 declaration 内容而不是旧数组位置生成 id：

1. 先补齐旧默认值：`mode=single`、`format=json`；对 `stem` 和 field name 做 Unicode NFC 与首尾空白规范化，保留 `fields` 的语义顺序；
2. 把 `{stem, fields, mode, format}` 编码为 key 排序、无额外空白的 UTF-8 canonical JSON，并计算 SHA-256；
3. 把 stem 转成小写 kebab 候选：每段非 ASCII 字母数字归一为一个 `-`，去掉首尾 `-`；结果为空时使用 `artifact`，以数字开头时加 `artifact-`；
4. 若每个不同 definition 的候选都唯一，候选就是 `artifact_id`；
5. 若多个不同 definition 得到同一候选，冲突组中的每个 id 都写成 `<candidate>-<hash-prefix>`。Prefix 至少 8 个十六进制字符，并同时延长到全 bundle 唯一；最终 id 再与非冲突候选做一次全局冲突检查。

这个算法使同一 definition 在 artifact 数组重排后得到同一 id。完全相同的重复 definitions 在生成 id 前作为重复身份失败，不静默合并。迁移报告逐项记录旧数组 index、normalized definition、完整 SHA-256 和生成的 `artifact_id`。

### 9.4 Migration report

成功转换在 destination 写 `.gskill-migration-report.json`，schema version 为 `gskill.migration-report.v1`。报告至少包含：

- source-relative 到 destination-relative 的 graph 与 phase 文件映射；
- 旧 graph/path reference 到新 graph id 的映射；
- 每个旧 artifact index 到 definition hash 和 `artifact_id` 的映射；
- runtime config 字段进入 portable declaration、preset、Studio-only state 或未迁移项的分类；
- 生成 preset id；
- converter 版本和完成状态。

报告不复制 secret value。失败时 converter 输出同样结构的 diagnostics，但不发布 partial destination。

## 10. 失败与禁止行为

本节集中列出前述正向契约的拒绝规则。

### 10.1 Format 与 topology

- 根 `SKILL.md` 不接受 topology、I/O 或 artifact 字段；这些字段只属于 `graph.yaml`。
- `graph.yaml` 和 phase frontmatter 是闭合 schema；未知字段、重复 YAML key 或错误类型失败。
- Root 或 registry graph 缺文件、graph/phase id 与目录不一致、未注册目录、缺少 phase 类型文件或同目录多个类型文件均失败。
- Phase 文件不写 `mode`、`phase_id` 或 graph id；类型和身份由文件系统与 `graph.yaml` 连接。
- `AGENT.md` 不接受 authoring `system_prompt`、旧 `batch` 或任意 `metadata` 字段；最终 `system_prompt` 只由 compiler 派生。
- `GRAPH.md`、phase `SKILL.md`、path-based `SUBGRAPH.md`、嵌套 `graphs/`、隐式物理 parent 和未声明 edge 都不是 v1 输入。
- 未知 phase dependency、未知 graph reference、phase DAG cycle 和 graph call cycle 均在执行前失败。
- `artifacts` 出现在 registry graph 时失败。

### 10.2 Resource 与 request

- 绝对 resource path、`..` 逃逸、解析后越出 skill root 的 symlink target 或 graph-local code 越出 graph directory 均失败。
- `tools/` 出现在 LOGIC 或 SUBGRAPH phase、`AGENT.md.tools` 声明名无法解析、body 引用未列入该清单的业务 tool、同一可见域重复或 root/local 同名歧义均失败；compiler 不通过 shadowing 猜 owner。目录中存在但未被当前 AGENT 列出的 tool 不会挂载给该 AGENT。
- `context_access` 出现 `working_memory`、`artifact` 以外的值或重复值时失败；缺省 `[]` 表示不授予这两个读取能力。
- Artifact declaration 的空/重复 fields、非 root output field、重复 id 或非法 mode/format 失败。
- Unknown 或 duplicate `ArtifactRequest.artifact_id` 失败；即使两项内容相同也不合并。
- Request 出现 `stem`、`fields`、`mode`、`format` 或其他 declaration override 字段时按未知字段失败。`destination` 不是改写 declaration 的入口。

### 10.3 Converter

- `SOURCE` 与 `DESTINATION` 相同、destination 已存在、destination basename 不是合法 Agent Skills name，或 destination 位于 source 内时，converter 在写入前失败。
- 未知 legacy 字段、未解决 Studio conflict、重复 graph/phase/artifact definition、graph id 规范化冲突、无法解析或越出 source 的 graph reference 均失败。
- Converter 只接受可明确提升为 flat registry 的直接本地 legacy subskills。任何 legacy subskill 内再包含 subskill、依赖物理嵌套推断 parent，或同一内容出现多个不一致 owner 时失败。
- Secret value 或不能安全归属到 portable declaration、RunPreset、Studio state 的配置项失败并进入 diagnostics；converter 不猜测、不丢弃也不复制。
- Converter 不覆盖 source、existing destination 或已有 destination 文件；失败不留下一个可被误认成成功 bundle 的 partial destination。

### 10.4 单一 reader

原子切换后的 runtime core 只读取本文格式。Legacy parser 只能由显式 `gskill migrate studio-skill` adapter 调用；`compile`、`predict`、`run`、SDK 和 MCP 不做格式嗅探，也不在新解析失败时回退 v0.3。

运行时 package 安装、`import graph_skill_runtime`、启动 MCP server 或 capability detection 都不注册、复制、改写或全局扫描用户业务 skills。每次业务调用仍提供显式 skill root。

## 11. Phase 2 原子切换与验收证据

Phase 2 已在当前 source tree 完成单一 reader cutover。当前实现、converter、contract manifests、portable fixtures 和活动文档指针共同使用本文契约。旧 parser 不在 production compile/run 路径中；失败出口仍是修正 portable compiler 或 converter，而不是恢复 dual reader。

当前 contract coverage 包括：

1. 新格式的 compile、predict 与 typed dataflow characterization 通过；
2. 一个 bundle 中的 missing root、Agent Skills metadata、unknown/duplicate graph/phase、directory/id mismatch、unknown graph reference、phase cycle 和 graph call cycle 能在同轮聚合；
3. root 与 registry graph 使用同一 `gskill.graph.v1` parser，且 registry graph 拒绝 root-only artifacts；
4. Artifact declaration 重排不改变 id，request 只按 id 选择且不能覆写 definition；
5. 递归 Agent Skills discovery 只发现根 `SKILL.md`；
6. Converter 对受控 v0.3 fixtures 生成 flat registry、`AGENT.md`、graph id references、project preset 和可复核 migration report，并证明 source 与 existing destination 不被覆盖；
7. 新 runtime core 的 compile/run 路径只有一个新 reader，legacy reader 只存在于显式 converter 边界；
8. UTF-8、路径 containment、case collision、create-if-absent destination 和确定性输出使用跨平台实现与测试，不依赖 shell 拼接或 POSIX-only rename 语义。

本次 cutover 的 Windows 本地证据为：ruff、mypy strict、1582 passed / 1 skipped、manifest validator、`uv build`、isolated-wheel CLI smoke 与 `pip-audit` 均通过，第三方依赖报告 0 个已知漏洞。远程 CI 计划在 Ubuntu、Windows 与 macOS 上运行，但本 PR 的远程结果尚未发生；因此本文不宣称三平台 CI 已通过。

若后续平台证据揭示缺陷，应修正 portable compiler/converter 和同一份契约，再重新运行门禁。失败出口不是让 production runtime 同时接受本文格式与 [`00-FORMAT-GROUND-TRUTH.md`](./00-FORMAT-GROUND-TRUTH.md) 的 v0.3 格式。
