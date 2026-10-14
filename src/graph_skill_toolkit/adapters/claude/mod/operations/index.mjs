import { validateArguments } from "../../../../ports/host/contract.mjs";
import { nativeCapabilities, invokeOperation, hasInvoke } from "./registry.mjs";
import { notSent } from "./tools/index.mjs";
export { nativeCapabilities } from "./registry.mjs";

/** Probe session APIs by calling them once per session; cached in Mod state. */
export async function sessionFacts($, state, sessionId) {
  if (state.sessionFacts && state.sessionFacts.sessionId === sessionId) return state.sessionFacts.facts;
  let sessionUsage;
  try { await $.session.usage({ breakdown: "summary" }); sessionUsage = true; } catch { sessionUsage = false; }
  const facts = { sessionUsage };
  state.sessionFacts = { sessionId, facts };
  return facts;
}

/** Check session authority, then dispatch to the matching interface module. */
export async function executeBridgeAction($, state, bridge, request, binding = {}) {
  if (!request || typeof request.id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(request.id) || request.skillRoot !== bridge.skillRoot) throw notSent("请求不属于当前页面连接。");
  let args;
  try { args = validateArguments(request.action, request.args ?? {}); } catch (error) { error.outcome = "not-sent"; throw error; }
  const generation = binding.generation ?? state.generation;
  const sessionId = binding.sessionId ?? await $.session.id();
  const guard = async () => {
    if (state.closed || state.generation !== generation || await $.session.id() !== sessionId) throw notSent("原宿主会话已结束或发生变化。");
  };
  await guard();
  const tools = await $.tool.list();
  await guard();
  const cap = nativeCapabilities(tools, await sessionFacts($, state, sessionId))[request.action];
  if (cap?.state !== "available") return { status: "unsupported", message: cap?.detail ?? "未知接口。", data: { capabilityState: cap?.state ?? "unknown" } };
  if (!hasInvoke(request.action)) return { status: "unsupported", message: "当前宿主接入未实现此接口。" };
  const owner = bridge.url + "/" + bridge.token;
  const execute = () => invokeOperation(request.action, $, { state, bridge, request: { ...request, args }, args, tools, guard, owner });
  if (request.action.startsWith("views.")) {
    const previous = state.viewQueues.get(owner) ?? Promise.resolve();
    const current = previous.catch(() => {}).then(execute);
    state.viewQueues.set(owner, current.then(() => {}, () => {}));
    return current;
  }
  return execute();
}
