import { fileURLToPath } from "node:url";

/** Server environment that points the runtime adapter at the fake runtime. */
export const fakeRuntimeCommand = [process.execPath, fileURLToPath(new URL("./fake-runtime.mjs", import.meta.url))];
export function fakeRuntimeEnv(extra = {}) {
  return { ...process.env, GRAPH_SKILL_RUNTIME: JSON.stringify(fakeRuntimeCommand), ...extra };
}

/** In-process compile port for backend tests: passes when the plugin can draw the graph. */
export const fakeCompiler = {
  async compile(root) {
    const { loadSkill } = await import("../../application/graph/source/files.mjs");
    const { projectGraph } = await import("../../application/graph/projection/graph.mjs");
    try {
      const skill = await loadSkill(root);
      projectGraph(skill.data, skill.kinds);
      return { status: "passed", diagnostics: [] };
    } catch (error) {
      return { status: "failed", diagnostics: [{ code: "[F-test]", severity: "fatal", message: error.message, source_path: "graph.yaml", line: 1 }] };
    }
  },
};
