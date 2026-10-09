#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const state = process.platform === "win32"
  ? join(process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local"), "GraphSkill")
  : join(homedir(), ".local", "share", "graph-skill");
const lifecycle = new Set(["install", "update", "uninstall", "status", "cleanup"]);
const version = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).version;

function installed() {
  try {
    const value = JSON.parse(readFileSync(join(state, "install.json"), "utf8"));
    if (value.schema !== "graph-skill.toolkit-install.v1" || !/^\d+\.\d+\.\d+-[a-f0-9]{16}$/.test(value.release)) {
      throw new Error("Invalid toolkit installation manifest");
    }
    return value;
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function packagedPython(source) {
  const bundle = JSON.parse(readFileSync(join(source, "bundle.json"), "utf8"));
  const target = `${process.platform}-${process.arch}`;
  if (bundle.schema !== "graph-skill.toolkit-bundle.v2" || bundle.target !== target) {
    throw new Error(`Use the ${target} Graph Skill archive. This directory is not a matching v2 bundle.`);
  }
  return join(source, "runtimes", "python", process.platform === "win32" ? "python.exe" : "bin/python3");
}

function run(command, args) {
  const environment = { ...process.env };
  delete environment.NODE_OPTIONS;
  delete environment.NODE_PATH;
  const result = spawnSync(command, args, {
    stdio: "inherit", windowsHide: true,
    env: environment,
  });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
}

try {
  if (Number(process.versions.node.split(".")[0]) < 18) throw new Error("The npm installer requires Node.js 18 or later. Alternatively, use the complete platform ZIP.");
  const [operation, ...args] = process.argv.slice(2);
  if (!operation || operation === "--help" || operation === "help") {
    console.log(`Graph Skill toolkit

  graph-skill install [BUNDLE_DIR] [--targets codex,claude] [--dry-run]
  graph-skill update [BUNDLE_DIR] [--targets codex,claude] [--dry-run]
  graph-skill status
  graph-skill uninstall [--dry-run]
  graph-skill cleanup [--dry-run]
  graph-skill <runtime command> [arguments]
  gskill <runtime command> [arguments]

Install uses the default user profiles of Codex and Claude Code Desktop.
Business operations use the independently packaged gskill runtime.
Node.js and Python are included in the platform archive.
The npm entry downloads the matching archive. Update without a directory downloads the newest toolkit release.
Cleanup removes verified inactive release caches; close/restart hosts first.
See the packaged README for installation and manual Desktop acceptance.`);
  } else if (operation === "--version") {
    console.log(version);
  } else if (lifecycle.has(operation)) {
    const explicitSource = args[0] && !args[0].startsWith("--") ? resolve(args[0]) : null;
    const hasBundle = existsSync(join(root, "bundle.json"));
    const online = !explicitSource && (operation === "update" || (operation === "install" && !hasBundle));
    if (online) {
      const { installRelease } = await import("../dist/installer.mjs");
      await installRelease({ version, latest: operation === "update", args, run });
    } else {
    // Run the incoming bundle's installer for an update, so lifecycle fixes
    // ship with the new release rather than depending on the old installation.
      const source = explicitSource || root;
      const tail = explicitSource ? args.slice(1) : args;
      let installerRoot = (operation === "install" || operation === "update") ? source : hasBundle ? root : null;
      if (!installerRoot) {
        const manifest = installed();
        if (manifest) installerRoot = join(state, "versions", manifest.release);
        else if (operation === "cleanup" && existsSync(join(state, "versions"))) {
          const candidates = readdirSync(join(state, "versions"), { withFileTypes: true })
            .filter(entry => entry.isDirectory() && /^\d+\.\d+\.\d+-[a-f0-9]{16}$/.test(entry.name))
            .map(entry => join(state, "versions", entry.name))
            .filter(path => {
              try {
                const raw = readFileSync(join(path, "bundle.json"));
                const bundle = JSON.parse(raw), ready = JSON.parse(readFileSync(join(path, "ready.json"), "utf8"));
                return bundle.schema === "graph-skill.toolkit-bundle.v2" && ready.schema === "graph-skill.toolkit-ready.v1" &&
                  ready.bundle_sha256 === createHash("sha256").update(raw).digest("hex");
              } catch { return false; }
            });
          const { compareVersions } = await import("../dist/installer.mjs");
          candidates.sort((a, b) => compareVersions(
            a.split(/[\\/]/).at(-1).split("-")[0], b.split(/[\\/]/).at(-1).split("-")[0]));
          installerRoot = candidates.at(-1);
        }
      }
      if (!installerRoot) console.log(JSON.stringify({ status: "not-installed", state_root: state }));
      else {
        const script = join(installerRoot, "packaging", "entry.py");
        run(packagedPython(installerRoot), ["-I", "-B", "-X", "utf8", script, operation, source, ...tail]);
      }
    }
  } else {
    const manifest = installed();
    if (!manifest) throw new Error("Toolkit is not installed. Extract a release archive and run its install.cmd or install.sh.");
    const executable = join(state, "versions", manifest.release, "runtimes", "python", process.platform === "win32" ? "python.exe" : "bin/python3");
    run(executable, ["-I", "-B", "-X", "utf8", "-m", "graph_skill_runtime", operation, ...args]);
  }
} catch (error) {
  console.error(`Graph Skill: ${error.message}`);
  process.exitCode = 1;
}
