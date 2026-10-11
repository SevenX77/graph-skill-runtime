import assert from 'node:assert/strict';
import {test} from 'node:test';
import {connect} from 'node:net';
import {claudeAdapter,validateBrowserBridge} from '../adapters/claude/browser/index.mjs';
import {bridgeDescriptor,executeBridgeAction,pollBridges,register} from '../adapters/claude/mod/hooks/register.js';
import {createHostBridge} from '../adapters/claude/bridge/server.mjs';

const root = '/business/中文 skill';
const bridge = {url:'http://127.0.0.1:31234',token:'a'.repeat(48),skillRoot:root};
const snapshot = {skillRoot:root,graph:{id:'hello-world'},hostBridge:{url:bridge.url,token:'b'.repeat(48)}};
const request = (action,args={}) => ({id:'request-1',action,args,skillRoot:root});
const makeState = () => ({bridges:new Map([[bridge.url,bridge]]),running:new Set(),seen:new Set(),receipts:new Map(),reported:new Set(),context:null,polling:false,closed:false,generation:0});
const tick = () => new Promise(resolve => setImmediate(resolve));

test('Claude browser uses its own token and preserves pending versus completed action results',async()=>{
  const calls=[];
  const adapter=claudeAdapter({snapshot:()=>snapshot,requestId:()=> 'request-1',fetch:async(url,init)=>{
    calls.push({url,init});
    const value=url.endsWith('/capabilities') ? {connected:true,capabilities:{'send-prompt':{available:true,detail:'starts a turn'}}} :
      url.includes('/result?') ? {status:'accepted',message:'turn started'} : {status:'pending',message:'waiting',requestId:'request-1'};
    return {ok:true,json:async()=>value};
  }});
  await adapter.connect({receive:payload=>assert.equal(payload,snapshot),fail:assert.fail});
  assert.equal((await adapter.capabilities())['send-prompt'].available,true);
  assert.equal((await adapter.capabilities())['open-root'].available,false);
  assert.deepEqual(await adapter.invoke('send-prompt',{text:'canvas test'}),{status:'pending',message:'waiting',requestId:'request-1'});
  assert.equal((await adapter.getResult('request-1')).status,'accepted');
  for(const {init} of calls) assert.equal(init.headers.Authorization,'Bearer '+snapshot.hostBridge.token);
  const submitted=JSON.parse(calls.find(call=>call.url.endsWith('/action')).init.body);
  assert.deepEqual(submitted,{id:'request-1',action:'send-prompt',args:{text:'canvas test'}});
  assert.equal((await adapter.invoke('arbitrary-shell',{text:'whoami'})).status,'unsupported');
  adapter.dispose();await assert.rejects(()=>adapter.getResult('request-1'),/关闭/);
});

test('Claude browser refuses missing or non-loopback credentials and never falls back to a different host',async()=>{
  for(const url of ['https://example.com','http://localhost:31234','http://127.0.0.1:31234/?token=x','http://user:pass@127.0.0.1:31234','http://127.0.0.2:31234']) {
    assert.throws(()=>validateBrowserBridge({...bridge,url}));
    assert.throws(()=>bridgeDescriptor({skillRoot:root,presentation:{bridge:{...bridge,url}}}));
  }
  const adapter=claudeAdapter({snapshot:()=>({graph:{},skillRoot:root})});
  await adapter.connect({receive:()=>{},fail:assert.fail});
  assert.equal((await adapter.capabilities())['send-prompt'].available,false);
  await assert.rejects(()=>adapter.invoke('send-prompt',{text:'hello'}),/未连接/);
});

test('Claude browser retains operation identity when the submission response is lost or malformed',async()=>{
  for(const failure of ['network','json']) {
    let effects=0,posts=0;
    const adapter=claudeAdapter({snapshot:()=>snapshot,requestId:()=> 'lost-response',fetch:async(url,init)=>{
      if(init.method==='POST') {
        posts++;effects++;
        if(failure==='network') throw new TypeError('Connection lost after request reached server');
        return {ok:true,json:async()=>{throw new SyntaxError('Truncated JSON');}};
      }
      assert.ok(url.endsWith('/result?id=lost-response'));
      return {ok:true,json:async()=>({status:'completed',message:'draft filled'})};
    }});
    await adapter.connect({receive:()=>{},fail:assert.fail});
    const answer=await adapter.invoke('fill-prompt',{text:'once'});
    assert.equal(answer.status,'pending');assert.equal(answer.requestId,'lost-response');
    assert.equal((await adapter.getResult(answer.requestId)).status,'completed');
    assert.equal(posts,1);assert.equal(effects,1);
  }
});

test('Claude worker preserves drafts and requests inspection through the normal host turn with honest receipts',async()=>{
  const called=[];
  const api={prompt:{fill:async value=>{called.push(value);return {isFilled:true};},submit:async value=>{called.push(value);return {text:value.text};}},tool:{
    list:async()=>[{name:'mcp__graph-skill-canvas__inspect_graph'}],
    call:assert.fail,
  }};
  assert.equal((await executeBridgeAction(api,makeState(),bridge,request('fill-prompt',{text:'hello'}))).status,'completed');
  assert.deepEqual(called.shift(),{text:'hello',mode:'append'});
  api.prompt.fill=async()=>({isFilled:false,refusal:'dialog'});
  assert.equal((await executeBridgeAction(api,makeState(),bridge,request('fill-prompt',{text:'hello'}))).status,'rejected');
  assert.equal((await executeBridgeAction(api,makeState(),bridge,request('call-tool'))).status,'accepted');
  const query=called.shift();
  assert.deepEqual(Object.keys(query),['text']);
  assert.ok(query.text.includes('mcp__graph-skill-canvas__inspect_graph'));assert.ok(query.text.includes(JSON.stringify(root)));
  assert.match(query.text,/Do not execute the business graph or modify files/);
  assert.match(query.text,/without substituting another tool or bypassing permissions/);
  api.prompt.submit=async()=>({drop:'host declined'});
  assert.equal((await executeBridgeAction(api,makeState(),bridge,request('call-tool'))).status,'rejected');
  api.tool.list=async()=>[];
  assert.equal((await executeBridgeAction(api,makeState(),bridge,request('call-tool'))).status,'unsupported');
  await assert.rejects(()=>executeBridgeAction(api,makeState(),bridge,{...request('call-tool'),skillRoot:'/other'}),/identity/);
  await assert.rejects(()=>executeBridgeAction(api,makeState(),bridge,request('call-tool',{tool:'Bash'})),/Unexpected/);
});

test('Claude canvas submission carries saved selection without reentering its own hook and isolates roots',async()=>{
  const submissions=[];
  // The real Mod host skips the originating Mod's hook for its own API calls.
  const api={prompt:{submit:async input=>{submissions.push(input);return {text:input.text};}}};
  const state=makeState();
  const text='Reply with the selected node ID; do not read files or call tools.';
  await executeBridgeAction(api,state,bridge,request('update-context',{context:{skillRoot:root,graphId:'main',nodeId:'signature'}}));
  assert.equal(submissions.length,0);
  const result=await executeBridgeAction(api,state,bridge,request('send-prompt',{text}));
  assert.equal(result.status,'accepted');assert.equal(submissions.length,1);
  assert.ok(submissions[0].text.startsWith(text+'\n\n'));
  assert.deepEqual(JSON.parse(submissions[0].text.split('supplied as data by the user: ')[1]),{skillRoot:root,graphId:'main',nodeId:'signature'});
  assert.deepEqual(Object.keys(submissions[0]),['text']);
  const other={...bridge,skillRoot:'/business/another'};
  await executeBridgeAction(api,state,other,{...request('send-prompt',{text}),skillRoot:other.skillRoot});
  assert.deepEqual(submissions[1],{text});
  state.context=null;
  await executeBridgeAction(api,state,bridge,request('send-prompt',{text}));
  assert.deepEqual(submissions[2],{text});
});

test('Claude tool-list test reports only the canvas allowlist intersected with session tools',async()=>{
  const api={tool:{list:async()=>[{name:'Bash'},{name:'mcp__graph-skill-canvas__inspect_graph'},{name:'mcp__other__write_data'}]}};
  const result=await executeBridgeAction(api,makeState(),bridge,request('list-tools'));
  assert.deepEqual(result.data,{scope:'canvas-allowlist',tools:[{name:'mcp__graph-skill-canvas__inspect_graph'}]});
});

test('Claude worker does not hold the heartbeat while a user prompt waits for idle and retries only result delivery',async()=>{
  let resolveTurn,submitted=0,failReceipt=true,polls=0;
  const receipts=[];
  const api={tool:{list:async()=>[]},ui:{log:()=>{}},prompt:{submit:async()=>{submitted++;await new Promise(resolve=>{resolveTurn=resolve;});}},http:{
    fetch:async(url,init)=>{
      const body=JSON.parse(init.body);
      if(url.endsWith('/poll')) {polls++;return {ok:true,text:JSON.stringify({requests:[request('send-prompt',{text:'test from canvas'})]})};}
      if(failReceipt) throw new Error('connection interrupted');
      receipts.push(body);return {ok:true,text:'{}'};
    },
  }};
  const state=makeState();
  await pollBridges(api,state);await pollBridges(api,state);
  assert.equal(polls,2);assert.equal(submitted,1);assert.equal(state.running.size,1);
  resolveTurn();await tick();
  assert.equal(state.receipts.size,1);assert.equal(receipts.length,0);
  failReceipt=false;await pollBridges(api,state);await tick();
  assert.equal(submitted,1);assert.equal(receipts.length,1);assert.equal(receipts[0].result.status,'accepted');
  assert.equal(state.receipts.size,0);assert.equal(state.running.size,0);
});

test('Claude large host refusal still produces an explicit bounded receipt',async()=>{
  const receipts=[];
  const api={tool:{list:async()=>[{name:'mcp__graph-skill-canvas__inspect_graph'}]},prompt:{submit:async()=>({drop:'x'.repeat(90000)})},ui:{log:assert.fail},http:{
    fetch:async(url,init)=>{
      if(url.endsWith('/poll')) return {ok:true,text:JSON.stringify({requests:[request('call-tool')]})};
      receipts.push(JSON.parse(init.body));return {ok:true,text:'{}'};
    },
  }};
  await pollBridges(api,makeState());await tick();
  assert.equal(receipts.length,1);assert.equal(receipts[0].result.status,'rejected');
  assert.equal(receipts[0].result.data.omitted,true);assert.ok(receipts[0].result.data.resultBytes>90000);
  assert.ok(Buffer.byteLength(JSON.stringify(receipts[0]))<65536);
});

test('Claude drops an in-flight old-session poll response even if a new view has reopened',async()=>{
  for(const reopened of [false,true]) {
    let releasePoll,enteredPoll,filled=0;
    const pollStarted=new Promise(resolve=>{enteredPoll=resolve;});
    const api={tool:{list:async()=>[]},ui:{log:assert.fail},prompt:{fill:async()=>{filled++;return {isFilled:true};}},http:{
      fetch:async()=>{enteredPoll();return new Promise(resolve=>{releasePoll=resolve;});},
    }};
    const state=makeState();
    const pending=pollBridges(api,state);
    await pollStarted;
    state.closed=true;state.generation++;state.bridges.clear();
    if(reopened) {
      state.closed=false;
      state.bridges.set('new-view',{...bridge,token:'d'.repeat(48)});
    }
    releasePoll({ok:true,text:JSON.stringify({requests:[request('fill-prompt',{text:'old session request'})]})});
    await pending;await tick();
    assert.equal(filled,0);assert.equal(state.running.size,0);assert.equal(state.receipts.size,0);
    assert.equal(state.polling,false);
  }
});

test('Claude selection reaches the next normal prompt without starting a turn, and session end stops polling',async()=>{
  const handlers=[];let timerCancelled=false,submitted=0,timerCallback,timers=0;
  register((event,matcher,handler)=>handlers.push({event,handler:typeof matcher==='function'?matcher:handler,matcher:typeof matcher==='function'?{}:matcher}));
  const api={clock:{every:(milliseconds,callback)=>{timers++;assert.equal(milliseconds,1000);timerCallback=callback;return {cancel:()=>{timerCancelled=true;}};}},command:{register:async()=>{}},
    session:{root:async()=>root},tool:{list:async()=>[{name:'mcp__Claude_Browser__preview_start'},{name:'mcp__Claude_Browser__navigate'}]},prompt:{submit:async()=>{submitted++;}},ui:{log:()=>{}},http:{fetch:async(url)=>({ok:true,text:JSON.stringify({requests:url.endsWith('/poll')?[request('update-context',{context:{skillRoot:root,graphId:'main',nodeId:'greet'}})]:[]})})}};
  const find=event=>handlers.find(item=>item.event===event).handler;
  await find('session.start')(api,{},async()=>({}));
  const result={result:{...snapshot,document:{path:root+'/SKILL.md',fileUrl:encodeURI('file://'+root+'/SKILL.md')},presentation:{kind:'http',url:bridge.url+'/view/'+'a'.repeat(64),preview:{name:'graph-skill-test',projectRoot:root},bridge}}};
  await find('tool.call')(api,{skill_root:root},async()=>result);
  await timerCallback();await tick();
  assert.equal(submitted,0);
  const original={text:'hello',context:['existing']};
  const next=await find('prompt.submit')(api,original,async value=>value);
  assert.equal(next.text,'hello');assert.equal(next.context[0],'existing');assert.match(next.context[1],/"nodeId":"greet"/);
  await find('session.end')(api,{},async()=>({}));assert.equal(timerCancelled,true);
  const cleared=await find('prompt.submit')(api,original,async value=>value);
  assert.equal(cleared,original);assert.equal(timers,1);
  const nextView={result:{...result.result,presentation:{...result.result.presentation,bridge:{...bridge,token:'c'.repeat(48)}}}};
  await find('tool.call')(api,{skill_root:root},async()=>nextView);
  assert.equal(timers,2);
  await timerCallback();await tick();
  assert.match((await find('prompt.submit')(api,original,async value=>value)).context[1],/"nodeId":"greet"/);
});

test('real loopback bridge carries browser requests through Mod actions and keeps two roots isolated',async()=>{
  const owner=createHostBridge({responseWaitMs:25});
  const fills=[],queries=[];
  const api={tool:{list:async()=>[{name:'mcp__graph-skill-canvas__inspect_graph'}],call:assert.fail},
    prompt:{fill:async input=>{fills.push(input);return {isFilled:true};},submit:async input=>{queries.push(input);return {text:input.text};}},ui:{log:assert.fail},
    http:{fetch:async(url,init)=>{const response=await fetch(url,init);return {ok:response.ok,status:response.status,text:await response.text()};}}};
  const state=makeState();state.bridges.clear();
  try {
    const roots=[root,'/business/second skill'];
    const adapters=[];
    for(const skillRoot of roots) {
      const view=await owner.createView(skillRoot);
      state.bridges.set(view.mod.url+'/'+view.mod.token,{...view.mod,skillRoot});
      let sequence=0;
      const adapter=claudeAdapter({snapshot:()=>({skillRoot,graph:{id:'actual'},hostBridge:view.browser}),requestId:()=> 'request-'+(++sequence)});
      await adapter.connect({receive:()=>{},fail:assert.fail});adapters.push(adapter);
    }
    assert.equal(state.bridges.size,2);
    await pollBridges(api,state);
    assert.equal((await adapters[0].capabilities())['call-tool'].available,true);
    const first=await adapters[0].invoke('fill-prompt',{text:'first root draft'});
    const second=await adapters[1].invoke('fill-prompt',{text:'second root draft'});
    assert.equal(first.status,'pending');assert.equal(second.status,'pending');
    await pollBridges(api,state);await tick();
    assert.equal((await adapters[0].getResult(first.requestId)).status,'completed');
    assert.equal((await adapters[1].getResult(second.requestId)).status,'completed');
    assert.deepEqual(fills,[{text:'first root draft',mode:'append'},{text:'second root draft',mode:'append'}]);
    // Both views used the same request id. A repeat must not run either action again.
    await pollBridges(api,state);assert.equal(fills.length,2);
    const context=await adapters[0].invoke('update-context',{context:{skillRoot:root,graphId:'main',nodeId:'greet'}});
    const query=await adapters[1].invoke('call-tool');
    await pollBridges(api,state);await tick();
    assert.equal((await adapters[0].getResult(context.requestId)).status,'completed');
    assert.equal((await adapters[1].getResult(query.requestId)).status,'accepted');
    assert.deepEqual(state.context,{skillRoot:root,graphId:'main',nodeId:'greet'});
    assert.equal(queries.length,1);
    assert.ok(queries[0].text.includes('mcp__graph-skill-canvas__inspect_graph'));
    assert.ok(queries[0].text.includes(JSON.stringify(roots[1])));
    assert.ok(!queries[0].text.includes(JSON.stringify(roots[0])));
    assert.equal((await adapters[1].invoke('call-tool',{skillRoot:root})).status,'rejected');
  } finally {state.closed=true;await owner.close();}
});

test('disconnect rotates view credentials while preserving lookup of an unresolved delivered request',async()=>{
  const owner=createHostBridge({responseWaitMs:10});
  async function send(descriptor,path,body) {
    const response=await fetch(descriptor.url+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+descriptor.token,'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
    return {ok:response.ok,status:response.status,body:await response.json()};
  }
  try {
    const old=await owner.createView(root);
    const capabilities={'fill-prompt':{available:true,detail:'append draft'}};
    await send(old.mod,'/poll',{capabilities});
    const pending=await send(old.browser,'/action',{id:'original',action:'fill-prompt',args:{text:'once'}});
    assert.equal(pending.body.status,'pending');
    assert.equal((await send(old.mod,'/poll',{capabilities})).body.requests[0].id,'original');
    await send(old.mod,'/disconnect',{});
    const current=await owner.createView(root);
    assert.notEqual(current.browser.token,old.browser.token);assert.notEqual(current.mod.token,old.mod.token);
    assert.equal((await send(old.mod,'/poll',{capabilities})).ok,false);
    const oldLookup=await send(old.browser,'/result?id=original');
    assert.equal(oldLookup.ok,true);assert.equal(oldLookup.body.status,'pending');assert.equal(oldLookup.body.requestId,'original');
    const attempted=await send(old.browser,'/action',{id:'different',action:'fill-prompt',args:{text:'must not execute'}});
    assert.ok(!attempted.ok || ['unsupported','rejected'].includes(attempted.body.status));
    assert.deepEqual((await send(current.mod,'/poll',{capabilities})).body.requests,[]);
  } finally {await Promise.all([owner.close(),owner.close()]);}
});


test('Claude browser refuses a transplanted snapshot before sending its token',async()=>{
  for(const pageOrigin of ['null','https://unrelated.invalid','http://127.0.0.1:32123']) {
    let requests=0,error;
    const adapter=claudeAdapter({snapshot:()=>snapshot,pageOrigin,fetch:async()=>{requests++;throw Error('must not fetch');}});
    await adapter.connect({receive:()=>assert.fail('must not render a mismatched origin'),fail:value=>{error=value;}});
    assert.match(error.message,/HTTP/);assert.equal(requests,0);
    assert.equal((await adapter.capabilities())['send-prompt'].available,false);
  }
});

test('MCP shutdown settles despite a client holding an unfinished action body',async t=>{
  const owner=createHostBridge();t.after(()=>owner.close());
  const view=await owner.createView(root),address=new URL(view.browser.url);
  const socket=connect({host:address.hostname,port:Number(address.port)});
  t.after(()=>socket.destroy());
  await new Promise((resolve,reject)=>{socket.once('connect',resolve);socket.once('error',reject);});
  socket.write(`POST /action HTTP/1.1\r\nHost: ${address.host}\r\nAuthorization: Bearer ${view.browser.token}\r\nContent-Length: 10000\r\nContent-Type: application/json\r\n\r\n{`);
  // A complete read-only roundtrip establishes that the listener is processing
  // requests while the first socket remains incomplete.
  assert.equal((await fetch(view.browser.url+'/capabilities',{headers:{Authorization:'Bearer '+view.browser.token}})).status,200);
  let timer;
  try {
    await Promise.race([owner.close(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('HTTP client blocked MCP shutdown')),1000);})]);
  } finally {clearTimeout(timer);socket.destroy();}
  await assert.rejects(fetch(view.browser.url));
});


test('HTTP action boundary rejects non-string identities and non-object arguments before dispatch',async t=>{
  const owner=createHostBridge();t.after(()=>owner.close());
  const view=await owner.createView(root);
  const post=async(descriptor,path,body)=>fetch(descriptor.url+path,{method:'POST',headers:{Authorization:'Bearer '+descriptor.token},body:JSON.stringify(body)});
  await post(view.mod,'/poll',{capabilities:{'call-tool':{available:true}}});
  for(const body of [{id:123,action:'call-tool'},{id:'invalid-array',action:'call-tool',args:[]},{id:'invalid-string',action:'call-tool',args:''}]) {
    assert.equal((await post(view.browser,'/action',body)).status,400);
  }
  assert.deepEqual((await (await post(view.mod,'/poll',{capabilities:{'call-tool':{available:true}}})).json()).requests,[]);
});
