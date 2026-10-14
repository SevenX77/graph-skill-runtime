import assert from "node:assert/strict";
import test from "node:test";
import { HOST_ACTIONS, INTERFACES } from "../../ports/host/catalog.mjs";
import { validateArguments, validateCapabilities, validateResult, failureResult } from "../../ports/host/contract.mjs";
import { operations as codexOperations } from "../../adapters/codex/driver/registry.mjs";
import { operations as claudeOperations } from "../../adapters/claude/mod/operations/registry.mjs";

test("every public host interface accepts its portable generic sample without a Graph Skill root", () => {
  assert.equal(new Set(HOST_ACTIONS).size,15);
  for (const entry of INTERFACES) assert.deepEqual(validateArguments(entry.id,entry.sample),entry.sample,entry.id);
  for (const registry of [codexOperations, claudeOperations]) {
    assert.deepEqual(Object.keys(registry).sort(), [...HOST_ACTIONS].sort());
    for (const action of HOST_ACTIONS) assert.equal(typeof registry[action].capability, "function", action);
  }
});

test("Port rejects hidden graph binding, malformed paths and nonportable input before dispatch", () => {
  for (const [action,args] of [
    ["files.openFile",{path:"relative.md"}],
    ["files.revealDirectory",{path:"C:/skill",skillRoot:"C:/skill"}],
    ["conversation.submitMessage",{text:" "}],
    ["tools.call",{tool:{name:"inspect"},arguments:[]}],
    ["views.open",{resource:{kind:"web",url:"file:///private"},reuseKey:"file",activate:true}],
    ["context.set",{key:"__proto__",content:{}}],
    ["views.requestDisplayMode",{mode:"focus"}],
  ]) assert.throws(()=>validateArguments(action,args),undefined,action);
  const cycle={}; cycle.self=cycle;
  assert.throws(()=>validateArguments("context.set",{key:"cycle",content:cycle}),/JSON/);
});

test("capability status has three explicit states and absent entries remain unknown", () => {
  const caps=validateCapabilities({"tools.call":{state:"available",detail:"direct",scope:"originating-server"},"files.revealDirectory":{state:"unavailable",detail:"no file browser API"}});
  assert.equal(caps["tools.call"].state,"available");
  assert.equal(caps["files.revealDirectory"].state,"unavailable");
  assert.equal(caps["views.open"].state,"unknown");
  assert.throws(()=>validateCapabilities({"tools.call":{available:true,detail:"legacy"}}));
  assert.deepEqual(validateResult({status:"accepted",message:"queued"}),{status:"accepted",message:"queued"});
  assert.equal(failureResult(new Error("lost reply"),true).status,"pending");
});
