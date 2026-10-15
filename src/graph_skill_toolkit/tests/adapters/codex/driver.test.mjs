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

test("Codex context updates and removes only this page's keys",async()=>{
  const h=host({updateModelContext:{structuredContent:{}}});
  await h.adapter.invoke("context.set",{key:"one",content:{node:"greet"}});
  await h.adapter.invoke("context.set",{key:"two",content:2});
  await h.adapter.invoke("context.remove",{key:"one"});
  assert.deepEqual(h.calls.map(([,value])=>value.structuredContent.toolkitContext),[
    {one:{node:"greet"}},{one:{node:"greet"},two:2},{two:2},
  ]);
});

test("Codex blocks stale context snapshots after a lost update receipt until reconnection", async () => {
  const updates = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }),
    updateModelContext: async payload => {
      updates.push(payload.structuredContent.toolkitContext);
      if (updates.length === 3) throw new Error("reply lost after possible host acceptance");
      return {};
    } };
  const driver = codexAdapter(app);
  await driver.invoke("context.set", { key: "a", content: 1 });
  await driver.invoke("context.set", { key: "b", content: 2 });
  await assert.rejects(driver.invoke("context.remove", { key: "a" }), /reply lost/);
  assert.equal((await driver.invoke("context.remove", { key: "b" })).status, "rejected");
  assert.equal((await driver.invoke("context.set", { key: "c", content: 3 })).status, "rejected");
  assert.deepEqual(updates, [{ a: 1 }, { a: 1, b: 2 }, { b: 2 }]);
  assert.equal((await codexAdapter(app).invoke("context.set", { key: "fresh", content: 4 })).status, "completed");
  assert.deepEqual(updates.at(-1), { fresh: 4 });
});

test("Codex known rejection keeps the last confirmed context writable", async () => {
  const updates = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }),
    updateModelContext: async payload => {
      updates.push(payload.structuredContent.toolkitContext);
      if (updates.length === 1) throw Object.assign(new Error("host rejected"), { code: -32600 });
      return {};
    } };
  const driver = codexAdapter(app);
  await assert.rejects(driver.invoke("context.set", { key: "rejected", content: 1 }), error => error.outcome === "rejected");
  assert.equal((await driver.invoke("context.set", { key: "accepted", content: 2 })).status, "completed");
  assert.deepEqual(updates, [{ rejected: 1 }, { accepted: 2 }]);
});

test("Codex internal host error cannot unlock stale context writes", async () => {
  const updates = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }),
    updateModelContext: async payload => {
      updates.push(payload.structuredContent.toolkitContext);
      if (updates.length === 3) throw Object.assign(new Error("internal failure after possible apply"), { code: -32603 });
      return {};
    } };
  const driver = codexAdapter(app);
  await driver.invoke("context.set", { key: "a", content: 1 });
  await driver.invoke("context.set", { key: "b", content: 2 });
  await assert.rejects(driver.invoke("context.remove", { key: "a" }), error => error.code === -32603 && error.outcome !== "rejected");
  assert.equal((await driver.invoke("context.remove", { key: "b" })).status, "rejected");
  assert.deepEqual(updates, [{ a: 1 }, { a: 1, b: 2 }, { b: 2 }]);
});

test("Codex display-mode request returns the host's mode without claiming focus",async()=>{
  const h=host({});
  const result=await h.adapter.invoke("views.requestDisplayMode",{mode:"fullscreen"});
  assert.equal(result.status,"completed");
  assert.deepEqual(result.data,{mode:"fullscreen"});
  assert.deepEqual(h.calls,[["display",{mode:"fullscreen"}]]);
  assert.equal((await h.adapter.invoke("views.requestDisplayMode",{mode:"pip"})).status,"unsupported");
});
