export const EVENT_TYPES = Object.freeze(["tool.completed", "turn.completed", "session.ended", "page.teardown", "host.contextChanged", "context.attached"]);
export const definition = { id: "events.subscribe", label: "订阅宿主事件", sample: { types: [...EVENT_TYPES] }, fields: ["types"], validate(args) {
  if (args.types !== undefined && (!Array.isArray(args.types) || args.types.length === 0 || args.types.some(type => !EVENT_TYPES.includes(type)))) throw new Error(`事件类型必须取自：${EVENT_TYPES.join("、")}。`);
}, facade: true };
