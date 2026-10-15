import { path } from "../../validation/index.mjs";
export const definition = { id: "files.revealDirectory", label: "定位目录", sample: { path: "C:/example/project" }, fields: ["path"], validate(args) {
  if (!path(args.path)) throw new Error("文件或目录路径必须是绝对路径。");
} };
