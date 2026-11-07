import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { fakeRuntimeEnv } from "../support/runtime.mjs";

test('real MCP results retain a root view across edits and isolate roots and connections',async()=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'codex-canvas-')));
  const clients=[];
  const graph=id=>`schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n`;
  async function connect(){
    const client=new Client({name:'codex-view-test',version:'1'});
    clients.push(client);
    await client.connect(new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../../dist/server.mjs',import.meta.url))],stderr:'pipe',env:fakeRuntimeEnv()}));
    return client;
  }
  const show=(client,root)=>client.callTool({name:'show_graph',arguments:{skill_root:root}});
  const identity=result=>result._meta?.['openai/widgetSessionId'];
  try{
    for(const name of ['one','two']){
      const root=join(temp,name);
      await mkdir(join(root,'phases','work'),{recursive:true});
      await writeFile(join(root,'SKILL.md'),'# Test\n');
      await writeFile(join(root,'phases','work','LOGIC.md'),'# Logic\n');
      await writeFile(join(root,'graph.yaml'),graph(name));
    }
    const a=join(temp,'one'),b=join(temp,'two'),client=await connect();
    const first=await show(client,a),id=identity(first);
    assert.equal(typeof id,'string');assert.ok(id.length>0);
    assert.equal(identity(await show(client,a+'/.')),id);
    assert.equal((await client.callTool({name:'inspect_graph',arguments:{skill_root:a+'/.'}})).structuredContent.graph.id,'one');
    assert.notEqual(identity(await show(client,b)),id);
    await writeFile(join(a,'graph.yaml'),graph('changed'));
    assert.equal((await client.callTool({name:'inspect_graph',arguments:{skill_root:a}})).structuredContent.graph.id,'changed');
    const changed=await show(client,a);
    assert.equal(changed.structuredContent.graph.id,'changed');assert.equal(identity(changed),id);
    const inspected=await client.callTool({name:'inspect_graph',arguments:{skill_root:a}});
    assert.equal(identity(inspected),id);
    await writeFile(join(a,'graph.yaml'),'broken');
    const invalid=await show(client,a);
    // An invalid graph keeps the same canvas open and carries the runtime's diagnostics.
    assert.notEqual(invalid.isError,true);assert.equal(identity(invalid),id);
    assert.equal(invalid.structuredContent.graph,null);assert.equal(invalid.structuredContent.compile.status,'failed');
    assert.equal(invalid.structuredContent.compile.diagnostics[0].code,'[F-fake-runtime]');
    assert.match(invalid.content[0].text,/currently invalid[\s\S]*\[F-fake-runtime\]/);
    assert.equal(identity(await show(client,join(temp,'missing'))),undefined);
    await writeFile(join(a,'graph.yaml'),graph('restored'));
    const fresh=await show(await connect(),a);
    assert.notEqual(identity(fresh),id);
    assert.equal(fresh.structuredContent.graph.id,'restored');
  }finally{
    await Promise.all(clients.map(client=>client.close()));
    await rm(temp,{recursive:true,force:true});
  }
});
