import { createRoot } from "react-dom/client";
import { createHostAdapter, SNAPSHOT_ELEMENT_ID } from "hostpane/page";
import { InterfaceLab, type Opened } from "../ui/index";
import type { LabPaths } from "../application/guide.mjs";
import packageInfo from "../../../package.json" with { type: "json" };

/** The lab paths and, when a page tool opened this page for a reason, the route and firing it named. */
function bootstrap(): { lab: LabPaths | null; opened: Opened } {
  try {
    const value = JSON.parse(document.querySelector("#" + SNAPSHOT_ELEMENT_ID)?.textContent ?? "null");
    return {
      lab: value?.lab && typeof value.lab.sandbox === "string" ? value.lab : null,
      opened: { route: typeof value?.route === "string" ? value.route : null, triggerFiring: typeof value?.triggerFiring === "string" ? value.triggerFiring : null },
    };
  } catch { return { lab: null, opened: { route: null, triggerFiring: null } }; }
}

const adapter = createHostAdapter({ appInfo: { name: "Plugin Interface Lab", version: packageInfo.version } });
const root = document.querySelector("#app");
if (!root) throw new Error("Missing Interface Lab application root.");
const { lab, opened } = bootstrap();
createRoot(root).render(<InterfaceLab adapter={adapter} lab={lab} opened={opened} />);
