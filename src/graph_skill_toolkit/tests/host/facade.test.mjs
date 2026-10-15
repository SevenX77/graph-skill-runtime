import assert from "node:assert/strict";
import test from "node:test";
import { hostAdapter } from "../../plugin_base/adapters/facade/index.mjs";
import { createHostAdapter } from "../../plugin_base/adapters/factory/index.mjs";
import { capability } from "../../plugin_base/ports/host/catalog.mjs";
import { launchHostInfo } from "../../plugin_base/adapters/launch/index.mjs";

const identity = { name: "chatgpt", version: "26.1007", client_type: "codex_desktop" };
const launch = launchHostInfo({ clientInfo: identity });
const snapshot = { hostInfo: launch, graph: { id:"main", nodes:[], edges:[], width:100, height:100 }, skillRoot:"C:/skill" };
function fixture({ identity: current = identity, status = "available", result = {status:"completed",message:"done"} } = {}) {
  let inspect = {transport:"mcp-app",connected:true,identity:current,capabilities:{"conversation.submitMessage":capability(status,"native message")}};
  const calls=[], selected=[];
  const connection = {connect:async ({receive})=>receive(snapshot),inspect:async()=>inspect,dispose:async()=>{}};
  const driver = info => {selected.push(info);return {invoke:async (action,args)=>{calls.push({action,args});return result;}};};
  const adapter=hostAdapter(()=>connection,driver,launch);
  return {adapter,calls,selected,update:value=>{inspect=value;}};
}

test("public adapter exposes one generic entry and typed namespace methods", async () => {
  const f=fixture();
  const received=[];
  await f.adapter.connect({receive:value=>received.push(value),fail:assert.fail});
  assert.equal(received[0].graph.id,"main");
  assert.equal((await f.adapter.host.getInfo()).id,"codex");
  assert.equal(f.adapter.hostName,"ChatGPT(Codex)");
  assert.equal((await f.adapter.host.getCapabilities())["conversation.submitMessage"].state,"available");
  assert.equal((await f.adapter.conversation.submitMessage({text:"hello"})).status,"completed");
  assert.deepEqual(f.calls,[{action:"conversation.submitMessage",args:{text:"hello"}}]);
  await f.adapter.dispose();
  assert.equal(f.adapter.state,"disposed");
});

test("unknown host, missing capability and malformed args do not reach a driver", async () => {
  const unknown=fixture({identity:{name:"other",version:"1"}});
  await unknown.adapter.connect({receive(){},fail:assert.fail});
  assert.equal(unknown.adapter.hostId,"unknown");
  assert.equal((await unknown.adapter.invoke("conversation.submitMessage",{text:"hello"})).status,"unsupported");
  assert.equal(unknown.selected.length,0);
  const unavailable=fixture({status:"unknown"});
  await unavailable.adapter.connect({receive(){},fail:assert.fail});
  assert.equal((await unavailable.adapter.invoke("conversation.submitMessage",{text:"hello"})).data.capabilityState,"unknown");
  assert.equal((await unavailable.adapter.invoke("conversation.submitMessage",{text:" ",skillRoot:"C:/skill"})).status,"error");
  assert.equal((await unavailable.adapter.invoke("shell",{})).status,"unsupported");
  assert.equal(unavailable.calls.length,0);
});

test("the facade captures portable arguments before asynchronous capability inspection", async () => {
  let release;
  const gate=new Promise(resolve=>{release=resolve;});
  const f=fixture();
  await f.adapter.connect({receive(){},fail:assert.fail});
  const original=f.adapter.capabilities;
  f.adapter.capabilities=async()=>{await gate;return original.call(f.adapter);};
  const args={text:"first"};
  const result=f.adapter.invoke("conversation.submitMessage",args);
  args.text="forged";
  release();
  assert.equal((await result).status,"completed");
  assert.equal(f.calls[0].args.text,"first");
});

test("a changed session identity revokes authority and cannot switch the page to another host", async () => {
  const f=fixture(); await f.adapter.connect({receive(){},fail:assert.fail});
  f.update({transport:"mcp-app",connected:true,identity:{...identity,name:"other"},capabilities:{"conversation.submitMessage":capability("available","test")}});
  const caps=await f.adapter.capabilities();
  assert.equal(f.adapter.hostId,"unknown");
  assert.equal(caps["conversation.submitMessage"].state,"unknown");
  assert.equal((await f.adapter.invoke("conversation.submitMessage",{text:"not sent"})).status,"unsupported");
  assert.equal(f.calls.length,0);
});

test("a dispatched action with a lost response retains pending rather than replaying", async () => {
  const f=fixture({result:{status:"pending",message:"unknown",requestId:"request_1"}});
  await f.adapter.connect({receive(){},fail:assert.fail});
  const result=await f.adapter.invoke("conversation.submitMessage",{text:"once"});
  assert.equal(result.status,"pending"); assert.equal(result.requestId,"request_1");
  assert.equal(f.calls.length,1);
});

test("factory selects transport from launch metadata, then waits for live identity", async () => {
  let codex=0,claude=0;
  const page={querySelector:()=>({textContent:JSON.stringify(snapshot)})};
  const adapter=createHostAdapter({document:page,window:{parent:{}},connections:{"mcp-app":()=>({connect:async ({receive})=>receive(snapshot),inspect:async()=>({transport:"mcp-app",connected:true,identity,capabilities:{"conversation.submitMessage":capability("available","test")}}),dispose(){}})},drivers:{codex:()=>{codex++;return {invoke:async()=>({status:"completed",message:"done"})};},claude:()=>{claude++;return {invoke:async()=>({status:"completed",message:"wrong"})};}}});
  await adapter.connect({receive(){},fail:assert.fail});
  assert.equal(codex,1);assert.equal(claude,0);
  assert.equal((await adapter.invoke("conversation.submitMessage",{text:"hello"})).status,"completed");
  await adapter.dispose();
});
