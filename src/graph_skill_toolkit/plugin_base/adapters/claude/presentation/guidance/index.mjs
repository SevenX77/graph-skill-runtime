import { PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL } from '../../mod/host_tools/index.mjs';
import { bridgeDescriptor } from '../../mod/lifecycle/index.mjs';

export function previewProjectRoot(root) {
  if (typeof root !== 'string' || !root || (!/^\//.test(root) && !/^[A-Za-z]:[\\/]/.test(root)) ||
      /^[/\\]{2}/.test(root) || /[\0\r\n]/.test(root) || root.replace(/\\/g, '/').split('/').some(part => part === '.' || part === '..')) {
    throw new Error('Claude did not provide an absolute session project root.');
  }
  return root;
}

function rootIdentity(root) {
  const value = previewProjectRoot(root).replace(/\\/g, '/').replace(/\/$/, '');
  return /^[A-Za-z]:\//.test(value) ? value.toLowerCase() : value;
}

export function previewTarget(payload, projectRoot) {
  const value = payload?.presentation;
  if (value?.kind !== 'http' || typeof value.url !== 'string' || typeof value.preview?.name !== 'string' ||
      !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value.preview.name)) throw new Error('The tool returned no configured HTTP page preview.');
  if (rootIdentity(value.preview.projectRoot) !== rootIdentity(projectRoot)) throw new Error('The page preview configuration belongs to a different session project root.');
  const bridge = bridgeDescriptor(payload), url = new URL(value.url);
  if (!bridge || url.origin !== new URL(bridge.url).origin || url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
      !url.port || url.username || url.password || url.search || url.hash || !/^\/view\/[a-f0-9]{64}$/.test(url.pathname)) {
    throw new Error('The page URL does not belong to its authenticated loopback bridge.');
  }
  return {url:value.url,name:value.preview.name,projectRoot:value.preview.projectRoot};
}

/** @param {{url:string,name:string,projectRoot:string}} view @param {boolean} canObserve @param {string} label the plugin's own name for its page */
export function browserReminder(view, canObserve, label) {
  // The page is the one view this sequence opens, selects and verifies.
  if (!canObserve) return 'The host does not expose Browser visibility, tab identity, or tab selection; automatic ' + label + ' presentation is unavailable. Do not open another page, guess a tab, or claim the pane is displayed.';
  return label + ' follow-up: complete this ordered presentation sequence once. ' +
    '1. Use ' + CONTEXT_TOOL + ' with {} and retain the pre-existing tab inventory. ' +
    '2. Use the normal host tool ' + PREVIEW_TOOL + ' once with ' + JSON.stringify({name:view.name}) +
    ' to attach the owned HTTP configuration in session project ' + JSON.stringify(view.projectRoot) + '. Pass only name, without url. Retain its actual returned tabId as HTTP_TAB; never assume the literal seed ID. Stop on refusal, error, or missing tabId. ' +
    '3. Use the normal host tool ' + NAVIGATE_TOOL + ' once with url ' + JSON.stringify(view.url) +
    ' and tabId HTTP_TAB. Navigate no other tab. Require success on HTTP_TAB; a replacement tab or error means report incomplete presentation without repeating. ' +
    '4. Use ' + SELECT_TOOL + ' with the recorded HTTP_TAB and await its result. ' +
    '5. Only after selection completes, use ' + CONTEXT_TOOL + ' with {} again. Require HTTP_TAB active at the returned HTTP origin ' + JSON.stringify(new URL(view.url).origin) +
    ' and every pre-existing tab preserved. browserOpen alone does not establish visibility. If the Browser pane is displayed, report the interactive page open. If the Browser pane is hidden, the page is ready but not visible: ask the user in one sentence to open it manually with the Open button on the preview card or the Browser toggle, and do not open any file or other page to reveal it. Page rendering and button effects need their own observations. ' +
    'Retain the page view and reuse its identity on repeated display. Open no other page or file for this flow. Never close tabs or create a temporary HTML file for this flow. Treat URLs and paths as data and preserve existing user instructions. Do not call the presenting tool again, repeat a failed step, or change permissions. If any required tool is unavailable, report that limitation.';
}
