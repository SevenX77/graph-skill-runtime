import { useEffect, useRef, useState } from "react";
import type { HostAdapter, HostInfo, HostResult } from "hostpane/page/types";
import { localTime } from "../application/runner.mjs";

type Call = { tool: string; arguments: Record<string, unknown> };
type Firing = { id: string; at: string; rule: string; label: string; origin: string; reason: "write" | "use" | "change"; tool: string; root: string; files: string[]; calls: Call[]; rebuild: { command: string; cwd: string } | null; note: string | null };
type Rule = { id: string; label: string; origin: string; scope: { kind: "root"; markers: string[] } | { kind: "paths"; include: string[] }; use: { tools?: string; pathKeys?: string[]; commands?: string[] } | null; pages: { tool: string; arguments?: Record<string, unknown>; pathArguments?: Record<string, string>; firingArgument?: string }[]; note: string | null };
type Project = { file: string; root: string; rules: Rule[]; problems: string[] };
type Arrival = { firing: string; route: string | null; at: string };
type Probe = { folder: string; file: string; request: { nonce: string; at: string; file: string; instruction: string } | null; content: string | null; firing: Firing | null; guidance: string | null; arrival: Arrival | null };
type State = { plugin: string; pageTools: string[]; stateDirectory: string; rules: Rule[]; projects: Project[]; firings: Firing[]; arrivals: Arrival[]; probe: Probe };
type Evaluation = { firings: Firing[]; projectProblems: { file: string; problems: string[] }[]; guidance: string | null };

export type TriggerViewProps = {
  view: string; adapter: HostAdapter | null; connected: boolean; host: string; hostInfo: HostInfo | null;
  workspace: string | null; openedFiring: string | null; onView: (id: string) => void;
};

/** A tool result's structured content, whichever form the host delivers it in. */
function structured(value: unknown): unknown {
  const item = value as { structuredContent?: unknown; result?: unknown; content?: unknown } | null;
  if (!item || typeof item !== "object") return null;
  if (item.structuredContent) return item.structuredContent;
  if (item.result !== undefined) return structured(item.result);
  const blocks = Array.isArray(value) ? value : Array.isArray(item.content) ? item.content : [];
  for (const block of blocks as { text?: unknown }[]) {
    if (typeof block?.text !== "string") continue;
    try { const data = JSON.parse(block.text); if (data && typeof data === "object") return data; } catch { /* Not the JSON block. */ }
  }
  return null;
}

/** The lab's own page-trigger tool, called through the host like any page-callable tool. */
async function labTriggers<T>(adapter: HostAdapter, host: string, args: Record<string, unknown>): Promise<T> {
  const tool = host === "claude" ? { name: "lab_triggers", server: "graph-skill-canvas", scope: "session" } : { name: "lab_triggers", scope: "originating-server" };
  const result = await adapter.invoke("tools.call", { tool, arguments: args });
  // Claude Code takes a session's tool list when the server first connects; a plugin
  // server replaced during the session serves lab_triggers, but the list still lacks it.
  if (result.status === "unsupported" && host === "claude") throw new Error(`${result.message} 本会话的工具清单是在插件服务加上 lab_triggers 之前取得的。在本会话输入 /mcp，选中 graph-skill-canvas 点 Reconnect（或新开一个会话），再回到本页。`);
  if (result.status !== "completed") throw new Error(result.message);
  const data = structured(result.data);
  if (!data) throw new Error("lab_triggers 没有返回可读的数据。");
  return data as T;
}

const REASON: Record<Firing["reason"], string> = { write: "写入", use: "使用", change: "变化" };
const short = (path: string) => path.length > 64 ? "…" + path.slice(-62) : path;
const Code = ({ children }: { children: string }) => <pre className="il-code">{children}</pre>;
const Direction = () => <span className="tag il-dir">宿主 → 页面</span>;

function NotConnected({ what }: { what: string }) {
  return <p className="card il-notice">{what}需要连接宿主。在 Claude Code 或 Codex 里调用 <code>open_interface_lab</code> 打开本页后再来。</p>;
}

/** 机制: what a page trigger is, its five steps on the Graph Skill rule, when it fires and its limits. */
function HowItWorks({ onView }: { onView: (id: string) => void }) {
  const steps: [string, string, string, string][] = [
    ["Agent 调用工具", "Agent", "Agent 改了一个 Graph Skill 文件：", "Edit  D:\\…\\hello-world\\graph.yaml"],
    ["宿主运行插件的钩子", "宿主", "工具调用结束后，宿主运行插件登记的 PostToolUse 钩子（Claude 登记在 ~/.claude/settings.json，Codex 登记在 ~/.codex/hooks.json），从标准输入交给它工具名和参数：", `{"tool_name":"Edit","tool_input":{"file_path":"D:\\\\…\\\\hello-world\\\\graph.yaml"}}`],
    ["按规则判断，写下记录", "Hostpane", "规则 graph-skill.root 说：同时含 SKILL.md 和 graph.yaml 的目录是一个根目录，改了里面的文件就打开画布。这次命中，钩子在 firings.jsonl 里记一条触发。", `{"rule":"graph-skill.root","reason":"write","tool":"Edit","root":"D:\\\\…\\\\hello-world",…}`],
    ["钩子把提示交给 Agent", "Hostpane 和宿主", "钩子的输出作为附加上下文（additionalContext）进入 Agent 的下一步，写明要调用的页面工具和确切参数：", `1. Rule graph-skill.root (Graph Skill 画布), Edit wrote D:\\…\\graph.yaml: call show_graph of the graph-skill-canvas MCP server with {"skill_root":"D:\\\\…\\\\hello-world"}.`],
    ["Agent 打开页面", "Agent 和宿主", "Agent 调用 show_graph。Claude 在内置浏览器里显示画布；Codex 在对话里显示 MCP App 视图。", "show_graph {\"skill_root\": \"D:\\\\…\\\\hello-world\"}"],
  ];
  return <div className="il-stack" data-scope="trigger-how" data-dim="none">
    <article className="card il-hero" data-cmp data-nofocus>
      <div className="il-head"><h2>页面触发</h2><Direction /></div>
      <p>Agent 改了文件或用了某个工具，插件的钩子就按规则判断这次改动属于哪个页面，再请 Agent 打开它。另外两类接口都由页面发起：宿主接口是页面调用宿主，本地能力是页面调用插件进程。页面触发方向相反，是宿主里的一次工具调用让页面出现。</p>
    </article>
    <article className="card" data-cmp data-nofocus>
      <h3>一次触发的五步</h3>
      <ol className="il-flow">
        {steps.map(([title, owner, text, example], index) => <li key={title}>
          <div className="il-step-head"><span className="il-step-no">{index + 1}</span><b>{title}</b><span className="tag xs">{owner}</span></div>
          <p>{text}</p>
          <Code>{example}</Code>
        </li>)}
      </ol>
    </article>
    <div className="il-pair">
      <article className="card" data-cmp data-nofocus>
        <h3>什么时候触发</h3>
        <dl className="il-kv">
          <div><dt>写入</dt><dd>Agent 用写文件的工具（Write、Edit、MultiEdit、NotebookEdit、apply_patch）改了规则范围里的文件。例：Edit graph.yaml。</dd></div>
          <div><dt>使用</dt><dd>Agent 用了规则声明的工具或命令，文件不变也算。例：调用 <code>mcp__gskill__compile</code>，或在 Skill 目录里运行 <code>gskill run .</code>。</dd></div>
          <div><dt>变化</dt><dd>命令行工具（Bash、PowerShell）运行之后，规则范围里的文件和上次记下的不一样。钩子不解析命令文本，只比对工作目录和最近 7 天触发过的目录。</dd></div>
        </dl>
      </article>
      <article className="card" data-cmp data-nofocus>
        <h3>不会触发</h3>
        <ul className="il-limits">
          <li>只读的工具：Read、Grep、Glob 等。</li>
          <li>插件自己的工具、内置浏览器和窗格工具，这样打开页面不会再触发打开页面。</li>
          <li>以 <code>.</code> 开头的目录、<code>node_modules</code>、<code>__pycache__</code> 里的文件。</li>
        </ul>
      </article>
    </div>
    <article className="card" data-cmp data-nofocus>
      <h3>规则从哪里来</h3>
      <dl className="il-kv">
        <div><dt>插件内置</dt><dd>每个页面的规则放在它自己的代码旁边，例如画布的 <code>apps/graph_canvas/triggers.json</code>。</dd></div>
        <div><dt>项目文件</dt><dd>项目在根目录的 <code>.hostpane/triggers.json</code> 里声明自己的哪些文件由哪个页面展示。项目规则只能写打开哪个页面、带什么参数，不能带命令。</dd></div>
      </dl>
      <Code>{`{ "id": "graph-skill.root", "label": "Graph Skill 画布",
  "scope": { "kind": "root", "markers": ["SKILL.md", "graph.yaml"] },
  "use": { "tools": "^mcp__gskill__", "pathKeys": ["skill_root", "skill_path"], "commands": ["gskill"] },
  "pages": [{ "tool": "show_graph", "pathArguments": { "skill_root": "." } }] }`}</Code>
    </article>
    <article className="card" data-cmp data-nofocus>
      <h3>限制</h3>
      <ul className="il-limits">
        <li>钩子不能自己打开页面。第 5 步取决于 Agent 是否照提示去做，所以端到端测试单独检查这一步。</li>
        <li>页面改动重新构建后，下次打开就是新页面；插件服务端代码的改动要等插件服务重启才生效。</li>
      </ul>
      <div className="row il-gap"><button type="button" className="btn sm" onClick={() => onView("test")}>做端到端测试 →</button></div>
    </article>
  </div>;
}

type StepState = "done" | "wait" | "fail" | "idle";
const STEP_TONE: Record<StepState, string> = { done: "available", wait: "unknown", fail: "unavailable", idle: "untested" };
const TIMEOUT_SECONDS = 180;

/** 端到端测试: prepare the probe, ask the agent to edit it, and watch the five steps happen. */
function EndToEnd({ adapter, connected, host, hostInfo, openedFiring }: TriggerViewProps) {
  const [state, setState] = useState<State | null>(null);
  const [sent, setSent] = useState<{ via: string; result: HostResult } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  async function refresh() {
    if (!adapter) return;
    try { const next = await labTriggers<State>(adapter, host, { action: "state" }); if (alive.current) { setState(next); setError(""); } }
    catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : String(failure)); }
  }
  useEffect(() => { if (connected) void refresh(); }, [connected]);

  const probe = state?.probe;
  const request = probe?.request ?? null;
  const elapsed = request ? Math.max(0, Math.round((now - Date.parse(request.at)) / 1000)) : 0;
  const edited = !!request && probe?.content?.trim() === request.nonce;
  const fired = !!probe?.firing;
  const arrived = !!probe?.arrival || (!!openedFiring && openedFiring === probe?.firing?.id);
  const complete = edited && fired && arrived;
  const timedOut = !!request && !complete && elapsed > TIMEOUT_SECONDS;

  // Poll while a test runs; stop once it is complete or has timed out.
  useEffect(() => {
    if (!connected || !request || complete || timedOut) return;
    const timer = setInterval(() => { setNow(Date.now()); void refresh(); }, 2000);
    return () => clearInterval(timer);
  }, [connected, request?.at, complete, timedOut]);

  async function start() {
    if (!adapter || busy) return;
    setBusy(true); setSent(null); setError("");
    try {
      const prepared = await labTriggers<{ instruction: string }>(adapter, host, { action: "prepare" });
      // The request travels to the agent only after the probe and its value exist.
      setNow(Date.now());
      await refresh();
      const submit = hostInfo?.capabilities?.["conversation.submitMessage"]?.state === "available";
      const result = submit
        ? await adapter.invoke("conversation.submitMessage", { text: prepared.instruction, model: { source: "current" }, effort: { source: "current" } })
        : await adapter.invoke("composer.writeDraft", { text: prepared.instruction, mode: "append" });
      setSent({ via: submit ? "conversation.submitMessage" : "composer.writeDraft", result });
    } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
    setBusy(false);
  }

  if (!adapter) return <><Intro /><NotConnected what="端到端测试" /></>;
  const sentState: StepState = sent ? (["completed", "accepted", "pending"].includes(sent.result.status) ? "done" : "fail") : request && (edited || fired) ? "done" : request ? "wait" : "idle";
  const steps: { title: string; state: StepState; detail: string; evidence?: string }[] = [
    { title: "准备测试文件", state: request ? "done" : "idle",
      detail: request ? `在 ${short(probe!.folder)} 放好标记文件 TRIGGER-PROBE.md 和 probe.txt；本次随机值 ${request.nonce}（${localTime(request.at)}）。` : "点“开始测试”后，插件准备测试目录和一个随机值。" },
    { title: "请 Agent 修改文件", state: sentState,
      detail: sent ? `${sent.via === "conversation.submitMessage" ? "已作为一条消息发给 Agent" : "已写进输入框，请按发送"}：${sent.result.message}` : request ? (edited || fired ? "请求已由此前的页面发出。" : "等待把修改请求发给 Agent。") : "页面把一句修改请求发给 Agent。" },
    { title: "Agent 改了文件", state: edited ? "done" : request ? (timedOut ? "fail" : "wait") : "idle",
      detail: edited ? `probe.txt 的内容是 ${request!.nonce}。` : request ? `probe.txt 现在是：${(probe?.content ?? "（读不到）").trim().slice(0, 80)}` : "probe.txt 的内容变成随机值。" },
    { title: "钩子记下一次触发", state: fired ? "done" : request ? (timedOut ? "fail" : "wait") : "idle",
      detail: fired ? `规则 ${probe!.firing!.rule}，${probe!.firing!.tool} ${REASON[probe!.firing!.reason]}，${localTime(probe!.firing!.at)}；触发编号 ${probe!.firing!.id}。` : "触发记录里出现规则 interface-lab.probe 的一次写入，时间晚于准备时间。",
      evidence: probe?.guidance ?? undefined },
    { title: "Agent 按提示打开页面", state: arrived ? "done" : request ? (timedOut ? "fail" : "wait") : "idle",
      detail: openedFiring && openedFiring === probe?.firing?.id ? "本页就是 Agent 用这次触发的编号调用 open_interface_lab 打开的。" : probe?.arrival ? `Agent 在 ${localTime(probe.arrival.at)} 用触发编号调用了 open_interface_lab；新打开的页面会显示结果。` : "Agent 用这次触发的编号调用 open_interface_lab。" },
  ];
  const stuck = steps.findIndex(step => step.state !== "done");
  const hints: Record<number, string> = {
    1: "没能把请求发给 Agent：看上面的原因；也可以复制下面的请求自己发。",
    2: "Agent 没有修改文件：看对话里 Agent 是否收到请求、是否用了写文件的工具。",
    3: "文件改了，钩子却没有记录：检查宿主是否登记了插件的 PostToolUse 钩子，以及 Agent 用的是否是写文件的工具。",
    4: "钩子记下了触发，Agent 却没有打开页面：提示已交给 Agent，但没有被执行。",
  };
  return <div className="il-stack" data-scope="trigger-test" data-dim="none">
    <Intro />
    {openedFiring ? <p className="card il-notice">本页由页面触发打开，触发编号 <code>{openedFiring}</code>。</p> : null}
    <article className="card" data-cmp data-nofocus>
      <div className="il-card-head">
        <h3>端到端测试</h3>
        <span className="tag" role="status"><i className={"il-dot " + (complete ? "available" : timedOut ? "unavailable" : request ? "unknown" : "untested")} />{complete ? `通过，用时 ${Math.round((Date.parse(probe!.arrival?.at ?? probe!.firing!.at) - Date.parse(request!.at)) / 1000)} 秒` : timedOut ? `未通过：停在第 ${stuck + 1} 步` : request ? `进行中 · ${elapsed} 秒` : "未开始"}</span>
        <button type="button" className="btn sm" disabled={!connected || busy} onClick={() => void start()}>{busy ? "准备中…" : request ? "重新测试" : "开始测试"}</button>
      </div>
      {error ? <p className="note il-warn">{error}</p> : null}
      <ol className="il-checks">
        {steps.map((step, index) => <li key={step.title} className={step.state}>
          <i className={"il-dot " + STEP_TONE[step.state]} />
          <div><b>{index + 1}. {step.title}</b><p>{step.detail}</p>
            {step.evidence ? <details className="il-other"><summary className="xs mute">钩子交给 Agent 的提示原文</summary><pre className="il-code">{step.evidence}</pre></details> : null}
          </div>
        </li>)}
      </ol>
      {timedOut && hints[stuck] ? <p className="note il-warn">{hints[stuck]}</p> : null}
      {request ? <details className="il-other"><summary className="xs mute">发给 Agent 的请求</summary><pre className="il-code">{request.instruction}</pre></details> : null}
    </article>
  </div>;
}

function Intro() {
  return <article className="card" data-cmp data-nofocus>
    <div className="il-head"><h2>端到端测试</h2><Direction /></div>
    <p className="il-purpose">在本宿主上真实走一遍五步：插件准备一个测试文件，页面请 Agent 改它，钩子触发，Agent 按提示重新打开本页。全部做到才算通过。</p>
  </article>;
}

function scopeText(scope: Rule["scope"]) {
  return scope.kind === "root" ? `含 ${scope.markers.join("、")} 的目录` : scope.include.join("\n");
}
function pageText(page: Rule["pages"][number]) {
  const args = { ...(page.arguments ?? {}), ...Object.fromEntries(Object.entries(page.pathArguments ?? {}).map(([key, value]) => [key, `<根目录>/${value === "." ? "" : value}`])), ...(page.firingArgument ? { [page.firingArgument]: "<触发编号>" } : {}) };
  return `${page.tool} ${JSON.stringify(args)}`;
}

function RuleCard({ rule, origin }: { rule: Rule; origin: string }) {
  return <div className="il-rule">
    <div className="il-step-head"><b>{rule.label}</b><code className="xs mute">{rule.id}</code><span className="tag xs">{origin}</span></div>
    <dl className="il-kv">
      <div><dt>范围</dt><dd><pre className="il-inline">{scopeText(rule.scope)}</pre></dd></div>
      {rule.use ? <div><dt>使用信号</dt><dd>{[rule.use.tools ? `工具 ${rule.use.tools}` : "", rule.use.commands?.length ? `命令 ${rule.use.commands.join("、")}` : ""].filter(Boolean).join("；")}</dd></div> : null}
      <div><dt>打开</dt><dd>{rule.pages.map(page => <code key={page.tool + JSON.stringify(page)} className="il-block">{pageText(page)}</code>)}</dd></div>
      {rule.note ? <div><dt>附注</dt><dd>{rule.note}</dd></div> : null}
    </dl>
  </div>;
}

const SAMPLES = [
  { id: "Edit", label: "Edit 改文件", needsPath: true },
  { id: "Write", label: "Write 写文件", needsPath: true },
  { id: "mcp__gskill__compile", label: "调用 gskill 编译", needsPath: true },
  { id: "Bash", label: "Bash 运行命令", needsPath: false },
] as const;

/** 规则与记录: the rules in effect, a dry run, and the latest firings. */
function RulesAndLog({ adapter, connected, host, workspace }: TriggerViewProps) {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [tool, setTool] = useState<(typeof SAMPLES)[number]["id"]>("Edit");
  const [path, setPath] = useState("");
  const [command, setCommand] = useState("gskill compile .");
  const [cwd, setCwd] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  async function refresh() {
    if (!adapter) return;
    try { setState(await labTriggers<State>(adapter, host, { action: "state", ...(workspace ? { workspace } : {}) })); setError(""); }
    catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
  }
  useEffect(() => { if (connected) void refresh(); }, [connected, workspace]);
  useEffect(() => { if (workspace && !path) setPath(workspace.replace(/[\\/]+$/, "") + (workspace.includes("\\") ? "\\examples\\hello-world\\graph.yaml" : "/examples/hello-world/graph.yaml")); if (workspace && !cwd) setCwd(workspace); }, [workspace]);

  async function evaluate() {
    if (!adapter) return;
    const event = tool === "Bash" ? { tool_name: tool, tool_input: { command }, ...(cwd ? { cwd } : {}) }
      : { tool_name: tool, tool_input: tool === "mcp__gskill__compile" ? { skill_root: path } : { file_path: path }, ...(workspace ? { cwd: workspace } : {}) };
    try { setEvaluation(await labTriggers<Evaluation>(adapter, host, { action: "evaluate", event, ...(workspace ? { workspace } : {}) })); setError(""); }
    catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
  }

  if (!adapter) return <NotConnected what="规则与记录" />;
  return <div className="il-stack" data-scope="trigger-rules" data-dim="none">
    <article className="card" data-cmp data-nofocus>
      <div className="il-card-head"><h3>生效的规则</h3><button type="button" className="btn ghost sm" onClick={() => void refresh()}>刷新</button></div>
      {error ? <p className="note il-warn">{error}</p> : null}
      {state ? <>
        <p className="xs mute">插件 {state.plugin} 可打开的页面工具：{state.pageTools.join("、")}。触发记录在 <code>{state.stateDirectory}</code>。</p>
        <div className="il-rules">
          {state.rules.map(rule => <RuleCard key={"plugin:" + rule.id} rule={rule} origin="插件内置" />)}
          {state.projects.flatMap(project => project.rules.map(rule => <RuleCard key={project.file + ":" + rule.id} rule={rule} origin={"项目文件 " + short(project.file)} />))}
        </div>
        {state.projects.length === 0 ? <p className="xs mute">{workspace ? `工作区 ${short(workspace)} 及其上级目录里没有 .hostpane/triggers.json。` : "宿主没有提供工作区目录。"}项目规则触发过一次后也会列在这里。</p> : null}
        {state.projects.filter(project => project.problems.length).map(project => <p key={project.file} className="note il-warn">项目文件 {project.file} 有问题，钩子跳过了出错的规则：{project.problems.join("；")}</p>)}
      </> : <p className="xs mute">读取中…</p>}
    </article>
    <article className="card" data-cmp data-nofocus>
      <h3>规则试算</h3>
      <p className="xs mute">假设 Agent 做了下面这次调用，看哪些规则会触发、会请 Agent 打开什么。试算不写任何记录；命令行调用只算“使用”，不比对文件变化。</p>
      <div className="il-run-bar">
        <div className="il-presets" role="group" aria-label="工具">{SAMPLES.map(item => <button type="button" key={item.id} className={"btn sm " + (tool === item.id ? "sec2" : "ghost")} aria-pressed={tool === item.id} onClick={() => setTool(item.id)}>{item.label}</button>)}</div>
        <button type="button" className="btn" disabled={!connected} onClick={() => void evaluate()}>试算</button>
      </div>
      {tool === "Bash"
        ? <><label className="il-field"><span className="label">命令</span><input className="input" value={command} onChange={event => setCommand(event.target.value)} /></label>
          <label className="il-field"><span className="label">工作目录</span><input className="input" value={cwd} onChange={event => setCwd(event.target.value)} /></label></>
        : <label className="il-field"><span className="label">{tool === "mcp__gskill__compile" ? "skill_root" : "文件路径"}</span><input className="input" value={path} onChange={event => setPath(event.target.value)} /></label>}
      {evaluation ? evaluation.firings.length ? <div className="il-returns">
        <span className="label">会触发 {evaluation.firings.length} 条规则</span>
        {evaluation.firings.map(firing => <p key={firing.origin + firing.rule + firing.root}><b>{firing.label}</b>（{REASON[firing.reason]}）→ {firing.calls.map(call => <code key={call.tool} className="il-block">{call.tool} {JSON.stringify(call.arguments)}</code>)}</p>)}
        <details className="il-other"><summary className="xs mute">钩子会交给 Agent 的提示</summary><pre className="il-code">{evaluation.guidance}</pre></details>
      </div> : <p className="note">不会触发：没有规则的范围包含这次调用。</p> : null}
    </article>
    <article className="card" data-cmp data-nofocus>
      <h3>最近的触发 <span className="mute">{state?.firings.length ?? 0}</span></h3>
      {state?.firings.length ? <ul className="il-firings">
        {state.firings.map(firing => <li key={firing.id}>
          <time>{localTime(firing.at)}</time>
          <div><b>{firing.label}</b> <span className="xs mute">{firing.tool} · {REASON[firing.reason]}</span>
            <p className="xs">{firing.files.length ? firing.files.map(short).join("、") : short(firing.root)}</p>
            <p className="xs mute">{firing.calls.map(call => call.tool).join("、")}{state.arrivals.some(item => item.firing === firing.id) ? " · 已打开" : ""}</p>
          </div>
        </li>)}
      </ul> : <p className="xs mute">还没有触发记录。</p>}
    </article>
  </div>;
}

/** The page-trigger mode: one of its three views. */
export function TriggerView(props: TriggerViewProps) {
  if (props.view === "test") return <EndToEnd {...props} />;
  if (props.view === "rules") return <RulesAndLog {...props} />;
  return <HowItWorks onView={props.onView} />;
}

export const TRIGGER_NAV = [
  { id: "how", name: "机制" },
  { id: "test", name: "端到端测试" },
  { id: "rules", name: "规则与记录" },
] as const;
