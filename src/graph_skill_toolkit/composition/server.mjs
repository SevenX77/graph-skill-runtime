import { servePlugin } from "../plugin_base/server/index.mjs";
import { graphCanvasApp } from "../apps/graph_canvas/server/app.mjs";
import packageInfo from "../package.json" with { type: "json" };

// The toolkit's one plugin process. The Interface Lab is a developer app: it
// is served only when the source-mode registration enables it.
const apps = [graphCanvasApp];
if (process.env.GRAPH_SKILL_INTERFACE_LAB === "1") apps.push((await import("../apps/interface_lab/server/app.mjs")).interfaceLabApp);
await servePlugin({ serverInfo: Object.freeze({ name: "graph-skill-canvas", version: packageInfo.version }), apps });
