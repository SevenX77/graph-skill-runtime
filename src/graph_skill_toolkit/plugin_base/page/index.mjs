// @ts-check
/** Plugin Base page entry: everything a plugin page may use. See ../README.md. */
export { createHostAdapter } from "../adapters/factory/index.mjs";
export { discoverConnection } from "../adapters/detection/index.mjs";
export { createMcpConnection } from "../adapters/codex/connection/index.mjs";
export { INTERFACES, HOST_ACTIONS } from "../ports/host/catalog.mjs";
export { SNAPSHOT_ELEMENT_ID } from "../template/publisher.mjs";
export { LOCAL_DEFINITIONS, LOCAL_ACTIONS } from "../local/definitions.mjs";
