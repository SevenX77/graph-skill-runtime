import assert from 'node:assert/strict';
import { test } from 'node:test';
import { codexAdapter } from '../adapters/codex/browser/index.mjs';
import { mkdtemp, mkdir, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';

test('Codex file requests use the same Windows path identity and never route folders through the file API', async () => {
  const files=[],messages=[];
  const app={
    getHostCapabilities:()=>({experimental:{'openai/files':{}},message:{}}),
    request:async value=>{files.push(value);return {};},
    sendMessage:async value=>{messages.push(value);return {};},
  };
  const adapter=codexAdapter(app);
  await adapter.invoke('open-file',{skillRoot:'C:\\Users\\test\\hello-world'});
  await adapter.invoke('open-file',{skillRoot:'C:/Users/test/hello-world/'});
  assert.deepEqual(files.map(call=>call.params.path),[
    'C:/Users/test/hello-world/SKILL.md','C:/Users/test/hello-world/SKILL.md',
  ]);
  assert.equal((await adapter.invoke('open-root',{skillRoot:'C:\\Users\\test\\hello-world'})).status,'accepted');
  assert.equal(files.length,2);
  assert.equal(messages.length,1);
  assert.match(messages[0].content[0].text,/打开此路径/);
  app.getHostCapabilities=()=>({experimental:{'openai/files':{}}});
  assert.equal((await adapter.capabilities())['open-root'].available,false);
  assert.equal((await adapter.invoke('open-root',{skillRoot:'C:/Users/test/hello-world'})).status,'unsupported');
  assert.equal(messages.length,1);
});

test('Codex receiving graph data has no file opening or message side effect',async()=>{
  const received=[];
  const app={connect:async()=>{},request:()=>assert.fail('Unexpected file request'),sendMessage:()=>assert.fail('Unexpected host turn')};
  await codexAdapter(app).connect({receive:p=>received.push(p),fail:assert.fail});
  const payload={skillRoot:'C:/skill',document:{path:'C:/skill/SKILL.md'},graph:{id:'main'}};
  app.ontoolresult({structuredContent:payload});
  assert.deepEqual(received,[payload]);
});

test('Codex draft append is gated by the advertised extension and never sends the draft', async()=>{
  const messages=[];
  let capabilities={message:{text:{}},experimental:{'openai/message':{draft:{}}}};
  const adapter=codexAdapter({
    getHostCapabilities:()=>capabilities,
    sendMessage:async value=>{messages.push(value);return {};},
  });
  assert.equal((await adapter.capabilities())['fill-prompt'].available,true);
  assert.equal((await adapter.invoke('fill-prompt',{skillRoot:'C:/skill',text:'DRAFT-APPEND'})).status,'accepted');
  assert.deepEqual(messages,[{role:'user',content:[{type:'text',text:'DRAFT-APPEND'}],_meta:{'openai/message':{target:'active',send:false}}}]);
  capabilities={message:{text:{}},experimental:{'openai/message':{}}};
  assert.equal((await adapter.invoke('fill-prompt',{skillRoot:'C:/skill',text:'Do not submit'})).status,'unsupported');
  assert.equal(messages.length,1);
});

test('real MCP results retain a root view across edits and isolate roots and connections',async()=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'codex-canvas-')));
  const clients=[];
  const graph=id=>`schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n`;
  async function connect(){
    const client=new Client({name:'codex-view-test',version:'1'});
    clients.push(client);
    await client.connect(new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../dist/server.mjs',import.meta.url))],stderr:'pipe'}));
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
    assert.notEqual(identity(await show(client,b)),id);
    await writeFile(join(a,'graph.yaml'),graph('changed'));
    const changed=await show(client,a);
    assert.equal(changed.structuredContent.graph.id,'changed');assert.equal(identity(changed),id);
    const inspected=await client.callTool({name:'inspect_graph',arguments:{skill_root:a}});
    assert.equal(identity(inspected),id);
    await writeFile(join(a,'graph.yaml'),'broken');
    const invalid=await show(client,a);
    assert.equal(invalid.isError,true);assert.equal(identity(invalid),id);
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
