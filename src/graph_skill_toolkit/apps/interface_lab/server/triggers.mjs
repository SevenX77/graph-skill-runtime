import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { evaluateTriggers, findProjectRules, readFirings, triggerGuidance, triggerStateDirectory } from "hostpane/triggers";

/** The lab's own trigger rule, declared in ../triggers.json. */
export const PROBE_RULE = "interface-lab.probe";
const MARKER = "TRIGGER-PROBE.md";
const PROBE_FILE = "probe.txt";
const MARKER_TEXT = `# Interface Lab trigger probe

The Plugin Interface Lab's end-to-end trigger test asks the agent to edit probe.txt in this
folder. This marker file makes the folder the root of the lab's trigger rule ${PROBE_RULE}.
`;
const IDLE_TEXT = "Interface Lab trigger probe: waiting for the next test.\n";

/** One rule as the page shows it: plain JSON, with a compiled tool pattern given as its source. */
function describe(rule) {
  const tools = rule.use?.tools;
  return {
    id: rule.id, label: rule.label, origin: rule.origin, scope: rule.scope,
    use: rule.use ? { ...rule.use, ...(tools !== undefined ? { tools: typeof tools === "string" ? tools : tools.source } : {}) } : null,
    pages: rule.pages, note: rule.note ?? null,
  };
}

/** The sentence the page sends the agent; the lab Skill tells the agent to carry it out. */
export function probeInstruction({ file, nonce }) {
  return `Interface Lab 触发测试：请用写文件的工具（Claude 用 Edit，Codex 用 apply_patch）把文件 ${file} 的全部内容改成 ${nonce}，只写这一个值，不做别的改动。改完后按页面触发提示打开页面。`;
}

/** The trigger test's server side: the probe folder, the current request, the lab openings that
 * named a firing, and read-only views of the plugin's trigger rules and log. */
export function createTriggerProbe({ ready, triggers }) {
  let request = null;
  const arrivals = [];
  const stateDirectory = () => triggerStateDirectory(triggers.name);
  const folderOf = lab => join(lab.stateDirectory, "trigger-probe");

  async function projects(workspace, firings) {
    const paths = new Set(workspace ? [workspace] : []);
    // A project file already seen firing is listed even when the workspace lies elsewhere.
    for (const firing of firings) if (firing.origin !== "plugin") paths.add(firing.root);
    const found = paths.size ? await findProjectRules([...paths], triggers) : [];
    return found.map(project => ({ file: project.file, root: project.root, rules: project.rules.map(describe), problems: project.problems }));
  }

  return {
    arrive(firing, route) {
      arrivals.unshift({ firing, route, at: new Date().toISOString() });
      arrivals.splice(50);
    },

    async prepare() {
      const lab = await ready;
      const folder = folderOf(lab);
      await mkdir(folder, { recursive: true });
      await writeFile(join(folder, MARKER), MARKER_TEXT, "utf8");
      const file = join(folder, PROBE_FILE);
      await writeFile(file, IDLE_TEXT, "utf8");
      const nonce = `probe-${randomUUID().slice(0, 8)}`;
      request = { nonce, at: new Date().toISOString(), file, instruction: probeInstruction({ file, nonce }) };
      return request;
    },

    async state(workspace) {
      const lab = await ready;
      const firings = await readFirings(stateDirectory(), { limit: 20 });
      const file = join(folderOf(lab), PROBE_FILE);
      const content = request ? await readFile(file, "utf8").catch(() => null) : null;
      // The test's firing is the probe rule's first write after the request.
      const firing = request ? [...firings].reverse().find(item => item.rule === PROBE_RULE && item.origin === "plugin" && item.reason === "write" && item.at >= request.at) ?? null : null;
      return {
        plugin: triggers.name, pageTools: triggers.pageTools, stateDirectory: stateDirectory(),
        rules: triggers.rules.map(describe), projects: await projects(workspace, firings), firings, arrivals: arrivals.slice(0, 20),
        probe: {
          folder: folderOf(lab), file, request, content, firing,
          guidance: firing ? triggerGuidance([firing], triggers) : null,
          arrival: firing ? arrivals.find(item => item.firing === firing.id) ?? null : null,
        },
      };
    },

    async evaluate(event, workspace) {
      const cwd = event.cwd ?? workspace;
      const sample = { hook_event_name: "PostToolUse", tool_name: event.tool_name, tool_input: event.tool_input ?? {}, ...(cwd ? { cwd } : {}) };
      const { firings, projectProblems } = await evaluateTriggers(sample, triggers, { stateDirectory: stateDirectory(), dryRun: true });
      return { event: sample, firings, projectProblems, guidance: firings.length ? triggerGuidance(firings, triggers) : null };
    },
  };
}
