import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, realpath, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { prepareLab } from "../../apps/interface_lab/server/state.mjs";

test("the lab reports the real paths of its state directory", async t => {
  const root = await mkdtemp(join(tmpdir(), "interface lab 中文 "));
  t.after(() => rm(root, { recursive: true, force: true }));
  const real = join(root, "real");
  await mkdir(real);
  const alias = join(root, "alias");
  await symlink(real, alias, process.platform === "win32" ? "junction" : "dir");
  const lab = await prepareLab(alias);
  const expected = await realpath(real);
  assert.deepEqual(lab, { stateDirectory: expected, sandbox: join(expected, "sandbox"), records: join(expected, "records"), sampleFile: join(expected, "sandbox", "sample.txt") });
});
