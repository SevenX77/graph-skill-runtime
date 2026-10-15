import assert from "node:assert/strict";
import test from "node:test";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";

function host(capabilities={}) {
  const calls=[];
  const app={getHostCapabilities:()=>capabilities,getHostContext:()=>({availableDisplayModes:["fullscreen"]}),
    sendMessage:async value=>{calls.push(["message",value]);return {};},
    callServerTool:async value=>{calls.push(["tool",value]);return value.name === "list_page_tools"
      ? {structuredContent:{scope:"originating-server",complete:true,tools:[{name:"inspect_graph"}]}}
      : {content:[{type:"text",text:"done"}]};},
    updateModelContext:async value=>{calls.push(["context",value]);return {};},
    requestDisplayMode:async value=>{calls.push(["display",value]);return {mode:value.mode};}};
  return {adapter:codexAdapter(app,{originatingServer:"graph-skill-canvas"}),calls};
}

test("Codex direct server tool does not submit a message or delegate to an Agent",async()=>{
  const h=host({serverTools:{}});
  assert.equal((await h.adapter.invoke("tools.call",{tool:{server:"graph-skill-canvas",name:"inspect_graph"},arguments:{skill_root:"C:/skill"}})).status,"completed");
  assert.deepEqual(h.calls,[["tool",{name:"inspect_graph",arguments:{skill_root:"C:/skill"}}]]);
  assert.equal((await h.adapter.invoke("tools.call",{tool:{server:"another",name:"inspect_graph"},arguments:{}})).status,"unsupported");
  assert.equal(h.calls.length,1);
});

test("Codex lists only its originating MCP server tools and rejects session inventory", async () => {
  const h = host({ serverTools: {} });
  const result = await h.adapter.invoke("tools.list", { scope: "originating-server" });
  assert.equal(result.status, "completed");
  assert.equal(result.data.scope, "originating-server");
  assert.deepEqual(h.calls, [["tool", { name: "list_page_tools", arguments: {} }]]);
  assert.equal((await h.adapter.invoke("tools.list", { scope: "session" })).status, "unsupported");
  assert.equal(h.calls.length, 1);
});

test("Codex display-mode request returns the host's mode without claiming focus",async()=>{
  const h=host({});
  const result=await h.adapter.invoke("views.requestDisplayMode",{mode:"fullscreen"});
  assert.equal(result.status,"completed");
  assert.deepEqual(result.data,{mode:"fullscreen"});
  assert.deepEqual(h.calls,[["display",{mode:"fullscreen"}]]);
  assert.equal((await h.adapter.invoke("views.requestDisplayMode",{mode:"pip"})).status,"unsupported");
});
