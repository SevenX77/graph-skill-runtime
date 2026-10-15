// @ts-check
/** The closed action vocabulary shared by the page, dispatcher and HTTP boundary. */
import { HOST_ACTIONS, INTERFACE_DEFINITIONS } from "./catalog.mjs";
import { portable } from "../../host_interfaces/validation/index.mjs";
export { HOST_ACTIONS } from "./catalog.mjs";

/** @param {unknown} value @returns {Record<string, unknown>} */
function record(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("接口数据必须是对象。");
  return /** @type {Record<string, unknown>} */ (value);
}

/** @param {unknown} value @returns {import('./index').HostCapabilities} */
export function validateCapabilities(value) {
  const source = record(value);
  return /** @type {import('./index').HostCapabilities} */ (Object.fromEntries(HOST_ACTIONS.map(action => {
    const item = source[action];
    if (item === undefined) return [action, { state: "unknown", detail: "宿主未声明此能力。" }];
    const capability = record(item);
    if (!["available", "unavailable", "unknown"].includes(/** @type {string} */ (capability.state)) || typeof capability.detail !== "string") throw new Error("适配器返回了无效能力说明。");
    if (capability.scope !== undefined && typeof capability.scope !== "string") throw new Error("无效的接口范围。");
    if (capability.constraints !== undefined) record(capability.constraints);
    if (capability.limits !== undefined && (!Array.isArray(capability.limits) || capability.limits.some(item => typeof item !== "string"))) throw new Error("无效的接口限制说明。");
    return [action, { state: capability.state, detail: capability.detail, ...(capability.scope ? {scope: capability.scope} : {}), ...(capability.constraints ? { constraints: structuredClone(capability.constraints) } : {}), ...(capability.limits ? { limits: [...capability.limits] } : {}) }];
  })));
}

/** @param {unknown} value */
function validEvidence(value) {
  if (value === undefined) return true;
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const limits = /** @type {{limits?: unknown}} */ (value).limits;
  return limits === undefined || (Array.isArray(limits) && limits.every(item => typeof item === "string"));
}

/** @param {unknown} value @returns {import('./index').HostResult} */
export function validateResult(value) {
  const result = record(value);
  if (typeof result.status !== "string" || !["completed", "accepted", "pending", "unsupported", "rejected", "error"].includes(result.status) ||
      typeof result.message !== "string" || (result.requestId !== undefined && typeof result.requestId !== "string") ||
      !validEvidence(result.evidence)) {
    throw Object.assign(new Error("适配器返回了无效结果，无法确认操作状态。"),
      typeof result.requestId === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(result.requestId) ? { requestId: result.requestId } : {});
  }
  return /** @type {import('./index').HostResult} */ (value);
}

/** Validate and snapshot an operation before awaiting its host capability.
 * @param {import('./index').HostAction} action
 * @param {unknown} input
 * @returns {import('./index').HostActionArgs}
 */
export function validateArguments(action, input = {}) {
  const args = record(input);
  const definition = INTERFACE_DEFINITIONS.find(item => item.id === action);
  if (!definition || Object.keys(args).some(key => !definition.fields.includes(key))) throw new Error("未知的宿主接口参数。");
  definition.validate(args);
  portable(args);
  if (new TextEncoder().encode(JSON.stringify(args)).length > 48000) throw new Error("接口参数超过 48 KiB。");
  return JSON.parse(JSON.stringify(args));
}

/** @param {unknown} error @param {boolean} [dispatched] @returns {import('./index').HostResult} */
export function failureResult(error, dispatched = false) {
  const detail = error instanceof Error ? error.message : String(error);
  const info = error && typeof error === "object" ? /** @type {Record<string, unknown>} */ (error) : {};
  if (info.outcome === "rejected") return { status: "rejected", message: detail };
  if (info.outcome === "unknown" || (dispatched && info.outcome !== "not-sent")) return {
    status: "pending", message: `请求结果未知：${detail}。请检查宿主结果，避免重复发送。`,
    ...(typeof info.requestId === "string" ? { requestId: info.requestId } : {}),
  };
  return { status: "error", message: detail };
}
