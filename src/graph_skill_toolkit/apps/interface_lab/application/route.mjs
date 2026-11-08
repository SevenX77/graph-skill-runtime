// @ts-check
/** The lab page's three modes and its selection, kept in the URL hash so a
 * reload or a shared tab returns to the same place: `#guide/start`,
 * `#guide/composer.writeDraft`, `#lab/composer.writeDraft`, `#trigger/test`. */

export const START = "start";
/** The page-trigger mode's views: how it works, the end-to-end test, rules and log. */
export const TRIGGER_VIEWS = Object.freeze(["how", "test", "rules"]);
/** @typedef {{ mode: "guide" | "lab" | "trigger", id: string }} Route */

/** @param {string | null | undefined} hash @param {readonly string[]} ids @param {Route} fallback @returns {Route} */
export function parseRoute(hash, ids, fallback) {
  const match = /^#?(guide|lab|trigger)(?:\/(.*))?$/.exec(hash ?? "");
  if (!match) return fallback;
  const mode = /** @type {Route["mode"]} */ (match[1]);
  const id = decodeURIComponent(match[2] ?? "");
  if (mode === "trigger") return { mode, id: TRIGGER_VIEWS.includes(id) ? id : TRIGGER_VIEWS[0] };
  if (ids.includes(id)) return { mode, id };
  return mode === "guide" ? { mode, id: START } : { mode, id: ids.includes(fallback.id) ? fallback.id : ids[0] };
}

/** @param {Route} route */
export const routeHash = route => `#${route.mode}/${route.id}`;

/** Guide and test share the operation; the test has no quick start, so it opens the first operation.
 * The trigger mode opens on its first view, and leaving it opens the quick start or the first operation.
 * @param {Route} route @param {Route["mode"]} mode @param {readonly string[]} ids @returns {Route} */
export function switchMode(route, mode, ids) {
  if (mode === "trigger") return { mode, id: route.mode === "trigger" ? route.id : TRIGGER_VIEWS[0] };
  const id = route.mode === "trigger" ? mode === "guide" ? START : ids[0] : route.id;
  return { mode, id: mode === "lab" && id === START ? ids[0] : id };
}
