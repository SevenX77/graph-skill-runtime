import type { CompileDiagnostic } from "../../ports/graph/index";

export interface InvalidGraph {
  skillRoot: string;
  diagnostics: CompileDiagnostic[];
  total: number;
}

/** Prominent notice for a skill the runtime does not compile. Messages are the runtime's own. */
export function InvalidGraphNotice({ invalid, hasGraph }: { invalid: InvalidGraph; hasGraph: boolean }) {
  return <section className="invalid-graph" role="alert" aria-label="图当前无法编译">
    <h2>图当前无法编译 · runtime 报告 {invalid.total} 个问题</h2>
    <p className="invalid-graph-note">{hasGraph ? "画布上淡显的是上一次编译通过的图。修好文件并保存后，画布会自动重画。" : "还没有编译通过的版本可显示。修好文件并保存后，画布会自动显示。"}</p>
    <ul>{invalid.diagnostics.map((item, index) => <li key={index} data-diagnostic-code={item.code}>
      <code>{item.code}</code> <span className="invalid-graph-message">{item.message}</span>
      {item.source_path ? <span className="invalid-graph-where">{item.source_path}{item.line ? `:${item.line}` : ""}{item.field_path ? ` · ${item.field_path}` : ""}</span> : null}
    </li>)}</ul>
    {invalid.total > invalid.diagnostics.length ? <p className="invalid-graph-note">另有 {invalid.total - invalid.diagnostics.length} 个问题未列出。</p> : null}
  </section>;
}
