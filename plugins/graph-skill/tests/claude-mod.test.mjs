import assert from 'node:assert/strict';
import {test} from 'node:test';
import {graphPayload, previewPath, register} from '../claude-mod/hooks/register.js';

const url = '/business/中文 skill/.gskill/canvas/view-Ab12cd/canvas.html';
const payload = {skillRoot:'/business/中文 skill',graph:{id:'actual'},presentation:{kind:'html',path:url}};
const tool = 'mcp__graph-skill-canvas__show_graph';
function host({available=true, canObserve=true}={}) {
  const handlers = [], opened = [], logs = [];
  register((name, matcher, fn) => handlers.push(typeof matcher === 'function' ? {name,matcher:{},fn:matcher} : {name,matcher,fn}));
  const api = {command:{register:async()=>{}},tool:{
    list:async()=>available ? [{name:'mcp__Claude_Browser__preview_start'},...(canObserve ? [{name:'mcp__Claude_Browser__tabs_context'}] : [])] : [],
    call:async value=>{opened.push(value);return {result:{}};}
  },ui:{log:value=>logs.push(value)}};
  const call=(event,input,next=async()=>({}))=>{
    const h=handlers.find(h=>h.name===event && Object.entries(h.matcher).every(([k,v])=>input[k]===v));
    return h ? h.fn(api,input,next) : next(input);
  };
  return {call,opened,logs};
}
test('Claude adapter requests HTML once and hands opening to the normal reviewed tool flow',async()=>{
  const h=host();let count=0;
  const result={result:JSON.stringify(payload),ref:42,text:'unchanged',context:['existing reminder']};
  const adapted=await h.call('tool.call',{tool,skill_root:'/symlink'},async input=>{
    count++;assert.equal(input.presentation,'html');assert.equal(input.skill_root,'/symlink');return result;
  });
  assert.equal(adapted.result,result.result);assert.equal(adapted.ref,42);assert.equal(adapted.text,result.text);
  assert.equal(adapted.context[0],'existing reminder');assert.equal(adapted.context.length,2);
  assert.ok(adapted.context[1].includes(JSON.stringify({url})));
  assert.match(adapted.context[1],/normal host tool mcp__Claude_Browser__preview_start/);
  assert.match(adapted.context[1],/mcp__Claude_Browser__tabs_context once with \{\}/);
  assert.match(adapted.context[1],/browserOpen alone does not establish visibility/);
  assert.match(adapted.context[1],/local-file preview entry/);
  assert.equal(count,1);
  assert.deepEqual(h.opened,[]);
  assert.ok((await h.call('command.run',{command:'graph-skill-canvas'})).text.includes(url));
  assert.equal(await h.call('ui.render',{component:'Pane'},async()=>'host'),'host');
  assert.equal(await h.call('tool.call',{tool:'unrelated'},async()=>'host'),'host');
});
test('Claude preserves graph results on denied, failed or unavailable preview paths',async()=>{
  const h=host();
  for(const result of [{deny:'no'},{isError:true},{result:{isError:true,structuredContent:payload}}]) {
    assert.equal(await h.call('tool.call',{tool,skill_root:'/skill'},async()=>result),result);
  }
  const demo={result:payload};
  assert.equal(await h.call('tool.call',{tool},async e=>{assert.equal(e.presentation,undefined);return demo;}),demo);
  assert.equal(h.opened.length,0);
  for(const options of [{available:false}]) {
    const adapter=host(options);let count=0;
    assert.equal(await adapter.call('tool.call',{tool,skill_root:'/skill'},async()=>{count++;return demo;}),demo);
    assert.equal(count,1);assert.equal(adapter.logs.length,1);
  }
  const limited=await host({canObserve:false}).call('tool.call',{tool,skill_root:'/skill'},async()=>demo);
  assert.equal(limited.result,payload);
  assert.match(limited.context[0],/does not expose Browser visibility/);
  assert.ok(!limited.context[0].includes('tabs_context'));
});
test('Claude validates owned local paths and MCP envelopes; rejects unrelated navigation',()=>{
  for(const result of [payload,{structuredContent:payload},JSON.stringify(payload),[{type:'text',text:JSON.stringify(payload)}],{content:[{type:'text',text:JSON.stringify(payload)}]}]) {
    assert.deepEqual(graphPayload({result}),payload);assert.equal(previewPath(graphPayload({result})),url);
  }
  for(const bad of ['https://example.com/','file:///private','http://127.0.0.1:31234/',url+'evil',url.replace('canvas.html','../private.html'),'/different'+url]) {
    assert.throws(()=>previewPath({...payload,presentation:{kind:'html',path:bad}}));
  }
  assert.throws(()=>previewPath({...payload,skillRoot:null}));
  const windows={...payload,skillRoot:'C:\\业务 skill',presentation:{kind:'html',path:'C:\\业务 skill\\.gskill\\canvas\\view-Ab12cd\\canvas.html'}};
  assert.equal(previewPath(windows),windows.presentation.path);
  assert.throws(()=>graphPayload({result:'broken'}));
});
