export const present = (yes, detail, extra = {}) => ({ state: yes ? "available" : "unavailable", detail, ...extra });
export const unknown = detail => ({ state: "unknown", detail });
export const has = (tools, name) => tools.some(tool => tool.name === name);
