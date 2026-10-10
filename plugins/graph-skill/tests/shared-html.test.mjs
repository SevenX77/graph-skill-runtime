import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile, mkdtemp, mkdir, writeFile, rm, realpath, symlink, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { codexAdapter } from '../src/adapters/codex.mjs';
import { claudeAdapter } from '../src/adapters/claude.mjs';
import { createClaudePreview, snapshotHtml, SNAPSHOT_SLOT, MAX_PREVIEW_BYTES } from '../src/adapters/claude-preview.mjs';
import { validateCanvas } from '../src/ui/canvas.mjs';
import { graph } from '../src/graph.mjs';

const payload = {graph:{...graph,width:352,height:548},skillRoot:'/business/中文 skill'};
const slot = /<script id="graph-skill-snapshot" type="application\/json">([\s\S]*?)<\/script>/;
const snapshot = text => JSON.parse(slot.exec(text)[1]);
test('both browser adapters deliver the same data and declare their actual root action',async()=>{
  const received=[],failed=[],actions=[];
  const app={connect:async()=>{},getHostCapabilities:()=>({experimental:{'openai/files':{}}}),request:async value=>actions.push(value),close:()=>{}};
  const codex=codexAdapter(app);
  const claude=claudeAdapter({snapshot:()=>payload,clipboard:{writeText:async root=>actions.push(root)}});
  await codex.connect({receive:p=>received.push(p),fail:e=>failed.push(e)});
  app.ontoolresult({structuredContent:payload});
  await claude.connect({receive:p=>received.push(p),fail:e=>failed.push(e)});
  assert.deepEqual(received,[payload,payload]);assert.equal(failed.length,0);
  await codex.openRoot(payload.skillRoot);await claude.openRoot(payload.skillRoot);
  assert.equal(actions[0].params.path,payload.skillRoot);assert.equal(actions[1],payload.skillRoot);
  assert.match(claude.rootActionLabel,/复制/);
  app.ontoolresult({isError:true,content:[{type:'text',text:'bad graph'}]});
  assert.equal(failed[0].message,'bad graph');
  app.request=async()=>{throw new Error('folder unavailable');};
  app.sendMessage=async value=>{actions.push(value);return {};};
  await codex.openRoot(payload.skillRoot);
  assert.match(actions[2].content[0].text,/中文 skill/);
  await claudeAdapter({snapshot:()=>({error:'invalidated'})}).connect({receive:()=>assert.fail(),fail:e=>assert.equal(e.message,'invalidated')});
});
test('shared validation rejects malformed roots, topology and bounds before rendering',()=>{
  assert.deepEqual(validateCanvas(payload),payload);
  for(const mutate of [p=>p.skillRoot=undefined,p=>p.graph.nodes=[],p=>p.graph.width=Infinity,p=>p.graph.nodes.push(p.graph.nodes[0]),p=>p.graph.nodes[0].x=NaN,p=>p.graph.nodes[0].x=10000,p=>p.graph.edges.push({from:'missing',to:'output'})]) {
    const value=structuredClone(payload);mutate(value);assert.throws(()=>validateCanvas(value));
  }
});
test('local snapshot changes only inert JSON and enforces host document size without truncation',async()=>{
  const html=await readFile(new URL('../dist/canvas.html',import.meta.url),'utf8');
  const value={...payload,extra:'</script><script>evil()</script><!-- $& 中文'};
  const output=snapshotHtml(html,value);
  assert.deepEqual(snapshot(output),value);
  assert.equal(output.replace(slot,SNAPSHOT_SLOT),html);
  assert.ok(!output.includes('<script>evil()'));
  assert.throws(()=>snapshotHtml(html,{value:'x'.repeat(MAX_PREVIEW_BYTES)}),/512 KiB/);
  assert.throws(()=>snapshotHtml('no slot',payload),/slot/);
});
test('real stdio writes shared local HTML, refreshes isolated roots and cleans up on connection close',async t=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'shared canvas 中文 ')));
  t.after(()=>rm(temp,{recursive:true,force:true}));
  async function fixture(name){
    const path=join(temp,name);await mkdir(join(path,'phases','process'),{recursive:true});
    await writeFile(join(path,'SKILL.md'),'---\nname: test\n---\n');
    await writeFile(join(path,'phases','process','LOGIC.md'),'# Logic\n');
    await writeFile(join(path,'graph.yaml'),`schema_version: gskill.graph.v1\ngraph_id: ${name}\nphases:\n  - id: process\n    depends_on: [input]\n    output: true\n`);
    return path;
  }
  const a=await fixture('one'),b=await fixture('two');
  const client=new Client({name:'shared-html-test',version:'1'});
  const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../dist/server.mjs',import.meta.url))],stderr:'pipe'});
  await client.connect(transport);t.after(()=>client.close());
  assert.deepEqual((await readdir(a)).sort(),['SKILL.md','graph.yaml','phases']);
  const show=skill_root=>client.callTool({name:'show_graph',arguments:{skill_root,presentation:'html'}});
  const result=await show(a),path=result.structuredContent.presentation.path;
  const other=await show(b),otherPath=other.structuredContent.presentation.path;
  assert.notEqual(path,otherPath);
  const resource=await client.readResource({uri:'ui://graph-skill/canvas-v2.html'});
  const content=await readFile(path,'utf8');
  assert.equal(content.replace(slot,SNAPSHOT_SLOT),resource.contents[0].text);
  assert.equal(resource.contents[0].text,await readFile(new URL('../dist/canvas.html',import.meta.url),'utf8'));
  assert.equal(snapshot(content).graph.id,'one');
  await writeFile(join(a,'graph.yaml'),(await readFile(join(a,'graph.yaml'),'utf8')).replace('graph_id: one','graph_id: updated'));
  assert.equal((await show(a)).structuredContent.presentation.path,path);
  assert.equal(snapshot(await readFile(path,'utf8')).graph.id,'updated');
  assert.equal(snapshot(await readFile(otherPath,'utf8')).graph.id,'two');
  await writeFile(join(a,'graph.yaml'),'broken');
  assert.equal((await show(a)).isError,true);
  assert.equal(typeof snapshot(await readFile(path,'utf8')).error,'string');
  await client.close();
  await assert.rejects(readFile(path),{code:'ENOENT'});
  await assert.rejects(readFile(otherPath),{code:'ENOENT'});
});
test('file owner preserves edits and rejects redirected cache paths',async t=>{
  const temp=await realpath(await mkdtemp(join(tmpdir(),'canvas owner ')));
  t.after(()=>rm(temp,{recursive:true,force:true}));
  const html=await readFile(new URL('../dist/canvas.html',import.meta.url),'utf8');
  const logs=[],preview=createClaudePreview(html,{report:x=>logs.push(x)});
  const root=join(temp,'skill');await mkdir(root);
  const path=await preview.show({...payload,skillRoot:root});
  await writeFile(path,'user edit');
  await assert.rejects(preview.show({...payload,skillRoot:root}),/preserved/);
  await preview.close();assert.equal(await readFile(path,'utf8'),'user edit');assert.ok(logs.length);
  const redirect=join(temp,'redirect'),outside=join(temp,'outside');
  await mkdir(redirect);await mkdir(outside);
  await symlink(outside,join(redirect,'.gskill'),process.platform==='win32'?'junction':'dir');
  const blocked=createClaudePreview(html);
  await assert.rejects(blocked.show({...payload,skillRoot:redirect}),/plain directory/);
  await blocked.close();assert.deepEqual(await readdir(outside),[]);
});
test('concurrent presentations serialize and separate process owners',async t=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'canvas concurrent ')));
  t.after(()=>rm(root,{recursive:true,force:true}));
  const html=await readFile(new URL('../dist/canvas.html',import.meta.url),'utf8');
  const first=createClaudePreview(html),second=createClaudePreview(html);
  t.after(async()=>{await first.close();await second.close();});
  const paths=await Promise.all(Array.from({length:6},(_,index)=>first.show({...payload,skillRoot:root,index})));
  assert.equal(new Set(paths).size,1);
  assert.equal(snapshot(await readFile(paths[0],'utf8')).index,5);
  const other=await second.show({...payload,skillRoot:root});
  assert.notEqual(paths[0],other);
  await first.close();assert.equal(snapshot(await readFile(other,'utf8')).skillRoot,root);
  await assert.rejects(first.show({...payload,skillRoot:root}),/closed/);
});
