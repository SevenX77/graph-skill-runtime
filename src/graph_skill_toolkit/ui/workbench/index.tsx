import { useEffect, useRef, useState } from "react";
import type { HostAction, HostAdapter, HostCapabilities, HostContext, HostResult, HostResultStatus } from "../../ports/host/index";
import { graph as demoGraph } from "../../demo/graph.mjs";
import { validateCanvas } from "../canvas/index.mjs";
import type { CanvasSnapshot } from "../canvas/types";
import { GraphCanvas } from "../canvas/view";

const actions: { id: HostAction; label: string; detail: string; needsPrompt?: boolean }[] = [
  { id: "open-root", label: "打开 Skill 目录", detail: "请求宿主打开当前 Skill 目录" },
  { id: "open-file", label: "打开 SKILL.md", detail: "请求宿主打开当前 Skill 的 SKILL.md" },
  { id: "fill-prompt", label: "填入草稿", detail: "把下方文本填入宿主输入框，不发送", needsPrompt: true },
  { id: "send-prompt", label: "发送并执行", detail: "向宿主发送下方文本并请求开始一轮对话", needsPrompt: true },
  { id: "update-context", label: "同步所选上下文", detail: "显式同步当前图和所选节点，不请求回复" },
  { id: "list-tools", label: "查看可调用工具", detail: "查看此适配器允许页面调用的工具" },
  { id: "call-tool", label: "只读检查图", detail: "只调用当前 Skill 的 inspect_graph" },
  { id: "request-skill", label: "请求使用 Skill", detail: "请求宿主读取当前 SKILL.md 并概述用途，不执行业务图" },
];

const statusLabels: Record<HostResultStatus, string> = {
  completed: "已完成此接口操作", accepted: "请求已接受", pending: "等待宿主结果",
  unsupported: "当前不可用", rejected: "请求被拒绝", error: "操作出错",
};

interface LogEntry {
  id: number;
  action: string;
  time: string;
  skillRoot: string | null;
  result: HostResult;
  acknowledged?: boolean;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function failedResult(error: unknown): HostResult {
  if (error && typeof error === "object" && "outcome" in error && error.outcome === "unknown") {
    const requestId = "requestId" in error && typeof error.requestId === "string" ? error.requestId : undefined;
    return { status: "pending", message: `请求结果未知：${messageOf(error)}。请检查宿主结果，避免重复发送。`, ...(requestId ? { requestId } : {}) };
  }
  return { status: "error", message: messageOf(error) };
}

function printable(value: unknown): string {
  try { return JSON.stringify(value, null, 2) ?? String(value); }
  catch { return String(value); }
}

function resultOf(result: HostResult): HostResult {
  if (!result || !Object.hasOwn(statusLabels, result.status) || typeof result.message !== "string") throw new Error("适配器返回了无效结果，无法判断操作状态。");
  return result;
}

function capabilitySet(value: HostCapabilities): HostCapabilities {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("适配器返回了无效能力列表。");
  for (const capability of Object.values(value)) {
    if (!capability || typeof capability.available !== "boolean" || typeof capability.detail !== "string") throw new Error("适配器返回了无效能力说明。");
  }
  return value;
}

export function GraphWorkbench({ adapter }: { adapter: HostAdapter | null }) {
  const [snapshot, setSnapshot] = useState<CanvasSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [connection, setConnection] = useState(adapter ? "connecting" : "standalone");
  const [failure, setFailure] = useState("");
  const [capabilities, setCapabilities] = useState<HostCapabilities>({});
  const [capabilityError, setCapabilityError] = useState("");
  const [capabilitiesRead, setCapabilitiesRead] = useState(false);
  const [prompt, setPrompt] = useState("请仅回复：Graph Skill 反向接口测试成功。");
  const [busy, setBusy] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const busyRef = useRef(false);
  const sequence = useRef(0);
  const alive = useRef(true);
  const root = snapshot?.skillRoot ?? null;
  const selectedNode = snapshot?.graph.nodes.find(node => node.id === selectedId) ?? null;
  const context: HostContext | null = root && snapshot ? { skillRoot: root, graphId: snapshot.graph.id, ...(selectedNode ? { nodeId: selectedNode.id } : {}) } : null;
  const pending = log.filter(entry => entry.result.status === "pending" && !entry.acknowledged);

  function append(action: string, result: HostResult, skillRoot = root) {
    if (!alive.current) return;
    setLog(current => [{ id: ++sequence.current, action, time: new Date().toLocaleTimeString(), skillRoot, result }, ...current]);
  }

  async function readCapabilities() {
    if (!adapter) return {};
    const value = capabilitySet(await adapter.capabilities());
    if (alive.current) {
      setCapabilities(value);
      setCapabilitiesRead(true);
      setCapabilityError("");
    }
    return value;
  }

  useEffect(() => {
    alive.current = true;
    let disposed = false;
    const state = document.documentElement.dataset;
    state.connection = adapter ? "connecting" : "standalone";
    delete state.toolResult;
    const fail = (error: unknown) => {
      if (disposed) return;
      setSnapshot(null);
      setSelectedId(null);
      setFailure(messageOf(error));
      state.toolResult = "invalid";
    };
    const receive = (payload: unknown) => {
      if (disposed) return;
      try {
        const value = validateCanvas(payload) as CanvasSnapshot;
        setSnapshot(value);
        setSelectedId(current => value.graph.nodes.some(node => node.id === current) ? current : null);
        setFailure("");
        state.toolResult = "received";
      } catch (error) { fail(error); }
    };
    if (adapter) {
      void adapter.connect({ receive, fail }).then(async () => {
        if (disposed) return;
        setConnection("connected");
        state.connection = "connected";
        try { await readCapabilities(); }
        catch (error) { if (!disposed) setCapabilityError(messageOf(error)); }
      }).catch(error => {
        if (disposed) return;
        setConnection("failed");
        state.connection = "failed";
        fail(error);
      });
    } else {
      receive({ graph: { ...demoGraph, width: 352, height: 548 }, skillRoot: null });
    }
    const dispose = () => {
      if (disposed) return;
      disposed = true;
      alive.current = false;
      void adapter?.dispose();
    };
    window.addEventListener("pagehide", dispose, { once: true });
    return () => { dispose(); window.removeEventListener("pagehide", dispose); };
  }, [adapter]);

  function disabledReason(action: HostAction, needsPrompt = false): string {
    if (!adapter) return "独立示例未连接宿主";
    if (connection !== "connected") return "宿主尚未连接";
    if (!root) return "尚未加载真实 Skill";
    if (busy) return "正在等待当前接口返回";
    if (pending.length) return "上一项请求仍在处理中，请先检查结果";
    if (!capabilitiesRead) return "请先读取宿主能力";
    if (!capabilities[action]?.available) return capabilities[action]?.detail ?? "适配器未声明此能力";
    if (needsPrompt && !prompt.trim()) return "先填写测试提示词";
    return "";
  }

  async function run(action: HostAction) {
    const definition = actions.find(item => item.id === action)!;
    if (disabledReason(action, definition.needsPrompt) || busyRef.current || !adapter || !root) return;
    busyRef.current = true;
    setBusy(action);
    const requestedRoot = root;
    try {
      const result = resultOf(await adapter.invoke(action, { skillRoot: requestedRoot, ...(definition.needsPrompt ? { text: prompt } : {}), ...(action === "update-context" && context ? { context } : {}) }));
      append(definition.label, result, requestedRoot);
    } catch (error) { append(definition.label, failedResult(error), requestedRoot); }
    finally { busyRef.current = false; if (alive.current) setBusy(null); }
  }

  async function inspectCapabilities() {
    if (busyRef.current || connection !== "connected") return;
    busyRef.current = true;
    setBusy("capabilities");
    try { append("检查宿主能力", { status: "completed", message: "已读取当前适配器的能力声明；原生效果以实际操作结果为准。", data: await readCapabilities() }); }
    catch (error) { setCapabilityError(messageOf(error)); append("检查宿主能力", { status: "error", message: messageOf(error) }); }
    finally { busyRef.current = false; if (alive.current) setBusy(null); }
  }

  async function checkResult(entry: LogEntry) {
    if (!adapter?.getResult || !entry.result.requestId || busyRef.current || connection !== "connected") return;
    busyRef.current = true;
    setBusy("check-result");
    try {
      const result = resultOf(await adapter.getResult(entry.result.requestId));
      if (alive.current) setLog(current => current.map(item => item.id === entry.id ? { ...item, result: { ...result, requestId: result.requestId ?? entry.result.requestId } } : item));
    } catch (error) { append("检查请求结果", { status: "error", message: messageOf(error), requestId: entry.result.requestId }, entry.skillRoot); }
    finally { busyRef.current = false; if (alive.current) setBusy(null); }
  }

  return (
    <main className="workbench" aria-label="Graph Skill canvas">
      <header className="app-header">
        <div className="heading"><strong>Graph Skill</strong><span className="prototype-badge">接口原型</span><span className={`connection ${connection}`} data-host={adapter?.hostName ?? "standalone"}>{adapter?.hostName ?? "独立示例"} · {connection === "connected" ? "页面就绪" : connection === "connecting" ? "连接中" : connection === "failed" ? "连接失败" : "未连接宿主"}</span></div>
        <div className="root-line"><span className="field-label">Skill</span><span id="skill-path" title={root ?? "示例画布未绑定实际 Skill"}>{root ?? "示例画布 · 未选择 Skill"}</span></div>
        <p id="status" role="status" aria-live="polite">{failure || capabilityError || (busy ? "正在等待接口返回…" : !adapter ? "这是独立示例。请通过宿主打开真实 Skill 后测试接口。" : "点击节点查看上下文；反向操作只在点击测试按钮后触发。")}</p>
      </header>
      <nav className="test-toolbar" aria-label="宿主接口测试">
        <button type="button" data-action="capabilities" disabled={connection !== "connected" || Boolean(busy)} title="读取当前适配器的能力与限制" onClick={() => void inspectCapabilities()}>检查宿主能力</button>
        {actions.map(action => {
          const reason = disabledReason(action.id, action.needsPrompt);
          return <span className="test-button-wrap" key={action.id} title={reason || action.detail}><button type="button" data-action={action.id} disabled={Boolean(reason)} aria-label={reason ? `${action.label}：${reason}` : action.label} onClick={() => void run(action.id)}>{action.label}</button></span>;
        })}
      </nav>
      <div className="content-layout">
        <section className="graph-panel" aria-label="图画布">
          <div className="graph-summary"><span>{snapshot?.graph.id ?? "等待图数据"}</span><span>{snapshot ? `${snapshot.graph.nodes.length} 节点 · ${snapshot.graph.edges.length} 连线` : ""}</span></div>
          <div className="graph-area">{snapshot ? <GraphCanvas graph={snapshot.graph} selectedId={selectedId} onSelect={setSelectedId} /> : <div className="empty-state">{failure || "正在读取图…"}</div>}</div>
          <p className="graph-hint">{selectedNode ? `已选择 ${selectedNode.id}；同步上下文需点击上方按钮。` : "点击节点或用 Tab + Enter 选择。"}</p>
        </section>
        <aside className="inspector" aria-label="节点与接口详情">
          <section className="inspector-section"><h2>所选节点</h2>{selectedNode ? <dl><dt>节点 ID</dt><dd data-selected-node>{selectedNode.id}</dd><dt>类型</dt><dd>{selectedNode.kind}</dd></dl> : <p className="muted">尚未选择节点。</p>}<details><summary>将发送的上下文</summary><pre data-selection-context>{context ? printable(context) : "未绑定实际 Skill"}</pre></details></section>
          <section className="inspector-section"><h2><label htmlFor="test-prompt">测试提示词</label></h2><textarea id="test-prompt" rows={4} value={prompt} onChange={event => setPrompt(event.target.value)} /><p className="muted">“填入草稿”只准备文本；“发送并执行”会请求宿主开始对话。“请求使用 Skill”请求读取说明并概述用途。</p></section>
          <section className="inspector-section capabilities"><details><summary>宿主能力与限制</summary>{capabilityError ? <p>{capabilityError}</p> : !capabilitiesRead ? <p className="muted">尚未取得能力声明。</p> : <ul>{actions.map(action => <li key={action.id}><strong>{action.label} <span>{capabilities[action.id]?.available ? "可测试" : "不可用"}</span></strong><p>{capabilities[action.id]?.detail ?? "适配器未声明此能力"}</p></li>)}</ul>}</details></section>
          <section className="inspector-section action-results"><div className="section-heading"><h2>操作结果</h2><span>{log.length}</span></div><p className="muted">“请求已接受”表示接口已受理，宿主任务是否完成需另行观察。</p><div className="action-log" role="log" aria-live="polite" aria-relevant="additions text">{log.length === 0 ? <p className="muted empty-log">尚未触发测试操作。</p> : log.map(entry => <article key={entry.id} className={`log-entry ${entry.result.status}`} data-result-status={entry.result.status}><div className="log-heading"><strong>{entry.action}</strong><time>{entry.time}</time></div><span className="result-status">{statusLabels[entry.result.status]}</span><p>{entry.result.message}</p>{entry.result.requestId ? <p className="request-id">请求：{entry.result.requestId}</p> : null}{entry.result.status === "pending" && entry.result.requestId && adapter?.getResult ? <button type="button" data-action="check-result" disabled={Boolean(busy) || connection !== "connected"} onClick={() => void checkResult(entry)}>检查请求结果</button> : null}{entry.result.status === "pending" ? entry.acknowledged ? <p className="muted">结果仍未知；已允许继续测试。</p> : <button type="button" data-action="acknowledge-unknown" disabled={Boolean(busy)} onClick={() => setLog(current => current.map(item => item.id === entry.id ? { ...item, acknowledged: true } : item))}>已查看宿主，继续测试</button> : null}{entry.result.data !== undefined ? <details><summary>响应数据</summary><pre>{printable(entry.result.data)}</pre></details> : null}</article>)}</div></section>
        </aside>
      </div>
    </main>
  );
}
