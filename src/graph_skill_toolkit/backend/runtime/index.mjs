import { spawn as spawnProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// The runtime owns gSkill validity. This adapter runs its compile command
// shell-free and returns the runtime's own result; it authors no diagnostics.

const RUNTIME_ARGS = ["-I", "-B", "-X", "utf8", "-m", "graph_skill_runtime"];
const OUTPUT_LIMIT = 4 * 1024 * 1024;

/** Runtime argv prefix: an explicit JSON array in GRAPH_SKILL_RUNTIME, else the
 * installed toolkit's bundled Python by the launcher's rule (bin/graph-skill.mjs). */
export function runtimeCommand({ env = process.env, stateRoot = join(homedir(), ".local", "share", "graph-skill"), platform = process.platform, read = readFileSync } = {}) {
  if (env.GRAPH_SKILL_RUNTIME) {
    const value = JSON.parse(env.GRAPH_SKILL_RUNTIME);
    if (!Array.isArray(value) || !value.length || value.some(item => typeof item !== "string" || !item)) throw new Error("GRAPH_SKILL_RUNTIME must be a JSON array of command arguments.");
    return value;
  }
  let manifest;
  try { manifest = JSON.parse(read(join(stateRoot, "install.json"), "utf8")); }
  catch (error) { throw new Error(`Graph Skill runtime is not installed (${error.code === "ENOENT" ? "no install.json" : error.message}).`); }
  if (manifest?.schema !== "graph-skill.toolkit-install.v1" || !/^\d+\.\d+\.\d+-[a-f0-9]{16}$/.test(manifest.release ?? "")) throw new Error("Invalid toolkit installation manifest.");
  const python = join(stateRoot, "versions", manifest.release, "runtimes", "python", platform === "win32" ? "python.exe" : "bin/python3");
  return [python, ...RUNTIME_ARGS];
}

function validDiagnostic(value) {
  return value && typeof value === "object" && typeof value.code === "string" && typeof value.message === "string" && typeof value.severity === "string";
}

/** Parse one `gskill compile` stdout into `{ status, diagnostics }`. */
export function parseCompileResult(stdout, exitCode) {
  let value;
  try { value = JSON.parse(stdout); } catch { throw new Error(`Runtime compile returned unreadable output (exit ${exitCode}).`); }
  if (value?.schema_version !== "gskill.compile-result.v1" || !["passed", "failed"].includes(value.status) || !Array.isArray(value.diagnostics) || !value.diagnostics.every(validDiagnostic)) {
    throw new Error(`Runtime compile returned an unrecognized result (exit ${exitCode}).`);
  }
  if ((value.status === "passed") !== (exitCode === 0)) throw new Error(`Runtime compile status ${value.status} disagrees with exit ${exitCode}.`);
  return { status: value.status, diagnostics: value.diagnostics };
}

/** Compile port: `compile(root) -> Promise<{ status: "passed"|"failed", diagnostics }>`.
 * A runtime that cannot be started, times out or answers outside its contract rejects. */
export function createRuntimeCompiler({ command = () => runtimeCommand(), spawn = spawnProcess, timeoutMs = 30000 } = {}) {
  return {
    compile(root) {
      return new Promise((resolve, reject) => {
        let argv;
        try { argv = [...command(), "compile", "--no-cache", root]; } catch (error) { reject(error); return; }
        const environment = { ...process.env };
        delete environment.NODE_OPTIONS;
        delete environment.NODE_PATH;
        delete environment.GRAPH_SKILL_RUNTIME;
        const child = spawn(argv[0], argv.slice(1), { stdio: ["ignore", "pipe", "pipe"], windowsHide: true, shell: false, env: environment });
        const out = [], err = [];
        let size = 0, settled = false;
        const finish = (error, value) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          if (error) reject(error); else resolve(value);
        };
        const timer = setTimeout(() => { child.kill(); finish(new Error(`Runtime compile exceeded ${timeoutMs} ms.`)); }, timeoutMs);
        const collect = target => chunk => {
          size += chunk.length;
          if (size > OUTPUT_LIMIT) { child.kill(); finish(new Error("Runtime compile output exceeded its limit.")); return; }
          target.push(chunk);
        };
        child.stdout.on("data", collect(out));
        child.stderr.on("data", collect(err));
        child.on("error", error => finish(new Error(`Graph Skill runtime could not start: ${error.message}`)));
        child.on("close", code => {
          if (settled) return;
          const stdout = Buffer.concat(out).toString("utf8");
          if (code !== 0 && code !== 2) {
            const detail = Buffer.concat(err).toString("utf8").trim().split(/\r?\n/).slice(-3).join(" ");
            finish(new Error(`Runtime compile failed with exit ${code}${detail ? `: ${detail}` : "."}`));
            return;
          }
          try { finish(null, parseCompileResult(stdout, code)); } catch (error) { finish(error); }
        });
      });
    },
  };
}
