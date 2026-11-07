// @ts-check
/** Keep each lab call tied to the host that produced it. */

/** @typedef {Pick<import('hostpane/page/types').HostInfo, 'id' | 'status' | 'name' | 'version' | 'transport' | 'sessionId'>} RunHost */

/** @param {import('hostpane/page/types').HostInfo} info @returns {RunHost} */
export function snapshotHost(info) {
  return { id: info.id, status: info.status, name: info.name, version: info.version, transport: info.transport, sessionId: info.sessionId };
}

const PERMISSION_MODE_LABELS = Object.freeze({ default: "手动", auto: "自动", bypassPermissions: "跳过权限确认", acceptEdits: "自动接受编辑", plan: "计划", dontAsk: "不询问" });

/** @param {string | null | undefined} mode */
export function permissionModeLabel(mode) {
  if (!mode) return "未知";
  return Object.hasOwn(PERMISSION_MODE_LABELS, mode) ? PERMISSION_MODE_LABELS[/** @type {keyof typeof PERMISSION_MODE_LABELS} */ (mode)] : mode;
}

/** @param {RunHost | null | undefined} info */
export function hostLabel(info) {
  if (!info || info.status !== 'confirmed' || info.id === 'unknown') return '未确认宿主';
  const name = info.id === 'codex' ? 'ChatGPT(Codex)' : 'Claude Code';
  return `${name} ${info.version ?? '版本未知'}`;
}

