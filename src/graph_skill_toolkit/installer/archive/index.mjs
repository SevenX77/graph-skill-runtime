import { createWriteStream } from "node:fs";
import { chmod, mkdir } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { pipeline } from "node:stream/promises";
import yauzl from "yauzl";

export function memberPath(name, prefix, destination) {
  const parts = name.split("/");
  if (!name.startsWith(prefix + "/") || name.includes("\\") || name.includes("\0") ||
      parts.some(part => part === ".." || part === "." || part.includes(":"))) {
    throw new Error(`Unsafe archive member: ${name}`);
  }
  if (process.platform === "win32" && parts.some(part =>
    /[ .]$/.test(part) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))) {
    throw new Error(`Unsupported Windows archive member: ${name}`);
  }
  const output = resolve(destination, name);
  if (!output.startsWith(resolve(destination) + sep)) throw new Error("Archive path escaped staging");
  return output;
}

// Call only after the complete archive matches its official release checksum.
// The destination is a fresh installer-owned temporary directory, never a user folder.
export async function extractArchive(archive, destination, prefix) {
  const zip = await new Promise((ok, fail) => yauzl.open(archive,
    { lazyEntries: true, strictFileNames: true, validateEntrySizes: true }, (error, value) => error ? fail(error) : ok(value)));
  const seen = new Set();
  await new Promise((ok, fail) => {
    const abort = error => { zip.close(); fail(error); };
    zip.on("error", abort);
    zip.on("end", ok);
    zip.on("entry", entry => {
      (async () => {
        const output = memberPath(entry.fileName, prefix, destination);
        const key = process.platform === "win32" ? output.toLowerCase() : output;
        if (seen.has(key)) throw new Error(`Duplicate archive path: ${entry.fileName}`);
        seen.add(key);
        const mode = entry.externalFileAttributes >>> 16;
        const type = mode & 0o170000;
        const directory = entry.fileName.endsWith("/");
        if (type && type !== (directory ? 0o040000 : 0o100000)) throw new Error("Archive contains a link or special file");
        if (directory) await mkdir(output, { recursive: true });
        else {
          await mkdir(dirname(output), { recursive: true });
          const input = await new Promise((yes, no) => zip.openReadStream(entry, (e, stream) => e ? no(e) : yes(stream)));
          await pipeline(input, createWriteStream(output, { flags: "wx", mode: 0o600 }));
          if (process.platform !== "win32") await chmod(output, mode & 0o111 ? 0o755 : 0o644);
        }
        zip.readEntry();
      })().catch(abort);
    });
    zip.readEntry();
  });
}
