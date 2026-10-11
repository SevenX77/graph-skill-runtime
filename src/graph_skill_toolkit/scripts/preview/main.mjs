// An explicit local test host. Production plugin startup exposes only stdio.
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const root = fileURLToPath(new URL("../../", import.meta.url));
const client = new Client({ name: "graph-canvas-preview", version: "0.0.1" });
let result, html;
try {
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(new URL("../../dist/server.mjs", import.meta.url))] }));
  result = await client.callTool({ name: "show_graph", arguments: process.argv[2] ? { skill_root: process.argv[2] } : {} });
  const resource = await client.readResource({ uri: "ui://graph-skill/canvas-v2.html" });
  html = resource.contents[0].text;
} catch (error) { await client.close(); throw error; }
const host = await build({ absWorkingDir: root, entryPoints: ["tests/host.mjs"], bundle: true, platform: "browser", format: "esm", target: "es2022", write: false });
const routes = new Map([
  ["/", ["text/html", '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>Graph Skill · MCP App test host</title><style>html,body{margin:0;width:100%;height:100%;background:#f6f7f9;font:13px system-ui}aside{height:38px;padding:9px 16px;background:#342e53;color:white}iframe{display:block;border:0;width:100%;height:calc(100dvh - 38px)}</style></head><body><aside>协议测试宿主 · 图查询连接真实服务；消息和文件请求仅记录，不驱动 Codex 会话</aside><iframe title="Graph Skill canvas" sandbox="allow-scripts allow-same-origin"></iframe><script type="module" src="/host.js"></script></body></html>']],
  ["/host.js", ["text/javascript", host.outputFiles[0].text]],
  ["/canvas.html", ["text/html", html]],
  ["/tool-result.json", ["application/json", JSON.stringify(result)]],
]);
const server = createServer(async (request, response) => {
  if (request.method === "POST" && request.url === "/inspect") {
    if (request.headers.origin !== `http://127.0.0.1:${server.address().port}`) { response.writeHead(403).end(); return; }
    try {
      const value = await client.callTool({ name: "inspect_graph", arguments: { skill_root: result.structuredContent.skillRoot } });
      response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" }).end(JSON.stringify(value));
    } catch (error) { response.writeHead(500).end(JSON.stringify({ error: error.message })); }
    return;
  }
  const route = routes.get(new URL(request.url, "http://127.0.0.1").pathname);
  if (request.method !== "GET" || !route) { response.writeHead(404).end(); return; }
  response.writeHead(200, { "Content-Type": `${route[0]}; charset=utf-8`, "Cache-Control": "no-store" });
  response.end(route[1]);
});
server.listen(0, "127.0.0.1", () => console.log(`Test host: http://127.0.0.1:${server.address().port}`));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, async () => { await client.close(); server.close(); });
