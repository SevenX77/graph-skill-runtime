import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

test("uninstalled bootstrap delegates lifecycle to the installed payload owner", async t => {
  const home = await mkdtemp(join(tmpdir(), "toolkit owner "));
  t.after(() => rm(home, { recursive: true, force: true }));
  const state = join(home, ".local", "share", "graph-skill");
  const release = "0.3.3-aaaaaaaaaaaaaaaa";
  const payload = join(state, "versions", release);
  await mkdir(join(payload, "bin"), { recursive: true });
  await writeFile(join(state, "install.json"), JSON.stringify({
    schema: "graph-skill.toolkit-install.v1", release,
  }));
  await writeFile(join(payload, "bin", "graph-skill.mjs"),
    'console.log(JSON.stringify({owner:"installed-payload",args:process.argv.slice(2)}));');
  const entry = fileURLToPath(new URL("../bin/graph-skill.mjs", import.meta.url));
  for (const args of [["status", "--json"], ["detect"], ["cleanup", "--dry-run"]]) {
    const result = spawnSync(process.execPath, [entry, ...args], {
      cwd: home, encoding: "utf8", windowsHide: true,
      env: { ...process.env, HOME: home, USERPROFILE: home },
    });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), { owner: "installed-payload", args });
  }
});
