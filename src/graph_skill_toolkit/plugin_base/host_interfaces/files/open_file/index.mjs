import { path, line } from "../../validation/index.mjs";
export const definition = { id: "files.openFile", label: "打开文件", sample: { path: "C:/example/project/README.md" }, fields: ["path", "line"], validate(args) {
  if (!path(args.path)) throw new Error("文件或目录路径必须是绝对路径。");
  if (args.line !== undefined && !line(args.line)) throw new Error("行号必须为正整数。");
} };
