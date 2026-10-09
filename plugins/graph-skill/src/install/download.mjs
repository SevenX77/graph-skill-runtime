import { createHash } from "node:crypto";
import { createWriteStream } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { extractArchive } from "./archive.mjs";

const repository = "SevenX77/graph-skill-runtime";
const api = `https://api.github.com/repos/${repository}/releases`;
export const targets = ["win32-x64", "darwin-arm64", "linux-x64", "linux-arm64"];

export function platformTarget(platform = process.platform, arch = process.arch) {
  const value = `${platform}-${arch}`;
  if (!targets.includes(value)) throw new Error(`No prebuilt Graph Skill package for ${value}. See the source-development instructions.`);
  return value;
}

export function compareVersions(a, b) {
  const left = a.split(".").map(Number), right = b.split(".").map(Number);
  for (let index = 0; index < 3; index++) if (left[index] !== right[index]) return left[index] - right[index];
  return 0;
}

export function releaseAssets(release, version, target) {
  if (release.draft || release.tag_name !== `graph-skill-toolkit-v${version}`) throw new Error("Unexpected toolkit release identity");
  const prefix = `graph-skill-${version}-${target}`;
  const select = name => {
    const matches = release.assets.filter(asset => asset.name === name);
    const expected = `https://github.com/${repository}/releases/download/${release.tag_name}/${name}`;
    if (matches.length !== 1 || matches[0].browser_download_url !== expected ||
        !Number.isSafeInteger(matches[0].size) || matches[0].size <= 0) throw new Error(`Missing or invalid release asset: ${name}`);
    return matches[0];
  };
  return { prefix, archive: select(prefix + ".zip"), checksums: select("SHA256SUMS.txt") };
}

export function checksumFor(text, filename) {
  const entries = text.split(/\r?\n/).map(line => /^([a-f0-9]{64})\s+\*?(.+)$/.exec(line)).filter(Boolean);
  const matches = entries.filter(entry => entry[2] === filename);
  if (matches.length !== 1) throw new Error(`Missing or duplicate checksum for ${filename}`);
  return matches[0][1];
}

async function request(url) {
  const response = await fetch(url, { headers: { "User-Agent": "graph-skill-installer", Accept: "application/vnd.github+json" } });
  if (!response.ok || !response.url.startsWith("https://")) throw new Error(`Release download failed: HTTP ${response.status} (${url})`);
  return response;
}

async function releaseFor(version, latest) {
  if (!latest) return { version, release: await (await request(`${api}/tags/graph-skill-toolkit-v${version}`)).json() };
  const candidates = [];
  let page = 1;
  while (true) {
    const response = await request(`${api}?per_page=100&page=${page++}`);
    for (const release of await response.json()) {
      const match = /^graph-skill-toolkit-v(\d+\.\d+\.\d+)$/.exec(release.tag_name);
      if (match && !release.draft) candidates.push({ version: match[1], release });
    }
    if (!response.headers.get("link")?.includes('rel="next"')) break;
  }
  candidates.sort((a, b) => compareVersions(b.version, a.version));
  if (!candidates.length) throw new Error("No published Graph Skill toolkit release found");
  if (compareVersions(candidates[0].version, version) < 0) throw new Error("Published release is older than this installer; refusing an automatic downgrade");
  return candidates[0];
}

async function download(asset, destination, expectedHash) {
  const response = await request(asset.browser_download_url);
  const hash = createHash("sha256");
  let bytes = 0;
  const observe = new Transform({ transform(chunk, encoding, done) {
    bytes += chunk.length;
    if (bytes > asset.size) return done(new Error("Download exceeds the release asset's recorded size"));
    hash.update(chunk); done(null, chunk);
  } });
  await pipeline(Readable.fromWeb(response.body), observe, createWriteStream(destination, { flags: "wx" }));
  if (bytes !== asset.size || (expectedHash && hash.digest("hex") !== expectedHash)) throw new Error(`Release checksum or size mismatch: ${asset.name}`);
}

export async function installRelease({ version, latest, args, run }) {
  const target = platformTarget();
  const selected = await releaseFor(version, latest);
  const assets = releaseAssets(selected.release, selected.version, target);
  const temporary = await mkdtemp(join(tmpdir(), "graph-skill-download-"));
  try {
    console.error(`Downloading Graph Skill ${selected.version} for ${target}...`);
    const checksumPath = join(temporary, "SHA256SUMS.txt"), archive = join(temporary, assets.archive.name);
    await download(assets.checksums, checksumPath);
    const expected = checksumFor(await readFile(checksumPath, "utf8"), assets.archive.name);
    await download(assets.archive, archive, expected);
    await extractArchive(archive, temporary, assets.prefix);
    const payload = join(temporary, assets.prefix);
    const bundle = JSON.parse(await readFile(join(payload, "bundle.json"), "utf8"));
    if (bundle.version !== selected.version || bundle.target !== target || bundle.schema !== "graph-skill.toolkit-bundle.v2") throw new Error("Downloaded bundle identity mismatch");
    const node = join(payload, "runtimes/node", process.platform === "win32" ? "node.exe" : "bin/node");
    run(node, [join(payload, "bin/graph-skill.mjs"), "install", payload, ...args]);
  } finally {
    // Only remove the fresh directory returned by this invocation's mkdtemp.
    if (dirname(resolve(temporary)) !== resolve(tmpdir()) || !temporary.split(/[\\/]/).at(-1).startsWith("graph-skill-download-")) throw new Error("Invalid installer cleanup root");
    await rm(temporary, { recursive: true, force: true });
  }
}
