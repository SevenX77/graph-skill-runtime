import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp,mkdir,writeFile,readFile,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Client} from '@modelcontextprotocol/client';
import {StdioClientTransport} from '@modelcontextprotocol/client/stdio';
import {launchHostInfo,requestClientInfo} from '../../adapters/launch/index.mjs';
import {readLaunchHostInfo,discoverConnection} from '../../adapters/detection/index.mjs';
import {createHostAdapter} from '../../adapters/factory/index.mjs';
import {pollBridges} from '../../adapters/claude/mod/lifecycle/index.mjs';
import {register} from '../../adapters/claude/mod/hooks/register.js';
import {createHostBridge} from '../../adapters/claude/bridge/server.mjs';
import {graph} from '../../application/graph/demo/graph.mjs';
import {SNAPSHOT_SLOT} from '../../ui/template/publisher.mjs';
import { fakeRuntimeEnv } from "../support/runtime.mjs";

const native={name:'Claude Code',version:'native-engine',client_type:'claude_code',sessionId:'session-A',source:'claude-mod-session'};
const codexClient={name:'codex-mcp-client',version:'engine-version'};
const claudeClient={name:'claude-code',version:'native-engine'};
const caps={'conversation.submitMessage':{state:'available',detail:'live'}};
const payload={skillRoot:'/business/skill',graph:{...graph,width:352,height:548}};
const slot=/<script id="graph-skill-snapshot" type="application\/json">([\s\S]*?)<\/script>/;
const extract=html=>JSON.parse(slot.exec(html)[1]);
const unavailable=info=>assert.ok(Object.values(info.capabilities).every(c=>c.state!=='available'));
const launch=(clientInfo=codexClient)=>launchHostInfo({clientInfo});
const httpLaunch=()=>launchHostInfo({clientInfo:claudeClient,presentation:'html',nativeHost:native});

test('launch reads identity from the current MCP request and never reuses a missing modern identity',()=>{
  let reads=0;
  const server={getClientVersion(){reads++;return codexClient;}};
  assert.deepEqual(requestClientInfo(server,{mcpReq:{}}),codexClient);
  assert.deepEqual(requestClientInfo(server,{mcpReq:{envelope:{'io.modelcontextprotocol/clientInfo':claudeClient}}}),claudeClient);
  assert.equal(requestClientInfo(server,{mcpReq:{envelope:{}}}),undefined);
  assert.equal(reads,1);
});

test('launch HostInfo preserves engine facts, never infers product from presentation, and grants no actions',()=>{
  const codex=launch();assert.equal(codex.id,'codex');assert.equal(codex.identitySource,'mcp-client');
  assert.equal(codex.name,'codex-mcp-client');assert.equal(codex.version,'engine-version');assert.equal(codex.sessionId,null);unavailable(codex);
  const claude=httpLaunch();assert.equal(claude.id,'claude');assert.equal(claude.sessionId,native.sessionId);unavailable(claude);
  for(const presentation of [undefined,'mcp-app','html']) {
    const unknown=launchHostInfo({clientInfo:{name:'other',version:'1'},presentation});
    assert.equal(unknown.id,'unknown');unavailable(unknown);
  }
  for(const clientInfo of [undefined,codexClient,{name:'other'}]) assert.throws(()=>launchHostInfo({clientInfo,presentation:'html',nativeHost:native}));
  assert.throws(()=>launchHostInfo({clientInfo:claudeClient,presentation:'mcp-app',nativeHost:native}));
  assert.throws(()=>launchHostInfo({clientInfo:claudeClient,presentation:'html',nativeHost:{...native,sessionId:''}}));
  const tampered={...claude,capabilities:caps};unavailable(readLaunchHostInfo(tampered));
  assert.throws(()=>readLaunchHostInfo({...claude,id:'codex'}));
  assert.throws(()=>{claude.sessionId='overwritten';});
});

test('explicit startup transport replaces frame inference and never falls back after an invalid launch',()=>{
  assert.equal(discoverConnection({snapshotText:'null',framed:true}),null);
  assert.throws(()=>discoverConnection({snapshotText:'{"hostBridge":{}}',framed:true}));
  assert.throws(()=>discoverConnection({snapshotText:JSON.stringify({hostInfo:launch()}),framed:false}));
  const snapshot={hostInfo:httpLaunch(),hostBridge:{}};
  assert.equal(discoverConnection({snapshotText:JSON.stringify(snapshot),framed:true}).transport,'http-bridge');
});

function connectedFacade(initial,live) {
  let evidence=live,called=0,callbacks;
  const adapter=createHostAdapter({document:{querySelector:()=>({textContent:JSON.stringify({hostInfo:initial})})},window:{parent:{}},
    connections:{[initial.transport]:()=>({connect:async c=>{callbacks=c;c.receive(payload);},inspect:async()=>evidence,dispose(){}})},
    drivers:{codex:()=>({invoke:async()=>{called++;return {status:'accepted',message:'live'};}}),claude:()=>({invoke:async()=>{called++;return {status:'accepted',message:'live'};}})}});
  return {adapter,get called(){return called;},set:v=>{evidence=v;},deliver:v=>callbacks.receive(v)};
}
const codexLive={transport:'mcp-app',connected:true,identity:{name:'chatgpt',version:'desktop-version',client_type:'codex_desktop'},capabilities:caps};
const claudeLive={transport:'http-bridge',connected:true,identity:native,capabilities:caps};
const callbacks={receive(){},fail:assert.fail};

test('known startup identity is visible before connect; real UI evidence enables operations without confusing version scopes',async()=>{
  const f=connectedFacade(launch(),codexLive),a=f.adapter;
  assert.equal(a.hostId,'codex');assert.equal(a.hostInfo.version,'engine-version');unavailable(a.hostInfo);
  assert.equal((await a.invoke('conversation.submitMessage',{text:'too soon'})).status,'error');
  await a.connect(callbacks);assert.equal(a.hostInfo.version,'desktop-version');
  assert.equal(a.hostInfo.identitySource,'mcp-initialize');
  assert.equal((await a.invoke('conversation.submitMessage',{text:'now'})).status,'accepted');
  assert.equal(f.called,1);await a.dispose();
});

test('launch/live host or session mismatch permanently disables a page, including identity arriving in a later tool result',async()=>{
  for(const [initial,live] of [
    [launch(claudeClient),codexLive],
    [httpLaunch(),{...claudeLive,identity:{...native,sessionId:'session-B'}}],
  ]) {
    const f=connectedFacade(initial,live);await f.adapter.connect(callbacks);
    assert.equal(f.adapter.hostId,'unknown');unavailable(f.adapter.hostInfo);
    assert.equal((await f.adapter.invoke('conversation.submitMessage',{text:'never'})).status,'unsupported');
    assert.equal(f.called,0);await f.adapter.dispose();
  }
  const f=connectedFacade(launch(),codexLive);await f.adapter.connect(callbacks);
  f.deliver({...payload,hostInfo:launch(claudeClient)});await f.adapter.capabilities();
  assert.equal(f.adapter.hostId,'unknown');assert.equal(f.called,0);await f.adapter.dispose();
});

test('a missing native identity cannot forward a model-supplied Claude launch claim',async()=>{
  const handlers=[];register((name,matcher,fn)=>handlers.push({name,matcher,fn}));
  const handler=handlers.find(x=>x.name==='tool.call' && x.matcher.tool==='mcp__graph-skill-canvas__show_graph');
  const api={session:{root:async()=>'/project',id:async()=>{throw new Error('missing');},version:async()=>({version:'native'})},
    tool:{list:async()=>[{name:'mcp__Claude_Browser__preview_start'},{name:'mcp__Claude_Browser__navigate'}]},ui:{log(){}}};
  let forwarded;
  await handler.fn(api,{skill_root:'/skill',native_host:native,presentation:'html',preview_project_root:'/forged'},async input=>{forwarded=input;return {result:{graph:{id:'preserved'}}};});
  assert.equal(forwarded.native_host,undefined);assert.equal(forwarded.presentation,undefined);assert.equal(forwarded.preview_project_root,undefined);
});

test('HTTP startup binds the originating session before the first heartbeat arrives',async t=>{
  const owner=createHostBridge();t.after(()=>owner.close());
  const view=await owner.createView(payload.skillRoot,httpLaunch());
  const poll=identity=>fetch(view.mod.url+'/poll',{method:'POST',headers:{Authorization:'Bearer '+view.mod.token,'Content-Type':'application/json'},body:JSON.stringify({identity,capabilities:caps})});
  assert.equal((await poll({...native,sessionId:'session-B'})).status,409);
  assert.equal((await poll(native)).status,401);
  const inspected=await (await fetch(view.browser.url+'/capabilities',{headers:{Authorization:'Bearer '+view.browser.token}})).json();
  assert.equal(inspected.connected,false);
});

test('real stdio and HTTP deliver startup identity before any page handshake and retain one HTML implementation',async t=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'graph-launch-')));
  t.after(()=>rm(temp,{recursive:true,force:true}));
  await mkdir(join(temp,'phases','process'),{recursive:true});
  await writeFile(join(temp,'SKILL.md'),'---\nname: launch-test\n---\n');
  await writeFile(join(temp,'graph.yaml'),'schema_version: gskill.graph.v1\ngraph_id: launch\nphases:\n  - id: process\n    depends_on: [input]\n    output: true\n');
  await writeFile(join(temp,'phases','process','LOGIC.md'),'# Logic\n');
  const template=await readFile(new URL('../../dist/canvas.html',import.meta.url),'utf8');
  for(const clientInfo of [codexClient,claudeClient,{name:'unrecognized-test-host',version:'1'}]) {
    const client=new Client(clientInfo);
    const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../../dist/server.mjs',import.meta.url))],stderr:'pipe',env:fakeRuntimeEnv()});
    await client.connect(transport);
    try {
      const isClaude=clientInfo.name==='claude-code';
      const args={skill_root:temp,...(isClaude?{presentation:'html',preview_project_root:temp,native_host:native}:{})};
      const result=await client.callTool({name:'show_graph',arguments:args});assert.notEqual(result.isError,true,JSON.stringify(result));
      const info=result.structuredContent.hostInfo;
      assert.equal(info.id,isClaude?'claude':clientInfo.name==='codex-mcp-client'?'codex':'unknown');unavailable(info);
      const uri=(await client.listTools()).tools.find(tool=>tool.name==='show_graph')._meta.ui.resourceUri;
      const resource=await client.readResource({uri});
      assert.equal(resource.contents[0].text.replace(slot,SNAPSHOT_SLOT),template);
      if(!isClaude) {
        assert.deepEqual(extract(resource.contents[0].text).hostInfo,info);
        const rejected=await client.callTool({name:'show_graph',arguments:{skill_root:temp,presentation:'html',preview_project_root:temp,native_host:native}});
        assert.equal(rejected.isError,true);continue;
      }
      const view=result.structuredContent.presentation;
      const html=await (await fetch(view.url)).text(),snapshot=extract(html);
      assert.deepEqual(snapshot.hostInfo,info);assert.equal(snapshot.hostInfo.sessionId,'session-A');
      assert.equal(html.replace(slot,SNAPSHOT_SLOT),template);assert.ok(!html.includes(view.bridge.token));
      const a=createHostAdapter({document:{querySelector:()=>({textContent:JSON.stringify(snapshot)})},window:{parent:null,location:{origin:new URL(view.url).origin}}});
      const graphFailures=[];
      await a.connect({receive(){},fail:error=>graphFailures.push(error)});assert.equal(a.hostId,'unknown');
      let filled=0,posted;
      const state={bridges:new Map([['native',{...view.bridge,skillRoot:temp}]]),running:new Set(),seen:new Set(),receipts:new Map(),reported:new Set(),context:null,polling:false,closed:false,generation:0};
      const api={session:{id:async()=>native.sessionId,version:async()=>({version:native.version})},tool:{list:async()=>[]},prompt:{fill:async()=>{filled++;return {isFilled:true};}},ui:{log:assert.fail},
        http:{fetch:async(url,init)=>{const r=await fetch(url,init),v={ok:r.ok,text:await r.text()};if(url.endsWith('/result'))posted?.();return v;}}};
      await pollBridges(api,state);await a.capabilities();assert.equal(a.hostId,'claude');assert.equal(a.hostInfo.sessionId,info.sessionId);
      const receipt=await a.invoke('composer.writeDraft',{text:'launch-bound',mode:'append'});
      const delivered=new Promise(r=>{posted=r;});await pollBridges(api,state);await delivered;
      assert.equal((await a.getResult(receipt.requestId)).status,'completed');assert.equal(filled,1);
      const second=await client.callTool({name:'show_graph',arguments:{...args,native_host:{...native,sessionId:'session-B'}}});
      assert.notEqual(second.structuredContent.presentation.url,view.url);
      await a.capabilities();assert.equal(a.hostId,'unknown');
      assert.equal((await a.invoke('composer.writeDraft',{text:'old',mode:'append'})).status,'unsupported');assert.equal(filled,1);
      const oldPoll=await fetch(view.bridge.url+'/poll',{method:'POST',headers:{Authorization:'Bearer '+view.bridge.token,'Content-Type':'application/json'},body:JSON.stringify({identity:native,capabilities:caps})});
      assert.equal(oldPoll.status,401);await a.dispose();
      assert.ok(graphFailures.every(error=>/session has ended/i.test(error.message)));
    } finally {await client.close();}
  }
});
