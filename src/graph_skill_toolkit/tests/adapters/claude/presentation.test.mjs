import assert from 'node:assert/strict';
import {test} from 'node:test';
import {previewProjectRoot, previewTarget} from '../../../plugin_base/adapters/claude/presentation/guidance/index.mjs';
import {graphPayload} from '../../../apps/graph_canvas/claude_mod/payload.js';
import {register} from '../../../apps/graph_canvas/claude_mod/hooks/register.js';

const projectRoot = '/host/project';
const url = 'http://127.0.0.1:31234/view/' + 'a'.repeat(64);
const token = 'mod_' + 'b'.repeat(48);
const payload = {skillRoot:'/business/中文 skill',graph:{id:'actual'},presentation:{
  kind:'http',url,preview:{name:'graph-skill-test',projectRoot},bridge:{url:'http://127.0.0.1:31234',token,key:'/business/中文 skill'},
}};
const tool = 'mcp__graph-skill-canvas__show_graph';
function host({available=true, canNavigate=true, canObserve=true, canSelect=true, root=projectRoot, rootError=false}={}) {
  const handlers = [], opened = [], logs = [];
  register((name, matcher, fn) => handlers.push(typeof matcher === 'function' ? {name,matcher:{},fn:matcher} : {name,matcher,fn}));
  const api = {command:{register:async()=>{}},session:{id:async()=>"native-session",version:async()=>({version:"native-engine"}),root:async()=>{
    if(rootError) throw new Error('session root unavailable');
    return root;
  }},tool:{
    list:async()=>available ? [{name:'mcp__Claude_Browser__preview_start'},...(canNavigate ? [{name:'mcp__Claude_Browser__navigate'}] : []),...(canObserve ? [{name:'mcp__Claude_Browser__tabs_context'}] : []),...(canSelect ? [{name:'mcp__Claude_Browser__tabs_select'}] : [])] : [],
    call:async value=>{opened.push(value);return {result:{}};}
  },ui:{log:value=>logs.push(value)}};
  const call=(event,input,next=async()=>({}))=>{
    const h=handlers.find(h=>h.name===event && Object.entries(h.matcher).every(([k,v])=>input[k]===v));
    return h ? h.fn(api,input,next) : next(input);
  };
  return {call,opened,logs};
}

test('Claude binds HTTP preview to the actual session root and requests normal attach then navigate',async()=>{
  const h=host();let count=0;
  const result={result:JSON.stringify(payload),ref:42,text:'unchanged',context:['existing reminder']};
  const adapted=await h.call('tool.call',{tool,skill_root:'/business-link',preview_project_root:'/untrusted-other-project',native_host:{sessionId:'model-forged'}},async input=>{
    count++;assert.equal(input.presentation,'html');assert.equal(input.skill_root,'/business-link');
    assert.equal(input.preview_project_root,projectRoot);
    assert.deepEqual(input.native_host,{name:'Claude Code',version:'native-engine',client_type:'claude_code',sessionId:'native-session',source:'claude-mod-session'});return result;
  });
  assert.equal(adapted.result,result.result);assert.equal(adapted.ref,42);assert.equal(adapted.text,result.text);
  assert.equal(adapted.context[0],'existing reminder');assert.equal(adapted.context.length,2);
  const reminder=adapted.context[1];
  assert.match(reminder,/normal host tool mcp__Claude_Browser__preview_start once with \{"name":"graph-skill-test"\}/);
  assert.match(reminder,/Pass only name, without url/);
  assert.match(reminder,/2\. Use the normal host tool mcp__Claude_Browser__preview_start once with/);
  const steps=['1. Use','2. Use','3. Use','4. Use','5. Only after selection completes'].map(step=>reminder.indexOf(step));
  assert.ok(steps.every((index,i)=>index>=0&&(i===0||index>steps[i-1])),reminder);
  assert.equal(reminder.indexOf('6. '),-1);
  // The canvas is the only view this sequence opens: no document tab, file preview or file tool.
  assert.doesNotMatch(reminder,/SKILL\.md|DOCUMENT_TAB|document|file preview|open_in_codex|show_pane|fileUrl/i);
  assert.match(reminder,/Open no other page or file for this flow/);
  // A hidden pane is revealed by the user; the agent never opens a file to reveal it.
  assert.match(reminder,/If the Browser pane is hidden, the page is ready but not visible: ask the user in one sentence to open it manually/);
  assert.match(reminder,/do not open any file or other page to reveal it/);
  assert.match(reminder,/HTTP_TAB active at the returned HTTP origin/);
  assert.ok(reminder.includes(JSON.stringify(url)));assert.ok(reminder.includes(JSON.stringify(projectRoot)));
  assert.match(reminder,/actual returned tabId/);
  assert.match(reminder,/never assume the literal seed ID/);
  // Regression: navigating any tab other than HTTP_TAB created an unwanted third tab on the real host.
  assert.match(reminder,/and tabId HTTP_TAB\. Navigate no other tab/);
  assert.match(reminder,/Never close tabs or create a temporary HTML file/);
  assert.match(reminder,/every pre-existing tab preserved/);
  assert.match(reminder,/Only after selection completes/);
  assert.doesNotMatch(reminder,/tabs_close/);
  assert.match(reminder,/mcp__Claude_Browser__tabs_context with \{\}/);
  assert.match(reminder,/browserOpen alone does not establish visibility/);
  assert.ok(!reminder.includes(token));
  assert.equal(count,1);assert.deepEqual(h.opened,[]);
  assert.ok((await h.call('command.run',{command:'graph-skill-canvas'})).text.includes(url));
  assert.equal(await h.call('ui.render',{component:'Pane'},async()=>'host'),'host');
  assert.equal(await h.call('tool.call',{tool:'unrelated'},async()=>'host'),'host');
});

test('Claude preserves denied and failed tool results without making any preview calls',async()=>{
  const h=host();
  for(const result of [{deny:'no'},{isError:true},{result:{isError:true,structuredContent:payload}}]) {
    assert.equal(await h.call('tool.call',{tool,skill_root:'/skill'},async()=>result),result);
  }
  const demo={result:payload};
  assert.equal(await h.call('tool.call',{tool},async e=>{assert.equal(e.presentation,undefined);return demo;}),demo);
  assert.equal(h.opened.length,0);
});

test('Missing Browser or valid host root preserves graph-only results and strips model-provided preview ownership',async()=>{
  for(const options of [{available:false},{canNavigate:false},{rootError:true},{root:''},{root:'relative'},{root:'/host/../other'},{root:'\\\\server\\share'}]) {
    const h=host(options);let count=0;
    const result={result:{graph:{id:'graph-only'}},ref:17,context:['existing']};
    const adapted=await h.call('tool.call',{tool,skill_root:'/skill',presentation:'html',preview_project_root:'/untrusted-other-project'},async input=>{
      count++;assert.equal(input.presentation,undefined);assert.equal(input.preview_project_root,undefined);return result;
    });
    assert.equal(count,1);assert.equal(adapted.result,result.result);assert.equal(adapted.ref,result.ref);
    assert.equal(adapted.context[0],'existing');assert.match(adapted.context[1],/Unable to show the graph/);
    assert.match(adapted.context[1],/graph result is preserved/);assert.equal(h.logs.length,1);assert.deepEqual(h.opened,[]);
    assert.match((await h.call('command.run',{command:'graph-skill-canvas'})).text,/Unable to show the graph/);
  }
});

test('A mismatched output project is rejected; missing visibility tools never imply a visible pane',async()=>{
  const mismatched={...payload,presentation:{...payload.presentation,preview:{...payload.presentation.preview,projectRoot:'/other'}}};
  const h=host();
  const rejected=await h.call('tool.call',{tool,skill_root:payload.skillRoot},async()=>({result:mismatched}));
  assert.equal(rejected.result,mismatched);assert.match(rejected.context[0],/different session project root/);
  assert.ok(!rejected.context[0].includes('preview_start once'));
  assert.deepEqual(h.opened,[]);
  for(const options of [{canObserve:false},{canSelect:false}]) {
    const limited=await host(options).call('tool.call',{tool,skill_root:'/skill'},async()=>({result:payload}));
    assert.equal(limited.result,payload);assert.match(limited.context[0],/does not expose Browser visibility/);
    assert.ok(!limited.context[0].includes('tabs_context'));
    assert.match(limited.context[0],/Do not open another page/);
  }
});

test('Claude validates MCP envelopes, absolute project identity and authenticated opaque preview URLs',()=>{
  for(const result of [payload,{structuredContent:payload},JSON.stringify(payload),[{type:'text',text:JSON.stringify(payload)}],{content:[{type:'text',text:JSON.stringify(payload)}]}]) {
    assert.deepEqual(graphPayload({result}),payload);
    assert.deepEqual(previewTarget(graphPayload({result}),projectRoot),{url,name:'graph-skill-test',projectRoot});
  }
  const windows={...payload,skillRoot:'C:/Business Skill',presentation:{...payload.presentation,preview:{name:'graph-skill-test',projectRoot:'c:/Business Project/'}}};
  assert.equal(previewTarget(windows,'C:\\Business Project').projectRoot,'c:/Business Project/');
  for(const root of ['relative','C:relative','\\\\server\\share','//server/share','/path/../other','C:\\path\\.\\other','/bad\nroot','/bad\0root',null]) {
    assert.throws(()=>previewProjectRoot(root));
  }
  for(const bad of [
    'https://example.com/', 'file:///private', 'http://127.0.0.1:31234/',
    url.replace(':31234',':31235'),url.replace('/view/','/other/'),url.slice(0,-1),url+'b',url+'?x=1',url+'#secret',
    url.replace('http://','http://user:password@'),url.replace('127.0.0.1','localhost'),
  ]) assert.throws(()=>previewTarget({...payload,presentation:{...payload.presentation,url:bad}},projectRoot));
  assert.throws(()=>previewTarget({...payload,presentation:{kind:'html',path:'/old/canvas.html'}},projectRoot));
  assert.throws(()=>previewTarget({...payload,presentation:{...payload.presentation,bridge:undefined}},projectRoot));
  assert.throws(()=>previewTarget({...payload,presentation:{...payload.presentation,bridge:{...payload.presentation.bridge,url:'http://127.0.0.1:31234/other'}}},projectRoot));
  assert.throws(()=>previewTarget({...payload,presentation:{...payload.presentation,preview:{name:'bad name',projectRoot}}},projectRoot));
  assert.throws(()=>graphPayload({result:'broken'}));
});

test('a stray document member is not consumed by the Claude preview target',()=>{
  const stray={...payload,document:{path:'/other/SKILL.md',fileUrl:'file:///other/SKILL.md'}};
  assert.deepEqual(previewTarget(stray,projectRoot),{url,name:'graph-skill-test',projectRoot});
});
