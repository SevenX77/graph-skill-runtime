// Codex owns the sidebar session, including close and explicit redisplay.
// Advertising only fullscreen lets closing hide that session rather than
// downgrade it to inline, which would persist across the next show_graph.
// See evidence/codex-native-20261011/closed-reopen-host-source.json.
// Other hosts can ignore this namespaced metadata.
export const codexResourceMetadata = {
  "openai/ui": {
    availableDisplayModes: ["fullscreen"],
    preferredDisplayMode: "fullscreen",
  },
};
