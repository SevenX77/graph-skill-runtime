import { unknownCapabilities } from "../../../../ports/host/catalog.mjs";
import * as revealDirectory from "../../../../host_interfaces/files/reveal_directory/claude.mjs";
import * as openFile from "../../../../host_interfaces/files/open_file/claude.mjs";
import * as writeDraft from "../../../../host_interfaces/composer/write_draft/claude.mjs";
import * as submitMessage from "../../../../host_interfaces/conversation/submit_message/claude.mjs";
import * as contextSet from "../../../../host_interfaces/context/set/claude.mjs";
import * as contextRemove from "../../../../host_interfaces/context/remove/claude.mjs";
import * as toolsList from "../../../../host_interfaces/tools/list/claude.mjs";
import * as toolsCall from "../../../../host_interfaces/tools/call/claude.mjs";
import * as viewsOpen from "../../../../host_interfaces/views/open/claude.mjs";
import * as viewsList from "../../../../host_interfaces/views/list/claude.mjs";
import * as viewsActivate from "../../../../host_interfaces/views/activate/claude.mjs";
import * as viewsClose from "../../../../host_interfaces/views/close/claude.mjs";
import * as displayMode from "../../../../host_interfaces/views/request_display_mode/claude.mjs";
import * as skillsList from "../../../../host_interfaces/skills/list/claude.mjs";
import * as skillsInvoke from "../../../../host_interfaces/skills/invoke/claude.mjs";

import { capability as revealDirectoryCapability } from "../../../../host_interfaces/files/reveal_directory/claude.mjs";
import { capability as openFileCapability } from "../../../../host_interfaces/files/open_file/claude.mjs";
import { capability as writeDraftCapability } from "../../../../host_interfaces/composer/write_draft/claude.mjs";
import { capability as submitMessageCapability } from "../../../../host_interfaces/conversation/submit_message/claude.mjs";
import { capability as contextSetCapability } from "../../../../host_interfaces/context/set/claude.mjs";
import { capability as contextRemoveCapability } from "../../../../host_interfaces/context/remove/claude.mjs";
import { capability as toolsListCapability } from "../../../../host_interfaces/tools/list/claude.mjs";
import { capability as toolsCallCapability } from "../../../../host_interfaces/tools/call/claude.mjs";
import { capability as viewsOpenCapability } from "../../../../host_interfaces/views/open/claude.mjs";
import { capability as viewsListCapability } from "../../../../host_interfaces/views/list/claude.mjs";
import { capability as viewsActivateCapability } from "../../../../host_interfaces/views/activate/claude.mjs";
import { capability as viewsCloseCapability } from "../../../../host_interfaces/views/close/claude.mjs";
import { capability as displayModeCapability } from "../../../../host_interfaces/views/request_display_mode/claude.mjs";
import { capability as skillsListCapability } from "../../../../host_interfaces/skills/list/claude.mjs";
import { capability as skillsInvokeCapability } from "../../../../host_interfaces/skills/invoke/claude.mjs";
import { invoke as openFileInvoke } from "../../../../host_interfaces/files/open_file/claude.mjs";
import { invoke as writeDraftInvoke } from "../../../../host_interfaces/composer/write_draft/claude.mjs";
import { invoke as submitMessageInvoke } from "../../../../host_interfaces/conversation/submit_message/claude.mjs";
import { invoke as contextSetInvoke } from "../../../../host_interfaces/context/set/claude.mjs";
import { invoke as contextRemoveInvoke } from "../../../../host_interfaces/context/remove/claude.mjs";
import { invoke as toolsListInvoke } from "../../../../host_interfaces/tools/list/claude.mjs";
import { invoke as toolsCallInvoke } from "../../../../host_interfaces/tools/call/claude.mjs";
import { invoke as viewsListInvoke } from "../../../../host_interfaces/views/list/claude.mjs";
import { invoke as viewsActivateInvoke } from "../../../../host_interfaces/views/activate/claude.mjs";
import { invoke as skillsListInvoke } from "../../../../host_interfaces/skills/list/claude.mjs";
import { invoke as skillsInvokeInvoke } from "../../../../host_interfaces/skills/invoke/claude.mjs";

export const operations = Object.freeze({
  "files.revealDirectory": revealDirectory, "files.openFile": openFile,
  "composer.writeDraft": writeDraft, "conversation.submitMessage": submitMessage,
  "context.set": contextSet, "context.remove": contextRemove,
  "tools.list": toolsList, "tools.call": toolsCall,
  "views.open": viewsOpen, "views.list": viewsList, "views.activate": viewsActivate,
  "views.close": viewsClose, "views.requestDisplayMode": displayMode,
  "skills.list": skillsList, "skills.invoke": skillsInvoke,
});

// The Mod engine accepts $ only as a plain argument to declared functions and
// only in call position, so dispatch is a static switch and capability checks
// read probed facts; `operations` stays the declarative inventory.
function capabilityFor(action, tools, facts) {
  switch (action) {
    case "files.revealDirectory": return revealDirectoryCapability(tools);
    case "files.openFile": return openFileCapability(tools);
    case "composer.writeDraft": return writeDraftCapability(tools);
    case "conversation.submitMessage": return submitMessageCapability(tools);
    case "context.set": return contextSetCapability(tools);
    case "context.remove": return contextRemoveCapability(tools);
    case "tools.list": return toolsListCapability(tools);
    case "tools.call": return toolsCallCapability(tools);
    case "views.open": return viewsOpenCapability(tools);
    case "views.list": return viewsListCapability(tools);
    case "views.activate": return viewsActivateCapability(tools);
    case "views.close": return viewsCloseCapability(tools);
    case "views.requestDisplayMode": return displayModeCapability(tools);
    case "skills.list": return skillsListCapability(tools, facts);
    case "skills.invoke": return skillsInvokeCapability(tools);
    default: return undefined;
  }
}

export function invokeOperation(action, $, context) {
  switch (action) {
    case "files.openFile": return openFileInvoke($, context);
    case "composer.writeDraft": return writeDraftInvoke($, context);
    case "conversation.submitMessage": return submitMessageInvoke($, context);
    case "context.set": return contextSetInvoke($, context);
    case "context.remove": return contextRemoveInvoke($, context);
    case "tools.list": return toolsListInvoke($, context);
    case "tools.call": return toolsCallInvoke($, context);
    case "views.list": return viewsListInvoke($, context);
    case "views.activate": return viewsActivateInvoke($, context);
    case "skills.list": return skillsListInvoke($, context);
    case "skills.invoke": return skillsInvokeInvoke($, context);
    default: return undefined;
  }
}

export function hasInvoke(action) {
  return ["composer.writeDraft", "context.remove", "context.set", "conversation.submitMessage", "files.openFile", "skills.invoke", "skills.list", "tools.call", "tools.list", "views.activate", "views.list"].includes(action);
}

/** @param {{sessionUsage?: boolean}} [facts] results of probing calls on the session */
export function nativeCapabilities(tools, facts = {}) {
  const result = unknownCapabilities("当前宿主接入尚未确认此接口；不以 Agent 或系统窗口代替。");
  for (const action of Object.keys(operations)) result[action] = capabilityFor(action, tools, facts);
  return result;
}
