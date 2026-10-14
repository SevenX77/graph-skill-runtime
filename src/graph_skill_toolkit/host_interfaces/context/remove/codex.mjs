import { declared, writeContext } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.updateModelContext?.structuredContent, "移除当前页面连接拥有的指定上下文", { scope: "page-connection" });
export const invoke = (app, args, state) => writeContext(app, state, args, true);
