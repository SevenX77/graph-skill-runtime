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
  const templateUrl = new URL("../../" + template, import.meta.url);
  const source = await readFile(templateUrl, "utf8");
  // A template names the stylesheets it inlines, so the page stays one file while reading them from their owner.
  const styles = await Promise.all([...source.matchAll(/\/\* INLINE_CSS (\S+) \*\//g)].map(async ([marker, path]) => {
    const file = new URL(path, templateUrl);
    try { return [marker, await readFile(file, "utf8")]; }
    catch (error) { throw new Error(`${template} names ${fileURLToPath(file)}, which cannot be read. Run: git submodule update --init vendor/ui-ux-template`, { cause: error }); }
  }));
  const html = styles.reduce((text, [marker, css]) => text.replace(marker, () => css), source).replace("/* APP_BUNDLE */", () => script);
  await writeFile(new URL(output, dist), html);
  return Buffer.byteLength(html);
}
const canvasBytes = await page("apps/graph_canvas/app/main.tsx", "apps/graph_canvas/ui/template/canvas.html", "canvas.html");
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
  absWorkingDir: root, entryPoints: ["composition/after_tool.mjs"], outfile: "dist/after-tool.mjs",
  bundle: true, platform: "node", format: "esm", target: "node22",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
  absWorkingDir: root, entryPoints: ["installer/download/main.mjs"], outfile: "dist/installer.mjs",
  bundle: true, platform: "node", format: "esm", target: "node18",
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
console.log(`Built server, hook, canvas (${canvasBytes} bytes), and npm installer`);
