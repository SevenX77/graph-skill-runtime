import { z } from "zod";
import { declared, responseResult, unsupported } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.experimental?.["openai/files"], "通过宿主文件扩展打开指定文件", { scope: "host-file-view", constraints: { lineNavigation: false } });
export async function invoke(app, args) {
  if (args.line !== undefined) return unsupported("当前文件扩展未声明行号定位能力。");
  return responseResult(await app.request({ method: "openai/files/open", params: { path: args.path.replace(/\\/g, "/") } }, z.object({}).passthrough()), "宿主已接受文件打开请求。", "accepted");
}
