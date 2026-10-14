import assert from "node:assert/strict";
import test from "node:test";
import { claudeAdapter } from "../../../adapters/claude/driver/index.mjs";
import { httpConnection } from "../../../adapters/claude/connection/index.mjs";
import { createHostBridge } from "../../../adapters/claude/bridge/server.mjs";
import { nativeCapabilities, executeBridgeAction } from "../../../adapters/claude/mod/operations/index.mjs";
import { createModState, pollBridges } from "../../../adapters/claude/mod/lifecycle/index.mjs";
import { register } from "../../../adapters/claude/mod/hooks/register.js";

const root = "C:/business/hello-world";
const identity = { name: "Claude Code", version: "2.1.295", client_type: "claude_code", sessionId: "session-a", source: "claude-mod-session" };
const token = "a".repeat(64);
const bridge = { url: "http://127.0.0.1:12345", token, skillRoot: root };
const request = (id, action, args = {}) => ({ id, action, args, skillRoot: root });
const tools = [
  { name: "mcp__ccd_view__show_pane" }, { name: "mcp__Claude_Browser__preview_start" },
  { name: "mcp__Claude_Browser__navigate" }, { name: "mcp__Claude_Browser__tabs_context" },
  { name: "mcp__Claude_Browser__tabs_select" }, { name: "mcp__Claude_Browser__tabs_close" },
  { name: "mcp__graph-skill-canvas__inspect_graph", mcp: true }, { name: "Skill" },
];
function modApi(overrides = {}) {
  const calls = [], messages = [], fills = [];
  const api = {
    session: { id: async () => "session-a", version: async () => ({ version: "2.1.295" }) },
    tool: { list: async () => tools, call: async input => { calls.push(input); return input.tool === "Skill"
      ? { result: { success: true, commandName: input.skill, status: "inline" } } : { result: { ok: true } }; } },
    mcp: { call: async (server, name, args) => { calls.push({ server, name, args }); return { content: [{ type: "text", text: "done" }] }; } },
    prompt: { fill: async input => { fills.push(input); return { isFilled: true }; }, submit: async input => { messages.push(input); return { text: input.text }; } },
    ...overrides,
  };
  return { api, calls, messages, fills };
}

test("Claude Mod does not inject page context into unrelated ordinary prompts", () => {
  const registered = [];
  register(event => { registered.push(event); });
  assert.equal(registered.includes("prompt.submit"), false);
});

test("Claude browser uses its own same-origin token and preserves a pending request id", async () => {
  const requests = [];
  const fetch = async (url, options) => {
    requests.push({ url, options });
    return { ok: true, json: async () => url.endsWith("/capabilities")
      ? { connected: true, identity, capabilities: nativeCapabilities(tools) }
      : { status: "pending", message: "waiting", requestId: "request-1" } };
  };
  const connection = httpConnection({ snapshot: () => ({ hostBridge: { url: bridge.url, token } }), fetch, pageOrigin: bridge.url });
  await connection.connect({ receive() {}, fail: assert.fail });
  const adapter = claudeAdapter(connection, { requestId: () => "request-1" });
  assert.equal((await connection.inspect()).identity.sessionId, "session-a");
  assert.equal((await adapter.invoke("conversation.submitMessage", { text: "hello" })).requestId, "request-1");
  assert.equal((await adapter.getResult("request-1")).status, "pending");
  assert.ok(requests.every(item => item.options.headers.Authorization === "Bearer " + token));
  assert.equal(requests.filter(item => item.url.endsWith("/action")).length, 1);
  connection.dispose();
});

test("Claude browser refuses missing, foreign and transplanted bridge credentials", async () => {
  for (const value of [null, {url:"http://localhost:12345",token}, {url:bridge.url,token:"short"}]) {
    const connection = httpConnection({ snapshot: () => ({ hostBridge: value }), fetch: assert.fail, pageOrigin: bridge.url });
    await assert.rejects(connection.connect({ receive: assert.fail, fail: assert.fail }));
  }
  const foreign = httpConnection({ snapshot: () => ({ hostBridge: {url:bridge.url,token} }), fetch: assert.fail, pageOrigin:"http://127.0.0.1:54321" });
  await assert.rejects(foreign.connect({ receive: assert.fail, fail: assert.fail }), /同一来源/);
});

test("Claude lost HTTP reply stays pending with the original id and is not resent", async () => {
  let submissions = 0;
  const connection = {request: async path => { if (path === "/action") { submissions++; throw new Error("lost reply"); } return { status:"pending",message:"check" }; }};
  const adapter = claudeAdapter(connection, {requestId: () => "fixed-id"});
  const result = await adapter.invoke("conversation.submitMessage", {text:"hello"});
  assert.deepEqual({status:result.status,requestId:result.requestId},{status:"pending",requestId:"fixed-id"});
  await adapter.getResult("fixed-id");
  assert.equal(submissions,1);
});

test("Claude Mod executes generic draft, context and submit interfaces without graph-specific arguments", async () => {
  const state = createModState(), {api,fills,messages} = modApi();
  assert.equal((await executeBridgeAction(api,state,bridge,request("draft","composer.writeDraft",{text:"draft",mode:"replace"}))).status,"completed");
  assert.deepEqual(fills,[{text:"draft",mode:"replace"}]);
  await executeBridgeAction(api,state,bridge,request("context","context.set",{key:"selection",content:{nodeId:"greet"}}));
  assert.equal((await executeBridgeAction(api,state,bridge,request("send","conversation.submitMessage",{text:"run"}))).status,"accepted");
  assert.match(messages[0].text,/"nodeId":"greet"/);
  await executeBridgeAction(api,state,bridge,request("remove","context.remove",{key:"selection"}));
  await executeBridgeAction(api,state,bridge,request("send2","conversation.submitMessage",{text:"again"}));
  assert.equal(messages[1].text,"again");
  assert.equal(fills.length,1);
});

test("Claude tool catalog is session inventory and direct calls stay distinct from Agent messages", async () => {
  const state=createModState(), {api,calls,messages}=modApi();
  const listed=await executeBridgeAction(api,state,bridge,request("list","tools.list"));
  assert.equal(listed.data.scope,"session");
  assert.ok(listed.data.tools.some(item=>item.name==="mcp__graph-skill-canvas__inspect_graph"));
  assert.equal((await executeBridgeAction(api,state,bridge,request("direct","tools.call",{tool:{server:"graph-skill-canvas",name:"inspect_graph",scope:"session"},arguments:{skill_root:root}}))).status,"completed");
  assert.deepEqual(calls.at(-1),{skill_root:root,tool:"mcp__graph-skill-canvas__inspect_graph"});
  assert.equal(messages.length,0);
  assert.equal((await executeBridgeAction(api,state,bridge,request("missing","tools.call",{tool:{name:"not_available"},arguments:{}}))).status,"unsupported");
  assert.equal((await executeBridgeAction(api,state,bridge,request("skill","skills.invoke",{skill:"graph-skill-canvas",input:"open"}))).status,"completed");
});

test("Claude view handles are connection-scoped and never close a pre-existing tab", async () => {
  const state=createModState(), tabs=[{tabId:"existing",isActive:false,origin:"file:///existing"}], calls=[];
  const {api}=modApi({tool:{list:async()=>tools,call:async input=>{
    calls.push(input);
    if(input.tool.endsWith("tabs_context")) return {result:{tabs:tabs.map(item=>({...item}))}};
    if(input.tool.endsWith("tabs_select")){for(const tab of tabs)tab.isActive=tab.tabId===input.tabId;return {result:{}};}
    if(input.tool.endsWith("tabs_close")){tabs.splice(tabs.findIndex(tab=>tab.tabId===input.tabId),1);return {result:{}};}
    return {result:{}};
  }}});
  const listed=await executeBridgeAction(api,state,bridge,request("list","views.list"));
  const oldId=listed.data.views[0].viewId;
  assert.equal((await executeBridgeAction(api,state,bridge,request("close-old","views.close",{viewId:oldId}))).status,"unsupported");
  assert.equal((await executeBridgeAction(api,state,bridge,request("open","views.open",{resource:{kind:"web",url:"http://127.0.0.1:12345/graph"},reuseKey:"canvas",activate:true}))).status,"unsupported");
  assert.equal((await executeBridgeAction(api,state,bridge,request("activate","views.activate",{viewId:oldId}))).status,"completed");
  assert.equal(tabs.length,1);
  assert.equal(tabs[0].tabId,"existing");
  assert.equal(calls.filter(input=>input.tool.endsWith("preview_start")).length,0);
});

test("real loopback bridge isolates Claude sessions and refuses old canvas operations", async t => {
  const owner=createHostBridge({responseWaitMs:10}); t.after(()=>owner.close());
  const first=await owner.createView(root);
  const post=async (credential,path,body) => {
    const response=await fetch(credential.url+path,{method:"POST",headers:{Authorization:"Bearer "+credential.token,"Content-Type":"application/json"},body:JSON.stringify(body)});
    return {status:response.status,data:await response.json()};
  };
  await post(first.mod,"/poll",{identity,capabilities:nativeCapabilities(tools)});
  const queued=await post(first.browser,"/action",{id:"old",action:"composer.writeDraft",args:{text:"old",mode:"append"}});
  assert.equal(queued.data.status,"pending");
  const takeover=await post(first.mod,"/poll",{identity:{...identity,sessionId:"session-b"},capabilities:nativeCapabilities(tools)});
  assert.equal(takeover.status,409);
  const second=await owner.createView(root);
  assert.notEqual(second.browser.token,first.browser.token);
  const stale=await post(first.browser,"/action",{id:"stale",action:"composer.writeDraft",args:{text:"old",mode:"append"}});
  assert.equal(stale.data.status,"unsupported");
});

test("Mod ignores an old-session poll response before any host side effect", async () => {
  const state=createModState(); state.bridges.set("one",bridge);
  let session="session-a", submitted=0;
  const api={session:{id:async()=>session,version:async()=>({version:"2.1.295"})},tool:{list:async()=>tools},
    prompt:{submit:async()=>{submitted++;return {}}},http:{fetch:async url=>{
      if(url.endsWith("/poll")){session="session-b";return {ok:true,text:JSON.stringify({requests:[request("old","conversation.submitMessage",{text:"must not send"})]})};}
      return {ok:true,text:"{}"};
    }}};
  await pollBridges(api,state);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(submitted,0);
});
