import { loadSkill, selectSkillRoot } from '../source/files.mjs';
import { projectGraph } from '../projection/graph.mjs';
import { graph } from '../demo/graph.mjs';

// Graph reading is a business use case, independent of host APIs. The runtime
// compiler decides validity and supplies every validity message; the plugin
// projects only graphs the runtime has accepted.

/** @typedef {{ compile(root: string): Promise<{ status: "passed" | "failed", diagnostics: object[] }> }} SkillCompiler */

/** One graph event for a root:
 * `snapshot { data: { graph, skillRoot } }` when the runtime accepts the skill,
 * `invalid { skillRoot, diagnostics }` carrying the runtime's compile diagnostics.
 * Selection failures, an unreachable runtime and undrawable accepted graphs reject.
 * @param {string | null} skillRoot
 * @param {{ compiler: SkillCompiler }} dependencies
 */
export async function readGraphState(skillRoot, { compiler }) {
  if (!skillRoot) return { type: "snapshot", data: { graph: { ...graph, width: 352, height: 548 }, skillRoot: null } };
  const root = await selectSkillRoot(skillRoot);
  const result = await compiler.compile(root);
  if (result.status === "failed") return { type: "invalid", skillRoot: root, diagnostics: result.diagnostics };
  let skill;
  try {
    skill = await loadSkill(root);
    return { type: "snapshot", data: { graph: projectGraph(skill.data, skill.kinds), skillRoot: skill.skillRoot } };
  } catch (error) {
    throw new Error(`The runtime accepted this graph, but the canvas cannot draw it: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/** One plain-text line per runtime diagnostic, for agent-facing tool text. */
export function describeDiagnostics(diagnostics) {
  return diagnostics.map(item => {
    const where = item.source_path ? ` (${item.source_path}${item.line ? `:${item.line}` : ""})` : "";
    return `${item.code} ${item.message}${where}`;
  }).join("\n");
}
