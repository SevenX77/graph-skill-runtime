import { servePlugin } from "hostpane/server";
import { graphCanvasApp } from "../apps/graph_canvas/server/app.mjs";
import { PLUGIN_NAME } from "./triggers.mjs";
import packageInfo from "../package.json" with { type: "json" };

// The toolkit's one plugin process. It serves the graph canvas.
const apps = [graphCanvasApp];
await servePlugin({ serverInfo: Object.freeze({ name: PLUGIN_NAME, version: packageInfo.version }), apps });
