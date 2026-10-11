import { createRoot } from "react-dom/client";
import { GraphWorkbench } from "../ui/workbench/index";
import { codexAdapter } from "../adapters/codex/browser/index.mjs";
import { claudeAdapter } from "../adapters/claude/browser/index.mjs";
import type { HostAdapter } from "../ports/host/index";

const snapshot = document.querySelector("#graph-skill-snapshot");
const isClaude = snapshot !== null && snapshot.textContent?.trim() !== "null";
const adapter: HostAdapter | null = isClaude ? claudeAdapter() : window.parent !== window ? codexAdapter() : null;
const root = document.querySelector("#app");
if (!root) throw new Error("Missing shared canvas application root.");
createRoot(root).render(<GraphWorkbench adapter={adapter} />);
