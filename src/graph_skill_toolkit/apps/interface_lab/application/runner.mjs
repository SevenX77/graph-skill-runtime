// @ts-check
/** Running one lab operation and reading its evidence. The page owns display;
 * this module owns how each operation reaches the Plugin Base. */
import { LOCAL_ACTIONS } from "hostpane/page";

/** @typedef {import('hostpane/page/types').HostAdapter} HostAdapter */
/** @typedef {import('hostpane/page/types').HostResult} HostResult */
/** @typedef {{type:string, at:string, data?:unknown}} LabEvent */

/** @param {HostAdapter} adapter @param {string} id @param {Record<string, unknown>} args
 * @param {(event: LabEvent, source: string) => void} onEvent
 * @returns {Promise<{result: HostResult, stop?: () => Promise<HostResult> | HostResult}>} */
export async function runOperation(adapter, id, args, onEvent) {
  if (id === "local.files.watch") {
    const watched = await adapter.local.files.watch(/** @type {{paths:string[]}} */ (args), event => onEvent(event, "local.files.watch"));
    const { stop, ...result } = watched;
    return result.status === "completed" ? { result, stop } : { result };
  }
  if (LOCAL_ACTIONS.includes(/** @type {any} */ (id))) return { result: await adapter.local.call(/** @type {any} */ (id), args) };
  if (id === "events.subscribe") return subscribe(adapter, args, onEvent);
  return { result: await adapter.invoke(/** @type {any} */ (id), args) };
}

/** events.subscribe takes a listener, so the lab runs it as a live subscription
 * and reports what it asked for and what the host can deliver.
 * @param {HostAdapter} adapter @param {Record<string, unknown>} args @param {(event: LabEvent, source: string) => void} onEvent
 * @returns {Promise<{result: HostResult, stop?: () => HostResult}>} */
async function subscribe(adapter, args, onEvent) {
  const types = /** @type {any} */ (args.types);
  const capability = (await adapter.capabilities())["events.subscribe"];
  if (capability?.state !== "available") return { result: { status: "unsupported", message: capability?.detail ?? "宿主未声明事件订阅。", evidence: { sent: args, limits: capability?.limits ?? [] } } };
  let received = 0;
  const unsubscribe = adapter.events.subscribe(event => { received++; onEvent(event, "events.subscribe"); }, types);
  const deliverable = /** @type {string[] | undefined} */ (capability.constraints?.types);
  return {
    result: { status: "completed", message: "已订阅；匹配的事件会出现在事件记录里，来源标为本次订阅。",
      evidence: { sent: { types: types ?? "all" }, receipt: { subscribed: true },
        observed: { hostDeliverableTypes: deliverable ?? null, requestedButNotDeliverable: deliverable && Array.isArray(types) ? types.filter(type => !deliverable.includes(type)) : null },
        limits: capability.limits ?? [] } },
    stop: () => { unsubscribe(); return { status: "completed", message: `已取消订阅；期间收到 ${received} 个事件。`, evidence: { sent: null, observed: { received }, limits: [] } }; },
  };
}

/** The exact text block the model will read for a context.update call, as the
 * evidence records it for each host. @param {HostResult} result @returns {string[]} */
export function contextReadout(result) {
  const sent = /** @type {any} */ (result.evidence?.sent);
  if (!sent || typeof sent !== "object") return [];
  if (typeof sent.attachAs === "string") return [sent.attachAs];
  if (Array.isArray(sent.content)) return sent.content.filter((/** @type {any} */ item) => item?.type === "text").map((/** @type {any} */ item) => item.text);
  return [];
}

/** The evidence file this page session writes its comparison records to.
 * @param {string} directory @param {string} host @param {string} startedAt */
export function recordPath(directory, host, startedAt) {
  const separator = directory.includes("\\") ? "\\" : "/";
  return directory.replace(/[\\/]+$/, "") + separator + `${host}-${startedAt.replace(/[:.]/g, "-")}.json`;
}

/** Session workspace used by host-file presets; local tests keep the sandbox.
 * @param {HostResult} result @returns {string | null} */
export function workspaceRoot(result) {
  const data = /** @type {{workspaceRoots?: unknown[], cwd?: unknown} | undefined} */ (result.data);
  const root = data?.workspaceRoots?.[0];
  return typeof root === "string" && root ? root : typeof data?.cwd === "string" && data.cwd ? data.cwd : null;
}

/** One local clock format for run cards and host events. @param {string} at */
export function localTime(at) {
  return new Date(at).toLocaleTimeString(undefined, { timeZoneName: "short" });
}
