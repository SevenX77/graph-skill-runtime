import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { servePlugin } from "hostpane/server";
import { graphCanvasApp } from "../apps/graph_canvas/server/app.mjs";
import { PLUGIN_NAME, toolkitTriggersAt } from "./triggers.mjs";
import packageInfo from "../package.json" with { type: "json" };

// The toolkit's one plugin process. The Interface Lab is a developer app: it
// is served only when the source-mode registration enables it.
const apps = [graphCanvasApp];
if (process.env.GRAPH_SKILL_INTERFACE_LAB === "1") {
  const { interfaceLabApp } = await import("../apps/interface_lab/server/app.mjs");
  // The lab shows the same trigger declaration the hook beside this bundle uses.
  const triggers = toolkitTriggersAt(dirname(fileURLToPath(import.meta.url)));
  apps.push(deps => interfaceLabApp(deps, { triggers }));
}
await servePlugin({ serverInfo: Object.freeze({ name: PLUGIN_NAME, version: packageInfo.version }), apps });
