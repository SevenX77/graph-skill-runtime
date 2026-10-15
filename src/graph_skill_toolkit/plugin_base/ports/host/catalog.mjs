import { definition as revealDirectory } from "../../host_interfaces/files/reveal_directory/index.mjs";
import { definition as openFile } from "../../host_interfaces/files/open_file/index.mjs";
import { definition as writeDraft } from "../../host_interfaces/composer/write_draft/index.mjs";
import { definition as submitMessage } from "../../host_interfaces/conversation/submit_message/index.mjs";
import { definition as contextSet } from "../../host_interfaces/context/set/index.mjs";
import { definition as contextRemove } from "../../host_interfaces/context/remove/index.mjs";
import { definition as toolsList } from "../../host_interfaces/tools/list/index.mjs";
import { definition as toolsCall } from "../../host_interfaces/tools/call/index.mjs";
import { definition as viewsOpen } from "../../host_interfaces/views/open/index.mjs";
import { definition as viewsList } from "../../host_interfaces/views/list/index.mjs";
import { definition as viewsActivate } from "../../host_interfaces/views/activate/index.mjs";
import { definition as viewsClose } from "../../host_interfaces/views/close/index.mjs";
import { definition as displayMode } from "../../host_interfaces/views/request_display_mode/index.mjs";
import { definition as skillsList } from "../../host_interfaces/skills/list/index.mjs";
import { definition as skillsInvoke } from "../../host_interfaces/skills/invoke/index.mjs";

export const INTERFACE_DEFINITIONS = Object.freeze([revealDirectory, openFile, writeDraft, submitMessage,
  contextSet, contextRemove, toolsList, toolsCall, viewsOpen, viewsList, viewsActivate,
  viewsClose, displayMode, skillsList, skillsInvoke]);
export const INTERFACES = Object.freeze(INTERFACE_DEFINITIONS.map(({ id, label, sample }) => Object.freeze({ id, label, sample: Object.freeze(sample) })));
export const HOST_ACTIONS = Object.freeze(INTERFACE_DEFINITIONS.map(item => item.id));
export const capability = (state, detail, extra = {}) => ({ state, detail, ...extra });
export const unknownCapabilities = detail => Object.fromEntries(HOST_ACTIONS.map(id => [id, capability("unknown", detail)]));
