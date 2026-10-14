import { declared, writeContext } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.updateModelContext?.structuredContent, "设置当前页面连接拥有的附加上下文", { scope: "page-connection" });
export const invoke = (app, args, state) => writeContext(app, state, args, false);
