import { string } from "../../validation/index.mjs";
export const definition = { id: "views.activate", label: "激活视图", sample: { viewId: "view-id" }, fields: ["viewId"], validate(args) {
  if (!string(args.viewId)) throw new Error("无效的视图标识。");
} };
