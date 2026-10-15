// Test stand-in for `python -m graph_skill_runtime compile --no-cache ROOT`.
// It speaks the runtime's compile-result contract; it does not stand in for the
// runtime's validity rules. A graph.yaml containing "fake-invalid" fails.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { loadSkill } from "../../apps/graph_canvas/application/source/files.mjs";
import { projectGraph } from "../../apps/graph_canvas/application/projection/graph.mjs";

const [command, flag, root] = process.argv.slice(2);
if (command !== "compile" || flag !== "--no-cache" || !root) { console.error("fake runtime: unexpected arguments"); process.exit(64); }
const diagnostic = message => ({ schema_version: "gskill.compile-diagnostic.v1", kind: "compile_diagnostic", code: "[F-fake-runtime]", severity: "fatal", message, source_path: "graph.yaml", line: 1, field_path: null, graph_id: null, phase_id: null, conflicting_phase: null });
let diagnostics = [];
try {
  if ((await readFile(join(root, "graph.yaml"), "utf8")).includes("fake-invalid")) throw new Error("graph.yaml is marked fake-invalid");
  const skill = await loadSkill(root);
  projectGraph(skill.data, skill.kinds);
} catch (error) { diagnostics = [diagnostic(error.message)]; }
process.stdout.write(JSON.stringify({ schema_version: "gskill.compile-result.v1", kind: "compile_result", status: diagnostics.length ? "failed" : "passed", skill_id: null, diagnostics }));
process.exit(diagnostics.length ? 2 : 0);
