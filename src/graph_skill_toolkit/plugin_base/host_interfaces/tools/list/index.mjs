export const definition = { id: "tools.list", label: "查询工具", sample: {}, fields: ["scope"], validate(args) {
  if (args.scope !== undefined && !["session", "originating-server"].includes(args.scope)) throw new Error("未知的工具范围。");
} };
