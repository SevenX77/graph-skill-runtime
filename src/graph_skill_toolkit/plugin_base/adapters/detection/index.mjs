// @ts-check
import { HOST_ACTIONS, validateCapabilities } from "../../ports/host/contract.mjs";

/** @param {unknown} value @returns {value is Record<string, unknown>} */
const record = value => value !== null && typeof value === "object" && !Array.isArray(value);
/** @param {unknown} value */
const label = value => typeof value === "string" && value.trim() && value.length <= 256 && !/[\x00-\x1f]/.test(value) ? value : null;

/** Discover only a channel. A parent frame conveys no product identity.
 * @param {{snapshotText?: string | null, framed: boolean}} environment
 * @returns {{transport: 'mcp-app' | 'http-bridge' | 'http-page', snapshot: unknown, hostInfo: import('../../ports/host/index').HostInfo} | null}
 */
export function discoverConnection({ snapshotText, framed }) {
  if (snapshotText !== undefined && snapshotText !== null) {
    let snapshot;
    try { snapshot = JSON.parse(snapshotText); }
    catch { throw new Error("画布的宿主数据无效；请从宿主重新打开画布。"); }
    if (snapshot !== null) {
      if (!record(snapshot)) throw new Error("画布启动数据必须是对象。");
      if (typeof snapshot.error === "string") throw new Error(snapshot.error);
      const hostInfo = readLaunchHostInfo(snapshot.hostInfo);
      if (!["mcp-app", "http-bridge", "http-page"].includes(hostInfo.transport)) throw new Error("画布没有有效的启动连接方式。");
      if (hostInfo.transport === "mcp-app" && !framed) throw new Error("请通过宿主的 MCP App 打开画布。");
      return { transport: /** @type {'mcp-app' | 'http-bridge' | 'http-page'} */ (hostInfo.transport), snapshot, hostInfo };
    }
  }
  // An unconfigured document is a standalone view, even inside an iframe.
  return null;
}

/** Startup data describes the caller; it never grants live action authority.
 * @param {unknown} value
 * @returns {import('../../ports/host/index').HostInfo}
 */
export function readLaunchHostInfo(value) {
  if (!record(value) || typeof value.transport !== "string" || !["mcp-app", "http-bridge", "http-page"].includes(value.transport) ||
      typeof value.id !== "string" || !["codex", "claude", "unknown"].includes(value.id) || typeof value.status !== "string" || !["confirmed", "unknown"].includes(value.status) ||
      typeof value.identitySource !== "string" || !["mcp-client", "mcp-initialize", "claude-mod-session", "none"].includes(value.identitySource)) {
    throw new Error("画布缺少有效的启动宿主信息，请从当前宿主重新打开。");
  }
  const facts = { transport: /** @type {import('../../ports/host/index').HostTransport} */(value.transport), identitySource: /** @type {import('../../ports/host/index').HostInfo['identitySource']} */(value.identitySource),
    name: label(value.name), version: label(value.version), clientType: label(value.clientType), sessionId: label(value.sessionId) };
  const info = unknownHost("已收到启动信息，等待当前宿主连接确认。", facts);
  if (value.id === "unknown" || value.status !== "confirmed") return info;
  const valid = value.identitySource === "mcp-client"
    ? (value.id === "codex" && ["codex-mcp-client", "chatgpt"].includes(facts.name ?? "") && (!facts.clientType || facts.clientType === "codex_desktop")) ||
      (value.id === "claude" && facts.name === "claude-code")
    : identifyHost({transport:facts.transport,connected:true,identity:{name:facts.name,version:facts.version,
      ...(facts.clientType ? {client_type:facts.clientType} : {}),sessionId:facts.sessionId,source:value.identitySource},capabilities:{}}).id === value.id;
  if (!valid) throw new Error("启动宿主信息与其身份来源不一致。");
  return immutable({ ...info, id: /** @type {import('../../ports/host/index').HostId} */(value.id), status: "confirmed" });
}

/** @param {import('../../ports/host/index').HostInfo} info */
function immutable(info) {
  for (const item of Object.values(info.capabilities)) Object.freeze(item);
  Object.freeze(info.capabilities);
  return Object.freeze(info);
}

/** @param {string} reason
 * @param {Partial<import('../../ports/host/index').HostInfo>} facts
 * @returns {import('../../ports/host/index').HostInfo}
 */
export function unknownHost(reason = "尚未取得宿主身份。", facts = {}) {
  return immutable({ name: null, version: null, clientType: null, sessionId: null, transport: "none", identitySource: "none",
    ...facts, id: "unknown", status: "unknown", reason,
    capabilities: Object.fromEntries(HOST_ACTIONS.map(action => [action, { state: "unknown", detail: reason }])) });
}

/** Only connection-returned evidence enters product identification.
 * @param {import('../../ports/host/index').HostEvidence} evidence
 * @returns {import('../../ports/host/index').HostInfo}
 */
export function identifyHost(evidence) {
  const { transport, connected, identity, capabilities } = evidence;
  const reported = record(identity) ? identity : {};
  const name = label(reported.name), version = label(reported.version);
  const facts = { transport, name, version: version === "unknown" ? null : version,
    clientType: label(reported.client_type), sessionId: transport === "http-bridge" || transport === "http-page" ? label(reported.sessionId) : null,
    identitySource: /** @type {import('../../ports/host/index').HostInfo['identitySource']} */(transport === "mcp-app" ? "mcp-initialize" : transport === "http-bridge" ? "claude-mod-session" : transport === "http-page" ? "mcp-client" : "none") };
  if (!connected) return unknownHost("宿主连接未就绪或心跳已过期。", facts);
  /** @type {import('../../ports/host/index').HostId} */
  let id = "unknown";
  // Exact protocol labels: contradictory client types never pass by branding.
  if (transport === "mcp-app" && name === "chatgpt" &&
      (reported.client_type === undefined || reported.client_type === "codex_desktop")) id = "codex";
  if (transport === "http-bridge" && name === "Claude Code" && reported.source === "claude-mod-session" &&
      facts.version && facts.sessionId && reported.client_type === "claude_code") id = "claude";
  if (transport === "http-page" && name === "claude-code" && reported.source === "mcp-client" && facts.version) id = "claude";
  if (id === "unknown") return unknownHost("连接未返回可确认且有适配器支持的宿主身份。", facts);
  try {
    return immutable({ ...facts, id, status: "confirmed", reason: "已读取当前连接的宿主身份和能力。", capabilities: validateCapabilities(capabilities) });
  } catch { return unknownHost("宿主返回的能力声明无效。", facts); }
}

/** @param {import('../../ports/host/index').HostInfo} info */
export function hostIdentityKey(info) {
  return JSON.stringify([info.id, info.transport, info.name, info.version, info.clientType, info.sessionId]);
}
