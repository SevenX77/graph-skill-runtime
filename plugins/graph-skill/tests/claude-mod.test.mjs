import assert from 'node:assert/strict';
import {test} from 'node:test';
import {graphPayload, makeCanvas, register} from '../claude-mod/hooks/register.js';
import {projectGraph} from '../src/project-graph.mjs';

const payload = {
  skillRoot: '/business/中文 skill',
  graph: projectGraph({graph_id:'actual',phases:[
    {id:'greet',depends_on:['input'],output:false},
    {id:'suffix',depends_on:['greet'],output:true}
  ]}, {greet:'LOGIC',suffix:'LOGIC'})
};

function host() {
  const handlers = [];
  register((name, matcher, fn) => { handlers.push({name, matcher, fn}); });
  const opened = [], logs = [];
  const ui = {
    open:async value => {opened.push(value);return {isPlaced:true};},
    invalidate:()=>{}, log:value=>logs.push(value),
    resolve:()=>Object.fromEntries(['Box','Text','Svg'].map(type=>[type, props=>{
      // The real host rejects Text.text. This reproduces the first native failure.
      if(type==='Text') assert.deepEqual(Object.keys(props).filter(k=>!['children','bold'].includes(k)),[]);
      return {type,props};
    }]))
  };
  const call = (event, input, next=async()=>({})) => {
    const handler=handlers.find(h=>h.name===event && Object.entries(h.matcher).every(([k,v])=>input[k]===v));
    return handler ? handler.fn({ui},input,next) : next(input);
  };
  return {call,opened,logs};
}

test('Mod observes exactly one completed graph call and returns it unchanged', async()=>{
  const h=host();let calls=0;
  const result={result:JSON.stringify(payload)};
  assert.equal(await h.call('tool.call',{tool:'mcp__graph-skill-canvas__show_graph',skill_root:'/symlink'},async()=>{calls++;return result;}),result);
  assert.equal(calls,1);assert.equal(h.opened.length,1);
  const tree=await h.call('ui.render',{component:'Pane',requestId:'graph-skill-canvas',surface:'desktop'});
  assert.equal(tree.props.children[1].props.children[0],payload.skillRoot);
  assert.equal(tree.props.children[3].type,'Svg');
  assert.match(tree.props.children[3].props.source,/>suffix</);
  assert.equal((tree.props.children[3].props.source.match(/marker-end=/g)||[]).length,3);
  assert.equal(await h.call('ui.render',{component:'Pane',requestId:'other'},async()=>'host'),'host');
  assert.equal(await h.call('tool.call',{tool:'unrelated'},async()=>'host'),'host');
  assert.equal(h.opened.length,1);
});

test('Mod skips denied, failed and demo results and exposes malformed graph failures without rerunning',async()=>{
  const h=host();
  for(const value of [{deny:'no'},{isError:true},{result:{isError:true,structuredContent:payload}}]) assert.equal(await h.call('tool.call',{tool:'mcp__graph-skill-canvas__show_graph',skill_root:'/skill'},async()=>value),value);
  const demo={result:payload};assert.equal(await h.call('tool.call',{tool:'mcp__graph-skill-canvas__show_graph'},async()=>demo),demo);
  const broken={result:'not JSON'};let calls=0;
  assert.equal(await h.call('tool.call',{tool:'mcp__graph-skill-canvas__show_graph',skill_root:'/skill'},async()=>{calls++;return broken;}),broken);
  assert.equal(calls,1);assert.equal(h.opened.length,0);assert.equal(h.logs.length,1);
  const tree=await h.call('ui.render',{component:'Pane',requestId:'graph-skill-canvas',surface:'desktop'});
  assert.equal(tree.type,'Text');assert.match(tree.props.children[0],/Unable to show/);
});

test('MCP result envelopes retain the same graph; SVG escapes labels and rejects malformed topology',()=>{
  for(const result of [payload,{structuredContent:payload},JSON.stringify(payload),[{type:'text',text:JSON.stringify(payload)}],{content:[{type:'text',text:JSON.stringify(payload)}]}]) assert.deepEqual(graphPayload({result}),payload);
  const malicious=structuredClone(payload);malicious.graph.nodes[0].label='<script>alert("x")</script>';
  const svg=makeCanvas(malicious).source;assert.doesNotMatch(svg,/<script>/);assert.match(svg,/&lt;script&gt;/);
  for(const mutate of [p=>p.graph.nodes.push(p.graph.nodes[0]),p=>p.graph.nodes[0].x=NaN,p=>p.graph.edges.push({from:'missing',to:'greet'}),p=>p.graph.width=Infinity,p=>p.graph.nodes[0].label='中'.repeat(50000)]){
    const value=structuredClone(payload);mutate(value);assert.throws(()=>makeCanvas(value));
  }
});
