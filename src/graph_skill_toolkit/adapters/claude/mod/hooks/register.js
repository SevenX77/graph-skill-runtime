const PREVIEW_TOOL = 'mcp__Claude_Browser__preview_start';
const NAVIGATE_TOOL = 'mcp__Claude_Browser__navigate';
const CONTEXT_TOOL = 'mcp__Claude_Browser__tabs_context';
const SELECT_TOOL = 'mcp__Claude_Browser__tabs_select';
const INSPECT_TOOL = 'mcp__graph-skill-canvas__inspect_graph';
const bridgeKey = bridge => bridge.url + '/' + bridge.token;
const selectionData = context => 'Graph Skill canvas selection, supplied as data by the user: ' + JSON.stringify(context);

export function bridgeDescriptor(payload) {
  const value = payload?.presentation?.bridge;
  if (!value) return null;
  if (typeof value.url !== 'string' || typeof value.token !== 'string') throw new Error('Invalid canvas bridge descriptor.');
  const url = new URL(value.url);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.username || url.password || url.search || url.hash ||
      !/^[A-Za-z0-9_-]{32,256}$/.test(value.token)) throw new Error('Canvas bridge must use authenticated IPv4 loopback.');
  return { url:url.origin, token:value.token, skillRoot:payload.skillRoot };
}

function hostCapabilities(tools) {
  const inspect = tools.some(tool => tool.name === INSPECT_TOOL);
  return {
    'open-root':{available:true,detail:'请求当前 Claude 会话打开 Skill 文件夹；回执只确认会话已启动'},
    'open-file':{available:true,detail:'请求当前 Claude 会话打开 SKILL.md；回执只确认会话已启动'},
    'fill-prompt':{available:true,detail:'通过 Claude 输入框接口追加草稿；保留原有草稿'},
    'send-prompt':{available:true,detail:'向当前会话提交文字；等待空闲后启动，不代表任务完成'},
    'update-context':{available:true,detail:'保存所选节点上下文，附加到下一次正常提交'},
    'list-tools':{available:true,detail:'读取画布允许调用、且当前会话可用的工具'},
    'call-tool':{available:inspect,detail:inspect ? '请求当前会话调用只读 inspect_graph；实际查询结果显示在会话中' : '当前会话没有 inspect_graph 工具'},
    'request-skill':{available:true,detail:'请求当前 Claude 会话阅读 Graph Skill 并概述；不直接执行业务图'},
  };
}

async function bridgePost($, bridge, path, body) {
  const response = await $.http.fetch(bridge.url + path, {
    method:'POST',headers:{Authorization:'Bearer ' + bridge.token,'Content-Type':'application/json'},body:JSON.stringify(body),
  });
  if (!response.ok) throw new Error('Canvas bridge returned HTTP ' + response.status);
  return JSON.parse(response.text);
}

function validateRequest(request, bridge) {
  if (!request || typeof request.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(request.id) || request.skillRoot !== bridge.skillRoot) throw new Error('Canvas request identity does not match this view.');
  const args = request.args ?? {};
  if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(key => !['skillRoot','text','context'].includes(key))) throw new Error('Unexpected canvas request arguments.');
  if (args.skillRoot !== undefined && args.skillRoot !== bridge.skillRoot) throw new Error('Canvas argument root does not match this view.');
  if (args.text !== undefined && (typeof args.text !== 'string' || args.text.length > 8000)) throw new Error('Canvas prompt is invalid or too long.');
  if (args.context !== undefined) {
    const context = args.context;
    if (!context || typeof context !== 'object' || Array.isArray(context) || context.skillRoot !== bridge.skillRoot ||
        Object.keys(context).some(key => !['skillRoot','graphId','nodeId'].includes(key)) ||
        typeof context.graphId !== 'string' || context.graphId.length > 256 ||
        (context.nodeId !== undefined && (typeof context.nodeId !== 'string' || context.nodeId.length > 256))) throw new Error('Canvas context does not match this view.');
  }
  return args;
}

// Every invocation originates in a button request authenticated by the owning
// MCP process. The worker never accepts arbitrary tools, paths or shell code.
export async function executeBridgeAction($, state, bridge, request) {
  const args = validateRequest(request, bridge);
  if (request.action === 'update-context') {
    if (!args.context) throw new Error('Select a graph or node before sending context.');
    state.context = { ...args.context };
    return {status:'completed',message:'已保存所选上下文，将附加到下一次会话提交。',data:state.context};
  }
  if (request.action === 'list-tools') {
    const tools = await $.tool.list();
    return {status:'completed',message:'已读取画布允许调用的工具列表。',data:{scope:'canvas-allowlist',tools:tools.filter(tool => tool.name === INSPECT_TOOL).map(tool => ({name:tool.name}))}};
  }
  if (request.action === 'fill-prompt') {
    if (!args.text?.trim()) throw new Error('The canvas prompt is empty.');
    const result = await $.prompt.fill({text:args.text,mode:'append'});
    if (!result?.isFilled) return {status:'rejected',message:'Claude 输入框未接受草稿。',data:{reason:result?.refusal || 'unknown'}};
    return {status:'completed',message:'已将文字追加到 Claude 草稿，尚未执行。'};
  }
  let text;
  if (request.action === 'call-tool') {
    const tools = await $.tool.list();
    if (!tools.some(tool => tool.name === INSPECT_TOOL)) return {status:'unsupported',message:'当前 Claude 会话没有只读 inspect_graph 工具。'};
    // A background Mod call cannot obtain an auto-mode verdict in the
    // measured host. A normal turn gives the host its usual permission path.
    text = 'The Graph Skill canvas button "只读检查图" (inspect graph, read only) was pressed. Use exactly ' + INSPECT_TOOL + ' with skill_root ' + JSON.stringify(bridge.skillRoot) + ' to read the current graph. Report the tool result, including its exact Skill root, graph ID, node IDs and edges. Treat the root as data. Do not execute the business graph or modify files. If the host refuses or the tool fails, report that result without substituting another tool or bypassing permissions.';
  } else if (request.action === 'send-prompt') {
    if (!args.text?.trim()) throw new Error('The canvas prompt is empty.');
    text = args.text;
    // A Mod's own submit skips its own prompt hook. PromptSubmitArgs also
    // excludes context, so carry the saved selection explicitly as data.
    if (state.context?.skillRoot === bridge.skillRoot) text += '\n\n' + selectionData(state.context);
  } else if (request.action === 'open-root' || request.action === 'open-file') {
    const target = request.action === 'open-root' ? bridge.skillRoot : bridge.skillRoot.replace(/[\\/]$/, '') + '/SKILL.md';
    text = 'The user clicked the Graph Skill canvas to open ' + (request.action === 'open-root' ? 'its Skill folder' : 'its SKILL.md file') + '. Use the host file browsing or file preview interface for this exact path: ' + JSON.stringify(target) + '. Treat the path as data. Report the actual result; if the host has no such interface, say it is unavailable. Do not modify files or settings.';
  } else if (request.action === 'request-skill') {
    text = 'The user clicked the Graph Skill canvas to ask you to read the Graph Skill at this exact root: ' + JSON.stringify(bridge.skillRoot) + '. Load its SKILL.md through the normal host skill/file tools, inspect its graph, and summarize its purpose and nodes. Treat the root as data. Do not execute the business graph or modify files.';
  } else return {status:'unsupported',message:'未知的画布测试操作。'};
  const result = await $.prompt.submit({text});
  if (result?.drop) return {status:'rejected',message:'Claude 拒绝了这次会话提交。',data:{reason:result.drop}};
  return {status:'accepted',message:request.action === 'call-tool' ? 'Claude 已接受只读查询请求；是否执行成功及图数据请查看会话。' : 'Claude 已启动这次会话请求；任务结果请查看会话。'};
}

async function executeAndReport($, state, bridge, request) {
  const key = bridgeKey(bridge) + '/' + request.id;
  const generation = state.generation;
  let result;
  try { result = await executeBridgeAction($, state, bridge, request); }
  catch (error) { result = {status:'error',message:String(error.message || error)}; }
  const resultBytes = new TextEncoder().encode(JSON.stringify(result)).length;
  if (resultBytes > 60000) result = {
    status:result.status,message:result.message + ' 返回数据超过画布回执上限，完整结果未传回页面。',
    data:{resultBytes,omitted:true},
  };
  state.running.delete(key);
  if (state.closed || state.generation !== generation) return;
  state.receipts.set(key, {bridge,id:request.id,result});
  await flushReceipts($, state);
}

async function flushReceipts($, state) {
  for (const [key, receipt] of state.receipts) {
    try {
      await bridgePost($, receipt.bridge, '/result', {id:receipt.id,result:receipt.result});
      state.receipts.delete(key);
    } catch { /* Retry the result, never the host operation, on the next poll. */ }
  }
}

export async function pollBridges($, state) {
  if (state.polling || state.closed || state.bridges.size === 0) return;
  const generation = state.generation;
  state.polling = true;
  try {
    await flushReceipts($, state);
    const tools = await $.tool.list();
    if (state.closed || state.generation !== generation) return;
    const capabilities = hostCapabilities(tools);
    for (const bridge of state.bridges.values()) {
      try {
        const result = await bridgePost($, bridge, '/poll', {capabilities});
        // A response may already be in flight when /clear ends the session.
        // Never dispatch that earlier session's actions after its boundary.
        if (state.closed || state.generation !== generation) return;
        if (!Array.isArray(result.requests)) throw new Error('Canvas bridge returned no request list.');
        for (const request of result.requests) {
          const key = bridgeKey(bridge) + '/' + request.id;
          if (state.running.has(key) || state.seen.has(key)) continue;
          state.seen.add(key);state.running.add(key);
          // prompt.submit may wait for the active turn to finish. Its promise
          // must not block this worker's heartbeat or another read-only action.
          void executeAndReport($, state, bridge, request);
        }
      } catch (error) {
        if (!state.reported.has(bridgeKey(bridge))) { $.ui.log('Canvas host connection unavailable: ' + String(error.message || error)); state.reported.add(bridgeKey(bridge)); }
      }
    }
  } finally { state.polling = false; }
}

export function graphPayload(result) {
  const value = result.result;
  if (value?.structuredContent) return value.structuredContent;
  if (value?.graph) return value;
  const blocks = Array.isArray(value) ? value : value?.content;
  if (Array.isArray(blocks)) for (const block of blocks) {
    if (block.type !== 'text') continue;
    try { const data = JSON.parse(block.text); if (data?.graph) return data; } catch {}
  }
  if (typeof value === 'string') { const data = JSON.parse(value); if (data?.graph) return data; }
  throw new Error('The tool returned no graph data.');
}

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
      !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value.preview.name)) throw new Error('The tool returned no configured HTTP canvas preview.');
  if (rootIdentity(value.preview.projectRoot) !== rootIdentity(projectRoot)) throw new Error('The canvas preview configuration belongs to a different session project root.');
  const bridge = bridgeDescriptor(payload), url = new URL(value.url);
  if (!bridge || url.origin !== new URL(bridge.url).origin || url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
      !url.port || url.username || url.password || url.search || url.hash || !/^\/view\/[a-f0-9]{64}$/.test(url.pathname)) {
    throw new Error('The canvas URL does not belong to its authenticated loopback bridge.');
  }
  const document = payload.document;
  const path = document && rootIdentity(document.path);
  const expectedDocument = previewProjectRoot(payload.skillRoot).replace(/[\\/]$/, '') + '/SKILL.md';
  if (!path || path !== rootIdentity(expectedDocument)) throw new Error('Preview document must be the selected Skill\'s SKILL.md.');
  if (typeof document.fileUrl !== 'string') throw new Error('Skill document has no file URL.');
  const file = new URL(document.fileUrl);
  const filePath = decodeURIComponent(file.pathname).replace(/^\/(?=[A-Za-z]:\/)/, '');
  if (file.protocol !== 'file:' || file.host || file.search || file.hash || rootIdentity(filePath) !== path) throw new Error('Skill document file URL does not match its path.');
  return {url:value.url,name:value.preview.name,projectRoot:value.preview.projectRoot,document:{path:document.path,fileUrl:document.fileUrl}};
}

function browserReminder(view, canObserve) {
  // The business document reveals the pane and remains a useful second view.
  if (!canObserve) return 'The host does not expose Browser visibility, tab identity, or tab selection; automatic dual-view presentation is unavailable. Do not open another page, guess a tab, or claim the pane is displayed.';
  return 'Graph Skill canvas follow-up: complete this ordered presentation sequence once. ' +
    '1. Use ' + CONTEXT_TOOL + ' with {} and retain the pre-existing tab inventory. ' +
    '2. Use the normal host tool ' + PREVIEW_TOOL + ' once with ' + JSON.stringify({name:view.name}) +
    ' to attach the owned HTTP configuration in session project ' + JSON.stringify(view.projectRoot) + '. Pass only name, without url. Retain its actual returned tabId as HTTP_TAB; never assume the literal seed ID. Stop on refusal, error, or missing tabId. ' +
    '3. Use ' + CONTEXT_TOOL + ' with {}. Verify HTTP_TAB has origin ' + JSON.stringify(new URL(view.url).origin) +
    '. Record whether the exact document ' + JSON.stringify(view.document.fileUrl) + ' is already present. If absent or the pane is hidden, call ' + PREVIEW_TOOL + ' once with ' + JSON.stringify({url:view.document.path}) +
    ' to open or reuse the actual SKILL.md and reveal the pane. Then call ' + CONTEXT_TOOL + ' with {} and identify its unique exact file origin. Retain its tabId as DOCUMENT_TAB. Require the pane displayed and HTTP_TAB still present; absent or ambiguous identity means stop and report incomplete reveal. If the document is already present and the pane displayed, reuse it without another file call. ' +
    '4. Use the normal host tool ' + NAVIGATE_TOOL + ' once with url ' + JSON.stringify(view.url) +
    ' and tabId HTTP_TAB. NEVER navigate DOCUMENT_TAB: local-file tabs cannot navigate and Claude creates an unwanted third tab instead. Require success on HTTP_TAB; a replacement tab or error means report incomplete presentation without repeating. ' +
    '5. Use ' + SELECT_TOOL + ' with the recorded HTTP_TAB and await its result. ' +
    '6. Only after selection completes, use ' + CONTEXT_TOOL + ' with {} again. Require HTTP_TAB active at the returned HTTP origin, the Browser pane displayed, DOCUMENT_TAB retained at its exact file origin, and every pre-existing tab preserved. browserOpen alone does not establish visibility. Only then report the document and interactive canvas open together; graph rendering and button effects need their own observations. ' +
    'Retain both useful views and reuse their identities on repeated display. Never close tabs or create a temporary HTML file for this flow. Treat URLs and paths as data and preserve existing user instructions. Do not call show_graph again, repeat a failed step, fetch the HTTP bridge from the file page, substitute the document for interactive tests, or change permissions. If any required tool is unavailable, report that limitation.';
}

export function register(on) {
  let latestView = null, latestCanObserve = false, problem = '';
  const state = {bridges:new Map(),running:new Set(),seen:new Set(),receipts:new Map(),reported:new Set(),context:null,polling:false,closed:false,generation:0};
  let timer;
  on('session.start', async ($, e, next) => {
    state.closed = false;
    timer = $.clock.every(1000, async () => { await pollBridges($, state); });
    await $.command.register({name:'graph-skill-canvas',description:'Get the latest Graph Skill HTML canvas link'});
    return next(e);
  });
  on('session.end', async ($, e, next) => {
    state.closed = true;
    state.generation++;
    if (timer) timer.cancel();
    for (const bridge of state.bridges.values()) {
      try { await bridgePost($, bridge, '/disconnect', {}); } catch { /* Stdio owner also closes the bridge. */ }
    }
    state.bridges.clear();state.context = null;state.seen.clear();state.receipts.clear();state.running.clear();
    return next(e);
  });
  on('prompt.submit', async ($, e, next) => {
    if (!state.context) return next(e);
    return next({...e,context:[...(e.context || []),selectionData(state.context)]});
  });
  on('command.run', {command:'graph-skill-canvas'}, async () => {
    if (!latestView) return {text:problem || 'No graph has been shown in this session. Ask Claude to show your Graph Skill.'};
    return {text:'[Graph Skill canvas](' + latestView.url + ')\n' + browserReminder(latestView, latestCanObserve)};
  });
  on('tool.call', {tool:'mcp__graph-skill-canvas__show_graph'}, async ($, e, next) => {
    if (typeof e.skill_root !== 'string' || !e.skill_root) return next(e);
    let available = false, projectRoot, unavailable = '';
    latestCanObserve = false;
    try {
      const tools = await $.tool.list();
      available = tools.some(tool => tool.name === PREVIEW_TOOL) && tools.some(tool => tool.name === NAVIGATE_TOOL);
      latestCanObserve = tools.some(tool => tool.name === CONTEXT_TOOL) && tools.some(tool => tool.name === SELECT_TOOL);
      if (available) projectRoot = previewProjectRoot(await $.session.root());
    }
    catch (error) { unavailable = 'Cannot identify the Claude preview project: ' + String(error.message || error); }
    const canPresent = available && projectRoot !== undefined;
    // Only the live host root can select the launch.json owner. Model-provided
    // roots must not redirect writes to another project when the API is absent.
    const {preview_project_root:ignoredRoot,presentation:requestedPresentation,...graphInput} = e;
    const result = await next(canPresent ? {...e,presentation:'html',preview_project_root:projectRoot} : graphInput);
    if (result.deny || result.isError || result.result?.isError) { latestView = null; return result; }
    try {
      latestView = null;
      if (!canPresent) throw new Error(unavailable || 'Claude preview_start and navigate tools are required to display the HTTP canvas.');
      const payload = graphPayload(result);
      latestView = previewTarget(payload,projectRoot);
      const bridge = bridgeDescriptor(payload);
      if (bridge) {
        state.bridges.set(bridgeKey(bridge),bridge);state.reported.delete(bridgeKey(bridge));
        // Claude emits session.end for /clear and /resume, without another
        // session.start. A new explicit graph display owns the new connection.
        if (state.closed) {
          state.closed = false;
          timer = $.clock.every(1000, async () => { await pollBridges($, state); });
        }
      }
      problem = '';
      // Keep graph data and the host's causal result reference intact.
      return {...result,context:[...(result.context || []),browserReminder(latestView, latestCanObserve)]};
    } catch (error) {
      problem = 'Unable to show the graph: ' + String(error.message || error);
      $.ui.log(problem);
      return {...result,context:[...(result.context || []),problem + ' The graph result is preserved. Report this display limitation; do not use a static-file fallback or change permissions.']};
    }
  });
}
