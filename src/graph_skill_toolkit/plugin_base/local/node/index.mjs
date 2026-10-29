import { createHash, randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { lstat, readFile, realpath, rename, stat, unlink, writeFile } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { LOCAL_LIMITS, LOCAL_TRANSPORT_OPERATIONS, validateLocalArguments } from "../definitions.mjs";

const EVENT_LIMIT = 500, WATCH_LIMIT = 16;
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const result = (status, message, evidence, data) => ({ status, message, ...(data === undefined ? {} : { data }), evidence: { limits: [], ...evidence } });
const POLL_LIMIT = pollMs => `变化通过每 ${pollMs} 毫秒比较文件是否存在、大小和修改时间发现；同一间隔内的多次保存合并为一次事件。`;
const LAUNCH_LIMIT = "操作系统只报告进程是否启动，不报告窗口是否真的出现；请在系统中观察实际效果。";

/** Shell-free launch of a system program. Resolves once the program exits or
 * three seconds after it started, whichever is first. */
function launch(spawnProcess, command, args, options = {}) {
  return new Promise(done => {
    let settled = false, timer;
    const finish = value => { if (settled) return; settled = true; clearTimeout(timer); done(value); };
    let child;
    try { child = spawnProcess(command, args, { stdio: "ignore", shell: false, detached: true, windowsHide: false, ...options }); }
    catch (error) { finish({ error: error.message }); return; }
    child.once("error", error => finish({ error: error.message }));
    child.once("spawn", () => { timer = setTimeout(() => { child.unref?.(); finish({ pid: child.pid ?? null, exitCode: null }); }, 3000); });
    child.once("exit", code => finish({ pid: child.pid ?? null, exitCode: code }));
  });
}

/** The program and arguments that perform a system action on this platform. */
export function systemCommand(kind, target, { platform = process.platform, env = process.env, isDirectory = false } = {}) {
  if (platform === "win32") {
    const system = env.SystemRoot || env.windir || "C:\\Windows";
    // explorer.exe parses /select only from its raw command line, so the path
    // is quoted here and the arguments are passed verbatim.
    if (kind === "reveal") return { command: system + "\\explorer.exe", args: [`/select,"${target.replaceAll("/", "\\")}"`], options: { windowsVerbatimArguments: true } };
    return { command: system + "\\System32\\rundll32.exe", args: ["url.dll,FileProtocolHandler", target], options: {} };
  }
  if (platform === "darwin") return { command: "/usr/bin/open", args: kind === "reveal" ? ["-R", target] : [target], options: {} };
  return { command: "xdg-open", args: [kind === "reveal" && !isDirectory ? dirname(target) : target], options: {} };
}

/** Local capabilities for one plugin process. Every page connection receives
 * its own credential, its own allowed roots and its own event queue.
 * @param {{http?: any, platform?: string, env?: Record<string, string|undefined>, spawnProcess?: typeof spawn, pollMs?: number, realpathOf?: (path: string) => Promise<string>}} [options]
 */
export function createLocalCapabilities({ http, platform = process.platform, env = process.env, spawnProcess = spawn, pollMs = 300, realpathOf = realpath } = {}) {
  const tokens = new Map();
  let closed = false;
  const fold = value => platform === "win32" || platform === "darwin" ? value.toLowerCase() : value;

  http?.mount(path => path === "/local/call" || path === "/local/events", async (request, response, url) => {
    response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
    const send = (code, data) => { if (!response.destroyed) response.writeHead(code).end(JSON.stringify(data)); };
    if (request.headers.origin && request.headers.origin !== http.origin) return send(403, { error: "Cross-origin requests are not accepted." });
    const connection = tokens.get(request.headers.authorization?.replace(/^Bearer /, ""));
    if (!connection) return send(401, { error: "Unknown local capability credential." });
    try {
      if (request.method === "POST" && url.pathname === "/local/call") {
        const chunks = []; let length = 0;
        for await (const chunk of request) {
          length += chunk.length;
          if (length > 3 * 1024 * 1024) throw new Error("Local capability request exceeds 3 MiB.");
          chunks.push(chunk);
        }
        const input = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
        return send(200, await connection.call(input.operation, input.args ?? {}));
      }
      if (request.method === "GET" && url.pathname === "/local/events") {
        const after = Number(url.searchParams.get("after") ?? 0), timeout = Number(url.searchParams.get("timeout_ms") ?? 20000);
        const controller = new AbortController();
        response.once("close", () => controller.abort());
        return send(200, await connection.wait(after, timeout, controller.signal));
      }
      send(405, { error: "Unsupported local capability route." });
    } catch (error) { send(400, { error: error.message }); }
  });

  function createConnection() {
    if (closed) throw new Error("Local capabilities are closed.");
    const token = randomBytes(32).toString("hex");
    const roots = [], events = [], waiters = new Set(), watches = new Map();
    let seq = 0, watchSeq = 0, ended = false;

    const under = (path, root) => path === root || path.startsWith(root.endsWith(sep) ? root : root + sep);
    /** True when no component between the granted root and the target is a link. */
    async function linkFree(root, rel) {
      let current = root;
      for (const part of rel.split(sep)) {
        current = join(current, part);
        if ((await lstat(current)).isSymbolicLink()) return false;
      }
      return true;
    }
    async function within(target) {
      const real = fold(await realpathOf(target));
      if (roots.some(root => under(real, root.real))) return true;
      // A packaged Windows host redirects a file's real location into its own
      // storage while the file's directories still resolve to their nominal
      // paths. The nominal path then decides, provided no link component lies
      // between the granted root and the target.
      const nominal = resolve(target);
      for (const root of roots) {
        const rel = relative(root.nominal, nominal);
        if (rel === "" || rel === ".." || rel.startsWith(".." + sep) || isAbsolute(rel)) continue;
        if (await linkFree(root.nominal, rel)) return true;
      }
      return false;
    }
    /** The scope check for a path that may not exist yet: its directory decides. */
    async function parentWithin(target) {
      try { return await within(target); }
      catch (error) { if (error.code !== "ENOENT") throw error; }
      return within(dirname(target));
    }
    function emit(type, data) {
      events.push({ seq: ++seq, type, at: new Date().toISOString(), data });
      if (events.length > EVENT_LIMIT) events.splice(0, events.length - EVENT_LIMIT);
      for (const wake of [...waiters]) wake();
    }
    const outside = (sent, path) => result("rejected", `路径不在此插件授权的目录内：${path}`, { sent, observed: { allowedRoots: roots.map(root => root.real) } });

    async function read(args) {
      const sent = { ...args };
      if (!await parentWithin(args.path)) return outside(sent, args.path);
      const real = await realpath(args.path), info = await stat(real);
      if (!info.isFile()) return result("rejected", "目标不是文件。", { sent });
      const max = args.maxBytes ?? 1024 * 1024;
      if (info.size > max) return result("rejected", `文件有 ${info.size} 字节，超过本次读取上限 ${max} 字节。`, { sent, observed: { size: info.size } });
      const bytes = await readFile(real);
      let content;
      if (args.encoding === "base64") content = bytes.toString("base64");
      else {
        try { content = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
        catch { return result("rejected", "文件不是有效的 UTF-8 文本；请用 base64 编码读取。", { sent, observed: { size: bytes.length } }); }
      }
      return result("completed", `已读取 ${bytes.length} 字节。`, { sent, receipt: { bytes: bytes.length }, observed: { path: real, size: info.size, mtimeMs: info.mtimeMs, sha256: sha256(bytes) } },
        { path: real, encoding: args.encoding ?? "utf8", content, size: bytes.length, mtimeMs: info.mtimeMs });
    }

    async function write(args) {
      const bytes = Buffer.from(args.content, args.encoding === "base64" ? "base64" : "utf8");
      const sent = { path: args.path, encoding: args.encoding ?? "utf8", bytes: bytes.length, sha256: sha256(bytes) };
      if (bytes.length > LOCAL_LIMITS.writeBytes) return result("rejected", "写入内容超过 1 MiB。", { sent });
      if (!await parentWithin(args.path)) return outside(sent, args.path);
      let target = resolve(args.path), created = false;
      try { target = await realpath(target); } catch (error) { if (error.code !== "ENOENT") throw error; created = true; }
      // Atomic replacement: a sibling temporary file is renamed over the target,
      // so a reader sees either the previous bytes or the new bytes.
      const temporary = join(dirname(target), `.${basename(target)}.${randomBytes(6).toString("hex")}.tmp`);
      try {
        await writeFile(temporary, bytes, { flag: "wx" });
        await rename(temporary, target);
      } catch (error) { await unlink(temporary).catch(() => {}); throw error; }
      const back = await readFile(target), info = await stat(target);
      const observed = { path: target, size: info.size, mtimeMs: info.mtimeMs, sha256: sha256(back), matchesSent: sha256(back) === sent.sha256 };
      return result("completed", `${created ? "已创建" : "已替换"}文件，写入 ${bytes.length} 字节。`, { sent, receipt: { replacedBy: "rename", temporary: basename(temporary) }, observed },
        { path: target, bytes: bytes.length, created });
    }

    async function snapshotOf(path) {
      try { const info = await stat(path); return { exists: true, size: info.size, mtimeMs: info.mtimeMs }; }
      catch (error) { if (error.code === "ENOENT" || error.code === "ENOTDIR") return { exists: false, size: null, mtimeMs: null }; throw error; }
    }

    async function watch(args) {
      const sent = { ...args };
      if (watches.size >= WATCH_LIMIT) return result("rejected", `每个页面连接最多同时监听 ${WATCH_LIMIT} 组文件。`, { sent });
      const paths = [...new Set(args.paths.map(path => resolve(path)))];
      for (const path of paths) if (!await parentWithin(path)) return outside(sent, path);
      const watchId = "w-" + (++watchSeq);
      const states = new Map();
      for (const path of paths) states.set(path, await snapshotOf(path));
      let checking = false;
      const timer = setInterval(async () => {
        if (checking) return;
        checking = true;
        try {
          for (const path of paths) {
            const before = states.get(path), after = await snapshotOf(path).catch(() => before);
            if (before.exists === after.exists && before.size === after.size && before.mtimeMs === after.mtimeMs) continue;
            states.set(path, after);
            emit("local.files.changed", { watchId, path, change: !before.exists ? "created" : !after.exists ? "deleted" : "modified", size: after.size, mtimeMs: after.mtimeMs });
          }
        } finally { checking = false; }
      }, pollMs);
      timer.unref?.();
      watches.set(watchId, timer);
      const initial = paths.map(path => ({ path, ...states.get(path) }));
      return result("completed", `正在监听 ${paths.length} 个路径；变化以 local.files.changed 事件送达。`,
        { sent, receipt: { watchId }, observed: { initial }, limits: [POLL_LIMIT(pollMs)] }, { watchId, paths, initial });
    }

    function unwatch(args) {
      const timer = watches.get(args.watchId);
      if (!timer) return result("rejected", "没有这个监听。", { sent: { ...args } });
      clearInterval(timer); watches.delete(args.watchId);
      return result("completed", "已停止监听。", { sent: { ...args }, observed: { activeWatches: watches.size } });
    }

    async function system(kind, target, sent) {
      let isDirectory = false;
      if (kind === "reveal") {
        if (!await within(target).catch(() => false)) return outside(sent, target);
        // The file manager runs outside this process's filesystem view (for example a
        // Windows packaged host redirects writes under %LOCALAPPDATA%), so it receives the real path.
        target = await realpath(target);
        isDirectory = (await stat(target)).isDirectory();
      }
      const { command, args, options } = systemCommand(kind, target, { platform, env, isDirectory });
      const receipt = await launch(spawnProcess, command, args, options);
      const evidence = { sent: { ...sent, ...(kind === "reveal" && target !== sent.path ? { realPath: target } : {}), command, args }, receipt, observed: { launched: !receipt.error }, limits: [LAUNCH_LIMIT,
        ...(kind === "reveal" && platform === "win32" ? ["资源管理器的退出码不表示成败（通常为 1）；以系统窗口是否选中目标为准。"] : []),
        ...(kind === "reveal" && platform !== "win32" && platform !== "darwin" ? ["Linux 打开所在目录，不能选中文件本身。"] : [])] };
      if (receipt.error) return result("error", "系统程序未能启动：" + receipt.error, evidence);
      return result("accepted", kind === "reveal" ? "已请求系统文件管理器定位该路径。" : "已请求系统默认浏览器打开网址。", evidence);
    }

    async function call(operation, input) {
      if (ended) return result("error", "本地能力连接已关闭。", { sent: { operation } });
      if (!LOCAL_TRANSPORT_OPERATIONS.includes(operation)) return result("error", "未知的本地能力。", { sent: { operation } });
      let args;
      try { args = validateLocalArguments(operation, input); }
      catch (error) { return result("error", error.message, { sent: input }); }
      try {
        switch (operation) {
          case "local.files.read": return await read(args);
          case "local.files.write": return await write(args);
          case "local.files.watch": return await watch(args);
          case "local.files.unwatch": return unwatch(args);
          case "local.system.openExternal": return await system("open", new URL(args.url).href, args);
          default: return await system("reveal", resolve(args.path), args);
        }
      } catch (error) {
        return result(error.code === "ENOENT" ? "rejected" : "error", error.code === "ENOENT" ? "路径不存在：" + (args.path ?? "") : error.message, { sent: args });
      }
    }

    function wait(after, timeoutMs = 20000, signal) {
      if (!Number.isSafeInteger(after) || after < 0) throw new Error("Invalid event cursor.");
      const answer = () => ({ cursor: seq, events: events.filter(event => event.seq > after), closed: ended });
      if (ended || events.some(event => event.seq > after)) return Promise.resolve(answer());
      return new Promise(done => {
        const finish = () => { clearTimeout(timer); waiters.delete(finish); signal?.removeEventListener?.("abort", finish); done(answer()); };
        const timer = setTimeout(finish, Math.max(0, Math.min(timeoutMs, 25000)));
        waiters.add(finish);
        if (signal?.aborted) finish(); else signal?.addEventListener?.("abort", finish, { once: true });
      });
    }

    const connection = {
      descriptor: http ? Object.freeze({ url: http.origin, token }) : null,
      /** Grant this page connection the directory tree under root. */
      async allow(root) {
        const real = fold(await realpath(root));
        if (!roots.some(item => item.real === real)) roots.push({ real, nominal: resolve(root) });
        return real;
      },
      get roots() { return roots.map(root => root.real); },
      call, wait,
      close() {
        ended = true;
        tokens.delete(token);
        for (const timer of watches.values()) clearInterval(timer);
        watches.clear();
        for (const wake of [...waiters]) wake();
      },
    };
    tokens.set(token, connection);
    return connection;
  }

  return {
    createConnection,
    close() { closed = true; for (const connection of [...tokens.values()]) connection.close(); },
  };
}
