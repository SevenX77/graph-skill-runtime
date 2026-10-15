export const SNAPSHOT_SLOT = '<script id="graph-skill-snapshot" type="application/json">null</script>';

// Only inert data varies between the MCP App document and the HTTP preview.
// The latter no longer uses Claude's size-limited local-file snapshot loader.
export function snapshotHtml(html, payload) {
  if (html.split(SNAPSHOT_SLOT).length !== 2) throw new Error("Canvas snapshot slot is missing or duplicated.");
  const data = JSON.stringify(payload).replace(/</g, "\\u003c");
  return html.replace(SNAPSHOT_SLOT, () => SNAPSHOT_SLOT.replace("null", () => data));
}
