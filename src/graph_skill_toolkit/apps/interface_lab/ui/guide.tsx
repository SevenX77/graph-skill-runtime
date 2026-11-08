import { INTERFACES, LOCAL_DEFINITIONS } from "hostpane/page";
import type { HostCapability } from "hostpane/page/types";
import type { Guide } from "../application/guide.mjs";
import { QUICKSTART, README, operationAnchor } from "../application/handbook.mjs";

type Param = { name: string; type: string; required: boolean; note: string };
type Definition = { id: string; label: string; sample: unknown; params: readonly Param[]; returns: string };

/** Hostpane's own definitions own each operation's label, fields and result summary. */
export const DEFINITIONS = new Map<string, Definition>([...INTERFACES, ...LOCAL_DEFINITIONS].map(item => [item.id, item as unknown as Definition]));

const link = (anchor: string) => `${README}#${anchor}`;

/** The page-side call for an operation; a subscription takes a listener instead of a promise. */
export function callExample(id: string, args: unknown) {
  const json = (value: unknown) => { const line = JSON.stringify(value); return line.length > 48 ? JSON.stringify(value, null, 2) : line; };
  if (id === "events.subscribe") return `const stop = adapter.events.subscribe(\n  event => log(event),\n  ${json((args as { types?: unknown }).types ?? ["tool.completed"]).replace(/\n/g, "\n  ")},\n);`;
  if (id === "local.files.watch") return `const watch = await adapter.local.files.watch(${json(args)}, event => log(event));\n// 停止：await watch.stop()`;
  return `const result = await adapter.${id}(${json(args)});`;
}

function Code({ children }: { children: string }) {
  return <pre className="il-code">{children}</pre>;
}

/** The guide's first page: what a Hostpane plugin is and the four steps to build one. */
export function GuideStart({ onOpen }: { onOpen: (id: string) => void }) {
  return <div className="il-stack" data-scope="guide-start" data-dim="none">
    <article className="card il-hero" data-cmp data-nofocus>
      <h2>快速上手</h2>
      <p>{QUICKSTART.summary}</p>
      <div className="il-parts">
        {QUICKSTART.parts.map(part => <div key={part.name}><b>{part.name}</b><code>{part.entry}</code><span>{part.text}</span></div>)}
      </div>
    </article>
    <article className="card" data-cmp data-nofocus>
      <div className="il-card-head"><h3>四步接入</h3><a className="btn ghost sm" href={README} target="_blank" rel="noreferrer">完整说明 ↗</a></div>
      <ol className="il-steps">
        {QUICKSTART.steps.map((step, index) => <li key={step.title}>
          <div className="il-step-head"><span className="il-step-no">{index + 1}</span><b>{step.title}</b><a className="xs mute" href={link(step.anchor)} target="_blank" rel="noreferrer">说明 ↗</a></div>
          <Code>{step.code}</Code>
        </li>)}
      </ol>
    </article>
    <div className="il-pair">
      <article className="card" data-cmp data-nofocus>
        <h3>结果状态</h3>
        <p className="xs mute il-envelope"><code>{QUICKSTART.envelope}</code></p>
        <dl className="il-kv">{QUICKSTART.statuses.map(item => <div key={item.id}><dt><i className={"il-dot " + item.tone} /><code>{item.id}</code></dt><dd>{item.text}</dd></div>)}</dl>
      </article>
      <article className="card" data-cmp data-nofocus>
        <h3>四段证据</h3>
        <p className="xs mute il-envelope">每次调用都带 evidence，用来核对宿主实际做了什么。</p>
        <dl className="il-kv">{QUICKSTART.evidence.map(item => <div key={item.id}><dt><code>{item.id}</code></dt><dd>{item.text}</dd></div>)}</dl>
      </article>
    </div>
    <article className="card" data-cmp data-nofocus>
      <h3>常用接口</h3>
      <div className="il-shortcuts">
        {["composer.writeDraft", "conversation.submitMessage", "context.update", "tools.call", "files.openFile", "local.files.read"].map(id => <button type="button" className="btn sec2 sm" key={id} onClick={() => onOpen(id)}><code>{id}</code><span className="mute">{DEFINITIONS.get(id)?.label}</span></button>)}
      </div>
    </article>
  </div>;
}

/** One operation's reference: fields, result, behaviour on each host, and the way to try it. */
export function GuideOperation({ guide, host, connected, capability, localAvailable, onTry }: {
  guide: Guide; host: string; connected: boolean; capability: HostCapability | undefined; localAvailable: boolean; onTry: () => void;
}) {
  const definition = DEFINITIONS.get(guide.id)!;
  const state = guide.kind === "host" ? capability?.state ?? "unknown" : localAvailable ? "available" : "unavailable";
  const stateText = connected ? { available: "当前宿主可用", unavailable: "当前宿主不可用", unknown: "当前宿主未声明" }[state] ?? state : "未连接宿主";
  const example = definition.sample;
  const limits = guide.kind === "host" ? capability?.limits ?? [] : [];
  return <div className="il-stack" data-scope="guide-op" data-dim="none">
    <article className="card" data-cmp data-nofocus>
      <div className="il-head">
        <h2>{guide.id}</h2>
        <span className="tag">{definition.label}</span>
        <span className="tag"><i className={"il-dot " + (connected ? state : "untested")} />{stateText}</span>
        <button type="button" className="btn sm il-try" onClick={onTry}>在测试页运行 →</button>
      </div>
      <p className="il-purpose">{guide.purpose}</p>
      {guide.kind === "local" ? <p className="xs mute">本地能力：由插件自己的 Node 进程执行，不经过宿主。</p> : null}
    </article>
    <article className="card" data-cmp data-nofocus>
      <div className="il-card-head"><h3>参数</h3><a className="xs mute" href={link(operationAnchor(guide.id))} target="_blank" rel="noreferrer">README ↗</a></div>
      {definition.params.length ? <table className="il-params">
        <thead><tr><th>字段</th><th>类型</th><th></th><th>说明</th></tr></thead>
        <tbody>{definition.params.map(param => <tr key={param.name}>
          <td><code className="b">{param.name}</code></td><td><code>{param.type}</code></td><td>{param.required ? "必填" : <span className="mute">可选</span>}</td><td>{param.note}</td>
        </tr>)}</tbody>
      </table> : <p className="mute">无参数，传 <code>{"{}"}</code>。</p>}
      <div className="il-returns"><span className="label">返回 data</span><p>{definition.returns}</p></div>
      <div className="il-returns"><span className="label">调用示例</span>
        <Code>{callExample(guide.id, example)}</Code>
      </div>
    </article>
    <article className="card" data-cmp data-nofocus>
      <h3>两个宿主上的表现</h3>
      <dl className="il-kv il-hosts">
        <div className={host === "claude" ? "current" : ""}><dt>Claude</dt><dd>{guide.expect.claude}</dd></div>
        <div className={host === "codex" ? "current" : ""}><dt>Codex</dt><dd>{guide.expect.codex}</dd></div>
      </dl>
      {limits.length ? <div className="il-returns"><span className="label">当前宿主声明的限制</span><ul className="il-limits">{limits.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
    </article>
  </div>;
}
