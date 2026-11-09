import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parseTriggerFile } from "hostpane/triggers";
import canvasRules from "../apps/graph_canvas/triggers.json" with { type: "json" };

/** The plugin's MCP server name; host tool names and trigger rules use it. */
export const PLUGIN_NAME = "graph-skill-canvas";

/** The toolkit's page-trigger declaration: its page tools, its own rules and, in a source
 * build, the folder its pages are built from. */
export function toolkitTriggers({ source = null } = {}) {
  const pageTools = ["show_graph"];
  const rules = [canvasRules].flatMap(file => {
    const parsed = parseTriggerFile(file, { origin: "plugin", pageTools });
    if (parsed.problems.length) throw new Error(`The toolkit's trigger rules are invalid: ${parsed.problems.join("; ")}`);
    return parsed.rules;
  });
  return { name: PLUGIN_NAME, pageTools, ignoreTools: ["open_skill_folder", "open_in_codex"], rules, source };
}

/** The declaration for the build in `directory`, the folder holding the bundled server and hook.
 * A source build has the toolkit's package.json beside that folder; an installed release has not. */
export function toolkitTriggersAt(directory) {
  const root = dirname(directory);
  let source = null;
  try {
    const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
    if (manifest?.name === "graph-skill-toolkit" && typeof manifest.scripts?.build === "string") source = { root, build: "npm run build" };
  } catch { /* An installed release carries no source to rebuild. */ }
  return toolkitTriggers({ source });
}
