// An explicit local test host. Production plugin startup exposes only stdio.
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const root = fileURLToPath(new URL("../", import.meta.url));
const client = new Client({ name: "graph-canvas-preview", version: "0.0.1" });
let result, html;
try {
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(new URL("../dist/server.mjs", import.meta.url))] }));
  result = await client.callTool({ name: "show_graph", arguments: process.argv[2] ? { skill_root: process.argv[2] } : {} });
  const resource = await client.readResource({ uri: "ui://graph-skill/canvas-v2.html" });
  html = resource.contents[0].text;
} finally {
  await client.close();
}
const host = await build({ absWorkingDir: root, entryPoints: ["tests/host.mjs"], bundle: true, platform: "browser", format: "esm", target: "es2022", write: false });
const routes = new Map([
  ["/", ["text/html", '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Graph Skill · MCP App test host</title><style>html,body{margin:0;width:100%;height:100%;background:#f6f7f9}iframe{display:block;border:0;width:100%;height:100dvh}</style></head><body><iframe title="Graph Skill canvas" sandbox="allow-scripts allow-same-origin"></iframe><script type="module" src="/host.js"></script></body></html>']],
  ["/host.js", ["text/javascript", host.outputFiles[0].text]],
  ["/canvas.html", ["text/html", html]],
  ["/tool-result.json", ["application/json", JSON.stringify(result)]],
]);
const server = createServer((request, response) => {
  const route = routes.get(new URL(request.url, "http://127.0.0.1").pathname);
  if (request.method !== "GET" || !route) { response.writeHead(404).end(); return; }
  response.writeHead(200, { "Content-Type": `${route[0]}; charset=utf-8`, "Cache-Control": "no-store" });
  response.end(route[1]);
});
server.listen(0, "127.0.0.1", () => console.log(`Test host: http://127.0.0.1:${server.address().port}`));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close());
