import assert from "node:assert/strict";
import test from "node:test";
import { mcpCapabilities } from "../../../adapters/codex/driver/registry.mjs";
import { bridgeKey, createModState, pollBridges } from "../../../adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction, nativeCapabilities } from "../../../adapters/claude/mod/operations/index.mjs";

const bridge = { url: "http://127.0.0.1:43123", token: "a".repeat(64), skillRoot: "C:/example" };
const request = id => ({ id, skillRoot: bridge.skillRoot, action: "skills.list", args: {} });

function host(usage) {
  const calls = [];
  let sessionId = "session-1";
  const $ = {
    session: { id: async () => sessionId, usage: async args => {
      calls.push(["session.usage", args]);
      return typeof usage === "function" ? usage(() => { sessionId = "session-2"; }) : usage;
    } },
    tool: { list: async () => [{ name: "Skill" }], call: () => assert.fail("Skill invocation is not a name inventory") },
    prompt: { submit: () => assert.fail("messages cannot list native Skills") },
  };
  return { $, calls };
}

const context = skills => ({ context: { breakdown: skills === undefined ? {} : { skills } } });
const listing = (totalSkills, names) => ({ totalSkills, includedSkills: names.length,
  skillFrontmatter: names.map(name => ({ name, source: "plugin", tokens: 10 })) });

test("Codex MCP App never claims an originating-server tool list as host Skill names", () => {
  const capability = mcpCapabilities({ serverTools: {}, message: { text: {} } })["skills.list"];
  assert.equal(capability.state, "unknown");
  assert.match(capability.detail, /Skill/);
});

test("Claude lists only a complete native session Skill context summary without activating Skill", async () => {
  const { $, calls } = host(context(listing(2, ["graph-skill", "graph-skill-canvas"])));
  const state = createModState();
  const capability = nativeCapabilities([{ name: "Skill" }], { sessionUsage: true })["skills.list"];
  assert.equal(capability.state, "available");
  assert.equal(nativeCapabilities([], { sessionUsage: true })["skills.list"].state, "available"); // Skill invocation is not needed for this read.
  assert.equal(nativeCapabilities([])["skills.list"].state, "unknown"); // Tool inventory alone cannot confirm session.usage.
  assert.equal(capability.constraints.completeOnly, true);
  const result = await executeBridgeAction($, state, bridge, request("full"));
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data, { scope: "session-context", complete: true, skills: ["graph-skill", "graph-skill-canvas"] });
  // One probing call establishes the session capability, then one call reads the listing.
  assert.deepEqual(calls, [["session.usage", { breakdown: "summary" }], ["session.usage", { breakdown: "summary" }]]);
});

test("Claude returns an empty list only when the native breakdown exists and omits skills", async () => {
  const { $ } = host(context());
  const result = await executeBridgeAction($, createModState(), bridge, request("empty"));
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data.skills, []);
});

test("Claude refuses a token-budget truncated list rather than falsely marking names complete", async () => {
  const { $ } = host(context(listing(3, ["one", "two"])));
  const result = await executeBridgeAction($, createModState(), bridge, request("partial"));
  assert.equal(result.status, "unsupported");
  assert.deepEqual(result.data, { complete: false, totalSkills: 3, includedSkills: 2 });
  assert.equal(Object.hasOwn(result.data, "skills"), false);
});

test("Claude rejects missing or inconsistent native evidence and a missing usage method", async () => {
  const cases = [undefined, { context: {} }, context({ totalSkills: 2, includedSkills: 2, skillFrontmatter: [{ name: "one" }] }),
    context({ totalSkills: 1, includedSkills: 1, skillFrontmatter: [{ name: "" }] })];
  for (const [i, payload] of cases.entries()) {
    const { $ } = host(payload);
    const result = await executeBridgeAction($, createModState(), bridge, request("invalid-" + i));
    assert.equal(result.status, "error");
  }
  const { $ } = host(context());
  delete $.session.usage;
  assert.equal(nativeCapabilities([{ name: "Skill" }], { sessionUsage: false })["skills.list"].state, "unavailable");
  const result = await executeBridgeAction($, createModState(), bridge, request("missing-api"));
  assert.equal(result.status, "unsupported");
  assert.equal(result.data.capabilityState, "unavailable");
});


test("Claude heartbeat reports Skill listing only when the current session has usage", async () => {
  for (const supportsUsage of [false, true]) {
    const state = createModState(), requests = [];
    state.bridges.set(bridgeKey(bridge), bridge);
    const $ = { session: { id: async () => "session-1", version: async () => ({ version: "2.1.277" }),
        ...(supportsUsage ? { usage: async () => context(listing(0, [])) } : {}) },
      tool: { list: async () => [{ name: "Skill" }] },
      http: { fetch: async (url, options) => { requests.push({ url, body: JSON.parse(options.body) });
        return { ok: true, text: JSON.stringify({ requests: [] }) }; } },
    };
    await pollBridges($, state);
    const heartbeat = requests.find(call => call.url.endsWith("/poll"));
    assert.ok(heartbeat);
    assert.equal(heartbeat.body.capabilities["skills.list"].state, supportsUsage ? "available" : "unavailable");
    assert.equal(heartbeat.body.capabilities["skills.invoke"].state, "available");
  }
});

test("Claude does not return names from a session that changed while reading usage", async () => {
  const { $ } = host(changeSession => { changeSession(); return context(listing(1, ["old-session-skill"])); });
  await assert.rejects(executeBridgeAction($, createModState(), bridge, request("stale")), /原宿主会话已结束/);
});
