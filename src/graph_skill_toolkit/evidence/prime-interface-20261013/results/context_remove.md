# `context.remove` 独立接口结果（2026-10-14 UTC）

## 结果与边界

**部分达到，真实 Desktop 效果未验证。** 本接口的目标是从当前页面连接拥有的上下文中移除一个 `key`，不发送消息，并在之后的上下文交付边界不再提供该值。Codex 在声明 `updateModelContext.structuredContent` 的模拟连接上发出完整剩余快照；Claude Mod 从当前连接存储中删除该值，之后通过 `prompt.submit` 提交的消息不再附带该值。真实 Codex Desktop 是否纳入/撤回下一轮上下文、真实 Claude Desktop 是否加载该 Mod 和提交后的模型输入，都没有本轮观察。Codex 在回执不明后可能恢复已移除键的共享状态风险尚未修复，不能把测试通过称为接口最终接通。

本结果服务于父目标 `shared-graph-ui-feasibility` 中的十五个宿主接口之一。来源为协调者转录的用户要求 `build/prime-interface-20261013/brief.txt` 和独立交接 `handoffs/context_remove.md`（两者均于本轮完整读取）；当前接口契约 `src/graph_skill_toolkit/ADAPTER.md:31-32,43,53`，目标现状 `VALIDATION.md:3-14,18-46`，导航 `ARCHITECTURE.md:83-89`。交接所给三个文档的 SHA-256 与本轮读取一致。父目标当前是紧凑 Markdown，不是 goal-contract/v1；JSON 检查器无适用的记录接口。用户原始对话并未直接出现在子会话，协调者负责原话校核与父目标验收。

**范围挑战和判断：** 这一结果若删除，十五接口“每个接口尝试接通并说明原因”的要求仍缺一项；若只通过模拟测试而没有原生观察，则可以规避真正的宿主效果，因此两层证据分开。`context.remove` 只移除页面拥有的未来附加上下文，不撤销已发送的历史消息或其他页面的上下文；不将临时 source-only 测试变成永久产品条件。两端行为不同：Codex 发送下一份完整结构化快照，Claude 只更改 Mod 内连接状态并在之后的提交消息中附带剩余数据。它们与“草稿不提交、工具直调不等于消息”的其他接口边界兼容。两个宿主结果共同有助于父目标，但不能单独证明共享 HTML、另外十四接口、原生显示及交付。

目标判断（[0,1] 是证据把握，不是完成率或权限）：来源 **0.94**：交接转录与当前契约明确，缺直接原始对话；解释 **0.88**：未来交付与页面拥有范围明确，真实宿主何时消费未定；有效性 **0.82**：若两端真实移除且无消息，可解决本接口的问题，但不能解决整个父目标；分解 **0.80**：本接口的协议请求、连接隔离、失败边界和原生观察联合足够，当前缺原生与回执不明隔离。直接用户原话、更换宿主实测、以及回执不明的修复测试将增强或改变这些判断。

## 核验事实、改动和测试

- `src/graph_skill_toolkit/host_interfaces/context/remove/{index,codex,claude}.mjs` 均未改动。`codex.mjs` 调用共享 `adapters/codex/driver/shared.mjs:writeContext`；它以每页的 `Map` 和串行队列构造 `structuredContent.toolkitContext`。`claude.mjs` 对 `state.contexts.get(owner).values` 执行 `delete(key)`。`conversation/submit_message/claude.mjs` 才将非空的当前连接值加入后来提交的文本。
- 新增唯一自有文件 `src/graph_skill_toolkit/tests/host/interfaces/context_remove.test.mjs`，SHA-256 `041963174d2ba84952dbd999f36e03637b556b41d4ab633913594daa1e250cec`。测试使用本地实际安装的 `@modelcontextprotocol/ext-apps` App/AppBridge 协议对象，断言先 set 两个键再 remove 一个键的三份完整快照、最后移除键得到空快照，且没有 `sendMessage`。另外测试缺少声明时不调宿主、Claude 两个页面连接间隔离并不在 remove 时发送、非法键或参数拒绝。
- 在 `src/graph_skill_toolkit/` 执行 `node --test tests/host/interfaces/context_remove.test.mjs`：**4/4 通过，exit 0**；`npm run typecheck`：**exit 0**。均为本地源码/SDK 模拟与静态检查，不是桌面客户端效果，也未运行共享 `dist` 构建。
- SDK `node_modules/@modelcontextprotocol/ext-apps/dist/src/spec.types.d.ts:292-311` 声明 `ui/update-model-context` 的 `structuredContent` 输入以及“每次覆写上一份上下文，通常下一条用户消息才送模型”；`app.d.ts:892-905,942-961` 声明 `updateModelContext` 的 Promise 只返回可选 `_meta` 的空回执，拒绝/超时/断连会抛错。回执只支持“请求确认”，不证明模型最终看见或不再看见键。Claude `prompt.submit` 的本地返回只表示消息受理。

## 已复现的跨文件风险与给协调者的公共改动建议

`adapters/codex/driver/shared.mjs:writeContext` 在 `updateModelContext` 抛错时保持旧 `state.contexts`，但宿主可能已接受请求、仅丢了回执。之后另一次写入可由旧快照重新引入此前移除的键。以下是**受控假宿主复现**，不是实测 Desktop 故障；在 `src/graph_skill_toolkit/` 以 `node --input-type=module` 从标准输入执行这段 JavaScript。假宿主在第三次调用记录请求后故意抛出“回执丢失”；正常真实宿主是否接受该请求未知。

```js
import {codexAdapter} from './adapters/codex/driver/index.mjs';
const calls=[]; let n=0;
const app={getHostCapabilities:()=>({updateModelContext:{structuredContent:{}}}),
  updateModelContext:async payload=>{
    calls.push(payload.structuredContent.toolkitContext);
    if (++n===3) throw new Error('receipt lost after possible host acceptance');
    return {};
  }};
const adapter=codexAdapter(app);
for (const [action,args] of [
  ['context.set',{key:'a',content:1}], ['context.set',{key:'b',content:2}],
  ['context.remove',{key:'a'}], ['context.remove',{key:'b'}],
]) { try { await adapter.invoke(action,args); } catch(e) { console.log('lost:',e.message); } }
console.log(JSON.stringify(calls));
```

本轮运行 exit 0，输出 `lost: receipt lost after possible host acceptance` 和以下快照：

```text
[{"a":1},{"a":1,"b":2},{"b":2},{"a":1}]
```

最后 `{"a":1}` 是旧键复活的*可能*，具体取决于第三次调用是否已被真实宿主接受。模拟抛错与重复调用由上述脚本明确制造，非调用方取消、超时截断或缺日志。**建议共享文件的 owner 在不明回执时 fail-closed**：给页面连接的上下文状态标记 `uncertain`；后续 `context.set/remove` 在请求发往宿主前拒绝，而不是从旧快照推演新的快照；当前连接销毁/重建后重新初始化。明确的、已收到的拒绝可维持已确认状态并允许后续操作；标准 SDK 的 `updateModelContext` 空回执不能靠 `isError` 推断全部拒绝。建议父级回归测试：假宿主接受一次 `remove(a)` 但抛出断连/超时；再次请求 `remove(b)` 或 `set(c)` 时断言**调用计数不增加**、返回或异常说明结果不明且需重连；新页面连接的状态清零并允许写入；明确拒绝路径另测。此处涉及 `context.set` 和共享 helper，不在子代理可写范围。不要把抛错自动重发或用对话消息替代上下文更新。

候选路径判断：共享状态加“不明”屏障 **0.82**，适用于不能查询最终宿主状态的 SDK；安全性强但暂停同页上下文写入直至重连，需假宿主和原生验证。提供宿主权威读回并对齐状态 **未评估**：本地 SDK 没发现上下文读回 API，不能假设存在。维持现状并解释风险 **0.30**：零修改但不能保证移除状态，不能用于最终接口验收。此处技术修复属于父级可决策范围；真实宿主支持声明和效果仍须后来观察。

## 最小后续证据

协调者先审查并整合共享上下文状态修复、运行针对失败路径的测试；再在隔离的真实 Codex Desktop 和 Claude Desktop 会话分别设置一个键、移除它、发送**之后的一条**人工测试消息并观察模型输入/宿主允许的上下文证据，同时确认没有由 remove 自身发消息。需绑定客户端版本、实际加载的本工作树/Mod 字节、连接会话、测试顺序与原始回执。用户先前将真实宿主操作保留给本人且禁止并发操控桌面；本子任务未开启 Computer Use、无待清理进程，也未提交、安装、发布或改变全局配置。
