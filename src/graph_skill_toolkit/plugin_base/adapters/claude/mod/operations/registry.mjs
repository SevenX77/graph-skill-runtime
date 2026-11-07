import { unknownCapabilities } from "../../../../ports/host/catalog.mjs";
import { MODE_LIMITS } from "./mode_limits.mjs";
import { capability as getInfoCapability } from "../../../../host_interfaces/host/get_info/claude.mjs";
import { capability as getCapabilitiesCapability } from "../../../../host_interfaces/host/get_capabilities/claude.mjs";
import { capability as getContextCapability, invoke as getContextInvoke } from "../../../../host_interfaces/host/get_context/claude.mjs";
import { capability as eventsCapability } from "../../../../host_interfaces/events/subscribe/claude.mjs";
import { capability as openFileCapability, invoke as openFileInvoke } from "../../../../host_interfaces/files/open_file/claude.mjs";
import { capability as revealDirectoryCapability, invoke as revealDirectoryInvoke } from "../../../../host_interfaces/files/reveal_directory/claude.mjs";
import { capability as writeDraftCapability, invoke as writeDraftInvoke } from "../../../../host_interfaces/composer/write_draft/claude.mjs";
import { capability as submitMessageCapability, invoke as submitMessageInvoke } from "../../../../host_interfaces/conversation/submit_message/claude.mjs";
import { capability as contextUpdateCapability, invoke as contextUpdateInvoke } from "../../../../host_interfaces/context/update/claude.mjs";
import { capability as toolsListCapability, invoke as toolsListInvoke } from "../../../../host_interfaces/tools/list/claude.mjs";
import { capability as toolsCallCapability, invoke as toolsCallInvoke } from "../../../../host_interfaces/tools/call/claude.mjs";
import { capability as skillsListCapability, invoke as skillsListInvoke } from "../../../../host_interfaces/skills/list/claude.mjs";
import { capability as skillsInvokeCapability, invoke as skillsInvokeInvoke } from "../../../../host_interfaces/skills/invoke/claude.mjs";
import { capability as viewsOpenCapability, invoke as viewsOpenInvoke } from "../../../../host_interfaces/views/open/claude.mjs";
import { capability as viewsListCapability, invoke as viewsListInvoke } from "../../../../host_interfaces/views/list/claude.mjs";
import { capability as viewsCloseCapability, invoke as viewsCloseInvoke } from "../../../../host_interfaces/views/close/claude.mjs";
import { capability as displayModeCapability, invoke as displayModeInvoke } from "../../../../host_interfaces/views/request_display_mode/claude.mjs";

// The Mod engine accepts $ only as a plain argument to declared functions and
// only in call position, so capability checks and dispatch are static switches.
function capabilityFor(action, tools, facts) {
  switch (action) {
    case "host.getInfo": return getInfoCapability();
    case "host.getCapabilities": return getCapabilitiesCapability();
    case "host.getContext": return getContextCapability();
    case "events.subscribe": return eventsCapability();
    case "files.openFile": return openFileCapability(tools);
    case "files.revealDirectory": return revealDirectoryCapability(tools);
    case "composer.writeDraft": return writeDraftCapability(tools);
    case "conversation.submitMessage": return submitMessageCapability(tools);
    case "context.update": return contextUpdateCapability(tools);
    case "tools.list": return toolsListCapability(tools);
    case "tools.call": return toolsCallCapability(tools);
    case "skills.list": return skillsListCapability(tools, facts);
    case "skills.invoke": return skillsInvokeCapability(tools);
    case "views.open": return viewsOpenCapability(tools);
    case "views.list": return viewsListCapability(tools);
    case "views.close": return viewsCloseCapability(tools);
    case "views.requestDisplayMode": return displayModeCapability(tools);
    default: return undefined;
  }
}

export function invokeOperation(action, $, context) {
  switch (action) {
    case "host.getContext": return getContextInvoke($, context);
    case "files.openFile": return openFileInvoke($, context);
    case "files.revealDirectory": return revealDirectoryInvoke($, context);
    case "composer.writeDraft": return writeDraftInvoke($, context);
    case "conversation.submitMessage": return submitMessageInvoke($, context);
    case "context.update": return contextUpdateInvoke($, context);
    case "tools.list": return toolsListInvoke($, context);
    case "tools.call": return toolsCallInvoke($, context);
    case "skills.list": return skillsListInvoke($, context);
    case "skills.invoke": return skillsInvokeInvoke($, context);
    case "views.open": return viewsOpenInvoke($, context);
    case "views.list": return viewsListInvoke($, context);
    case "views.close": return viewsCloseInvoke($, context);
    case "views.requestDisplayMode": return displayModeInvoke($, context);
    default: return undefined;
  }
}

/** Declarative inventory: every catalog action has a Claude capability module. */
export const operations = Object.freeze({
  "host.getInfo": { capability: getInfoCapability }, "host.getCapabilities": { capability: getCapabilitiesCapability },
  "host.getContext": { capability: getContextCapability, invoke: getContextInvoke }, "events.subscribe": { capability: eventsCapability },
  "files.openFile": { capability: openFileCapability, invoke: openFileInvoke }, "files.revealDirectory": { capability: revealDirectoryCapability, invoke: revealDirectoryInvoke },
  "composer.writeDraft": { capability: writeDraftCapability, invoke: writeDraftInvoke }, "conversation.submitMessage": { capability: submitMessageCapability, invoke: submitMessageInvoke },
  "context.update": { capability: contextUpdateCapability, invoke: contextUpdateInvoke }, "tools.list": { capability: toolsListCapability, invoke: toolsListInvoke },
  "tools.call": { capability: toolsCallCapability, invoke: toolsCallInvoke }, "skills.list": { capability: skillsListCapability, invoke: skillsListInvoke },
  "skills.invoke": { capability: skillsInvokeCapability, invoke: skillsInvokeInvoke }, "views.open": { capability: viewsOpenCapability, invoke: viewsOpenInvoke },
  "views.list": { capability: viewsListCapability, invoke: viewsListInvoke }, "views.close": { capability: viewsCloseCapability, invoke: viewsCloseInvoke },
  "views.requestDisplayMode": { capability: displayModeCapability, invoke: displayModeInvoke },
});

const INVOCABLE = ["host.getContext", "files.openFile", "files.revealDirectory", "composer.writeDraft", "conversation.submitMessage", "context.update", "tools.list", "tools.call",
  "skills.list", "skills.invoke", "views.open", "views.list", "views.close", "views.requestDisplayMode"];
export const hasInvoke = action => INVOCABLE.includes(action);

/** @param {{sessionUsage?: boolean}} [facts] results of probing calls on the session */
export function nativeCapabilities(tools, facts = {}) {
  const result = unknownCapabilities("当前宿主接入尚未确认此接口；不以 Agent 或系统窗口代替。");
  for (const action of Object.keys(result)) result[action] = capabilityFor(action, tools, facts) ?? result[action];
  const mode = facts.permissionMode;
  const limits = typeof mode === "string" && Object.hasOwn(MODE_LIMITS, mode) ? MODE_LIMITS[mode] : {};
  for (const [action, limit] of Object.entries(limits)) if (result[action]?.state === "available") result[action] = { ...result[action], modeLimit: { mode, ...limit } };
  return result;
}
