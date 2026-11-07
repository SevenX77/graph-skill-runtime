import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp,mkdir,writeFile,readFile,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Client} from '@modelcontextprotocol/client';
import {StdioClientTransport} from '@modelcontextprotocol/client/stdio';
import {launchHostInfo,SNAPSHOT_SLOT} from 'hostpane/server';
import {createHostAdapter} from 'hostpane/page';
import {registerPluginBase} from 'hostpane/claude-mod';
import { fakeRuntimeEnv } from "../support/runtime.mjs";

const native={name:'Claude Code',version:'native-engine',client_type:'claude_code',sessionId:'session-A',source:'claude-mod-session'};
const codexClient={name:'codex-mcp-client',version:'engine-version'};
const claudeClient={name:'claude-code',version:'native-engine'};
const caps={'conversation.submitMessage':{state:'available',detail:'live'}};
const slot=/<script id="plugin-base-snapshot" type="application\/json">([\s\S]*?)<\/script>/;
const extract=html=>JSON.parse(slot.exec(html)[1]);
const unavailable=info=>assert.ok(Object.values(info.capabilities).every(c=>c.state!=='available'));
const httpLaunch=()=>launchHostInfo({clientInfo:claudeClient,presentation:'html',nativeHost:native});

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
      let filled=0;
      // The Mod as the engine runs it: public registration, session start, and its 1-second timer.
      const hooks=new Map();let tick;
      const state=registerPluginBase((name,...rest)=>hooks.set(name,rest.at(-1)),{pluginName:'graph-skill-canvas-mod',pages:[]});
      const api={session:{id:async()=>native.sessionId,version:async()=>({version:native.version})},tool:{list:async()=>[]},prompt:{fill:async()=>{filled++;return {isFilled:true};}},ui:{log:assert.fail},
        clock:{every:(_ms,fn)=>{tick=fn;return {cancel(){}};}},command:{register:async()=>{}},
        http:{fetch:async(url,init)=>{const r=await fetch(url,init);return {ok:r.ok,status:r.status,text:await r.text()};}}};
      await hooks.get('session.start')(api,{},async e=>e);
      state.bridges.set('native',{...view.bridge,skillRoot:temp});
      const pollBridges=()=>tick();
      await pollBridges();await a.capabilities();assert.equal(a.hostId,'claude');assert.equal(a.hostInfo.sessionId,info.sessionId);
      let heartbeatWork;
      const heartbeat=setInterval(()=>{if(!state.polling)heartbeatWork=pollBridges();},10);
      let receipt;
      try { receipt=await a.invoke('composer.writeDraft',{text:'launch-bound',mode:'append'}); }
      finally { clearInterval(heartbeat);await heartbeatWork; }
      assert.equal(receipt.status,'completed');assert.equal(receipt.settled,true);assert.equal(filled,1);
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
