// Page-input validation for runtime compile diagnostics. The runtime authors
// every message; the page only bounds and shapes what it displays.
const LIMIT = 50;
const text = (value, max) => typeof value === "string" && value ? value.slice(0, max) : null;

export function validateInvalidEvent(event) {
  const root = event?.skillRoot;
  if (typeof root !== "string" || !root) throw new Error("Missing Skill path.");
  if (!Array.isArray(event.diagnostics)) throw new Error("Invalid compile diagnostics.");
  const diagnostics = event.diagnostics.slice(0, LIMIT).map(item => {
    if (!item || typeof item.code !== "string" || typeof item.message !== "string" || typeof item.severity !== "string") throw new Error("Invalid compile diagnostic.");
    return {
      code: item.code.slice(0, 200), severity: item.severity.slice(0, 40), message: item.message.slice(0, 4000),
      source_path: text(item.source_path, 1000), line: Number.isSafeInteger(item.line) && item.line > 0 ? item.line : null, field_path: text(item.field_path, 1000),
    };
  });
  return { skillRoot: root, diagnostics, total: event.diagnostics.length };
}
