import { createRoot } from "react-dom/client";
import { createHostAdapter, SNAPSHOT_ELEMENT_ID } from "../../../plugin_base/page/index.mjs";
import { InterfaceLab } from "../ui/index";
import type { LabPaths } from "../application/guide.mjs";
import packageInfo from "../../../package.json" with { type: "json" };

function bootstrapLab(): LabPaths | null {
  try {
    const value = JSON.parse(document.querySelector("#" + SNAPSHOT_ELEMENT_ID)?.textContent ?? "null");
    return value?.lab && typeof value.lab.sandbox === "string" ? value.lab : null;
  } catch { return null; }
}

const adapter = createHostAdapter({ appInfo: { name: "Plugin Interface Lab", version: packageInfo.version } });
const root = document.querySelector("#app");
if (!root) throw new Error("Missing Interface Lab application root.");
createRoot(root).render(<InterfaceLab adapter={adapter} lab={bootstrapLab()} />);
