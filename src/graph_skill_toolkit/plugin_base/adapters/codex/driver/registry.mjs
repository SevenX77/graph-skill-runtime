import { unknownCapabilities } from "../../../ports/host/catalog.mjs";
import * as openFile from "../../../host_interfaces/files/open_file/codex.mjs";
import * as revealDirectory from "../../../host_interfaces/files/reveal_directory/codex.mjs";
import * as writeDraft from "../../../host_interfaces/composer/write_draft/codex.mjs";
import * as submitMessage from "../../../host_interfaces/conversation/submit_message/codex.mjs";
import * as contextSet from "../../../host_interfaces/context/set/codex.mjs";
import * as contextRemove from "../../../host_interfaces/context/remove/codex.mjs";
import * as toolsCall from "../../../host_interfaces/tools/call/codex.mjs";
import * as toolsList from "../../../host_interfaces/tools/list/codex.mjs";
import * as displayMode from "../../../host_interfaces/views/request_display_mode/codex.mjs";
import * as viewsOpen from "../../../host_interfaces/views/open/codex.mjs";
import * as viewsList from "../../../host_interfaces/views/list/codex.mjs";
import * as viewsActivate from "../../../host_interfaces/views/activate/codex.mjs";
import * as viewsClose from "../../../host_interfaces/views/close/codex.mjs";
import * as skillsList from "../../../host_interfaces/skills/list/codex.mjs";
import * as skillsInvoke from "../../../host_interfaces/skills/invoke/codex.mjs";

export const operations = Object.freeze({
  "files.revealDirectory": revealDirectory,
  "files.openFile": openFile,
  "composer.writeDraft": writeDraft,
  "conversation.submitMessage": submitMessage,
  "context.set": contextSet,
  "context.remove": contextRemove,
  "tools.call": toolsCall,
  "tools.list": toolsList,
  "views.requestDisplayMode": displayMode,
  "views.open": viewsOpen,
  "views.list": viewsList,
  "views.activate": viewsActivate,
  "views.close": viewsClose,
  "skills.list": skillsList,
  "skills.invoke": skillsInvoke,
});

export function mcpCapabilities(host, context = {}) {
  if (!host || typeof host !== "object" || Array.isArray(host)) throw new Error("MCP host capabilities are missing.");
  for (const name of ["message", "serverTools", "updateModelContext", "experimental"]) {
    if (host[name] !== undefined && (!host[name] || typeof host[name] !== "object" || Array.isArray(host[name]))) throw new Error("Invalid MCP capability: " + name);
  }
  const files = host.experimental?.["openai/files"], draft = host.experimental?.["openai/message"]?.draft;
  if (files !== undefined && (!files || typeof files !== "object" || Array.isArray(files))) throw new Error("Invalid file capability.");
  if (draft !== undefined && (!draft || typeof draft !== "object" || Array.isArray(draft))) throw new Error("Invalid draft capability.");
  const result = unknownCapabilities("当前接入尚未确认此宿主原生接口；不会交给 Agent 代办。");
  for (const [action, operation] of Object.entries(operations)) result[action] = operation.capability(host, context);
  return result;
}
