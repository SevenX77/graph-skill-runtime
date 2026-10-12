import { createHash } from "node:crypto";

// A new HTML build must not reuse a host page running an older script, even
// when both local candidates have the same package version. Session-specific
// launch data is injected afterward and does not change this build identity.
export function canvasResourceUri(html) {
  return `ui://graph-skill/canvas-${createHash("sha256").update(html).digest("hex")}.html`;
}

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
