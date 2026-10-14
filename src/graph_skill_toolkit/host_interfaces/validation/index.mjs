/** Common transport constraints. Each interface owns its own fields and semantics. */
export function record(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("接口数据必须是对象。");
  return value;
}

export function string(value, max = 256) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max && !/[\0\r\n]/.test(value);
}

export function path(value) {
  return string(value, 32768) && (/^[A-Za-z]:[\\/]/.test(value) || value.startsWith("/"));
}

export function line(value) {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
}

export function text(value) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 8000;
}

export function portable(value, depth = 0) {
  if (depth > 32) throw new Error("接口 JSON 嵌套超过 32 层。");
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number" && Number.isFinite(value)) return;
  if (Array.isArray(value)) { for (const item of value) portable(item, depth + 1); return; }
  if (value && Object.getPrototypeOf(value) === Object.prototype) { for (const item of Object.values(value)) portable(item, depth + 1); return; }
  throw new Error("接口参数必须是可传输的 JSON 数据。");
}
