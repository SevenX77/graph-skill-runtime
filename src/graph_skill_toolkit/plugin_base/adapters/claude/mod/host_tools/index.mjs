// Adapter tool identifiers; every use checks the current native inventory.
export const PREVIEW_TOOL = 'mcp__Claude_Browser__preview_start';
export const NAVIGATE_TOOL = 'mcp__Claude_Browser__navigate';
export const CONTEXT_TOOL = 'mcp__Claude_Browser__tabs_context';
export const SELECT_TOOL = 'mcp__Claude_Browser__tabs_select';
export const CLOSE_TOOL = 'mcp__Claude_Browser__tabs_close';
// One host tool shows every side pane: the file pane and the Browser (preview) pane.
export const SHOW_PANE_TOOL = 'mcp__ccd_view__show_pane';
// The host reveals a file or folder of the session in the system file manager.
export const REVEAL_PATH_TOOL = 'mcp__ccd_host__reveal_path';
// Layout of the page's container: the main window's sidebar and this session's open panes.
export const SIDEBAR_TOOL = 'mcp__ccd_window__set_sidebar_collapsed';
export const WINDOW_LAYOUT_TOOL = 'mcp__ccd_window__get_window_layout';
export const LAYOUT_TOOL = 'mcp__ccd_view__get_layout';
// The desktop host's session metadata; the engine's session API has no permission mode.
export const SESSION_TOOL = 'mcp__ccd_session_mgmt__get_session';
