import { isAbsolute, join } from "node:path";
import { pathToFileURL } from "node:url";

// The selected business document has one identity across host deliveries.
// Callers verify the business root through loadSkill before constructing it.
export function skillDocument(skillRoot) {
  if (typeof skillRoot !== "string" || !isAbsolute(skillRoot)) throw new Error("A verified absolute Skill root is required.");
  const path = join(skillRoot, "SKILL.md");
  return { path, fileUrl: pathToFileURL(path).href };
}
