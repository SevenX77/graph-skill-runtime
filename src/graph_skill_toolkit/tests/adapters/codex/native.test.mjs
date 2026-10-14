import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mcpConnection } from '../../../adapters/codex/connection/index.mjs';
import { codexAdapter } from '../../../adapters/codex/driver/index.mjs';
import { mkdtemp, mkdir, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { fakeRuntimeEnv } from "../../support/runtime.mjs";

test('Codex opens only an explicit file path; directory reveal remains unknown without a host API', async () => {
  const files=[],messages=[];
  const app={
    getHostCapabilities:()=>({experimental:{'openai/files':{}},message:{}}),
    request:async value=>{files.push(value);return {};},
    sendMessage:async value=>{messages.push(value);return {};},
  };
  const adapter=codexAdapter(app);
  await adapter.invoke('files.openFile',{path:'C:\\Users\\test\\hello-world\\SKILL.md'});
  await adapter.invoke('files.openFile',{path:'C:/Users/test/hello-world/SKILL.md'});
  assert.deepEqual(files.map(call=>call.params.path),[
    'C:/Users/test/hello-world/SKILL.md','C:/Users/test/hello-world/SKILL.md',
  ]);
  assert.equal((await adapter.invoke('files.revealDirectory',{path:'C:\\Users\\test\\hello-world'})).status,'unsupported');
  assert.equal(files.length,2);
  assert.equal(messages.length,0);
  app.getHostCapabilities=()=>({experimental:{'openai/files':{}}});
  assert.equal((await adapter.invoke('files.revealDirectory',{path:'C:/Users/test/hello-world'})).status,'unsupported');
  assert.equal(messages.length,0);
});

test('Codex receiving graph data has no file opening or message side effect',async()=>{
  const received=[];
  const app={connect:async()=>{},close:async()=>{},request:()=>assert.fail('Unexpected file request'),sendMessage:()=>assert.fail('Unexpected host turn')};
  const connection=mcpConnection(app);
  try {
  await connection.connect({receive:p=>received.push(p),fail:assert.fail});
  const payload={skillRoot:'C:/skill',graph:{id:'main'}};
  app.ontoolresult({structuredContent:payload});
  assert.deepEqual(received,[payload]);
  } finally { await connection.dispose(); }
});

test('Codex draft append is gated by the advertised extension and never sends the draft', async()=>{
  const messages=[];
  let capabilities={message:{text:{}},experimental:{'openai/message':{draft:{}}}};
  const adapter=codexAdapter({
    getHostCapabilities:()=>capabilities,
    sendMessage:async value=>{messages.push(value);return {};},
  });
  assert.equal((await adapter.invoke('composer.writeDraft',{text:'DRAFT-APPEND',mode:'append'})).status,'accepted');
  assert.deepEqual(messages,[{role:'user',content:[{type:'text',text:'DRAFT-APPEND'}],_meta:{'openai/message':{target:'active',send:false}}}]);
  capabilities={message:{text:{}},experimental:{'openai/message':{}}};
  assert.equal((await adapter.invoke('composer.writeDraft',{text:'Do not submit',mode:'append'})).status,'unsupported');
  assert.equal(messages.length,1);
});

test('real MCP results retain a root view across edits and isolate roots and connections',async()=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'codex-canvas-')));
  const clients=[];
  const graph=id=>`schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n`;
  async function connect(){
    const client=new Client({name:'codex-view-test',version:'1'});
    clients.push(client);
    await client.connect(new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../../../dist/server.mjs',import.meta.url))],stderr:'pipe',env:fakeRuntimeEnv()}));
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
