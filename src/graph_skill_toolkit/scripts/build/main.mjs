import { build } from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const dist = new URL("../../dist/", import.meta.url);
await mkdir(dist, { recursive: true });
const browser = await build({
  absWorkingDir: root, entryPoints: ["app/main.tsx"], bundle: true,
  platform: "browser", format: "iife", target: "es2022", minify: true, write: false,
  charset: "utf8", define: { "process.env.NODE_ENV": '"production"' },
});
const template = await readFile(new URL("../../ui/template/canvas.html", import.meta.url), "utf8");
// Keep script contents inside the one HTML resource even if a dependency contains a closing tag.
const script = browser.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
const page = template.replace("/* APP_BUNDLE */", () => script);
await writeFile(new URL("canvas.html", dist), page);
await build({
  absWorkingDir: root, entryPoints: ["server/main.mjs"], outfile: "dist/server.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["hooks/after-tool.mjs"], outfile: "dist/after-tool.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["installer/download/main.mjs"], outfile: "dist/installer.mjs",
  bundle: true, platform: "node", format: "esm", target: "node18",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
console.log(`Built server, hook, canvas (${Buffer.byteLength(page)} bytes), and npm installer`);
