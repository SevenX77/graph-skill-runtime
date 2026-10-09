// Optional real Codex connection check; no model request or GUI claim.
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const child = spawn("codex", ["app-server", "--stdio"], { shell: false, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
const pending = new Map();
const transcript = [];
let nextId = 1;
let errors = "";
child.stderr.on("data", (chunk) => { errors += chunk; });
const lines = createInterface({ input: child.stdout });
lines.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.id !== undefined && pending.has(message.id)) {
    const { resolve, reject, timer } = pending.get(message.id);
    pending.delete(message.id);
    clearTimeout(timer);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  }
});
function request(method, params) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    // A bounded diagnostic wait, not a product support verdict.
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`No response within 60s: ${method}`)); }, 60000);
    pending.set(id, { resolve, reject, timer });
    child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
  });
}
try {
  const init = await request("initialize", { clientInfo: { name: "graph_canvas_probe", version: "0.0.1" }, capabilities: { experimentalApi: true } });
  transcript.push({ initialize: init });
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method: "initialized", params: {} })}\n`);
  let cursor;
  let target;
  do {
    const response = await request("mcpServerStatus/list", { limit: 100, ...(cursor ? { cursor } : {}) });
    target = response.data.find((server) => server.name === "graph-skill-canvas");
    cursor = response.nextCursor;
  } while (!target && cursor);
  if (!target) throw new Error("Codex did not discover graph-skill-canvas");
  transcript.push({ server: target });
  const resource = await request("mcpServer/resource/read", { server: "graph-skill-canvas", uri: "ui://graph-skill/canvas-v2.html" });
  const content = resource.contents[0];
  transcript.push({ resource: { uri: content.uri, mimeType: content.mimeType, bytes: Buffer.byteLength(content.text), sha256: createHash("sha256").update(content.text).digest("hex") } });
  const cwds = [fileURLToPath(new URL("../../../", import.meta.url))];
  const hooks = await request("hooks/list", { cwds });
  transcript.push({ hooks: hooks.data.map(entry => ({ cwd: entry.cwd, inventory: entry.hooks.map(hook => ({ eventName: hook.eventName, sourcePath: hook.sourcePath, pluginId: hook.pluginId, trustStatus: hook.trustStatus })), hooks: entry.hooks.filter(hook => JSON.stringify(hook).includes("graph-skill-canvas")), errors: entry.errors.filter(error => JSON.stringify(error).includes("graph-skill")), warnings: entry.warnings.filter(warning => warning.includes("graph-skill")) })) });
  const skills = await request("skills/list", { cwds, forceReload: true });
  transcript.push({ skills: skills.data.map(entry => ({ cwd: entry.cwd, skills: entry.skills.filter(skill => JSON.stringify(skill).includes("graph-skill-canvas")), errors: entry.errors.filter(error => JSON.stringify(error).includes("graph-skill")) })) });
  console.log(JSON.stringify(transcript, null, 2));
} catch (error) {
  transcript.push({ error: error.message });
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await mkdir(new URL("../evidence/", import.meta.url), { recursive: true });
  await writeFile(new URL("../evidence/codex-connection-v2.json", import.meta.url), JSON.stringify(transcript, null, 2));
  child.stdin.end();
  const cleanup = setTimeout(() => child.kill(), 5000);
  await new Promise((resolve) => child.once("exit", resolve));
  clearTimeout(cleanup);
  await writeFile(new URL("../evidence/codex-connection-v2.stderr.txt", import.meta.url), errors);
  lines.close();
}
