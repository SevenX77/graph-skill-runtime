// A native local-file preview receives one validated snapshot. The next graph
// tool call updates the file; preview_start reloads it through the host.
export function claudeAdapter({ snapshot = () => JSON.parse(document.querySelector("#graph-skill-snapshot").textContent), clipboard = globalThis.navigator?.clipboard } = {}) {
  return {
    rootActionLabel: "复制 Skill 文件夹路径",
    async connect({ receive, fail }) {
      const payload = snapshot();
      if (payload?.error) fail(new Error(payload.error));
      else receive(payload);
    },
    async openRoot(root) {
      if (!clipboard) throw new Error("当前预览无法复制路径，请从顶部选择路径文本。");
      await clipboard.writeText(root);
      return "已复制 Skill 文件夹路径";
    },
    dispose() {},
  };
}
