import assert from 'node:assert/strict';
import {test} from 'node:test';
import {discoverConnection,identifyHost} from '../../adapters/detection/index.mjs';
import {createHostAdapter} from '../../adapters/factory/index.mjs';
import {createHostBridge} from '../../adapters/claude/bridge/server.mjs';
import {readHostIdentity,pollBridges} from '../../adapters/claude/mod/lifecycle/index.mjs';
import {graph} from '../../application/graph/demo/graph.mjs';
import {launchHostInfo} from '../../adapters/launch/index.mjs';

const capabilities={'conversation.submitMessage':{state:'available',detail:'live declared message capability'}};
const codex={name:'chatgpt',version:'26.1007.2314.0',client_type:'codex_desktop'};
const claude={name:'Claude Code',version:'2.1.295',client_type:'claude_code',sessionId:'session-a',source:'claude-mod-session'};
const evidence=(identity=codex,transport='mcp-app')=>({identity,transport,connected:true,capabilities:structuredClone(capabilities)});
const payload={skillRoot:'/business/skill',graph:{...graph,width:352,height:548}};
const cb={receive(){},fail:assert.fail};
const disabled=info=>{assert.equal(info.id,'unknown');assert.equal(info.status,'unknown');assert.ok(Object.values(info.capabilities).every(x=>x.state!=='available'));};

test('connection discovery never supplies product identity, even for a framed snapshot',()=>{
  assert.equal(discoverConnection({snapshotText:'null',framed:true}),null);
  const snapshot={hostBridge:{},hostInfo:launchHostInfo({presentation:'html'})};
  assert.deepEqual(discoverConnection({snapshotText:JSON.stringify(snapshot),framed:true}),{transport:'http-bridge',snapshot,hostInfo:snapshot.hostInfo});
  assert.equal(discoverConnection({snapshotText:'null',framed:false}),null);
});

test('HostInfo preserves actual reports, freezes its data, and never invents versions or MCP session IDs',()=>{
  const input=evidence(), info=identifyHost(input);
  assert.deepEqual({...info,capabilities:undefined},{id:'codex',status:'confirmed',name:codex.name,version:codex.version,
    clientType:'codex_desktop',sessionId:null,transport:'mcp-app',identitySource:'mcp-initialize',reason:'已读取当前连接的宿主身份和能力。',capabilities:undefined});
  input.capabilities['conversation.submitMessage'].state='unavailable';
  assert.equal(info.capabilities['conversation.submitMessage'].state,'available');
  assert.throws(()=>{info.id='claude';});assert.throws(()=>{info.capabilities['conversation.submitMessage'].state='unavailable';});
  assert.equal(identifyHost(evidence({...codex,version:'unknown'})).version,null);
  assert.equal(identifyHost(evidence({name:'chatgpt'})).version,null);
  assert.equal(identifyHost(evidence(claude,'http-bridge')).sessionId,'session-a');
});

test('unrecognized, contradictory, incomplete, expired and malformed reports grant no operations',()=>{
  for (const identity of [null,{},[],{name:'Codex'},{...codex,name:'Official test host'},{...codex,client_type:'claude_code'},
    {...codex,client_type:'codex_browser'},{...codex,name:'chatgpt\nforged'},claude]) disabled(identifyHost(evidence(identity)));
  for (const identity of [null,codex,{...claude,source:'snapshot'},{...claude,sessionId:''},{...claude,version:'unknown'},
    {...claude,version:null}]) disabled(identifyHost(evidence(identity,'http-bridge')));
  disabled(identifyHost({...evidence(),connected:false}));
  disabled(identifyHost({...evidence(),capabilities:null}));
  disabled(identifyHost({...evidence(),capabilities:{'conversation.submitMessage':{state:'yes',detail:'invalid'}}}));
  const noActions=identifyHost({...evidence(),capabilities:{}});
  assert.equal(noActions.id,'codex');assert.ok(Object.values(noActions.capabilities).every(x=>x.state!=='available'));
});

function isolated(initial) {
  let report=initial,selected=0,called=0,disposed=0;
  const connection={connect:async({receive})=>receive(payload),inspect:async()=>report,dispose:()=>{disposed++;}};
  const driver=()=>{selected++;return {invoke:async()=>{called++;return {status:'accepted',message:'test'};}};};
  const adapter=createHostAdapter({document:{querySelector:()=>({textContent:JSON.stringify({hostInfo:launchHostInfo({presentation:initial.transport==='http-bridge'?'html':'mcp-app'}),...(initial.transport==='http-bridge'?{hostBridge:{}}:{})})})},
    window:{parent:{}},connections:{[initial.transport]:()=>connection},drivers:{codex:driver,claude:driver}});
  return {adapter,set:value=>{report=value;},counts:()=>({selected,called,disposed})};
}

test('an arbitrary frame with a fully capable unknown peer never constructs an execution adapter',async()=>{
  const testCase=isolated(evidence({...codex,name:'Another MCP App host'})),{adapter}=testCase;
  disabled(adapter.hostInfo);await adapter.connect(cb);disabled(adapter.hostInfo);
  assert.equal((await adapter.invoke('conversation.submitMessage',{text:'do not dispatch'})).status,'unsupported');
  assert.deepEqual(testCase.counts(),{selected:0,called:0,disposed:0});
  await adapter.dispose();assert.equal(testCase.counts().disposed,1);
});

test('a late heartbeat can identify Claude; stale heartbeat revokes authority and identity replacement cannot switch sessions',async()=>{
  const connected=evidence(claude,'http-bridge'),testCase=isolated({...connected,connected:false}),{adapter}=testCase;
  await adapter.connect(cb);disabled(adapter.hostInfo);assert.equal(testCase.counts().selected,0);
  testCase.set(connected);await adapter.capabilities();assert.equal(adapter.hostId,'claude');
  await adapter.invoke('conversation.submitMessage',{text:'current'});assert.equal(testCase.counts().called,1);
  testCase.set({...connected,connected:false});await adapter.capabilities();disabled(adapter.hostInfo);
  testCase.set(connected);await adapter.capabilities();assert.equal(adapter.hostId,'claude');assert.equal(testCase.counts().selected,1);
  testCase.set(evidence({...claude,sessionId:'session-b'},'http-bridge'));await adapter.capabilities();disabled(adapter.hostInfo);
  testCase.set(connected);await adapter.capabilities();disabled(adapter.hostInfo);
  assert.equal((await adapter.invoke('conversation.submitMessage',{text:'must not send'})).status,'unsupported');
  assert.deepEqual(testCase.counts(),{selected:1,called:1,disposed:0});await adapter.dispose();
});

test('MCP teardown and a failed identity read clear previously confirmed authority',async()=>{
  const testCase=isolated(evidence()),{adapter}=testCase;
  await adapter.connect(cb);assert.equal(adapter.hostId,'codex');
  testCase.set({...evidence(),connected:false});await adapter.capabilities();disabled(adapter.hostInfo);
  testCase.set(null);await assert.rejects(adapter.capabilities());disabled(adapter.hostInfo);
  await adapter.dispose();disabled(adapter.hostInfo);
});

test('Claude reporter reads live engine/session APIs and missing APIs cannot fabricate identity',async()=>{
  const calls=[];
  assert.deepEqual(await readHostIdentity({session:{id:async()=>{calls.push('id');return 'real-id';},version:async()=>{calls.push('version');return {version:'engine-build'};}}}),
    {...claude,sessionId:'real-id',version:'engine-build'});
  assert.deepEqual(calls,['id','version']);assert.equal(await readHostIdentity({session:{}}),null);
  assert.equal(await readHostIdentity({session:{id:async()=>'',version:async()=>({version:'build'})}}),null);
});

test('authenticated HTTP bridge binds session identity, expires capabilities, and rejects takeover with queued actions',async t=>{
  let now=0;
  const owner=createHostBridge({responseWaitMs:5,now:()=>now});t.after(()=>owner.close());
  const view=await owner.createView(payload.skillRoot);
  const post=async(credential,path,body)=>{const response=await fetch(credential.url+path,{method:'POST',headers:{Authorization:'Bearer '+credential.token,'Content-Type':'application/json'},body:JSON.stringify(body)});return {status:response.status,body:await response.json()};};
  const inspect=async()=>{const response=await fetch(view.browser.url+'/capabilities',{headers:{Authorization:'Bearer '+view.browser.token}});return {transport:'http-bridge',...await response.json()};};
  disabled(identifyHost(await inspect()));
  await post(view.mod,'/poll',{identity:claude,capabilities});assert.equal(identifyHost(await inspect()).id,'claude');
  now=5001;disabled(identifyHost(await inspect()));
  await post(view.mod,'/poll',{identity:claude,capabilities});
  const action=await post(view.browser,'/action',{id:'queued',action:'conversation.submitMessage',args:{text:'original session only'}});assert.equal(action.body.status,'pending');
  assert.equal((await post(view.mod,'/poll',{identity:{...claude,sessionId:'session-b'},capabilities})).status,409);
  disabled(identifyHost(await inspect()));
  assert.equal((await post(view.mod,'/poll',{identity:claude,capabilities})).status,401);
  const receipt=await fetch(view.browser.url+'/result?id=queued',{headers:{Authorization:'Bearer '+view.browser.token}});
  assert.equal((await receipt.json()).status,'error');
  const next=await owner.createView(payload.skillRoot);assert.notEqual(next.browser.token,view.browser.token);
  await post(next.mod,'/poll',{identity:{...claude,sessionId:'session-b'},capabilities});
  const rejected=await post(view.browser,'/action',{id:'old-page',action:'conversation.submitMessage',args:{text:'must not send'}});
  assert.equal(rejected.body.status,'unsupported');
});

test('Mod never executes a response if identity APIs are missing or the session changes before execution',async()=>{
  for (const missing of [true,false]) {
    let ids=0,submitted=0;
    const api={session:missing ? {} : {id:async()=>++ids===1?'original':'replacement',version:async()=>({version:'build'})},
      tool:{list:async()=>[]},prompt:{submit:async()=>{submitted++;}},ui:{log:assert.fail},
      http:{fetch:async(url)=>({ok:true,text:JSON.stringify(url.endsWith('/poll') ? {requests:[{id:'test',action:'conversation.submitMessage',skillRoot:payload.skillRoot,args:{text:'never'}}]} : {})})}};
    const bridge={url:'http://127.0.0.1:12345',token:'a'.repeat(48),skillRoot:payload.skillRoot};
    const state={bridges:new Map([['test',bridge]]),running:new Set(),seen:new Set(),receipts:new Map(),reported:new Set(),context:null,polling:false,closed:false,generation:0};
    await pollBridges(api,state);await new Promise(resolve=>setImmediate(resolve));assert.equal(submitted,0);
  }
});
