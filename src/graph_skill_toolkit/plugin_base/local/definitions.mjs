// @ts-check
/** The five local capabilities: operations the plugin's own Node process
 * performs on the local machine for its page, without the host. This module is
 * pure and page-safe; the executors live in ./node/. */
import { path as absolutePath, string, portable, record } from "../host_interfaces/validation/index.mjs";

export const LOCAL_LIMITS = Object.freeze({ readBytes: 4 * 1024 * 1024, writeBytes: 1024 * 1024, watchPaths: 32 });
const encodings = ["utf8", "base64"];

/** @param {unknown} value */
const encoding = value => value === undefined || encodings.includes(/** @type {string} */ (value));

/** @param {unknown} value */
function webUrl(value) {
  if (!string(value, 8192)) return false;
  try { const url = new URL(/** @type {string} */ (value)); return (url.protocol === "https:" || url.protocol === "http:") && !url.username && !url.password; }
  catch { return false; }
}

export const LOCAL_DEFINITIONS = Object.freeze([
  { id: "local.files.read", label: "读取本地文件", fields: ["path", "encoding", "maxBytes"], sample: { path: "C:/example/project/notes.txt" },
    /** @param {Record<string, unknown>} args */
    validate(args) {
      if (!absolutePath(args.path)) throw new Error("文件路径必须是绝对路径。");
      if (!encoding(args.encoding)) throw new Error("编码只能是 utf8 或 base64。");
      if (args.maxBytes !== undefined && !(Number.isSafeInteger(args.maxBytes) && /** @type {number} */ (args.maxBytes) >= 1 && /** @type {number} */ (args.maxBytes) <= LOCAL_LIMITS.readBytes)) throw new Error("maxBytes 必须在 1 到 4 MiB 之间。");
    } },
  { id: "local.files.write", label: "写入本地文件", fields: ["path", "content", "encoding"], sample: { path: "C:/example/project/notes.txt", content: "written by the plugin\n" },
    /** @param {Record<string, unknown>} args */
    validate(args) {
      if (!absolutePath(args.path)) throw new Error("文件路径必须是绝对路径。");
      if (typeof args.content !== "string") throw new Error("写入内容必须是字符串。");
      if (!encoding(args.encoding)) throw new Error("编码只能是 utf8 或 base64。");
      if (args.content.length > LOCAL_LIMITS.writeBytes * 2) throw new Error("写入内容超过 1 MiB。");
    } },
  { id: "local.files.watch", label: "监听文件变化", fields: ["paths"], sample: { paths: ["C:/example/project/notes.txt"] },
    /** @param {Record<string, unknown>} args */
    validate(args) {
      if (!Array.isArray(args.paths) || !args.paths.length || args.paths.length > LOCAL_LIMITS.watchPaths || !args.paths.every(absolutePath)) throw new Error("paths 必须是 1 到 32 个绝对路径。");
    } },
  { id: "local.system.openExternal", label: "用系统浏览器打开网址", fields: ["url"], sample: { url: "https://example.com/" },
    /** @param {Record<string, unknown>} args */
    validate(args) { if (!webUrl(args.url)) throw new Error("只能打开不含账号信息的 http 或 https 网址。"); } },
  { id: "local.system.revealInFileManager", label: "在系统资源管理器中定位", fields: ["path"], sample: { path: "C:/example/project/notes.txt" },
    /** @param {Record<string, unknown>} args */
    validate(args) { if (!absolutePath(args.path)) throw new Error("路径必须是绝对路径。"); } },
]);

/** Ends a watch started by local.files.watch; reached through the watch result's stop(). */
const UNWATCH = { id: "local.files.unwatch", label: "停止监听", fields: ["watchId"], sample: { watchId: "w-1" },
  /** @param {Record<string, unknown>} args */
  validate(args) { if (!string(args.watchId, 128)) throw new Error("watchId 无效。"); } };

export const LOCAL_ACTIONS = Object.freeze(LOCAL_DEFINITIONS.map(item => item.id));
/** Every operation a local transport carries: the five capabilities plus unwatch. */
export const LOCAL_TRANSPORT_OPERATIONS = Object.freeze([...LOCAL_ACTIONS, UNWATCH.id]);
export const LOCAL_EVENT_TYPES = Object.freeze(["local.files.changed"]);

/** Validate and snapshot local operation arguments.
 * @param {string} operation @param {unknown} input @returns {Record<string, unknown>} */
export function validateLocalArguments(operation, input = {}) {
  const args = record(input);
  const definition = [...LOCAL_DEFINITIONS, UNWATCH].find(item => item.id === operation);
  if (!definition) throw new Error("未知的本地能力。");
  if (Object.keys(args).some(key => !definition.fields.includes(key))) throw new Error("未知的本地能力参数。");
  definition.validate(args);
  portable(args);
  return JSON.parse(JSON.stringify(args));
}
