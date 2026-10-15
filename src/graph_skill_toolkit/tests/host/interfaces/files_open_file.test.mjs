import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { mcpCapabilities } from "../../../plugin_base/adapters/codex/driver/registry.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { mcpConnection } from "../../../plugin_base/adapters/codex/connection/index.mjs";
import { nativeCapabilities, executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";

const action = "files.openFile";
const file = "C:/project with spaces/技能/SKILL.md";

function pair() {
  const left = { start: async () => {} }, right = { start: async () => {} };
  left.send = async message => queueMicrotask(() => right.onmessage?.(message));
  right.send = async message => queueMicrotask(() => left.onmessage?.(message));
  left.close = async () => left.onclose?.();
  right.close = async () => right.onclose?.();
  return { left, right };
}

test("file request validates an absolute path and optional positive line without a Graph root", () => {
  assert.deepEqual(validateArguments(action, {path:file,line:1}), {path:file,line:1});
  for (const args of [{path:"relative.txt"},{path:""},{path:file,line:0},{path:file,line:1.5},{path:file,line:"1"}]) {
    assert.throws(() => validateArguments(action,args));
  }
  assert.throws(() => validateArguments(action,{path:file,key:"C:/project"}), /未知的宿主接口参数/);
});

test("Codex advertised file extension sends one native request through the official SDK", async t => {
  const {left,right}=pair(), calls=[];
  const bridge=new AppBridge(null,{name:"chatgpt",version:"3.2"},{experimental:{"openai/files":{}}});
  bridge.setRequestHandler("openai/files/open", {params:z.object({path:z.string()})}, async request => {
    calls.push(request);
    return {opened:true};
  });
  const app=new App({name:"Graph canvas",version:"0.3.5"},{},{autoResize:false});
  const connection=mcpConnection(app,{transport:left});
  t.after(async()=>{await connection.dispose();await bridge.close();});
  await bridge.connect(right);
  await connection.connect({receive(){},fail:assert.fail});
  const cap=mcpCapabilities(app.getHostCapabilities())[action];
  assert.equal(cap.state,"available");
  assert.equal(cap.constraints.lineNavigation,false);
  const adapter=codexAdapter(app);
  const result=await adapter.invoke(action,{path:"C:\\project with spaces\\技能\\SKILL.md"});
  assert.equal(result.status,"accepted");
  assert.deepEqual(calls,[{path:file}]);
  assert.equal((await adapter.invoke(action,{path:file,line:4})).status,"unsupported");
  assert.equal(calls.length,1);
});

test("Codex without the file declaration cannot dispatch, and a host error is not success", async () => {
  const calls=[], app={getHostCapabilities:()=>({}),getHostContext:()=>({}),request:async request=>{calls.push(request);return {isError:true};}};
  assert.equal(mcpCapabilities(app.getHostCapabilities())[action].state,"unavailable");
  assert.equal((await codexAdapter(app).invoke(action,{path:file})).status,"unsupported");
  assert.equal(calls.length,0);
  app.getHostCapabilities=()=>({experimental:{"openai/files":{}}});
  assert.equal((await codexAdapter(app).invoke(action,{path:file})).status,"error");
  assert.equal(calls.length,1);
});

test("Claude calls the listed native file-pane tool with flat arguments and only reports acceptance", async () => {
  const tools=[{name:"mcp__ccd_view__show_pane",mcp:true}], calls=[];
  const api={session:{id:async()=>"session-a"},tool:{list:async()=>tools,call:async input=>{
    calls.push(input);
    return {result:{content:[{type:"text",text:'Showing the file pane.\n{"views":[{"placement":"primary"}],"open_panes":["file","preview"]}'}]}};
  }}};
  const state=createModState(), bridge={url:"http://127.0.0.1:12345",token:"x",key:null};
  assert.equal(nativeCapabilities(tools)[action].state,"available");
  assert.equal(nativeCapabilities(tools)[action].constraints.lineNavigation,true);
  const result=await executeBridgeAction(api,state,bridge,{id:"open1",action,args:{path:file,line:3},key:null});
  assert.equal(result.status,"accepted");
  assert.match(result.message,/实际显示效果需观察/);
  assert.deepEqual(calls,[{tool:"mcp__ccd_view__show_pane",pane:"file",path:file,line:3}]);
  tools.splice(0);
  assert.equal(nativeCapabilities(tools)[action].state,"unavailable");
  assert.equal((await executeBridgeAction(api,state,bridge,{id:"open2",action,args:{path:file},key:null})).status,"unsupported");
  assert.equal(calls.length,1);
});

test("Claude refuses a changed session or host denial before claiming file display", async () => {
  const tools=[{name:"mcp__ccd_view__show_pane",mcp:true}];
  let session="one", calls=0;
  const api={session:{id:async()=>session},tool:{list:async()=>tools,call:async()=>{calls++;return {deny:"Not allowed"};}}};
  const state=createModState(), bridge={url:"http://127.0.0.1:12345",token:"x",key:null};
  const request={id:"open3",action,args:{path:file},key:null};
  await assert.rejects(executeBridgeAction(api,state,bridge,request),error=>error.outcome==="rejected");
  assert.equal(calls,1);
  api.tool.list=async()=>{session="two";return tools;};
  await assert.rejects(executeBridgeAction(api,state,bridge,{...request,id:"open4"}),error=>error.outcome==="not-sent");
  assert.equal(calls,1);
});
