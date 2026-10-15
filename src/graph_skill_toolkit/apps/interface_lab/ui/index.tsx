import { useEffect, useMemo, useRef, useState } from "react";
import type { HostAdapter, HostCapabilities, HostInfo, HostResult } from "../../../plugin_base/page/types";
import { GUIDES, GROUPS, CONTEXT_PROBE, type LabPaths } from "../application/guide.mjs";
import { runOperation, contextReadout, recordPath } from "../application/runner.mjs";

type Verdict = "" | "matches" | "differs" | "not-observed";
type Run = { id: number; op: string; args: unknown; result: HostResult; at: string; verdict: Verdict; note: string; stop?: () => Promise<HostResult> | HostResult; stopped?: HostResult };
type EventRow = { id: number; type: string; at: string; data?: unknown; source: string };

const statusText: Record<HostResult["status"], string> = {
  completed: "已完成", accepted: "已受理", pending: "结果待确认", unsupported: "当前不可用", rejected: "被拒绝", error: "出错",
};
const verdictText: Record<Exclude<Verdict, "">, string> = { matches: "与预期一致", differs: "与预期不符", "not-observed": "未观察到效果" };
const show = (value: unknown) => value === undefined || value === null ? "（无）" : JSON.stringify(value, null, 2);

export function InterfaceLab({ adapter, lab: initialLab }: { adapter: HostAdapter | null; lab: LabPaths | null }) {
  const [connection, setConnection] = useState(adapter ? "连接中" : "未在宿主中打开");
  const [failure, setFailure] = useState("");
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(adapter?.hostInfo ?? null);
  const [capabilities, setCapabilities] = useState<HostCapabilities>({});
  const [lab, setLab] = useState<LabPaths | null>(initialLab);
  const [selected, setSelected] = useState(GUIDES[0].id);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const sequence = useRef(0);
  const startedAt = useRef(new Date().toISOString());
  const host = hostInfo?.id ?? "unknown";
  const guide = GUIDES.find(item => item.id === selected)!;
  const lastViewId = useMemo(() => {
    for (const run of runs) { const id = (run.result.data as { viewId?: unknown } | undefined)?.viewId; if (run.op === "views.open" && typeof id === "string") return id; }
    return null;
  }, [runs]);
  const presetContext = { lab, host, lastViewId };
  const draft = drafts[selected] ?? show(guide.presets[0].args(presetContext));

  function addEvent(event: { type: string; at: string; data?: unknown }, source: string) {
    setEvents(previous => [{ id: ++sequence.current, ...event, source }, ...previous].slice(0, 400));
  }

  useEffect(() => {
    if (!adapter) return;
    let disposed = false, unsubscribe = () => {};
    const receive = (payload: unknown) => {
      const value = payload as { lab?: LabPaths } | null;
      if (value?.lab && typeof value.lab.sandbox === "string") setLab(value.lab);
    };
    void adapter.connect({ receive, fail: error => { if (!disposed) setFailure(String(error instanceof Error ? error.message : error)); } }).then(async () => {
      if (disposed) return;
      setConnection("已连接");
      unsubscribe = adapter.events.subscribe(event => addEvent(event, "页面启动时的全量订阅"));
      setCapabilities(await adapter.capabilities());
      setHostInfo(adapter.hostInfo);
    }).catch(error => { if (!disposed) { setConnection("连接失败"); setFailure(String(error instanceof Error ? error.message : error)); } });
    return () => { disposed = true; unsubscribe(); void adapter.dispose(); };
  }, [adapter]);

  function stateOf(id: string) {
    if (id.startsWith("local.")) return adapter?.local.available ? "available" : "unavailable";
    return capabilities[id]?.state ?? "unknown";
  }

  async function run(op = selected, text = draft) {
    if (!adapter || busy) return;
    setBusy(true);
    let args: unknown = null, outcome: { result: HostResult; stop?: Run["stop"] };
    try {
      args = JSON.parse(text);
      if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("参数必须是 JSON 对象。");
      outcome = await runOperation(adapter, op, args as Record<string, unknown>, addEvent);
    } catch (error) {
      outcome = { result: { status: "error", message: error instanceof Error ? error.message : String(error), evidence: { sent: args ?? text, limits: [] } } };
    }
    setRuns(previous => [{ id: ++sequence.current, op, args, result: outcome.result, stop: outcome.stop, at: new Date().toLocaleTimeString(), verdict: "", note: "" }, ...previous]);
    if (op === "host.getCapabilities") setCapabilities(await adapter.capabilities().catch(() => capabilities));
    setBusy(false);
  }

  async function update(id: number, change: Partial<Run>) {
    const next = runs.map(item => item.id === id ? { ...item, ...change } : item);
    setRuns(next);
    if ("verdict" in change || "note" in change) await save(next);
  }

  async function save(list: Run[]) {
    if (!adapter || !lab) { setSaved("没有实验室目录，无法保存对照记录。"); return; }
    const path = recordPath(lab.records, host, startedAt.current);
    const document = { schema: "plugin-interface-lab.records.v1", host: hostInfo, startedAt: startedAt.current,
      entries: [...list].reverse().map(item => ({ operation: item.op, args: item.args, at: item.at, status: item.result.status, message: item.result.message, evidence: item.result.evidence ?? null, verdict: item.verdict || null, note: item.note })) };
    const result = await adapter.local.files.write({ path, content: JSON.stringify(document, null, 2) + "\n" });
    setSaved(result.status === "completed" ? `对照记录已写入 ${path}` : `对照记录未写入：${result.message}`);
  }

  async function check(item: Run) {
    if (!adapter?.getResult || !item.result.requestId) return;
    try { await update(item.id, { result: await adapter.getResult(item.result.requestId) }); }
    catch (error) { setFailure(String(error instanceof Error ? error.message : error)); }
  }

  const visibleEvents = events.filter(event => !filter || event.type.includes(filter) || event.source.includes(filter));
  const opRuns = runs.filter(item => item.op === selected || (selected === "context.update" && item.op === "conversation.submitMessage" && item.args && (item.args as { text?: string }).text === CONTEXT_PROBE));
  const current = capabilities[selected];
  const limits = guide.kind === "host" ? current?.limits ?? [] : [];

  return <div className="lab">
    <header className="lab-header">
      <h1>Plugin Interface Lab</h1>
      <span className="facts">宿主 <b>{hostInfo?.status === "confirmed" ? `${hostInfo.name ?? hostInfo.id} ${hostInfo.version ?? ""}` : "未确认"}</b></span>
      <span className="facts">连接 <b>{connection}</b>（{hostInfo?.transport ?? "none"}）</span>
      <span className="facts">本地能力 <b>{adapter?.local.available ? "可用" : "不可用"}</b></span>
      <span className="facts">实验室目录 <code>{lab?.stateDirectory ?? "未知"}</code></span>
    </header>
    <div className="lab-body">
      <nav className="op-list" aria-label="接口列表">
        {GROUPS.map(group => <div key={group}>
          <h2>{group}</h2>
          {GUIDES.filter(item => item.group === group).map(item => <button type="button" key={item.id} aria-current={item.id === selected} onClick={() => setSelected(item.id)} title={item.id}>
            <span className={"dot " + stateOf(item.id)} />{item.id}
            {runs.some(run => run.op === item.id) ? <span className="count">{runs.filter(run => run.op === item.id).length}</span> : null}
          </button>)}
        </div>)}
      </nav>
      <main className="detail">
        {failure ? <p className="banner">{failure}</p> : null}
        <h2>{guide.id}<code>{guide.kind === "host" ? "宿主接口" : "本地能力（插件进程执行，不经过宿主）"}</code></h2>
        <p className="purpose">{guide.purpose}</p>
        <h3>当前连接上的状态</h3>
        <span className="capability"><span className={"dot " + stateOf(selected)} />{stateOf(selected)} · {guide.kind === "host" ? current?.detail ?? "宿主尚未声明此能力。" : adapter?.local.available ? "插件服务为本页面提供了本地能力。" : "插件服务没有为本页面提供本地能力。"}</span>
        <h3>预期效果</h3>
        <div className="expect">
          <div className={host === "claude" ? "current" : ""}><b>Claude</b>{guide.expect.claude}</div>
          <div className={host === "codex" ? "current" : ""}><b>Codex</b>{guide.expect.codex}</div>
        </div>
        <h3>怎样核对</h3>
        <p className="purpose">{guide.check}</p>
        {limits.length ? <><h3>宿主声明的限制</h3><ul className="limits">{limits.map(item => <li key={item}>{item}</li>)}</ul></> : null}
        <h3>参数（JSON，可编辑）</h3>
        <div className="row">{guide.presets.map(preset => <button type="button" key={preset.label} onClick={() => setDrafts(previous => ({ ...previous, [selected]: show(preset.args(presetContext)) }))}>{preset.label}</button>)}</div>
        <textarea aria-label="接口参数" spellCheck={false} value={draft} onChange={event => setDrafts(previous => ({ ...previous, [selected]: event.target.value }))} />
        <div className="row">
          <button type="button" className="primary" disabled={!adapter || busy || connection !== "已连接"} onClick={() => void run()}>调用 {guide.id}</button>
          {selected === "context.update" ? <button type="button" disabled={!adapter || busy || connection !== "已连接"} onClick={() => void run("conversation.submitMessage", JSON.stringify({ text: CONTEXT_PROBE }))}>让模型复述上下文</button> : null}
          <span className="muted">结果显示四段证据：发送了什么、宿主回执、观察到的实际效果、适用的限制。</span>
        </div>
        {saved ? <p className="muted">{saved}</p> : null}
        <h3>调用记录（{opRuns.length}）</h3>
        {opRuns.length === 0 ? <p className="muted">还没有调用。</p> : opRuns.map(item => <article className="run" key={item.id}>
          <div className="run-head"><code>{item.op}</code><span className={"status " + item.result.status}>{statusText[item.result.status]}</span>
            {item.result.requestId ? <code className="muted">请求 {item.result.requestId}</code> : null}<time>{item.at}</time></div>
          <p className="run-message">{item.result.message}</p>
          {item.op === "context.update" && item.result.status === "completed" ? <div className="readout">
            <h4>模型将读到的原文（插件实际发送）</h4>
            {contextReadout(item.result).map((text, index) => <pre key={index}>{text}</pre>)}
            {(item.result.data as { cleared?: boolean } | undefined)?.cleared ? <p className="muted">这是一次清除：宿主收到空上下文。</p> : null}
            {host === "claude" ? <p className="muted">Claude 会在下一条提交时附上这段文字；实际附上的原文见事件记录里的 context.attached。</p> : <p className="muted">Codex 只确认收到；用“让模型复述上下文”核对模型实际读到的内容。</p>}
          </div> : null}
          <div className="evidence">
            <section><h4>发送了什么（sent）</h4><pre>{show(item.result.evidence?.sent)}</pre></section>
            <section><h4>宿主回执（receipt）</h4><pre>{show(item.result.evidence?.receipt)}</pre></section>
            <section><h4>观察到的效果（observed）</h4><pre>{show(item.result.evidence?.observed)}</pre></section>
            <section><h4>适用的限制（limits）</h4><pre>{item.result.evidence?.limits?.length ? item.result.evidence.limits.join("\n") : "（无）"}</pre></section>
            {item.result.data !== undefined ? <section style={{ gridColumn: "1 / -1" }}><h4>返回数据（data）</h4><pre>{show(item.result.data)}</pre></section> : null}
          </div>
          {item.stop && !item.stopped ? <div className="row" style={{ padding: "0 10px 8px" }}><button type="button" onClick={async () => update(item.id, { stopped: await item.stop!() })}>停止{item.op === "local.files.watch" ? "监听" : "订阅"}</button></div> : null}
          {item.stopped ? <p className="run-message muted">{item.stopped.message}</p> : null}
          {item.result.status === "pending" && item.result.requestId && adapter?.getResult ? <div className="row" style={{ padding: "0 10px 8px" }}><button type="button" onClick={() => void check(item)}>查询回执（不会重发）</button></div> : null}
          <div className="compare" role="group" aria-label="对照结论">
            <span className="muted">你观察到的效果：</span>
            {(Object.keys(verdictText) as Exclude<Verdict, "">[]).map(key => <button type="button" key={key} aria-pressed={item.verdict === key} onClick={() => void update(item.id, { verdict: key })}>{verdictText[key]}</button>)}
            <input placeholder="备注（离开输入框时保存）" defaultValue={item.note} onBlur={event => { if (event.target.value !== item.note) void update(item.id, { note: event.target.value }); }} />
          </div>
        </article>)}
      </main>
      <aside className="events" aria-label="事件记录">
        <div className="events-head"><h2>事件记录</h2><input placeholder="按类型或来源过滤" value={filter} onChange={event => setFilter(event.target.value)} /><button type="button" onClick={() => setEvents([])}>清空</button></div>
        <div className="event-list" role="log" aria-live="polite">
          {visibleEvents.length === 0 ? <p className="muted">还没有事件。在对话里发消息、调用工具，或在本页运行“监听文件变化”。</p> : visibleEvents.map(event => <details className="event" key={event.id}>
            <summary><code>{event.type}</code><span>{new Date(event.at).toLocaleTimeString()}</span></summary>
            <div className="source">来源：{event.source}</div>
            <pre>{show(event.data)}</pre>
          </details>)}
        </div>
      </aside>
    </div>
  </div>;
}
