import { randomBytes } from "node:crypto";

// Graph credentials authorize selected roots only. They carry no host action
// authority. MCP App and HTTP preview use this same direct HTTP/SSE backend.
export function createGraphBackend({ http, source }) {
  if (!source) throw new Error("Graph backend needs a live graph source.");
  const credentials = new Map(), streams = new Set();
  let closed = false;
  http.mount(path => path === "/graph/events", (request, response, url) => {
    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", "Authorization");
    response.setHeader("Cross-Origin-Resource-Policy", "cross-origin");
    if (request.headers["access-control-request-private-network"] === "true") response.setHeader("Access-Control-Allow-Private-Network", "true");
    const send = (code, error) => response.writeHead(code).end(JSON.stringify({ error }));
    if (request.method === "OPTIONS") { response.writeHead(204).end(); return; }
    if (request.method !== "GET") return send(405, "Expected GET.");
    const credential = credentials.get(request.headers.authorization?.replace(/^Bearer /, ""));
    if (!credential) return send(401, "Unknown graph connection.");
    const selected = url.searchParams.has("root") ? url.searchParams.get("root") : null;
    if (!credential.roots.has(selected)) return send(403, "This graph connection has not selected that Skill.");
    response.setHeader("Content-Type", "text/event-stream; charset=utf-8");
    response.setHeader("Connection", "keep-alive");
    response.writeHead(200);
    response.flushHeaders();
    const stream = { response, credential };
    streams.add(stream);
    const unsubscribe = source.subscribe(credential.roots.get(selected), event => {
      if (response.destroyed) return;
      if (response.writableLength > 8 * 1024 * 1024) { response.destroy(); return; }
      try { response.write(`data: ${JSON.stringify(event)}\n\n`); }
      catch { response.destroy(); }
    });
    const heartbeat = setInterval(() => { if (!response.destroyed) response.write(": heartbeat\n\n"); }, 15000);
    response.once("close", () => { clearInterval(heartbeat); unsubscribe(); streams.delete(stream); });
  });
  return {
    createConnection() {
      if (closed || !http.origin) throw new Error("Open the local backend before creating a graph connection.");
      const token = randomBytes(32).toString("hex");
      const credential = { roots: new Map() };
      credentials.set(token, credential);
      return {
        descriptor: Object.freeze({ url: http.origin, token }),
        select(requestedRoot, actualRoot = requestedRoot) { credential.roots.set(requestedRoot, actualRoot); credential.roots.set(actualRoot, actualRoot); },
        close() {
          credentials.delete(token);
          for (const stream of streams) if (stream.credential === credential) stream.response.end();
        },
      };
    },
    close() {
      closed = true;
      credentials.clear();
      for (const { response } of streams) response.end();
      source.close();
    },
  };
}
