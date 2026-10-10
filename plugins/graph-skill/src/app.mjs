import { createCanvas } from "./ui/canvas.mjs";
import { codexAdapter } from "./adapters/codex.mjs";
import { claudeAdapter } from "./adapters/claude.mjs";
import { graph } from "./graph.mjs";

const canvas = createCanvas(document);
const isClaude = document.querySelector("#graph-skill-snapshot")?.textContent.trim() !== "null";
const adapter = isClaude ? claudeAdapter() : window.parent !== window ? codexAdapter() : null;
if (adapter) {
  canvas.connect(adapter).catch(error => canvas.fail(error));
  window.addEventListener("pagehide", () => adapter.dispose(), { once: true });
} else {
  canvas.receive({ graph: { ...graph, width: 352, height: 548 }, skillRoot: null });
}
