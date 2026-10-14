import { createRoot } from "react-dom/client";
import { GraphWorkbench } from "../ui/workbench/index";
import { createCanvasComposition } from "./composition.mjs";

const { adapter, source } = createCanvasComposition();
const root = document.querySelector("#app");
if (!root) throw new Error("Missing shared canvas application root.");
createRoot(root).render(<GraphWorkbench adapter={adapter} source={source} />);
