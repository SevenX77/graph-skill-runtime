import { build } from "esbuild";
import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../..", import.meta.url));
const dist = new URL("../../dist/", import.meta.url);
await mkdir(dist, { recursive: true });
// Each page is one self-contained HTML resource: its bundle is inlined into its template.
async function page(entry, template, output) {
  const browser = await build({
    absWorkingDir: root, entryPoints: [entry], bundle: true,
    platform: "browser", format: "iife", target: "es2022", minify: true, write: false,
    charset: "utf8", define: { "process.env.NODE_ENV": '"production"' },
  });
  // Keep script contents inside the HTML resource even if a dependency contains a closing tag.
  const script = browser.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
  const html = (await readFile(new URL("../../" + template, import.meta.url), "utf8")).replace("/* APP_BUNDLE */", () => script);
  await writeFile(new URL(output, dist), html);
  return Buffer.byteLength(html);
}
const canvasBytes = await page("apps/graph_canvas/app/main.tsx", "apps/graph_canvas/ui/template/canvas.html", "canvas.html");
const labBytes = await page("apps/interface_lab/app/main.tsx", "apps/interface_lab/ui/template/lab.html", "interface-lab.html");
await mkdir(new URL('claude-mod/hooks/', dist), { recursive: true });
await mkdir(new URL('claude-mod/.claude-plugin/', dist), { recursive: true });
await build({
  absWorkingDir: root, entryPoints: ['composition/claude_mod/hooks/register.js'],
  outfile: 'dist/claude-mod/hooks/register.js', bundle: true, platform: 'neutral',
  format: 'esm', target: 'es2022', charset: 'utf8',
});
await copyFile(new URL('../../composition/claude_mod/hooks/hooks.json', import.meta.url), new URL('claude-mod/hooks/hooks.json', dist));
await copyFile(new URL('../../composition/claude_mod/.claude-plugin/plugin.json', import.meta.url), new URL('claude-mod/.claude-plugin/plugin.json', dist));
await build({
  absWorkingDir: root, entryPoints: ["composition/server.mjs"], outfile: "dist/server.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["apps/graph_canvas/hooks/after-tool.mjs"], outfile: "dist/after-tool.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["installer/download/main.mjs"], outfile: "dist/installer.mjs",
  bundle: true, platform: "node", format: "esm", target: "node18",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
console.log(`Built server, hook, canvas (${canvasBytes} bytes), interface lab (${labBytes} bytes), and npm installer`);
