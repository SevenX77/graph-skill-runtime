import { record, string, path, line } from "../../validation/index.mjs";
export const definition = { id: "views.open", label: "打开视图", sample: { resource: { kind: "web", url: "https://example.com" }, reuseKey: "interface-example", activate: true }, fields: ["resource", "reuseKey", "activate"], validate(args) {
  const resource = record(args.resource);
  if (Object.keys(resource).some(key => !["kind", "path", "url", "line"].includes(key)) || !string(args.reuseKey) || typeof args.activate !== "boolean") throw new Error("无效的视图请求。");
  if (resource.kind === "file") {
    if (!path(resource.path) || resource.url !== undefined || (resource.line !== undefined && !line(resource.line))) throw new Error("无效的文件视图。");
  } else if (resource.kind === "web") {
    if (typeof resource.url !== "string") throw new Error("无效的网页视图。");
    const url = new URL(resource.url);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || resource.path !== undefined || resource.line !== undefined) throw new Error("无效的网页视图。");
  } else throw new Error("未知的视图类型。");
} };
