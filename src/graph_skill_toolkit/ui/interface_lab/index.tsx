import { useEffect, useRef, useState } from "react";
import { INTERFACES } from "../../ports/host/catalog.mjs";
import type { HostAction, HostAdapter, HostCapabilities, HostResult } from "../../ports/host/index";

type Entry = { id: number; action: HostAction; result: HostResult; time: string };
const labels: Record<HostResult["status"], string> = {
  completed: "接口已完成", accepted: "请求已受理", pending: "结果待确认",
  unsupported: "当前不可用", rejected: "请求被拒绝", error: "接口错误",
};
const display = (value: unknown) => JSON.stringify(value, null, 2) ?? String(value);

export function InterfaceLab({ adapter, connected, capabilities, samples }: {
  adapter: HostAdapter | null;
  connected: boolean;
  capabilities: HostCapabilities;
  samples: Partial<Record<HostAction, Record<string, unknown>>>;
}) {
  const [action, setAction] = useState<HostAction>("files.openFile");
  const [input, setInput] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<Entry[]>([]);
  const sequence = useRef(0);
  const current = INTERFACES.find(item => item.id === action)!;
  useEffect(() => { setInput(display(samples[action] ?? current.sample)); }, [action, samples[action] && display(samples[action])]);
  const state = capabilities[action]?.state ?? "unknown";
  const reason = capabilities[action]?.detail ?? "宿主尚未声明此能力。";

  async function run() {
    if (!adapter || !connected || busy || state !== "available") return;
    setBusy(true);
    let result: HostResult;
    try {
      const args: unknown = JSON.parse(input);
      if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("接口参数须为 JSON 对象。");
      result = await adapter.invoke(action, args as Record<string, unknown>);
    } catch (error) { result = { status: "error", message: error instanceof Error ? error.message : String(error) }; }
    setLog(previous => [{ id: ++sequence.current, action, result, time: new Date().toLocaleTimeString() }, ...previous]);
    setBusy(false);
  }

  async function check(entry: Entry) {
    if (!adapter?.getResult || !entry.result.requestId || busy) return;
    setBusy(true);
    try {
      const result = await adapter.getResult(entry.result.requestId);
      setLog(previous => previous.map(item => item.id === entry.id ? { ...item, result } : item));
    } catch (error) {
      setLog(previous => previous.map(item => item.id === entry.id ? { ...item, result: { status: "pending", message: String(error), requestId: entry.result.requestId } } : item));
    } finally { setBusy(false); }
  }

  return <>
    <nav className="test-toolbar" aria-label="通用宿主接口测试">
      {INTERFACES.map(item => <button type="button" key={item.id} data-action-select={item.id} aria-pressed={action === item.id}
        onClick={() => setAction(item.id as HostAction)} title={capabilities[item.id]?.detail ?? "能力未确认"}>{item.label}</button>)}
    </nav>
    <section className="inspector-section interface-lab" aria-label="宿主接口调用">
      <h2>{current.label} <code>{action}</code></h2>
      <p className="muted" data-capability-state={state}>能力：{state} · {reason}</p>
      <label htmlFor="interface-input">接口参数 JSON</label>
      <textarea id="interface-input" rows={6} spellCheck={false} value={input} onChange={event => setInput(event.target.value)} />
      <button type="button" data-action="invoke-interface" disabled={!connected || busy || state !== "available"} onClick={() => void run()}>调用接口</button>
      <p className="muted">调用结果与宿主实际显示分别核对；待确认请求可查询回执，不会自动重发。</p>
      <div className="section-heading"><h2>接口结果</h2><span>{log.length}</span></div>
      <div className="action-log" role="log" aria-live="polite">
        {log.length === 0 ? <p className="muted">尚未调用接口。</p> : log.map(entry => <article key={entry.id} className={`log-entry ${entry.result.status}`} data-result-status={entry.result.status}>
          <div className="log-heading"><strong>{entry.action}</strong><time>{entry.time}</time></div>
          <span className="result-status">{labels[entry.result.status]}</span><p>{entry.result.message}</p>
          {entry.result.requestId ? <p className="request-id">请求：{entry.result.requestId}</p> : null}
          {entry.result.status === "pending" && entry.result.requestId && adapter?.getResult ? <button type="button" data-action="check-result" disabled={busy} onClick={() => void check(entry)}>查询回执</button> : null}
          {entry.result.data !== undefined ? <details><summary>响应数据</summary><pre>{display(entry.result.data)}</pre></details> : null}
        </article>)}
      </div>
    </section>
  </>;
}
