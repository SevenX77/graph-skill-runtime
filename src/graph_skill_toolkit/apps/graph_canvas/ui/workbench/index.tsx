import { useEffect, useState } from "react";
import type { HostAdapter, HostInfo } from "hostpane/page/types";
import type { GraphConnection } from "../../ports/graph/index";
import { graph as demoGraph } from "../../application/demo/graph.mjs";
import { validateCanvas } from "../canvas/index.mjs";
import type { CanvasSnapshot } from "../canvas/types";
import { GraphCanvas } from "../canvas/view";
import { HostStatus } from "../host_status/index";
import { validateInvalidEvent } from "../diagnostics/index.mjs";
import { InvalidGraphNotice, type InvalidGraph } from "../diagnostics/index";

export function GraphWorkbench({ adapter, source }: { adapter: HostAdapter | null; source: GraphConnection | null }) {
  const [snapshot, setSnapshot] = useState<CanvasSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [connection, setConnection] = useState(adapter ? "connecting" : "standalone");
  const [graphFailure, setGraphFailure] = useState("");
  const [invalid, setInvalid] = useState<InvalidGraph | null>(null);
  const [hostFailure, setHostFailure] = useState("");
  const failure = graphFailure || hostFailure;
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(adapter?.hostInfo ?? null);
  const selectedNode = snapshot?.graph.nodes.find(node => node.id === selectedId) ?? null;

  useEffect(() => {
    let disposed = false;
    let identityTimer: ReturnType<typeof setInterval> | undefined;
    const page = document.documentElement.dataset;
    page.connection = adapter ? "connecting" : "standalone";
    delete page.toolResult;
    const receive = (payload: unknown) => {
      if (disposed) return;
      try {
        const value = validateCanvas(payload) as CanvasSnapshot;
        setSnapshot(value);
        setSelectedId(current => value.graph.nodes.some(node => node.id === current) ? current : null);
        setGraphFailure("");
        setInvalid(null);
        page.graphConnection = "live";
        page.toolResult = "received";
      } catch (error) {
        setGraphFailure(error instanceof Error ? error.message : String(error));
        page.toolResult = "invalid";
      }
    };
    const invalidGraph = (event: unknown) => {
      if (disposed) return;
      try {
        setInvalid(validateInvalidEvent(event) as InvalidGraph);
        setGraphFailure("");
        page.graphConnection = "invalid";
      } catch (error) { setGraphFailure(error instanceof Error ? error.message : String(error)); }
    };
    const failGraph = (error: unknown) => {
      if (!disposed) { setGraphFailure(error instanceof Error ? error.message : String(error)); page.graphConnection = "failed"; }
    };
    const failHost = (error: unknown) => {
      if (!disposed) setHostFailure(error instanceof Error ? error.message : String(error));
    };
    // Codex delivers show_graph's arguments before its result; both carry the root.
    const launch = (payload: unknown) => {
      if (disposed || !source || !payload || typeof payload !== "object") return;
      const input = "toolInput" in payload && payload.toolInput && typeof payload.toolInput === "object" ? payload.toolInput as Record<string, unknown> : null;
      const root = input ? input.skill_root : "skillRoot" in payload ? payload.skillRoot : undefined;
      if (root === null || (typeof root === "string" && root.length > 0)) source.selectRoot(root);
    };
    if (source) { page.graphConnection = "connecting"; source.connect({ receive, invalid: invalidGraph, fail: failGraph }); }
    else if (adapter) failGraph(new Error("当前页面缺少本地画布后端连接，请重新连接最新插件并打开画布。"));
    const refresh = async () => {
      if (!adapter || disposed) return;
      try {
        await adapter.capabilities();
        if (!disposed) setHostInfo(adapter.hostInfo);
      } catch (error) { if (!disposed) failHost(error); }
    };
    if (adapter) {
      void adapter.connect({ receive: launch, fail: failHost }).then(() => {
        if (disposed) return;
        setConnection("connected"); page.connection = "connected";
        void refresh();
        identityTimer = setInterval(() => { void refresh(); }, 2000);
      }).catch(error => {
        if (disposed) return;
        setConnection("failed"); page.connection = "failed";
        failHost(error);
      });
    } else if (!source) receive({ graph: { ...demoGraph, width: 352, height: 548 }, skillRoot: null });
    const dispose = () => {
      if (disposed) return;
      disposed = true;
      clearInterval(identityTimer);
      source?.dispose();
      void adapter?.dispose();
    };
    window.addEventListener("pagehide", dispose, { once: true });
    return () => { dispose(); window.removeEventListener("pagehide", dispose); };
  }, [adapter, source]);

  return <main className="workbench" aria-label="Graph Skill canvas">
    <header className="app-header">
      <div className="heading"><strong>Graph Skill</strong><HostStatus info={hostInfo} connection={connection} /></div>
      <div className="root-line"><span className="field-label">Skill</span><span id="skill-path" title={snapshot?.skillRoot ?? invalid?.skillRoot ?? "示例画布未绑定实际 Skill"}>{snapshot?.skillRoot ?? invalid?.skillRoot ?? "示例画布 · 未选择 Skill"}</span></div>
      <p id="status" role="status" aria-live="polite">{failure || (hostInfo?.status === "unknown" ? hostInfo.reason : "点击节点可查看数据。")}</p>
    </header>
    <div className="content-layout">
      <section className="graph-panel" aria-label="图画布">
        <div className="graph-summary"><span>{snapshot?.graph.id ?? "等待图数据"}</span><span>{snapshot ? `${snapshot.graph.nodes.length} 节点 · ${snapshot.graph.edges.length} 连线` : ""}</span></div>
        {invalid ? <InvalidGraphNotice invalid={invalid} hasGraph={!!snapshot} /> : null}
        <div className={invalid && snapshot ? "graph-area stale" : "graph-area"}>{snapshot ? <GraphCanvas graph={snapshot.graph} selectedId={selectedId} onSelect={setSelectedId} /> : <div className="empty-state">{failure || (invalid ? "没有可显示的图" : "正在读取图…")}</div>}</div>
        <p className="graph-hint">{selectedNode ? `已选择 ${selectedNode.id}。` : "点击节点或用 Tab + Enter 选择。"}</p>
      </section>
      <aside className="inspector" aria-label="节点与连接详情">
        <section className="inspector-section"><h2>所选节点</h2>{selectedNode ? <dl><dt>节点 ID</dt><dd data-selected-node>{selectedNode.id}</dd><dt>类型</dt><dd>{selectedNode.kind}</dd></dl> : <p className="muted">尚未选择节点。</p>}</section>
        <section className="inspector-section"><details><summary>宿主连接信息</summary><pre data-host-info>{hostInfo ? JSON.stringify(hostInfo, null, 2) : "独立示例未连接宿主"}</pre></details></section>
      </aside>
    </div>
  </main>;
}
