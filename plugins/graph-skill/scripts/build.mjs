import { build } from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const dist = new URL("../dist/", import.meta.url);
await mkdir(dist, { recursive: true });
const browser = await build({
  absWorkingDir: root, entryPoints: ["src/app.mjs"], bundle: true,
  platform: "browser", format: "iife", target: "es2022", minify: true, write: false,
});
const template = await readFile(new URL("../src/canvas.html", import.meta.url), "utf8");
// Keep script contents inside the one HTML resource even if a dependency contains a closing tag.
const script = browser.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
await writeFile(new URL("canvas.html", dist), template.replace("/* APP_BUNDLE */", () => script));
await build({
  absWorkingDir: root, entryPoints: ["src/server.mjs"], outfile: "dist/server.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["src/after-tool.mjs"], outfile: "dist/after-tool.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
console.log("Built server, hook, and self-contained canvas");
