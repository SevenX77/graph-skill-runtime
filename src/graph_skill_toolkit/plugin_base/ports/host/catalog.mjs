import { definition as getInfo } from "../../host_interfaces/host/get_info/index.mjs";
import { definition as getCapabilities } from "../../host_interfaces/host/get_capabilities/index.mjs";
import { definition as getContext } from "../../host_interfaces/host/get_context/index.mjs";
import { definition as eventsSubscribe } from "../../host_interfaces/events/subscribe/index.mjs";
import { definition as openFile } from "../../host_interfaces/files/open_file/index.mjs";
import { definition as revealDirectory } from "../../host_interfaces/files/reveal_directory/index.mjs";
import { definition as writeDraft } from "../../host_interfaces/composer/write_draft/index.mjs";
import { definition as submitMessage } from "../../host_interfaces/conversation/submit_message/index.mjs";
import { definition as contextUpdate } from "../../host_interfaces/context/update/index.mjs";
import { definition as toolsList } from "../../host_interfaces/tools/list/index.mjs";
import { definition as toolsCall } from "../../host_interfaces/tools/call/index.mjs";
import { definition as skillsList } from "../../host_interfaces/skills/list/index.mjs";
import { definition as skillsInvoke } from "../../host_interfaces/skills/invoke/index.mjs";
import { definition as viewsOpen } from "../../host_interfaces/views/open/index.mjs";
import { definition as viewsList } from "../../host_interfaces/views/list/index.mjs";
import { definition as viewsClose } from "../../host_interfaces/views/close/index.mjs";
import { definition as displayMode } from "../../host_interfaces/views/request_display_mode/index.mjs";

/** The 17 host interfaces, in catalog order. */
export const INTERFACE_DEFINITIONS = Object.freeze([getInfo, getCapabilities, getContext, eventsSubscribe,
  openFile, revealDirectory, writeDraft, submitMessage, contextUpdate, toolsList, toolsCall,
  skillsList, skillsInvoke, viewsOpen, viewsList, viewsClose, displayMode]);
export const INTERFACES = Object.freeze(INTERFACE_DEFINITIONS.map(({ id, label, sample }) => Object.freeze({ id, label, sample: Object.freeze(sample) })));
export const HOST_ACTIONS = Object.freeze(INTERFACE_DEFINITIONS.map(item => item.id));
/** Operations the page facade answers itself; they need no host driver. */
export const FACADE_ACTIONS = Object.freeze(INTERFACE_DEFINITIONS.filter(item => item.facade).map(item => item.id));
/** Operations a host driver executes. */
export const DRIVER_ACTIONS = Object.freeze(HOST_ACTIONS.filter(id => !FACADE_ACTIONS.includes(id)));
export const capability = (state, detail, extra = {}) => ({ state, detail, ...extra });
export const unknownCapabilities = detail => Object.fromEntries(HOST_ACTIONS.map(id => [id, capability("unknown", detail)]));
