import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { runTriggerHook } from "hostpane/triggers";
import { toolkitTriggersAt } from "./triggers.mjs";

// The toolkit's PostToolUse hook, bundled to dist/after-tool.mjs: Hostpane's trigger
// runner with the toolkit's declaration for the build beside this bundle.
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  await runTriggerHook(toolkitTriggersAt(dirname(fileURLToPath(import.meta.url))));
}
