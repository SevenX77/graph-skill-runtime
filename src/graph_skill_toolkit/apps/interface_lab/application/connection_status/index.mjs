// @ts-check
/** One reading of a call decides both its record and its interface signal, so
 * the record, the header and the side list always agree. Yellow means a test
 * is still open; a closed test is green or red. */

/** @typedef {import('hostpane/page/types').HostInfo} HostInfo */
/** @typedef {import('hostpane/page/types').HostCapability} HostCapability */
/** @typedef {import('hostpane/page/types').HostResult} HostResult */
/** @typedef {import('../result_status/index.mjs').RunHost} RunHost */
/** @typedef {{op:string, connection:object, host:RunHost, result:HostResult, verdict?:''|'matches'|'differs'|'not-observed'}} Call */
/** @typedef {'success'|'testing'|'failure'|'untested'} SignalCode */
/** @typedef {{code:SignalCode, tone:'available'|'unavailable'|'unknown'|'untested', label:string, detail:string}} Signal */

/** @type {Record<SignalCode, Signal['tone']>} */
const TONES = { success: 'available', failure: 'unavailable', testing: 'unknown', untested: 'untested' };

/** @param {RunHost} runHost @param {HostInfo} host */
function sameHost(runHost, host) {
  return runHost.status === 'confirmed' && runHost.id === host.id && runHost.transport === host.transport &&
    runHost.version === host.version && runHost.sessionId === host.sessionId;
}

/** @param {SignalCode} code @param {string} label @param {string} detail @returns {Signal} */
function signal(code, label, detail) {
  return { code, tone: TONES[code], label, detail };
}

/** A person's comparison settles a call; without one, its result does.
 * @param {Pick<Call, 'result' | 'verdict'>} call @returns {Signal} */
export function callSignal({ result, verdict }) {
  if (verdict === 'matches') return signal('success', '已确认成功', '人工核对确认实际效果与预期一致。');
  if (verdict === 'differs') return signal('failure', '与预期不符', '人工核对发现实际效果与预期不符。');
  if (verdict === 'not-observed') return signal('failure', '未观察到效果', '人工核对没有观察到预期效果。');
  switch (result.status) {
    case 'completed': return signal('success', '已完成', result.message);
    case 'accepted': return signal('testing', '已受理，待确认', '宿主已受理；请核对实际效果后选择对照结论。');
    case 'pending': return signal('testing', '等待回执', result.message);
    case 'rejected': return signal('failure', '被拒绝', result.message);
    case 'unsupported': return signal('failure', '当前不可用', result.message);
    default: return signal('failure', '出错', result.message);
  }
}

/** The interface shows its latest test on this connection and host. A declared
 * outage needs no test; an open test wins over any earlier result.
 * @param {{operation:string, kind:'host'|'local', connected:boolean, connection:object|null, host:HostInfo|null,
 *   capability?:HostCapability, localAvailable:boolean, calls:readonly Call[], running?:string|null}} input
 * @returns {Signal} */
export function connectionStatus({ operation, kind, connected, connection, host, capability, localAvailable, calls, running }) {
  if (!connected) return signal('untested', '尚未连接', '页面尚未建立当前宿主连接。');
  if (kind === 'host' && host?.status !== 'confirmed') return signal('untested', '宿主待确认', host?.reason || '当前宿主身份尚未确认。');
  if (kind === 'host' && capability?.state === 'unavailable') return signal('failure', '当前不可用', capability.detail);
  if (kind === 'local' && !localAvailable) return signal('failure', '当前不可用', '页面没有可用的插件本地能力连接。');
  if (running === operation) return signal('testing', '测试中', '正在等待这次调用的结果。');

  // Calls arrive newest first.
  const latest = calls.find(call => call.connection === connection && call.op === operation &&
    (kind === 'local' || (host && sameHost(call.host, host))));
  if (latest) return callSignal(latest);
  if (kind === 'local') return signal('untested', '未测试', '插件本地连接已建立；还没有调用。');
  return signal('untested', '未测试', capability?.detail || '宿主尚未声明此接口；还没有调用。');
}
