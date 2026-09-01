---
doc: skill-spec-index
role: index
status: living
ssot: graph_skill_format_templates
updated: 2026-08-27
---

# Skill Spec 文档入口

[`01-PORTABLE-GSKILL-V1.md`](./01-PORTABLE-GSKILL-V1.md) 是当前 production reader 的唯一 portable 格式契约，状态为 `audited-ready`。当前业务 gSkill 使用根 `SKILL.md` + `graph.yaml` + phase `AGENT.md` + 单层 `graphs/<graph_id>/` registry；runtime core 没有 dual reader 或格式嗅探回退。`audited-ready` 表示语义已审但尚未由 owner 建立新 SHA-256 哈希锁，因此不能标为 `FROZEN`。

[`00-FORMAT-GROUND-TRUTH.md`](./00-FORMAT-GROUND-TRUTH.md) 是 `superseded` 的 v0.3 契约。它只服务显式 `python -m graph_skill_runtime migrate studio-skill` converter 与历史核验，不再被 production compile、predict、run、inspect、SDK、module CLI 或 MCP 当作当前格式读取。

[`11-error-code-spec.md`](./11-error-code-spec.md) 是 `living` 的唯一当前错误码目录与语义事实源。它与代码 `ERROR_REGISTRY` 保持 98 码双射；compile rules、format spec 和其他页面只链接目录或个别 owning rule，不再复制错误码全表。

当前规则：

- 新建、编辑、校验、fixture 和示例都以 [`01-PORTABLE-GSKILL-V1.md`](./01-PORTABLE-GSKILL-V1.md) 为准。
- MVP1 设计文档只保留架构意图、历史证据和跨模块链接，不再重复 portable YAML 模板。
- `01` 拥有当前格式与 converter contract；`11` 拥有当前错误码语义。两者职责不同，不形成并行契约。
- 本目录内其余拆分页面只作为背景说明或历史索引；如果与 `01` 冲突，以 `01` 为准并修正活动入口。
- `_migration-src` 已退役删除；需要历史细节时看 git 历史，不再保留第二套迁移源。

## Current Format Contract

- [01-PORTABLE-GSKILL-V1.md](./01-PORTABLE-GSKILL-V1.md): 当前目录结构、根 `SKILL.md`、`graph.yaml`、`LOGIC.md`、`AGENT.md`、`SUBGRAPH.md`、flat registry、artifact-by-id、bundle compile 与一次性 converter。

## Active Contract Pages

- [11-error-code-spec.md](./11-error-code-spec.md): `living` 的 98 码唯一当前 catalog；逐码定义 stage、合法状态、原因、修复和 owner。

## Legacy Converter Input

- [00-FORMAT-GROUND-TRUTH.md](./00-FORMAT-GROUND-TRUTH.md): `superseded` v0.3 输入契约和 pre-cutover 历史正文；不是 production reader 格式。

## Retired v0.3 Redirect Pages

这些 `retired` 页面只保留 v0.3 历史导航，并把读者导向 `01` 的对应章节；它们不再承载模板真相源：

- [01-physical-layout.md](./01-physical-layout.md)
- [02-graph-md-spec.md](./02-graph-md-spec.md)
- [03-logic-md-spec.md](./03-logic-md-spec.md)
- [04-subgraph-md-spec.md](./04-subgraph-md-spec.md)
- [05-agent-md-spec.md](./05-agent-md-spec.md)
- [06-cognitive-template-spec.md](./06-cognitive-template-spec.md)
- [07-mention-syntax-spec.md](./07-mention-syntax-spec.md)
- [08-resource-mechanisms-spec.md](./08-resource-mechanisms-spec.md)
- [09-builtin-modules-spec.md](./09-builtin-modules-spec.md)
- [10-skill-resolver-protocol-spec.md](./10-skill-resolver-protocol-spec.md)
- [12-compile-runtime-flow-spec.md](./12-compile-runtime-flow-spec.md)
