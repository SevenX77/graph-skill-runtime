import { execFileSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const repository = resolve(root, "../..");
const output = join(root, "release");
const git = (...args) => execFileSync("git", args, { cwd: repository, encoding: "utf8" }).trim();
if (git("status", "--porcelain", "--untracked-files=normal")) throw new Error("Commit source before packaging the npm installer");
const commit = git("rev-parse", "HEAD");
const { version } = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
const metadata = JSON.parse(await readFile(join(root, "npm/package.json"), "utf8"));
await mkdir(output, { recursive: true });
const stage = await mkdtemp(join(output, "npm-stage-"));
try {
  for (const [source, target] of [
    ["bin/graph-skill.mjs", "bin/graph-skill.mjs"], ["dist/installer.mjs", "dist/installer.mjs"],
    ["npm/README.md", "README.md"], ["../../LICENSE", "LICENSE"],
  ]) {
    await mkdir(dirname(join(stage, target)), { recursive: true });
    await cp(join(root, source), join(stage, target));
  }
  const names = ["yauzl", "pend"];
  let notices = "Bundled npm installer dependencies\n";
  for (const name of names) {
    const directory = join(root, "node_modules", name);
    notices += `\n--- ${name} ---\n` + await readFile(join(directory, "LICENSE"), "utf8");
  }
  await writeFile(join(stage, "THIRD_PARTY_NOTICES.txt"), notices);
  await writeFile(join(stage, "package.json"), JSON.stringify({ ...metadata, version, sourceCommit: commit }, null, 2) + "\n");
  if (!process.env.npm_execpath) throw new Error("Run through npm run pack:installer");
  const result = JSON.parse(execFileSync(process.execPath,
    [process.env.npm_execpath, "pack", "--json", "--pack-destination", output], { cwd: stage, encoding: "utf8" }));
  if (git("rev-parse", "HEAD") !== commit || git("status", "--porcelain", "--untracked-files=normal")) throw new Error("Source changed during npm packaging");
  console.log(JSON.stringify({ source_commit: commit, ...result[0] }, null, 2));
} finally {
  if (dirname(resolve(stage)) !== resolve(output)) throw new Error("Invalid npm staging cleanup root");
  await rm(stage, { recursive: true, force: true });
}
