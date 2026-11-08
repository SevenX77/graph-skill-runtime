import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { UX } from "../../../../../vendor/ui-ux-template/core/behavior/ux.js";
import type { HostAdapter, HostInfo, HostResult } from "hostpane/page/types";
import { GUIDES, GROUPS, CONTEXT_PROBE, type LabPaths } from "../application/guide.mjs";
import { runOperation, contextReadout, recordPath, workspaceRoot, localTime } from "../application/runner.mjs";
import { hostLabel, permissionModeLabel, snapshotHost } from "../application/result_status/index.mjs";
import { callSignal, connectionStatus } from "../application/connection_status/index.mjs";
import { parseRoute, routeHash, switchMode, START, type Route } from "../application/route.mjs";
import { GuideOperation, GuideStart } from "./guide";

type Verdict = "" | "matches" | "differs" | "not-observed";
type Run = { id: number; op: string; connection: HostAdapter; args: unknown; result: HostResult; host: ReturnType<typeof snapshotHost>; at: string; verdict: Verdict; note: string; stop?: () => Promise<HostResult> | HostResult; stopped?: HostResult };
type EventRow = { id: number; type: string; at: string; data?: unknown; source: string };
type LabProps = { adapter: HostAdapter | null; lab: LabPaths | null };

const connectionKeys = new WeakMap<HostAdapter, number>();
let nextConnectionKey = 0;
function connectionKey(adapter: HostAdapter | null) {
  if (!adapter) return "standalone";
  let key = connectionKeys.get(adapter);
  if (!key) { key = ++nextConnectionKey; connectionKeys.set(adapter, key); }
  return String(key);
}

const verdictText: Record<Exclude<Verdict, "">, string> = { matches: "与预期一致", differs: "与预期不符", "not-observed": "未观察到效果" };
const show = (value: unknown) => value === undefined || value === null ? "（无）" : JSON.stringify(value, null, 2);
const SCHEMES = [{ id: "prism", name: "浅" }, { id: "aurora", name: "深" }];
const MODES = [{ id: "guide", name: "指南" }, { id: "lab", name: "测试" }] as const;
const IDS = GUIDES.map(guide => guide.id);
const ROUTE_KEY = "lab-route";

/** The URL hash wins; otherwise the page reopens where this browser last left it, or on the quick start. */
function initialRoute(): Route {
  let remembered: string | null = null;
  try { remembered = localStorage.getItem(ROUTE_KEY); } catch { /* A blocked store opens the quick start. */ }
  const fallback = parseRoute(remembered, IDS, { mode: "guide", id: START });
  return parseRoute(location.hash, IDS, fallback);
}

/** Long evidence fades at the clipped edge only while it actually overflows (template rule 22). */
function Evidence({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLPreElement>(null);
  const measure = () => { const node = ref.current; if (node) node.classList.toggle("fades", node.scrollHeight - node.scrollTop - node.clientHeight > 1); };
  useLayoutEffect(measure);
  return <pre ref={ref} className="il-scroll" onScroll={measure}>{children}</pre>;
}

/** React rewrites className on commit, so the one UX engine reasserts its own state and indicators. */
function refreshTemplate() {
  document.querySelectorAll<HTMLElement>("[data-scope]").forEach(scope => UX.paint(scope));
  document.querySelectorAll(".seg>button.on").forEach(button => button.setAttribute("class", button.getAttribute("class") ?? ""));
}

export function InterfaceLab(props: LabProps) {
  return <InterfaceLabSession key={connectionKey(props.adapter)} {...props} />;
}

function InterfaceLabSession({ adapter, lab: initialLab }: LabProps) {
  const [connection, setConnection] = useState(adapter ? "连接中" : "未在宿主中打开");
  const [failure, setFailure] = useState("");
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(adapter?.hostInfo ?? null);
  const [lab, setLab] = useState<LabPaths | null>(initialLab);
  const [route, setRoute] = useState<Route>(initialRoute);
  const selected = route.id === START ? IDS[0] : route.id;
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [waiting, setWaiting] = useState<{ op: string; since: number } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [saved, setSaved] = useState("");
  const [overlay, setOverlay] = useState<"nav" | "events" | null>(null);
  const main = useRef<HTMLElement>(null);
  const [scheme, setScheme] = useState(document.documentElement.dataset.scheme ?? "prism");
  const [dimming, setDimming] = useState<boolean>(UX.dimOthers() as boolean);
  const sequence = useRef(0);
  const startedAt = useRef(new Date().toISOString());
  const host = hostInfo?.id ?? "unknown";
  const capabilities = hostInfo?.capabilities ?? {};
  const guide = GUIDES.find(item => item.id === selected)!;
  const lastViewId = useMemo(() => {
    for (const run of runs) { const id = (run.result.data as { viewId?: unknown } | undefined)?.viewId; if (run.op === "views.open" && typeof id === "string") return id; }
    return null;
  }, [runs]);
  const presetContext = { lab, host, lastViewId, workspaceRoot: workspace };
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
    let refresh: ReturnType<typeof setInterval> | undefined;
    void adapter.connect({ receive, fail: error => { if (!disposed) setFailure(String(error instanceof Error ? error.message : error)); } }).then(async () => {
      if (disposed) return;
      setConnection("已连接");
      unsubscribe = adapter.events.subscribe(event => addEvent(event, "页面启动时的全量订阅"));
      await adapter.capabilities();
      if (disposed) return;
      setHostInfo(adapter.hostInfo);
      const context = await adapter.host.getContext();
      if (!disposed) setWorkspace(workspaceRoot(context));
      // The permission mode changes while the page stays open.
      if (!disposed) refresh = setInterval(() => { void adapter.capabilities().then(() => { if (!disposed) setHostInfo(adapter.hostInfo); }).catch(() => {}); }, 5000);
    }).catch(error => { if (!disposed) { setConnection("连接失败"); setFailure(String(error instanceof Error ? error.message : error)); } });
    return () => { disposed = true; if (refresh) clearInterval(refresh); unsubscribe(); void adapter.dispose(); };
  }, [adapter]);

  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - waiting.since) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  useLayoutEffect(refreshTemplate);
  useLayoutEffect(() => { main.current?.scrollTo({ top: 0, behavior: "instant" }); main.current?.classList.remove("scrolled"); }, [route.mode, route.id]);
  useEffect(() => {
    document.documentElement.dataset.mode = route.mode;
    const hash = routeHash(route);
    if (location.hash !== hash) history.replaceState(null, "", hash);
    try { localStorage.setItem(ROUTE_KEY, hash); } catch { /* A blocked store only forgets the place. */ }
  }, [route]);
  useEffect(() => {
    const follow = () => setRoute(current => parseRoute(location.hash, IDS, current));
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  useEffect(() => {
    window.addEventListener("resize", refreshTemplate);
    return () => window.removeEventListener("resize", refreshTemplate);
  }, []);
  useEffect(() => {
    if (!overlay) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent) { if (event.key === "Escape") setOverlay(null); return; }
      if ((event.target as Element).closest?.(".il-side.show,.bar")) return;
      setOverlay(null);
      // The press that closes an overlay only closes it; it does not also act on what lay beneath.
      const swallow = (click: Event) => { click.stopPropagation(); click.preventDefault(); };
      document.addEventListener("click", swallow, { capture: true, once: true });
      document.addEventListener("pointerup", () => setTimeout(() => document.removeEventListener("click", swallow, { capture: true })), { once: true });
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("pointerdown", close); };
  }, [overlay]);

  function chooseScheme(id: string) {
    if (id === scheme) return;
    const apply = () => { document.documentElement.dataset.scheme = id; setScheme(id); };
    try { localStorage.setItem("lab-scheme", id); } catch { /* A blocked store only loses the remembered choice. */ }
    if ("startViewTransition" in document && !matchMedia("(prefers-reduced-motion:reduce)").matches) UX.transition(apply);
    else apply();
  }

  function signalOf(id: string) {
    const item = GUIDES.find(guide => guide.id === id)!;
    return connectionStatus({ operation: id, kind: item.kind, connected: connection === "已连接", connection: adapter, host: hostInfo,
      capability: capabilities[id], localAvailable: adapter?.local.available ?? false, calls: runs, running: waiting?.op ?? null });
  }

  async function run(op = selected, text = draft) {
    if (!adapter || busy) return;
    const runHost = snapshotHost(adapter.hostInfo);
    setBusy(true);
    setElapsed(0);
    setWaiting({ op, since: Date.now() });
    let args: unknown = null, outcome: { result: HostResult; stop?: Run["stop"] };
    try {
      args = JSON.parse(text);
      if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("参数必须是 JSON 对象。");
      outcome = await runOperation(adapter, op, args as Record<string, unknown>, addEvent);
    } catch (error) {
      outcome = { result: { status: "error", message: error instanceof Error ? error.message : String(error), evidence: { sent: args ?? text, limits: [] } } };
    }
    setRuns(previous => [{ id: ++sequence.current, op, connection: adapter, args, result: outcome.result, host: runHost, stop: outcome.stop, at: new Date().toISOString(), verdict: "", note: "" }, ...previous]);
    setHostInfo(adapter.hostInfo);
    setWaiting(null);
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
      entries: [...list].reverse().map(item => ({ operation: item.op, args: item.args, at: item.at, host: item.host, status: item.result.status, message: item.result.message, evidence: item.result.evidence ?? null, verdict: item.verdict || null, note: item.note })) };
    const result = await adapter.local.files.write({ path, content: JSON.stringify(document, null, 2) + "\n" });
    setSaved(result.status === "completed" ? `对照记录已写入 ${path}` : `对照记录未写入：${result.message}`);
  }

  async function check(item: Run) {
    if (!adapter?.getResult || !item.result.requestId) return;
    try {
      // A later receipt adds to what the call already showed; what was sent stays on the record.
      const later = await adapter.getResult(item.result.requestId);
      await update(item.id, { result: { ...later, evidence: { ...item.result.evidence, ...later.evidence, sent: later.evidence?.sent ?? item.result.evidence?.sent, limits: later.evidence?.limits ?? item.result.evidence?.limits ?? [] } } });
    }
    catch (error) { setFailure(String(error instanceof Error ? error.message : error)); }
  }

  const visibleEvents = events.filter(event => !filter || event.type.includes(filter) || event.source.includes(filter));
  const runsOf = (id: string) => runs.filter(item => item.op === id || (id === "context.update" && item.op === "conversation.submitMessage" && item.args && (item.args as { text?: string }).text === CONTEXT_PROBE));
  const opRuns = runsOf(selected);
  const current = capabilities[selected];
  const selectedSignal = signalOf(selected);
  const limits = guide.kind === "host" ? current?.limits ?? [] : [];

  const tally = GUIDES.reduce((counts, item) => { counts[signalOf(item.id).tone]++; return counts; }, { available: 0, unavailable: 0, unknown: 0, untested: 0 } as Record<"available" | "unavailable" | "unknown" | "untested", number>);

  const open = (id: string, mode: Route["mode"] = route.mode) => { setRoute({ mode, id }); setOverlay(null); };
  const connected = !!adapter && connection === "已连接";
  const filesOp = selected === "files.openFile" || selected === "files.revealDirectory";
  const hostTone = connection === "已连接" ? hostInfo?.status === "confirmed" ? "available" : "unknown" : connection === "连接中" ? "unknown" : "unavailable";
  const otherHost = host === "codex" ? "claude" : "codex";
  const emptySlots = (result: HostResult) => (["sent", "receipt", "observed", "limits"] as const).filter(slot => slot === "limits" ? !result.evidence?.limits?.length : result.evidence?.[slot] === undefined || result.evidence?.[slot] === null);

  function runCard(item: Run, latest: boolean) {
    const empty = emptySlots(item.result);
    const body = <>
      <p className="il-message">{item.result.message}</p>
      {item.op === "context.update" && item.result.status === "completed" ? <div className="il-readout">
        <span className="label">模型将读到的原文（插件实际发送）</span>
        {contextReadout(item.result).map((text, index) => <pre key={index}>{text}</pre>)}
        {(item.result.data as { cleared?: boolean } | undefined)?.cleared ? <p className="note">这是一次清除：宿主收到空上下文。</p> : null}
        {host === "claude" ? <p className="note">Claude 对其他来源的提交使用隐藏段落；本页提交在可见消息后内联段落。原文与路径见 context.attached。</p> : <p className="note">Codex 只确认收到；用“让模型复述上下文”核对模型实际读到的内容。</p>}
      </div> : null}
      <div className="il-evidence">
        {item.result.data !== undefined ? <section className="wide"><span className="label">返回数据 data</span><Evidence>{show(item.result.data)}</Evidence></section> : null}
        {empty.includes("sent") ? null : <section><span className="label">发送 sent</span><Evidence>{show(item.result.evidence?.sent)}</Evidence></section>}
        {empty.includes("receipt") ? null : <section><span className="label">回执 receipt</span><Evidence>{show(item.result.evidence?.receipt)}</Evidence></section>}
        {empty.includes("observed") ? null : <section><span className="label">观察 observed</span><Evidence>{show(item.result.evidence?.observed)}</Evidence></section>}
        {empty.includes("limits") ? null : <section><span className="label">限制 limits</span><Evidence>{item.result.evidence!.limits!.join("\n")}</Evidence></section>}
      </div>
      {empty.length ? <p className="xs mute il-empty">无内容：{empty.join(" · ")}</p> : null}
      {item.stop && !item.stopped ? <div className="row il-gap"><button type="button" className="btn sec2 sm" onClick={async () => update(item.id, { stopped: await item.stop!() })}>停止{item.op === "local.files.watch" ? "监听" : "订阅"}</button></div> : null}
      {item.stopped ? <p className="note">{item.stopped.message}</p> : null}
      {item.result.status === "pending" && item.result.requestId && adapter?.getResult ? <div className="row il-gap"><button type="button" className="btn sec2 sm" onClick={() => void check(item)}>查询回执（不会重发）</button></div> : null}
      <div className="il-compare" role="group" aria-label="对照结论">
        <div className="seg">
          <i className="seg-ind" />
          {(Object.keys(verdictText) as Exclude<Verdict, "">[]).map(key => <button type="button" key={key} className={item.verdict === key ? "on" : ""} aria-pressed={item.verdict === key} onClick={() => void update(item.id, { verdict: key })}>{verdictText[key]}</button>)}
        </div>
        <input className="input" placeholder="备注（离开输入框时保存）" defaultValue={item.note} onBlur={event => { if (event.target.value !== item.note) void update(item.id, { note: event.target.value }); }} />
      </div>
    </>;
    const head = <>
      <span className="tag"><i className={"il-dot " + callSignal(item).tone} />{callSignal(item).label}</span>
      {item.op !== selected ? <code className="xs">{item.op}</code> : null}
      <span className="xs mute">{item.verdict ? verdictText[item.verdict] : "待对照"}</span>
      {item.result.requestId ? <code className="xs mute">请求 {item.result.requestId}</code> : null}
      <time title={(item.op.startsWith("local.") ? "页面宿主：" : "调用宿主：") + hostLabel(item.host)}>{localTime(item.at)}</time>
    </>;
    return latest
      ? <article className="card" data-cmp data-nofocus key={item.id}><div className="il-run-head">{head}</div>{body}</article>
      : <details className="card il-older" data-cmp data-nofocus key={item.id}><summary className="il-run-head">{head}<span className="il-older-msg">{item.result.message}</span></summary>{body}</details>;
  }

  const labView = <>
    <section data-scope="lab-op" className="il-stack">
      <article className="card" data-cmp data-nofocus>
        <div className="il-head">
          <h2>{guide.id}</h2>
          <span className="tag" role="status"><i className={"il-dot " + selectedSignal.tone} />{selectedSignal.label}</span>
          <button type="button" className="btn ghost sm il-try" onClick={() => open(selected, "guide")}>参数说明</button>
        </div>
        <p className="il-purpose">{guide.purpose}</p>
        {selectedSignal.detail ? <p className="xs mute">{selectedSignal.detail}</p> : null}
        {guide.kind === "host" && current && current.state !== "available" ? <p className="note il-warn">宿主声明 {current.state}：{current.detail}</p> : null}
        {guide.kind === "local" && !adapter?.local.available ? <p className="note il-warn">插件服务没有为本页面提供本地能力。</p> : null}
        {current?.modeLimit && guide.kind === "host" ? <p className="note il-warn">当前权限模式（{permissionModeLabel(current.modeLimit.mode)}）下{current.modeLimit.effect === "blocked" ? "不可用" : "部分可用"}：{current.modeLimit.detail}</p> : null}
      </article>
      <article className="card" data-cmp data-nofocus>
        <div className="il-run-bar">
          <div className="il-presets">{guide.presets.map(preset => <button type="button" className="btn sec2 sm" key={preset.label} onClick={() => setDrafts(previous => ({ ...previous, [selected]: show(preset.args(presetContext)) }))}>{preset.label}</button>)}</div>
          {selected === "context.update" ? <button type="button" className="btn sec2" disabled={!connected || busy} onClick={() => void run("conversation.submitMessage", JSON.stringify({ text: CONTEXT_PROBE }))}>让模型复述</button> : null}
          <button type="button" className="btn" disabled={!connected || busy} onClick={() => void run()}>{busy ? "运行中…" : "运行"}</button>
        </div>
        {filesOp ? <label className="il-field"><span className="label">工作区目录</span><input className="input" aria-label="工作区目录" placeholder="宿主未提供，请填写真实目录" value={workspace ?? ""} onChange={event => {
          setWorkspace(event.target.value || null);
          setDrafts(previous => { const next = { ...previous }; delete next["files.openFile"]; delete next["files.revealDirectory"]; return next; });
        }} /></label> : null}
        {guide.kind === "local" ? <p className="xs mute il-gap">样例文件在插件状态目录：<code>{lab?.sampleFile ?? "未知"}</code></p> : null}
        {guide.note ? <p className="xs mute il-gap">{guide.note}</p> : null}
        <textarea className="input" aria-label="接口参数" spellCheck={false} rows={Math.min(14, Math.max(3, draft.split("\n").length))} value={draft} onChange={event => setDrafts(previous => ({ ...previous, [selected]: event.target.value }))} />
        {waiting ? <p className="note" role="status">宿主处理中…已等待 {elapsed} 秒。{["conversation.submitMessage", "skills.invoke"].includes(waiting.op) ? "会话忙时，提交排队到空闲；等待回执不会重复提交。" : "正在等待宿主回执。"}</p> : null}
        {saved ? <p className="note">{saved}</p> : null}
      </article>
      <article className="card" data-cmp data-nofocus>
        <div className="il-expect">
          <span className="label">{host === "codex" ? "Codex" : "Claude"} 上的预期</span>
          <p>{host === "codex" ? guide.expect.codex : guide.expect.claude}</p>
          <span className="label">怎样核对</span>
          <p>{guide.check}</p>
          {limits.length ? <><span className="label">宿主声明的限制</span><ul className="il-limits">{limits.map(item => <li key={item}>{item}</li>)}</ul></> : null}
          <details className="il-other"><summary className="xs mute">{otherHost === "codex" ? "Codex" : "Claude"} 上的预期</summary><p>{guide.expect[otherHost]}</p></details>
        </div>
      </article>
    </section>
    <section data-scope="runs" className="il-stack il-runs">
      <div className="il-section-title">调用记录 <span className="mute">{opRuns.length}</span></div>
      {opRuns.length === 0 ? <p className="xs mute">还没有调用。选一个预设，点“运行”。</p> : opRuns.map((item, index) => runCard(item, index === 0))}
    </section>
  </>;

  const guideView = route.id === START
    ? <GuideStart onOpen={id => open(id, "guide")} />
    : <GuideOperation guide={guide} host={host} capability={current} localAvailable={adapter?.local.available ?? false} onTry={() => open(selected, "lab")} />;

  return <>
    <div className="bar">
      <div className="bar-in" data-scope="bar" data-dim="none" data-cmp data-nofocus>
        <button type="button" className="il-open nav" aria-expanded={overlay === "nav"} onClick={() => setOverlay(overlay === "nav" ? null : "nav")}>接口</button>
        <div className="seg il-modes" role="tablist" aria-label="页面模式">
          <i className="seg-ind" />
          {MODES.map(item => <button type="button" role="tab" key={item.id} className={route.mode === item.id ? "on" : ""} aria-selected={route.mode === item.id} onClick={() => setRoute(switchMode(route, item.id, IDS))}>{item.name}</button>)}
        </div>
        <span className="sep" />
        <span className="il-host" title={`连接：${connection}（${hostInfo?.transport ?? "none"}）· 权限模式：${permissionModeLabel(hostInfo?.permissionMode)} · 本地能力：${adapter?.local.available ? "可用" : "不可用"}`}><i className={"il-dot " + hostTone} />{hostLabel(hostInfo)}</span>
        <button type="button" className="il-open events" aria-expanded={overlay === "events"} onClick={() => setOverlay(overlay === "events" ? null : "events")}>事件 {events.length}</button>
        <span className="sep" />
        <div className="seg quiet" role="group" aria-label="明暗">
          <i className="seg-ind" />
          {SCHEMES.map(item => <button type="button" key={item.id} className={scheme === item.id ? "on" : ""} aria-pressed={scheme === item.id} onClick={() => chooseScheme(item.id)}>{item.name}</button>)}
        </div>
        <span className="il-dim" title="聚焦时淡化周围"><button type="button" role="switch" className="switch" aria-label="聚焦时淡化周围" aria-checked={dimming} onClick={() => { UX.dimOthers(!dimming); setDimming(!dimming); }} /></span>
      </div>
    </div>
    <div className="il-work">
      <nav className={"il-side nav" + (overlay === "nav" ? " show" : "")} aria-label="接口列表">
        <div className="il-brand"><b>Hostpane</b><span className="xs mute">17 个宿主接口 · 5 个本地能力</span></div>
        <div className="il-tally" title="每个接口在本次连接上的测试状态">
          <span><i className="il-dot available" />{tally.available}</span>
          <span><i className="il-dot unavailable" />{tally.unavailable}</span>
          <span><i className="il-dot unknown" />{tally.unknown}</span>
          <span><i className="il-dot untested" />{tally.untested} 未测</span>
        </div>
        <div className="seg il-ops">
          <i className="seg-ind" />
          {route.mode === "guide" ? <button type="button" className={route.id === START ? "on il-start" : "il-start"} aria-current={route.id === START} onClick={() => open(START, "guide")}>快速上手</button> : null}
          {GROUPS.flatMap(group => [
            <h2 key={"group-" + group}>{group}</h2>,
            ...GUIDES.filter(item => item.group === group).map(item => <button type="button" key={item.id} className={item.id === route.id ? "on" : ""} aria-current={item.id === route.id} title={signalOf(item.id).label} onClick={() => open(item.id)}>
              <i className={"il-dot " + signalOf(item.id).tone} /><span>{item.id.split(".").flatMap((part, index) => index ? [".", <wbr key={index} />, part] : [part])}</span>
              {capabilities[item.id]?.modeLimit ? <span className="il-mode-tag">{capabilities[item.id]?.modeLimit?.effect === "blocked" ? "不可用" : "部分"}</span> : null}
              {runsOf(item.id).length ? <span className="il-count">{runsOf(item.id).length}</span> : null}
            </button>),
          ])}
        </div>
        <details className="il-env">
          <summary className="xs mute">连接与目录</summary>
          <div className="il-fact">宿主<b>{hostLabel(hostInfo)}</b></div>
          <div className="il-fact">连接<b>{connection}（{hostInfo?.transport ?? "none"}）</b></div>
          <div className="il-fact">权限模式<b>{permissionModeLabel(hostInfo?.permissionMode)}</b></div>
          <div className="il-fact">本地能力<b>{adapter?.local.available ? "可用" : "不可用"}</b></div>
          <div className="il-fact">实验室目录<b><code>{lab?.stateDirectory ?? "未知"}</code></b></div>
          <p className="note xs">sample.txt 是插件状态目录 sandbox 里的临时样例，供本地能力测试；宿主文件测试用工作区目录。</p>
        </details>
      </nav>
      <main ref={main} className={"il-main " + route.mode} onScroll={event => event.currentTarget.classList.toggle("scrolled", event.currentTarget.scrollTop > 0)}>
        {failure ? <p className="card il-banner">{failure}</p> : null}
        {route.mode === "guide" ? guideView : labView}
      </main>
      <aside className={"il-side events" + (overlay === "events" ? " show" : "")} aria-label="事件记录">
        <div className="il-events-head"><h2>事件 <span className="mute">{events.length}</span></h2><input className="input" placeholder="过滤类型或来源" value={filter} onChange={event => setFilter(event.target.value)} /><button type="button" className="btn ghost sm" onClick={() => setEvents([])}>清空</button></div>
        <div role="log" aria-live="polite">
          {visibleEvents.length === 0 ? <p className="xs mute">还没有事件。在对话里发消息、调用工具，或运行“监听文件变化”。</p> : visibleEvents.map(event => <details className="il-event" key={event.id}>
            <summary><code>{event.type}</code><span>{localTime(event.at)}</span></summary>
            <div className="il-event-body">
              <p className="xs mute">来源：{event.source}</p>
              <pre>{show(event.data)}</pre>
            </div>
          </details>)}
        </div>
      </aside>
    </div>
  </>;
}
