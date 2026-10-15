import { unknownCapabilities } from "../../../ports/host/catalog.mjs";
import * as getInfo from "../../../host_interfaces/host/get_info/codex.mjs";
import * as getCapabilities from "../../../host_interfaces/host/get_capabilities/codex.mjs";
import * as getContext from "../../../host_interfaces/host/get_context/codex.mjs";
import * as eventsSubscribe from "../../../host_interfaces/events/subscribe/codex.mjs";
import * as openFile from "../../../host_interfaces/files/open_file/codex.mjs";
import * as revealDirectory from "../../../host_interfaces/files/reveal_directory/codex.mjs";
import * as writeDraft from "../../../host_interfaces/composer/write_draft/codex.mjs";
import * as submitMessage from "../../../host_interfaces/conversation/submit_message/codex.mjs";
import * as contextUpdate from "../../../host_interfaces/context/update/codex.mjs";
import * as toolsCall from "../../../host_interfaces/tools/call/codex.mjs";
import * as toolsList from "../../../host_interfaces/tools/list/codex.mjs";
import * as skillsList from "../../../host_interfaces/skills/list/codex.mjs";
import * as skillsInvoke from "../../../host_interfaces/skills/invoke/codex.mjs";
import * as viewsOpen from "../../../host_interfaces/views/open/codex.mjs";
import * as viewsList from "../../../host_interfaces/views/list/codex.mjs";
import * as viewsClose from "../../../host_interfaces/views/close/codex.mjs";
import * as displayMode from "../../../host_interfaces/views/request_display_mode/codex.mjs";

export const operations = Object.freeze({
  "host.getInfo": getInfo, "host.getCapabilities": getCapabilities, "host.getContext": getContext, "events.subscribe": eventsSubscribe,
  "files.openFile": openFile, "files.revealDirectory": revealDirectory,
  "composer.writeDraft": writeDraft, "conversation.submitMessage": submitMessage, "context.update": contextUpdate,
  "tools.list": toolsList, "tools.call": toolsCall, "skills.list": skillsList, "skills.invoke": skillsInvoke,
  "views.open": viewsOpen, "views.list": viewsList, "views.close": viewsClose, "views.requestDisplayMode": displayMode,
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
