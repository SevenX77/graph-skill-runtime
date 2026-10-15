export const definition = { id: "views.requestDisplayMode", label: "请求显示模式", sample: { mode: "fullscreen" }, fields: ["mode"], validate(args) {
  if (!["inline", "fullscreen", "pip"].includes(args.mode)) throw new Error("未知的显示模式。");
} };
