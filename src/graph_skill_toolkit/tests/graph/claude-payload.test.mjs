import assert from 'node:assert/strict';
import {test} from 'node:test';
import {graphPayload} from '../../apps/graph_canvas/claude_mod/payload.js';

const payload = {skillRoot:'/business/中文 skill',graph:{id:'actual'},presentation:{kind:'http',url:'http://127.0.0.1:31234/view/'+'a'.repeat(43)}};

test('the canvas Mod page reads its payload from every MCP result envelope and refuses a result without a graph',()=>{
  for(const result of [payload,{structuredContent:payload},JSON.stringify(payload),[{type:'text',text:JSON.stringify(payload)}],{content:[{type:'text',text:JSON.stringify(payload)}]}]) {
    assert.deepEqual(graphPayload({result}),payload);
  }
  assert.throws(()=>graphPayload({result:'broken'}));
  assert.throws(()=>graphPayload({result:{content:[{type:'text',text:'{"other":1}'}]}}),/no graph data/);
});
