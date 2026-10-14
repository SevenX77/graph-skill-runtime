import { randomUUID } from "node:crypto";

// Opaque view keys for one MCP connection. Codex additionally scopes reuse to
// its host, conversation, server and verified resource identity.
export function createCodexCanvasSessions() {
  const roots = new Map();
  return {
    metadata(canonicalRoot) {
      if (!roots.has(canonicalRoot)) roots.set(canonicalRoot, randomUUID());
      return { "openai/widgetSessionId": roots.get(canonicalRoot) };
    },
    existingMetadata(canonicalRoot) {
      const id = roots.get(canonicalRoot);
      return id ? { "openai/widgetSessionId": id } : {};
    },
  };
}
