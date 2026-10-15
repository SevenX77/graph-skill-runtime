import { mkdir, realpath, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

/** The lab's own state directory: comparison records and the sandbox the local
 * capability tests read, write, watch and reveal. */
export function labStateDirectory({ platform = process.platform, env = process.env, home = homedir() } = {}) {
  if (platform === "win32") return join(env.LOCALAPPDATA || join(home, "AppData", "Local"), "plugin-interface-lab");
  if (platform === "darwin") return join(home, "Library", "Application Support", "plugin-interface-lab");
  return join(env.XDG_STATE_HOME || join(home, ".local", "state"), "plugin-interface-lab");
}

export async function prepareLab(nominalDirectory) {
  await mkdir(nominalDirectory, { recursive: true });
  // Report real paths: a Windows packaged host redirects writes under %LOCALAPPDATA%,
  // and the developer and the file manager must see where the files actually are.
  const stateDirectory = await realpath(nominalDirectory);
  const sandbox = join(stateDirectory, "sandbox"), records = join(stateDirectory, "records");
  await mkdir(sandbox, { recursive: true });
  await mkdir(records, { recursive: true });
  const sampleFile = join(sandbox, "sample.txt");
  await writeFile(sampleFile, "Plugin Interface Lab sample file.\n接口测试样例文件。\n", { flag: "wx" }).catch(error => { if (error.code !== "EEXIST") throw error; });
  return { stateDirectory, sandbox, records, sampleFile };
}
