// @ts-check
/** The lab page's two modes and its selection, kept in the URL hash so a
 * reload or a shared tab returns to the same place: `#guide/start`,
 * `#guide/composer.writeDraft`, `#lab/composer.writeDraft`. */

export const START = "start";
/** @typedef {{ mode: "guide" | "lab", id: string }} Route */

/** @param {string | null | undefined} hash @param {readonly string[]} ids @param {Route} fallback @returns {Route} */
export function parseRoute(hash, ids, fallback) {
  const match = /^#?(guide|lab)(?:\/(.*))?$/.exec(hash ?? "");
  if (!match) return fallback;
  const mode = /** @type {"guide" | "lab"} */ (match[1]);
  const id = decodeURIComponent(match[2] ?? "");
  if (ids.includes(id)) return { mode, id };
  return mode === "guide" ? { mode, id: START } : { mode, id: ids.includes(fallback.id) ? fallback.id : ids[0] };
}

/** @param {Route} route */
export const routeHash = route => `#${route.mode}/${route.id}`;

/** Switching mode keeps the operation; the lab has no quick start, so it opens the first operation instead.
 * @param {Route} route @param {"guide" | "lab"} mode @param {readonly string[]} ids @returns {Route} */
export const switchMode = (route, mode, ids) => ({ mode, id: mode === "lab" && route.id === START ? ids[0] : route.id });
