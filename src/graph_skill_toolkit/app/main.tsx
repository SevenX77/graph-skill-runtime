import { createRoot } from "react-dom/client";
import { GraphWorkbench } from "../ui/workbench/index";
import { createHostAdapter } from "../adapters/index.mjs";

const adapter = createHostAdapter();
const root = document.querySelector("#app");
if (!root) throw new Error("Missing shared canvas application root.");
createRoot(root).render(<GraphWorkbench adapter={adapter} />);
