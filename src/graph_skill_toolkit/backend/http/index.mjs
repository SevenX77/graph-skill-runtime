import { createServer } from "node:http";

// One loopback listener for the App. Route owners retain their own credentials,
// origin rules and lifecycle; this module owns sockets and listener shutdown.
export function createLocalHttpServer() {
  const routes = [];
  let server, origin, opening, closing, closed = false;
  return {
    get origin() { return origin; },
    mount(matches, handle) {
      if (closed) throw new Error("Local backend is closed.");
      routes.push({ matches, handle });
    },
    async open() {
      if (closed) throw new Error("Local backend is closed.");
      return opening ??= new Promise((resolve, reject) => {
        server = createServer((request, response) => {
          response.setHeader("Cache-Control", "no-store");
          response.setHeader("Content-Type", "application/json; charset=utf-8");
          response.setHeader("X-Content-Type-Options", "nosniff");
          response.setHeader("Referrer-Policy", "no-referrer");
          if (request.headers.host !== new URL(origin).host) {
            response.writeHead(403).end(JSON.stringify({ error: "Invalid loopback host." }));
            return;
          }
          const url = new URL(request.url, origin);
          const route = routes.find(candidate => candidate.matches(url.pathname));
          if (!route) { response.writeHead(404).end(JSON.stringify({ error: "Unknown backend route." })); return; }
          void Promise.resolve().then(() => route.handle(request, response, url)).catch(() => response.destroy());
        });
        server.once("error", reject);
        server.listen(0, "127.0.0.1", () => {
          origin = `http://127.0.0.1:${server.address().port}`;
          resolve(origin);
        });
      });
    },
    close() {
      return closing ??= (async () => {
        closed = true;
        if (opening) await opening;
        if (server?.listening) await new Promise(resolve => { server.close(resolve); server.closeAllConnections(); });
      })();
    },
  };
}
