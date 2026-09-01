---
module: graph-skill-runtime
doc: error-code-catalog
role: contract
status: living
updated: 2026-08-27
---

# Graph Skill Runtime 错误码目录

本文是 Graph Skill Runtime 已注册错误码的唯一当前目录与语义契约。它定义每个错误码表示的合法状态、触发原因、等级、发生阶段、修复方向和规则 owner。其他设计文档可以在描述控制流时引用某个错误码，但不得再复制一份平行全表。

[`ERROR_REGISTRY`](../../src/graph_skill_runtime/core/error_registry.py) 是本文的可执行镜像。目录与 registry 必须保持双射：本文恰好列出 registry 的 98 个 code，每个 code 只出现一次，`level` 与有序 `stage` 也必须一致。修改任一方时，必须在同一变更中更新另一方并机械核对；registry 中存在但本文缺失的码、本文多出的码、重复码或 stage 漂移都属于契约缺陷。

`living` 表示本目录随已注册集合持续维护，不表示关联格式已经建立机器哈希锁。[`Portable gSkill v1`](./01-PORTABLE-GSKILL-V1.md) 是状态为 `audited-ready` 的当前 production reader 契约；Phase 2 的前 10 个 bundle 边界码已经随原子切换成为当前错误语义。[`00-FORMAT-GROUND-TRUTH.md`](./00-FORMAT-GROUND-TRUTH.md) 已是 `superseded` 的 v0.3 converter 输入与历史证据。错误目录保持 `living`，portable 格式保持 `audited-ready`，两者都不得在 owner 盖章和 SHA-256 哈希锁建立前冒用 `FROZEN`。

## 1. 使用规则

- **正向定义**先说明系统接受什么状态；“触发原因”只描述该状态如何被违反。
- **FATAL** 表示当前编译、装配、执行或评测无法安全继续；**WARN** 表示主体仍可继续，但 runtime 必须留下可观察诊断。
- **阶段**是有序集合。多阶段码按 registry 中的顺序书写，例如 `编译期 / 装配期`；调用方不得自行缩减为单一阶段。
- 错误码中的 `v3` 是既有码族的稳定身份，不等同于 portable 文件格式的 schema version。
- 下表中“graph 声明”“Agent phase 声明”等词表达跨格式不变量。当前 portable graph 声明是 `graph.yaml`，内部 Agent phase 是 `AGENT.md`；legacy 规范中的 `GRAPH.md` 或 phase `SKILL.md` 示例只解释已被取代的 v0.3 表示，绝不是 portable bundle 的正确写法。
- “Owning spec”链接到定义该合法状态的契约。目录拥有错误码语义，owner spec 拥有被校验对象的完整字段或运行规则，两者通过链接协作而不复制彼此。

## 2. Phase 2 portable bundle 新增码（10）

这些码定义当前 portable v1 bundle 边界。它们与状态为 `audited-ready` 的 portable 主契约和 `ERROR_REGISTRY` 共同构成当前可执行错误语义；本目录仍是唯一错误码 catalog。

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-skill-entry-missing]` | FATAL | 编译期 | 每个 portable 业务 skill root 恰有一个根 `SKILL.md` 作为 Agent Skills 入口。 | 根 `SKILL.md` 不存在或不是普通文件。 | 在业务 skill 根目录创建符合 Agent Skills 规范的 `SKILL.md`；根 graph 另由 `graph.yaml` 声明。 | [Portable v1 §3](./01-PORTABLE-GSKILL-V1.md#3-根-skillmdagent-skills-入口) |
| `[F-v3-skill-entry-nested]` | FATAL | 编译期 | Agent Skills discovery 在一个 bundle 中只发现根 `SKILL.md`；内部 Agent phase 使用 `AGENT.md`。 | skill root 之下的其他位置出现了 `SKILL.md`。 | 删除嵌套入口；若它表示内部 Agent phase，将其按契约改为 `AGENT.md`。 | [Portable v1 §2、§8](./01-PORTABLE-GSKILL-V1.md#2-唯一目录布局) |
| `[F-v3-skill-metadata-invalid]` | FATAL | 编译期 | 根 `SKILL.md` frontmatter 只含 Agent Skills 允许字段，并满足必需字段、类型和取值约束。 | YAML 无法解析，出现未知字段，或 `name`、`description` 等 metadata 不满足约束。 | 按 Agent Skills 字段表修正根 frontmatter；扩展数据放进 `metadata` 字符串映射。 | [Portable v1 §3.1](./01-PORTABLE-GSKILL-V1.md#31-frontmatter) |
| `[F-v3-skill-name-directory-mismatch]` | FATAL | 编译期 | 根 `SKILL.md.name` 与 skill root 目录 basename 完全相等。 | 两个名称在字符、大小写或规范化结果上不一致。 | 让目录名和 `SKILL.md.name` 使用同一个合法 Agent Skills name。 | [Portable v1 §3.1](./01-PORTABLE-GSKILL-V1.md#31-frontmatter) |
| `[F-v3-graph-registry-invalid]` | FATAL | 编译期 | 可选 `graphs/` 是目录，registry graph 只位于一层 `graphs/<graph_id>/graph.yaml`。 | `graphs` 不是目录，或发现嵌套 registry、越层 `graph.yaml` 等非扁平布局。 | 把所有 registry graph 提升到单层 `graphs/<graph_id>/`，删除第二级 registry。 | [Portable v1 §6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-graph-id-duplicate]` | FATAL | 编译期 | Root graph 与全部 registry graph 在一个 bundle 内共享唯一 `graph_id` 命名空间。 | 两个或更多 graph 声明了同一个 `graph_id`。 | 为冲突 graph 分配不同 id，并同步所有 graph reference。 | [Portable v1 §4.1](./01-PORTABLE-GSKILL-V1.md#41-graph-字段) |
| `[F-v3-graph-id-directory-mismatch]` | FATAL | 编译期 | 每个 registry graph 的目录 basename 与其 `graph.yaml.graph_id` 完全相等；root graph 不受此目录等值规则约束。 | `graphs/<directory>/graph.yaml` 声明了不同的 `graph_id`。 | 重命名 registry 目录或修正 `graph_id`，并同步引用。 | [Portable v1 §4.1](./01-PORTABLE-GSKILL-V1.md#41-graph-字段) |
| `[F-v3-artifact-declaration-invalid]` | FATAL | 编译期 | Artifact 只由 root graph 声明；每项字段闭合、id 唯一，并且 `fields` 引用 root graph 已声明输出。 | Registry graph 声明 artifact，declaration 字段或类型非法，id 重复，或引用未知 root output field。 | 把合法 declaration 移到 root `graph.yaml`，修正 id、字段、mode、format 与输出引用。 | [Portable v1 §4.5](./01-PORTABLE-GSKILL-V1.md#45-root-only-artifact-declarations) |
| `[F-v3-graph-reference-unknown]` | FATAL | 编译期 / 装配期 | 每条 `SUBGRAPH.md.graph` 或 `AGENT.md.subgraphs[].graph` 都指向本 bundle flat registry 中已注册的 graph id。 | 引用为空、拼写错误，指向 root graph，或目标不在 registry。 | 将引用改为现有 registry `graph_id`，或先在 `graphs/<graph_id>/` 注册目标。 | [Portable v1 §6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-graph-call-cycle]` | FATAL | 编译期 | 由所有显式 graph reference 形成的 bundle 调用图是有向无环图。 | Graph 调用链回到当前加载栈中的 graph，形成直接或间接循环。 | 打断循环 edge，或把共享逻辑抽成不反向引用 caller 的 registry graph。 | [Portable v1 §6、§8](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |

## 3. Graph 与 compile 码（22）

本节保留既有 graph、compile 和 dataflow 语义。Portable 实现复用这些码时，以 `graph.yaml`、`AGENT.md` 和 flat registry 绑定这些不变量；不能沿用 legacy 文件名作为 portable 修复方案。

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-graph-schema-unknown-field]` | FATAL | 编译期 | Graph 声明只包含所选格式 schema 允许的字段，并且文档本身可解析为一个 mapping。 | Graph 声明出现未知字段、重复 key，或无法解析为合法 mapping。 | 删除未知字段或先在 owning schema 中正式定义；portable graph 使用闭合 `graph.yaml` 字段表。 | [Portable v1 §4](./01-PORTABLE-GSKILL-V1.md#4-graphyaml唯一机器拓扑) |
| `[F-v3-graph-name-invalid]` | FATAL | 编译期 | Graph identity 存在并满足所选格式的命名语法；portable v1 使用合法 `graph_id`。 | Graph identity 缺失、类型错误或不符合命名规则。 | 将 portable `graph_id` 改为 1–64 字符的小写 kebab-case，并同步引用。 | [Portable v1 §4.1](./01-PORTABLE-GSKILL-V1.md#41-graph-字段) |
| `[F-v3-graph-schema-version-mismatch]` | FATAL | 编译期 | Graph 声明的 schema version 与当前所选 reader 精确一致。 | Version 缺失、类型错误，或值不受当前 reader 支持。 | 当前 portable reader 只接受 `gskill.graph.v1`；不要用 legacy version 冒充 portable 输入。 | [Portable v1 §4.1](./01-PORTABLE-GSKILL-V1.md#41-graph-字段) |
| `[F-v3-graph-llm-role-unknown]` | FATAL | 编译期 | Graph 级 `llm_role` 为空或能被宿主注入的 role resolver 解析。 | 声明了宿主未知或不可用的 graph role。 | 改用已注册 role，或在宿主的权威 role truth 中配置它。 | [Portable v1 §4.1、§5.2](./01-PORTABLE-GSKILL-V1.md#41-graph-字段) |
| `[F-v3-graph-root-missing]` | FATAL | 编译期 | 每个 graph directory 都有精确命名、可读取的根 graph 声明；portable v1 使用 `graph.yaml`。 | Skill/graph root 不是目录，`graph.yaml` 缺失或大小写错误，或 portable root 只留下 legacy `GRAPH.md`。 | 在正确 graph directory 创建 `graph.yaml`；legacy source 通过显式 converter 转换，不在 portable reader 中回退。 | [Portable v1 §2、§4](./01-PORTABLE-GSKILL-V1.md#2-唯一目录布局) |
| `[F-v3-graph-phases-dir-missing]` | FATAL | 编译期 | 每个 graph directory 都有 `phases/` 目录，并包含 graph 注册的 phase 目录。 | `phases/` 缺失、不是目录或没有 phase entry。 | 创建 `phases/<phase_id>/`，并让它与 graph 的 phase registry 对齐。 | [Portable v1 §2、§4.2](./01-PORTABLE-GSKILL-V1.md#2-唯一目录布局) |
| `[F-v3-graph-phases-missing]` | FATAL | 编译期 | Graph 声明包含非空、类型正确的 phase registry。 | `phases` 缺失、不是 list 或为空。 | 在 `graph.yaml` 添加至少一个完整 `GraphPhase` object。 | [Portable v1 §4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-id-invalid]` | FATAL | 编译期 | 每个 phase id 满足 grammar，不使用保留字，并能安全映射到一个目录。 | Phase id 缺失、类型错误、使用 `input`，或包含非法字符/路径逃逸形态。 | 按 `GraphPhase.id` grammar 修正 id，并同步 phase 目录和依赖。 | [Portable v1 §4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-name-mismatch]` | FATAL | 编译期 | `graph.yaml.phases[].id` 与所属 `phases/<phase_id>/` 目录一一对应。 | 注册 phase 缺目录、目录未注册，或两侧名称不一致。 | 让 registry id 与目录 basename 完全相等；删除无 owner 的目录或补齐注册。 | [Portable v1 §2、§4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-id-duplicate]` | FATAL | 编译期 | 同一 graph 内的 phase id 在精确比较和大小写不敏感比较下都唯一。 | `phases` 出现重复或跨平台大小写冲突的 id。 | 为每个 phase 分配唯一 id，并同步目录、dependency 和引用。 | [Portable v1 §4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-depends-unknown]` | FATAL | 编译期 | 每项 `depends_on` 非空、无重复，只引用 `input` sentinel 或同 graph 已注册 phase。 | Dependency 拼写错误、目标未注册、重复，或把 `input` 与其他依赖混用。 | 改为合法的已注册 phase id；入口 phase 单独使用 `depends_on: [input]`。 | [Portable v1 §4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-output-phase-invalid]` | FATAL | 编译期 | Graph 至少有一个 `output: true` 的 terminal phase，且 output 值是 boolean。 | 无输出 phase、output 类型非法，或标为 output 的 phase 仍有下游。 | 把至少一个 DAG terminal 标成 `output: true`，并修正非 terminal 标记。 | [Portable v1 §4.2](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-cycle]` | FATAL | 编译期 | 单个 graph 的 phase dependency graph 是有向无环图。 | `depends_on` 形成直接或间接 phase cycle。 | 删除或改向依赖 edge，恢复可拓扑排序的 DAG。 | [Portable v1 §4.2、§8](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-island]` | FATAL | 编译期 | 每个 phase 都能从 graph input 经 dependency edge 到达。 | Phase 或 phase 子图与任何入口不连通。 | 增加正确依赖连接，或删除不属于该 graph 的孤立 phase。 | [Portable v1 §4.2、§8](./01-PORTABLE-GSKILL-V1.md#42-graphphase) |
| `[F-v3-graph-phase-mode-ambiguous]` | FATAL | 编译期 | 每个 phase 目录恰有一个行为文件：`LOGIC.md`、`AGENT.md` 或 `SUBGRAPH.md`。 | 同一 phase 目录同时包含多个行为文件。 | 保留与该节点职责一致的唯一行为文件；portable Agent phase 必须使用 `AGENT.md`。 | [Portable v1 §2、§5](./01-PORTABLE-GSKILL-V1.md#5-phase-文件) |
| `[F-v3-graph-phase-node-missing]` | FATAL | 编译期 | 每个已注册 phase 目录包含一个且仅一个合法行为文件。 | Phase 目录没有 `LOGIC.md`、`AGENT.md` 或 `SUBGRAPH.md`。 | 添加正确类型的行为文件；不要在 portable phase 中创建 `SKILL.md`。 | [Portable v1 §2、§5](./01-PORTABLE-GSKILL-V1.md#5-phase-文件) |
| `[F-v3-graph-io-not-object]` | FATAL | 编译期 | Graph 的 `io.inputs` 与 `io.outputs` 顶层都是 JSON Schema object。 | 任一顶层 schema 不是 mapping 或 `type` 不是 `object`。 | 将顶层设为 `type: object`，并声明 `properties`。 | [Portable v1 §4.3](./01-PORTABLE-GSKILL-V1.md#43-io-schema-与静态数据流) |
| `[F-v3-graph-io-schema-invalid]` | FATAL | 编译期 | Graph I/O 是合法 Draft 2020-12 JSON Schema，且 `required` 只引用同一 schema 的 property。 | Schema 结构、类型、keyword 或 required/property 关系非法。 | 修正 `io.inputs` / `io.outputs` object schema。 | [Portable v1 §4.3](./01-PORTABLE-GSKILL-V1.md#43-io-schema-与静态数据流) |
| `[F-v3-graph-io-physical-file-deprecated]` | FATAL | 编译期 | Graph 与 phase I/O 直接内联在各自声明中，由一个 schema owner 维护。 | 使用外置 I/O 文件或 `io_*_ref` 一类已退役引用。 | 把 schema 内联到 `graph.yaml.io` 或 phase frontmatter `io`，删除物理 I/O 引用。 | [Portable v1 §4.3、§5](./01-PORTABLE-GSKILL-V1.md#43-io-schema-与静态数据流) |
| `[F-v3-graph-dataflow-source-missing]` | FATAL | 编译期 | 每个必需 phase input 都由 graph input、上游 phase output、显式运行绑定或 iterator 注入提供。 | 某必需输入在当前 phase 的可达上游中没有来源。 | 增加正确 dependency/上游 output，调整 I/O，或提供契约允许的显式绑定。 | [Portable v1 §4.3、§8](./01-PORTABLE-GSKILL-V1.md#43-io-schema-与静态数据流) |
| `[F-v3-compile-recursion-cycle]` | FATAL | 编译期 | 递归解析外部 skill/subagent 时，同一 skill root 在一条加载栈中最多出现一次。 | 解析链重新进入当前加载栈中的 skill root。 | 打断跨 skill 循环，或抽出不反向依赖 caller 的共享能力。 | [Portable v1 bundle compile](./01-PORTABLE-GSKILL-V1.md#8-bundle-compile) |
| `[F-v3-compile-depth-exceeded]` | FATAL | 编译期 | 递归 skill 解析深度不超过 runtime 的安全上限。 | Subagent/skill 解析链超过配置的最大深度。 | 降低嵌套层数，合并无必要中间层，或重构调用边界。 | [Portable v1 bundle compile](./01-PORTABLE-GSKILL-V1.md#8-bundle-compile) |

## 4. Logic、iterate、subgraph 与 golden 码（23）

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-logic-schema-unknown-field]` | FATAL | 编译期 | `LOGIC.md` frontmatter 只包含该 phase schema 允许的字段。 | Frontmatter 出现未知字段或把其他 phase 类型的字段放入 LOGIC。 | 删除未知字段，或把需求写入正确的 owning schema。 | [Portable v1 §5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-io-schema-invalid]` | FATAL | 编译期 | LOGIC phase 的 inputs/outputs 都是合法 JSON Schema object。 | Logic I/O 缺失、不是 object schema 或 keyword 关系非法。 | 按 phase I/O 契约修正 object schema。 | [Portable v1 §4.3、§5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-actions-empty]` | FATAL | 编译期 | LOGIC phase 声明至少一个唯一 action，并由 body 顺序明确执行次序。 | `actions` 缺失、为空、包含重复项，或与 body action 序列不一致。 | 声明非空 action registry，并让 body `<action>` 序列与之完全一致。 | [Portable v1 §5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-name-invalid]` | FATAL | 编译期 | 每个 action name 是可安全映射到一级 Python 模块与函数的合法名称。 | Action name 为空、含路径分隔符、不是合法函数名或发生规范化冲突。 | 使用合法的一级 Python 函数名，并同步模块文件和声明。 | [Portable v1 §5.1、§6](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-dir-missing]` | FATAL | 编译期 | 每个 LOGIC action 都由允许 scope 中的明确 registry owner 提供；本地实现位于该 phase 的 `actions/`。 | Phase-local `actions/` 缺失且没有其他允许的显式 owner，或把 `actions/` 放在非法 graph scope。 | 在所属 LOGIC phase 创建 `actions/`，或通过契约允许的 registry 注册实现。 | [Portable v1 §5.1、§6](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-not-found]` | FATAL | 编译期 | 每个已声明 action 都能解析到唯一实现模块。 | `<action_name>.py` 不存在，或允许的 registry 中没有同名 action。 | 添加正确模块/函数，或删除、改正无实现的 action 声明。 | [Portable v1 §5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-entrypoint-missing]` | FATAL | 编译期 | 本地 action 模块导出与 action id 同名、接收一个 inputs 参数的可调用函数。 | 模块无法加载、缺少同名函数，或函数签名不符合契约。 | 导出 `def <action_name>(inputs) -> dict`，并消除模块加载错误。 | [Portable v1 §5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-purity-violation]` | FATAL | 编译期 | LOGIC action 是只读输入、以返回 dict 写出结果的纯计算，不直接产生宿主副作用。 | 静态扫描发现文件写入、进程/路径篡改或其他禁止的副作用。 | 移除副作用，把 I/O 交给显式 adapter/tool 边界。 | [Portable v1 §5.1、§8](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-action-return-invalid]` | FATAL | 运行期 | 每个 action 成功时返回 dict。 | Action 返回 `None`、标量、list 或其他非 dict 值。 | 返回只包含业务输出的 dict。 | [Portable v1 §5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-output-field-undeclared]` | FATAL | 运行期 | Action 返回的每个 key 都属于该 LOGIC phase 的 `io.outputs.properties`。 | 返回 dict 含未声明输出字段。 | 在确有业务契约时声明该 output；否则删除多余返回 key。 | [Portable v1 §4.3、§5.1](./01-PORTABLE-GSKILL-V1.md#51-logicmd) |
| `[F-v3-logic-validator-type-invalid]` | FATAL | 编译期 | LOGIC `validator` 省略或为 boolean。 | `validator` 使用字符串、数字、object 等非 boolean 值。 | 改为 `true` / `false`。 | [Portable v1 §5.1、§5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-logic-validator-missing]` | FATAL | 编译期 | `validator: true` 的 LOGIC phase 在同一目录提供 `validator.py`。 | 已启用 validator，但文件不存在。 | 添加同级 `validator.py`，或在无需校验时设为 `false`。 | [Portable v1 §5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-logic-validator-entrypoint-missing]` | FATAL | 编译期 | `validator.py` 可加载并导出顶层 `validate` 函数。 | 文件有语法/加载错误，或没有 `validate` entrypoint。 | 修复模块并导出契约签名的 `validate`。 | [Portable v1 §5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-logic-validator-failed]` | FATAL | 运行期 | Logic validator 返回 `None` 或合法 dict，且不抛异常。 | Validator 抛异常、返回非法类型或校验后的输出仍不合 schema。 | 修正 action 输出、validator 规则或返回值。 | [Portable v1 §5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-iterate-accumulate-fields-missing]` | FATAL | 编译期 | Loop iterate 的 `item_var` 与 `accumulate.var` 都在节点 `io.inputs` 中声明。 | Loop iterate 使用的 item 或累积字段没有输入 schema owner。 | 在 loop 节点 `io.inputs` 声明两个字段，或修正 iterate 名称。 | [Portable v1 §4.4](./01-PORTABLE-GSKILL-V1.md#44-iteratespec) |
| `[F-v3-iterate-over-not-list]` | FATAL | 编译期 / 运行期 | `iterate.over` 的静态 schema 与实际运行值都是 array/list。 | 编译时 schema 不是 array，或运行时解析值不是 list。 | 修正 `over` 字段 schema、输入值或 iterate 声明。 | [Portable v1 §4.4](./01-PORTABLE-GSKILL-V1.md#44-iteratespec) |
| `[F-v3-agent-validator-failed]` | FATAL | 运行期 | Agent validator 接收合格输出并返回 `None` 或合法 dict。 | Validator 抛异常、返回非法类型或校验后输出不合 schema。 | 将失败反馈给 Agent 重试；同时修正输出或校验规则。 | [Portable v1 §5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-subgraph-validator-failed]` | FATAL | 运行期 | SUBGRAPH phase validator 对 child graph 输出完成确定性校验。 | Validator 抛异常、返回非法类型或产出不合 schema。 | 检查 child graph 输出和父 phase 校验规则。 | [Portable v1 §5.3、§5.4](./01-PORTABLE-GSKILL-V1.md#53-subgraphmd) |
| `[F-v3-subgraph-schema-unknown-field]` | FATAL | 编译期 | `SUBGRAPH.md` 只包含 `name`、`graph`、`io`、validator、overwrite 与 iterate 契约字段。 | Frontmatter 出现未知字段或 legacy path 字段进入 portable 声明。 | 删除未知字段；portable graph call 使用 `graph` id。 | [Portable v1 §5.3](./01-PORTABLE-GSKILL-V1.md#53-subgraphmd) |
| `[F-v3-subgraph-name-invalid]` | FATAL | 编译期 | SUBGRAPH phase 的显示 `name` 存在并满足 owning schema 的字符串约束。 | `name` 缺失、为空、类型错误或违反命名约束。 | 提供合法、非空的显示名称。 | [Portable v1 §5.3](./01-PORTABLE-GSKILL-V1.md#53-subgraphmd) |
| `[F-v3-subgraph-target-skill-invalid]` | FATAL | 编译期 | 在 legacy converter 读取的 path-based v0.3 输入中，subgraph path 必须解析到 source root 内的有效 child skill。 | Legacy subgraph path 无法解析、越界、不是目录或缺少该格式根 graph。 | 修正 converter source 中的受约束 path；portable v1 不使用 path，改用 `SUBGRAPH.md.graph`，未知 id 由 graph-reference 码报告。 | [Superseded v0.3 converter input](./00-FORMAT-GROUND-TRUTH.md#4-subgraphmd) |
| `[F-v3-subgraph-io-schema-invalid]` | FATAL | 编译期 | SUBGRAPH phase 的 inputs/outputs 都是合法 JSON Schema object。 | Subgraph I/O 缺失、不是 object schema 或 schema keyword 非法。 | 修正 phase `io.inputs` / `io.outputs`；父子边界不要求字段全集相等。 | [Portable v1 §4.3、§5.3](./01-PORTABLE-GSKILL-V1.md#53-subgraphmd) |
| `[F-v3-golden-stale-fields]` | FATAL | eval 期 | 每个节点 golden expected output 包含当前 `io.outputs.required` 的全部字段。 | Golden 仍使用旧输出形状，缺少当前必需字段。 | 重新生成 golden，或按当前 output schema 补齐期望字段。 | [Golden eval](../mvp1/02-mechanism/05-run-inner/06-golden-eval/mvp1-alignment.md#3-接口契约) |

## 5. Agent 与 mention 码（18）

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-agent-schema-unknown-field]` | FATAL | 编译期 | Agent phase frontmatter 只包含其闭合 schema 允许的字段；portable 使用 `AGENT.md`。 | 出现未知字段、authoring `system_prompt` 或其他不属于 Agent phase 的字段。 | 删除未知字段，并把行为写入结构化 body/合法 frontmatter。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-llm-role-unknown]` | FATAL | 编译期 | Agent 的有效 role 能按 phase → graph → host fallback 规则解析。 | 选中的 phase/graph role 不在宿主 resolver 中。 | 使用已注册 role，或在宿主权威配置中注册它。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-io-schema-invalid]` | FATAL | 编译期 | Agent phase inputs/outputs 都是合法 JSON Schema object。 | Agent I/O 缺失、不是 object schema 或 schema 非法。 | 修正 `AGENT.md.io`，尤其是 output schema。 | [Portable v1 §4.3、§5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-output-schema-invalid]` | FATAL | 运行期 | Agent 完成值满足 phase `io.outputs` schema。 | `finish_task` 输出未通过严格 schema 校验。 | 向模型返回结构化反馈并重试，或修正不合理的 output schema。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-output-schema-missing]` | FATAL | 运行期 | 每个可执行 Agent AST 都携带编译期生成的 output schema。 | 运行时 AST 缺少 `io.outputs`，说明编译/装配管线产生非法状态。 | 修正编译与装配管线；不要在运行时猜测 schema。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-tool-unknown]` | FATAL | 编译期 | `AGENT.md.tools` 中每个业务 tool 都唯一解析到 skill-root 或当前 phase-local owner。 | Tool 未注册、拼写错误、scope 歧义或 body 使用未列入清单的业务 tool。 | 注册唯一实现并列入当前 Agent 的 `tools`，或删除引用。 | [Portable v1 §5.2、§6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-agent-tool-reserved]` | FATAL | 编译期 | Framework builtin 由 runtime 挂载，不出现在业务 `tools` registry 或 `AGENT.md.tools`。 | 业务清单重复声明 `finish_task`、reference reader 等保留工具。 | 从业务 `tools` 列表删除保留项；按 capability contract 使用 builtin。 | [Portable v1 §5.2、§6](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-subagent-invalid]` | FATAL | 编译期 | 每个 subagent entry 完整声明唯一 `name`、可解析 `target_skill` 和非空 `description`。 | Entry 缺字段、类型错误、重复或 target identity 非法。 | 补齐并修正 `name`、`target_skill`、`description`。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-subgraph-invalid]` | FATAL | 编译期 | 每个 portable subgraph entry 完整声明唯一 `name`、registry `graph` id 和非空 `description`。 | Entry 缺字段、类型错误、重复，或仍使用 legacy path/target shape。 | 补齐 `name`、`graph`、`description`；目标存在性由 graph-reference 码校验。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-max-iterations-invalid]` | FATAL | 编译期 | `max_iterations` 省略或为 1..50 的 integer。 | 值不是 integer 或超出范围。 | 设为 1..50，或省略以使用默认 10。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-body-tag-unknown]` | FATAL | 编译期 | Agent body 顶层只使用 `role`、`goal`、`step`、`protocol`、`example` 五类标签。 | 出现未知顶层标签或把 authoring 内容写成不受支持的结构。 | 改用五类白名单标签或普通 Markdown 文本。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-role-missing]` | FATAL | 编译期 | Agent body 恰有一个非空 `<role>`。 | Role 标签缺失、重复或内容为空。 | 添加一个明确的 `<role>` 并合并重复声明。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-goal-missing]` | FATAL | 编译期 | Agent body 恰有一个非空 `<goal>`。 | Goal 标签缺失、重复或内容为空。 | 添加一个可验证的 `<goal>` 并合并重复声明。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-step-invalid]` | FATAL | 编译期 | 每个 `<step>` 有合法且唯一的 id、非空 name 与正文。 | Step id/name 缺失、非法、重复或内容为空。 | 修正 step 的 id、name 和内容，确保 id 唯一。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-protocol-invalid]` | FATAL | 编译期 | 每个 `<protocol>` 有合法唯一 id 和非空正文。 | Protocol id 缺失、非法、重复或内容为空。 | 修正 id 与内容，确保 registry 唯一。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-agent-example-invalid]` | FATAL | 编译期 | 每个 inline `<example>` 有合法唯一 id 和非空内容。 | Example id 缺失、非法、重复或正文为空。 | 修正 `<example id>` 并提供完整示例内容。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-mention-syntax-invalid]` | FATAL | 编译期 | Mention 使用 `@type:NAME` 语法，type 与 name 都完整且无空白。 | Token 残缺、含空格或使用未知 mention type。 | 改成 owning registry 支持的 `@type:NAME`。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-mention-target-not-found]` | FATAL | 编译期 | 每个 mention 都能在对应 tool、subagent、subgraph、resource、example 或 protocol registry 中解析。 | Name 不存在、scope 不可见或引用类型与 registry 不匹配。 | 注册正确目标，或修正文案中的 type/name。 | [Portable v1 §5.2、§6](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |

## 6. Resource 与 resolver 码（18）

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-resource-reference-invalid]` | FATAL | 编译期 | 每个 reference entry 完整声明唯一 id、合法 path 和非空 summary。 | Entry 不是 object、缺字段或字段类型错误。 | 补齐 `id`、`path`、`summary`。 | [Portable v1 §5.2、§6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-resource-reference-id-invalid]` | FATAL | 编译期 | Reference id 满足 grammar，并在可见 registry 中唯一。 | Id 缺失、非法、重复或发生规范化冲突。 | 改为合法唯一 id，并同步 mention。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resource-reference-path-invalid]` | FATAL | 编译期 / 运行期 | Reference path 是从 skill root 解析的 portable 相对路径，解析后仍位于 root 且可读。 | Path 绝对、含逃逸、symlink 越界、字符非法或运行时不可读。 | 改为 skill-root-relative POSIX path，并保证目标留在 root 内。 | [Portable v1 §6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-resource-reference-summary-missing]` | FATAL | 编译期 | 每个 reference 都有能说明用途的非空 summary。 | Summary 缺失、类型错误或只含空白。 | 添加简洁、可判别用途的 summary。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resource-reference-not-found]` | FATAL | 运行期 | `read_reference` 只读取当前 Agent registry 中已声明的 id。 | Tool 调用给出不存在或当前 scope 不可见的 reference id。 | 使用 registry 中的 id，或先在 Agent 声明中注册资源。 | [Builtin tools](../mvp1/02-mechanism/05-run-inner/04-tools/mvp1-alignment.md#3-接口契约) |
| `[F-v3-resource-example-invalid]` | FATAL | 编译期 | 每个 document example entry 完整声明唯一 id、合法 path 和非空 summary。 | Entry 不是 object、缺字段或字段类型错误。 | 补齐 `id`、`path`、`summary`。 | [Portable v1 §5.2、§6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-resource-example-id-invalid]` | FATAL | 编译期 | Example id 满足 grammar，并在可见 registry 中唯一。 | Id 缺失、非法、重复或发生规范化冲突。 | 改为合法唯一 id，并同步 mention。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resource-example-path-missing]` | FATAL | 编译期 | 每个 document example 都显式提供 path。 | Path 字段缺失或为空。 | 添加指向 skill-root example resource 的相对 path。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resource-example-path-invalid]` | FATAL | 编译期 / 运行期 | Example path 是从 skill root 解析的 portable 相对路径，解析后仍位于 root 且可读。 | Path 绝对、逃逸、symlink 越界、字符非法或运行时不可读。 | 改为 skill-root-relative POSIX path，并保证目标留在 root 内。 | [Portable v1 §6](./01-PORTABLE-GSKILL-V1.md#6-flat-graph-registry调用图与资源) |
| `[F-v3-resource-example-summary-missing]` | FATAL | 编译期 | 每个 document example 都有非空 summary。 | Summary 缺失、类型错误或只含空白。 | 添加说明示例用途的 summary。 | [Portable v1 §5.2](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resource-example-not-found]` | FATAL | 运行期 | `read_example` 只读取当前 Agent registry 中已声明的 id。 | Tool 调用给出不存在或当前 scope 不可见的 example id。 | 使用 registry 中的 id，或先在 Agent 声明中注册示例。 | [Builtin tools](../mvp1/02-mechanism/05-run-inner/04-tools/mvp1-alignment.md#3-接口契约) |
| `[F-v3-reference-reader-failed]` | WARN | 装配期 | Reference reader 成功返回合法知识报告；失败时 runtime 记录 WARN 并使用受控 raw-excerpt fallback。 | Reader 超时、抛异常或返回不合法内容。 | 查看 trace 修复 reader/资源；在此期间确认 fallback 内容可接受。 | [Assembly](../mvp1/02-mechanism/03-assemble/mvp1-alignment.md#2-数据流--机制) |
| `[F-v3-resolver-skill-id-invalid]` | FATAL | 编译期 | 外部 subagent `target_skill` 满足 resolver contract 的命名与类型要求。 | `target_skill` 缺失、为空、类型错误或命名非法。 | 使用合法的外部 skill id。 | [Portable v1 `AGENT.md`](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-skill-id-ambiguous]` | FATAL | 编译期 / 装配期 | 一个外部 skill id 在当前 search paths 中解析到且只解析到一个 root。 | Resolver 对同一 id 命中多个 skill root。 | 收窄 search paths，或移除重复注册。 | [Current resolver source](../../src/graph_skill_runtime/core/local_workspace_resolver.py) |
| `[F-v3-skill-not-registered]` | FATAL | 编译期 / 装配期 | 每个外部 `target_skill` 都能由注入 resolver 解析。 | Resolver 没有目标 id 的注册记录。 | 注册/导入目标 skill，或修正 `target_skill`。 | [Portable v1 `AGENT.md`](./01-PORTABLE-GSKILL-V1.md#52-agentmd) |
| `[F-v3-resolver-path-invalid]` | FATAL | 编译期 | Resolver 返回存在、受允许边界约束且包含 portable 根入口的 skill root。 | Registry path 不存在、不是目录、越界或缺少必需入口。 | 修正 registry 记录，使其指向合法 portable skill root。 | [Portable v1 root contract](./01-PORTABLE-GSKILL-V1.md#2-唯一目录布局) |
| `[F-v3-resolver-interface-invalid]` | FATAL | 编译期 | 注入 resolver 实现单一 `resolve_skill` protocol，签名和返回类型符合契约。 | 对象缺少方法、暴露旧接口或返回非法值。 | 实现并注入符合 protocol 的 resolver。 | [Current resolver protocol source](../../src/graph_skill_runtime/core/skill_resolver_protocol.py) |
| `[F-v3-resolver-missing]` | FATAL | 运行期 | 需要外部解析的内部调用总能取得已解析 resolver；公共入口可按契约补默认 local resolver。 | 内部 helper 在需要 resolver 时收到 `None`。 | 在 composition/public boundary 建立 resolver，并向内部调用显式传递。 | [Current resolver protocol source](../../src/graph_skill_runtime/core/skill_resolver_protocol.py) |

## 7. Cognitive、runtime 与冲突码（7）

| Code | Level | Stage | 正向定义 | 触发原因 | 修复建议 | Owning spec |
| --- | --- | --- | --- | --- | --- | --- |
| `[F-v3-cognitive-output-schema-invalid]` | FATAL | 装配期 / 装配前 | Cognitive assembly 接收合法 JSON output schema，并把它放入完成协议。 | 传入 schema 缺失、不是 JSON Schema 或无法生成 exit contract。 | 检查 Agent `io.outputs` 和装配调用的 schema。 | [Assembly](../mvp1/02-mechanism/03-assemble/mvp1-alignment.md#2-数据流--机制) |
| `[F-v3-tool-argument-invalid]` | FATAL | 运行期 | Builtin tool 调用参数满足该 tool 的闭合输入 schema。 | 参数缺失、类型错误、含未知字段或违反业务约束。 | 按 tool schema 修正调用参数。 | [Builtin tools](../mvp1/02-mechanism/05-run-inner/04-tools/mvp1-alignment.md#3-接口契约) |
| `[F-v3-runtime-state-mapping-failed]` | FATAL | 运行期 | StateMapper 只切片已声明 inputs，只合并已声明 outputs，并在每层满足 required。 | 初始化、slice、merge 或 final projection 缺字段、越界写入或违反 schema。 | 检查 graph/phase I/O、上游输出和运行输入。 | [Graph execution](../mvp1/02-mechanism/04-run-outer/01-graph-exec/mvp1-alignment.md#3-接口契约) |
| `[F-v3-runtime-phase-failed]` | FATAL | 运行期 | Phase 执行要么成功返回合格输出，要么使用更具体的已注册错误码失败。 | 未知异常无法归入 action、validator、tool、state mapping 等细分码。 | 查看 trace 根异常，在 owning layer 修复并在适用时引入更具体契约。 | [Graph execution](../mvp1/02-mechanism/04-run-outer/01-graph-exec/mvp1-alignment.md#3-接口契约) |
| `[F-v3-sequential-overwrite-unauthorized]` | FATAL | 编译期 | 当前 phase 只有在 `allow_sequential_overwrite` 明确列出字段时，才覆盖传递祖先写过的同名 output。 | 同一路径上的后继 phase 重写字段，但未声明授权。 | 在确有业务意图时把字段列入当前 phase 白名单；否则更名或移除重复 owner。 | [Portable v1 §5.4](./01-PORTABLE-GSKILL-V1.md#54-validator-与顺序覆盖) |
| `[F-v3-parallel-write-conflict]` | FATAL | 编译期 | 互非祖先的并行 phase 不写同一个 blackboard 字段。 | 两个无依赖先后关系的 phase 声明同名 output。 | 让字段只有一个 owner，或用真实数据依赖排出先后次序。 | [Portable v1 §4.3、§8](./01-PORTABLE-GSKILL-V1.md#43-io-schema-与静态数据流) |
| `[F-v3-agent-exit-control-failed]` | FATAL | 运行期 | Agent 在迭代预算内调用 `finish_task`，并提交通过 output schema 的业务结果。 | 达到迭代上限仍无合格 finish marker。 | 改进 role/goal/protocol 与 tool feedback，使模型完成 `finish_task`；必要时修正不合理 schema。 | [Exit control](../mvp1/02-mechanism/05-run-inner/05-exit-control/mvp1-alignment.md) |

## 8. 变更与验收纪律

新增或修改错误码时，变更必须同时满足以下条件：

1. Owning spec 先定义合法状态、失败判据和 owner；错误码不能代替规则正文。
2. `ERROR_REGISTRY` 注册唯一 code、level、完整有序 stage、remediation 与文档引用。
3. 本目录增加或更新唯一一行，不在 compile rules、format spec、README 或 checklist 复制全表。
4. 发出点提供与规则匹配的结构化定位和 message；测试证明因果输入会产生目标 code。
5. 机械检查本文与 registry 的数量、重复、code set、level 和 stage 完全一致，并验证相对链接存在。

删除码必须先确认没有发出点和当前 contract owner；历史解释留在 git history，不在活动目录中保留第二套 retired catalog。
## 9. 错误码层级与归属

本节是错误码**载体归属**的权威声明。这个 runtime 一共有三个已声明的错误码词表，加上一个留给外部 owner 的前缀；每个错误码恰好属于其中一个层，每个层恰好有一个可枚举的机器镜像。§1 的「目录与 registry 双射」只约束第 1 层；第 2、3 层不与第 1 层双射，理由分别写在 §9.2 与 §9.3。

层与镜像的对应关系：

| 层 | 词表形状 | 机器镜像（唯一 owner） | 数量 | 与第 1 层双射 |
| --- | --- | --- | --- | --- |
| 1 · skill 诊断目录 | `[F-v3-*]` | [`ERROR_REGISTRY`](../../src/graph_skill_runtime/core/error_registry.py) | 见 §1 | 本层即第 1 层，与本文 §2–§7 双射 |
| 2 · 应用边界码 | `GSKILL_*` | [`RuntimeErrorCode`](../../src/graph_skill_runtime/domain/models.py) | 8 | 否（§9.2） |
| 3 · 一次性 converter 码 | `GSKILL_MIGRATION_*` | [`MigrationErrorCode`](../../src/graph_skill_runtime/migration/studio_v030.py) | 26 | 否（§9.3） |
| 外部前缀保留 | `[F-v3-gateway-*]` | 本仓不注册，只在 [`core/exceptions.py`](../../src/graph_skill_runtime/core/exceptions.py) 保留前缀 | 不由本仓决定 | 不适用（§9.4） |

### 9.1 第 1 层 · skill 诊断目录（`[F-v3-*]`）

**正向定义**：第 1 层描述「一个 portable skill 在编译、装配、运行或评测中违反了哪一条已声明规则」。它的读者是 skill 作者，每一行都指向一份 owning spec 中被违反的合法状态。

- 机器镜像是 `ERROR_REGISTRY`；本文 §2–§7 是它的文档面，两者按 §1 双射。
- 消费者是 [`ErrorPayload.code`](../../src/graph_skill_runtime/core/exceptions.py)：未注册的码在构造时即被拒绝（`unknown graph_skill_runtime error code`）。所以「进入 `ERROR_REGISTRY`」等价于「成为一个合法的编译诊断码」。
- 每个已注册码在 [`spec/features.yaml`](../../spec/features.yaml) 有且只有一个 primary owning feature，由 `scripts/validate_round28_manifest.py` 机械校验。

### 9.2 第 2 层 · 应用边界码（`GSKILL_*`，8 个）

**正向定义**：第 2 层描述「一次 SDK / CLI / MCP 调用以哪一类失败结束」。它的读者是宿主与调用方，粒度是**类别**，不是规则。机器镜像是 `RuntimeErrorCode`（`StrEnum`），消费者是 `RuntimeErrorPayload.code` —— 三个 transport 返回同一个失败形状。

| Code | 触发边界 | 含义 |
| --- | --- | --- |
| `GSKILL_COMPILE_FAILED` | compile / predict / run 入口 | 编译没有产出可运行 skill。完整第 1 层缺陷集走 `CompileResult.diagnostics`；本码只在没有任何已注册规则覆盖该异常时作为兜底行出现。 |
| `GSKILL_CONFIG_INVALID` | 配置解析（`application/config.py`） | 解析后的配置违反 schema、取值约束或 precedence 规则。 |
| `GSKILL_EXECUTOR_UNAVAILABLE` | executor 探测（`adapters/vendor_cli/runtime.py`） | 被选中的 executor 无法构造或探测失败；fallback 声明绝不静默顶替。 |
| `GSKILL_INTERNAL_ERROR` | 任意 transport 出口 | 无法归入其他类别的运行时故障，必须留下可观察诊断。 |
| `GSKILL_INVALID_REQUEST` | 请求解析与 handoff 提交 | 调用本身非法：参数、run 控制或 Agent 提交不满足契约。 |
| `GSKILL_NOT_IMPLEMENTED` | host-native resume | 契约中存在但本 release line 未实现的路径。 |
| `GSKILL_RUN_FAILED` | 执行与 golden 评测 | 执行到达失败终态。 |
| `GSKILL_SNAPSHOT_NOT_FOUND` | resume（`application/service.py`） | 被寻址的不可变 request snapshot / run id 不存在。 |

**为何不与第 1 层双射**：第 2 层是**包含**第 1 层的类别，不是它的同级行。`GSKILL_COMPILE_FAILED` 的语义就是「一组第 1 层诊断的容器」，把容器和被容纳者放进同一张表会让「一个词只指向一个对象」不再成立。两层唯一相接的地方是 [`CompileDiagnostic.code`](../../src/graph_skill_runtime/domain/models.py)（普通 `str`）：[`adapters/engine.py`](../../src/graph_skill_runtime/adapters/engine.py) 在引擎给出注册码时写第 1 层码，在没有任何注册规则覆盖该异常时才退到 `GSKILL_COMPILE_FAILED`。如果这个兜底码被注册进第 1 层，「没有规则匹配」就与「匹配到某条规则」不可区分了。第 2 层本身已由 `StrEnum` 闭合，拼错在类型层即不可表示，所以它从来不缺机器约束，只缺文档面——本节补上的正是文档面。

### 9.3 第 3 层 · 一次性 converter 码（`GSKILL_MIGRATION_*`，26 个）

**正向定义**：第 3 层描述「一棵被冻结的 Studio v0.3 输入树为什么不能被转换成 portable gSkill v1」。机器镜像是 `MigrationErrorCode`（`StrEnum`），消费者是 `MigrationDiagnostic.code` → `MigrationReport.diagnostics` → `MigrationFailure`，可达路径只有显式 `gskill migrate studio-skill`。

| Code | 触发边界 | 含义 |
| --- | --- | --- |
| `GSKILL_MIGRATION_ARTIFACT_DUPLICATE` | runtime_config artifact | runtime_config 出现重复 artifact 定义。 |
| `GSKILL_MIGRATION_ARTIFACT_ID_COLLISION` | runtime_config artifact | 用完整定义哈希后 artifact id 仍然歧义。 |
| `GSKILL_MIGRATION_ARTIFACT_INVALID` | runtime_config artifact | artifact 定义的结构、类型、mode 或 format 非法。 |
| `GSKILL_MIGRATION_CONFIG_CONFLICT` | runtime_config | Studio 输入存在未解决的冲突，converter 不替用户裁决。 |
| `GSKILL_MIGRATION_CONFIG_INVALID` | runtime_config | runtime_config 字段缺失、类型错误或取值非法。 |
| `GSKILL_MIGRATION_DESTINATION_EXISTS` | 发布边界 | DESTINATION 已存在（含 staged 期间出现）；迁移绝不覆盖它。 |
| `GSKILL_MIGRATION_DESTINATION_INVALID` | 参数校验 | DESTINATION 与 SOURCE 相同，或不是合法可写目标。 |
| `GSKILL_MIGRATION_EXTERNAL_SKILL_INVALID` | 外部 subagent 引用 | 外部 subagent 的 `target_skill` 不是合法 Agent Skills name。 |
| `GSKILL_MIGRATION_GRAPH_ID_COLLISION` | graph id 规范化 | 多个 legacy graph name 规范化到同一个 graph id。 |
| `GSKILL_MIGRATION_GRAPH_ID_INVALID` | graph id 规范化 | legacy graph name 无法规范化出合法 graph id。 |
| `GSKILL_MIGRATION_GRAPH_INVALID` | graph 产出 | legacy graph 无法组成合法 `graph.yaml`。 |
| `GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID` | graph 引用 | legacy 引用不在 root graph 的引用集内，或指向未注册目标。 |
| `GSKILL_MIGRATION_GRAPH_RESOURCE_UNSUPPORTED` | 资源提升 | legacy 子 graph 根 `tools/` 无法在不改变 tool scope 的前提下提升。 |
| `GSKILL_MIGRATION_NESTED_SUBGRAPH_UNSUPPORTED` | 拓扑能力边界 | legacy 子 graph 含嵌套 graph 引用，flat registry 不承接。 |
| `GSKILL_MIGRATION_PHASE_INVALID` | phase 产出 | phase 无法组成合法 portable phase 文件。 |
| `GSKILL_MIGRATION_PHASE_INVENTORY_INVALID` | phase 清点 | legacy phase 目录不是恰好一个行为文件。 |
| `GSKILL_MIGRATION_PRESET_INVALID` | 参数校验 | `--preset-id` 不是合法 preset id。 |
| `GSKILL_MIGRATION_RESOURCE_COLLISION` | 资源 owner | legacy 根同时存在两个等价资源 owner（如 `refs/` 与 `references/`）。 |
| `GSKILL_MIGRATION_RESOURCE_PATH_UNSUPPORTED` | 资源路径 | 资源路径越出其 graph root 或不在允许目录下。 |
| `GSKILL_MIGRATION_SKILL_METADATA_INVALID` | 根 metadata | legacy metadata 无法组成合法 Agent Skills activation 字段（如 description 过长）。 |
| `GSKILL_MIGRATION_SOURCE_INVALID` | SOURCE 读取 | SOURCE 不是目录，缺 `GRAPH.md`，或 legacy 必需字段缺失、类型错误。 |
| `GSKILL_MIGRATION_SOURCE_VERSION_UNSUPPORTED` | SOURCE 读取 | `GRAPH.md` 的 `schema_version` 不是 v0.3.0；converter 只接受被冻结的那一版。 |
| `GSKILL_MIGRATION_STAGED_VALIDATION_FAILED` | staged 校验 | staging 目录的产物校验抛出未归类异常；报告仍然完整落盘。 |
| `GSKILL_MIGRATION_SYMLINK_UNSUPPORTED` | 文件拷贝 | 迁移不拷贝 symlink。 |
| `GSKILL_MIGRATION_TOPOLOGY_INVALID` | 拓扑一致性 | legacy frontmatter 的 phases 与 body phase 次序不完全一致。 |
| `GSKILL_MIGRATION_UNKNOWN_FIELD` | 闭合字段校验 | legacy 声明出现该 schema 未定义的字段。 |

**为何不并入第 1 层**，三条独立理由，任一条成立即足够：

1. **进入 `ERROR_REGISTRY` 等价于成为合法编译诊断码**（§9.1）。把 converter 词表放进去，就让被冻结的 v0.3 词表在当前编译诊断闭集里变成可构造的值。项目规则把 legacy v0.3 解析限定在显式 `gskill migrate studio-skill` 边界，并禁止它成为 portable 失败后的 fallback；词表层面的混入正是那条边界最先被抹掉的地方。
2. **第 1 层每一行都携带编译→装配→运行流水线中的有序 stage 和一份 owning spec**，描述的是「被编译的那个 skill」的合法状态。这 26 个码描述的是**输入树**的合法状态，它们的 owning spec 是状态为 `superseded` 的 [`00-FORMAT-GROUND-TRUTH.md`](./00-FORMAT-GROUND-TRUTH.md)。并入需要为它们编造一个流水线里不存在的 stage，并让这份**当前**目录成为一份已退役格式的共同 owner。
3. **第 1 层每个码在 `spec/features.yaml` 有唯一 primary owning feature**。converter 是一个有界用例，不是 26 个可追溯的 runtime feature；为通过 round28 校验而虚构 26 个 owner 会污染 traceability 事实源。

**原本真正的缺陷不是「没登记」，而是「不可枚举」**：这 26 个码曾经是 66 处裸 `str` 字面量，`MigrationDiagnostic.code` 的类型是 `str`，因此一个拼写错误就等于静默新增第 27 个码，没有任何文档、类型或测试知道它。现在 `MigrationDiagnostic.code` 的类型是 `MigrationErrorCode`，拼错在校验期即 `ValidationError`。

### 9.4 外部前缀保留（`[F-v3-gateway-*]`）

`[F-v3-gateway-*]` **不是本仓注册的码集**，而是留给外部 gateway owner 的前缀。gateway 异常继承本仓的公共异常族并自带 `code`，所以 [`core/exceptions.py`](../../src/graph_skill_runtime/core/exceptions.py) 的 `_payload_from_message()` 对这个前缀返回 `None`，而不是按「未注册的 core 码」拒绝。当前保留的前缀恰好只有 `[F-v3-gateway-`。前缀内各码的 level、stage 与 owning spec 由 gateway 侧维护，本目录不复制。

### 9.5 收口规则

1. 新增错误码必须登记进**恰好一个**已声明层的机器镜像。既不属于任何镜像、又是错误码形状的字符串字面量，是契约缺陷，不是新词表。
2. 三层的码集两两不相交；`[F-v3-gateway-*]` 前缀不得与第 1 层已注册码重叠。
3. §9 不复制第 1 层的行——第 1 层的行只在 §2–§7。
4. 新增一个**层**（而不是一个码）必须同批完成三件事：本节声明它、存在一个具名机器镜像、门禁覆盖它。
5. 机械门禁：[`tests/test_error_code_vocabulary_layers.py`](../../tests/test_error_code_vocabulary_layers.py) 校验层的数量与成员、层间不相交、§9 与镜像逐码一致、`src/` 下没有逃出已声明层的错误码字面量。
