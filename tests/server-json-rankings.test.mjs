import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import crypto from 'node:crypto';
import {readServerJsonRankings} from '../lib/server-json-rankings.mjs';
import {assertRequestedArtifactFormat, toolsForArtifactFormat} from '../lib/artifact-format-policy.mjs';

function load(path, bindings, names) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '')
    .replace(/^export\s+/gm, '');
  return new Function(...Object.keys(bindings), source + `\nreturn {${names.join(',')}};`)(...Object.values(bindings));
}
const metric = (label, key, divisor = 1) => ({label, unit: 'fixture', divisor,
  value_paths: [['stats', 'minecraft:custom', key]]});
const args = () => ({path:'/srv/fixture/stats', pattern:'*.json', recursive:false,
  max_files:120, identity_map_path:'', limit:10,
  metrics:[metric('Playtime','minecraft:play_time',72000), metric('Distance','*_one_cm',100000),
    metric('Mob kills','minecraft:mob_kills'),metric('Player kills','minecraft:player_kills'),metric('Deaths','minecraft:deaths')]});
function dataset(count=43) {
  const items = Array.from({length:count},(_,i)=>({relative_path:`id${String(i).padStart(2,'0')}.json`,
    content:JSON.stringify({stats:{'minecraft:custom':{'minecraft:play_time':i*72000,
      'minecraft:walk_one_cm':i*100000,'minecraft:sprint_one_cm':i*200000,
      'minecraft:mob_kills':i*10,'minecraft:player_kills':i,'minecraft:deaths':i+1},
      'minecraft:mined':{unrelated: 'SOURCE_ONLY_NOT_FOR_PROVIDER'.repeat(1500)}}},null,2)}));
  return {complete:true,truncated:false,scan_truncated:false,files_discovered:count,files_returned:count,items};
}

test('local aggregation covers all 43 files, five top tens, units and mapped identities without raw data',async()=>{
  const input=dataset();
  const request={...args(),identity_map_path:'/srv/fixture/usercache.json'};
  const calls=[];
  const tools=load('../lib/tool-runtime.js',{readServerJsonRankings,hostInspect:async a=>{
    calls.push(a);
    return a.pattern==='usercache.json'?{...dataset(1),items:[{relative_path:'usercache.json',
      content:JSON.stringify([{uuid:'id42',name:'Fixture Leader'}])}]}:input;
  }},['executeVectorTool','getVectorTools']);
  const context={};
  const result=await tools.executeVectorTool({name:'server_json_rankings',arguments:request,context});
  assert.equal(calls.length,2);
  assert.equal(result.files_processed,43);
  assert.equal(result.source_complete,true);
  assert.equal(result.local_processing,true);
  assert.equal(result.rankings.length,5);
  for(const ranking of result.rankings){
    assert.equal(ranking.rows.length,10);
    assert.equal(ranking.valid_records,43);
    assert.equal(ranking.rows[0].name,'Fixture Leader');
    assert.equal(ranking.rows[0].rank,1);
    assert.equal(ranking.rows.at(-1).id,'id33');
  }
  assert.equal(result.rankings[0].rows[0].value,42);
  assert.equal(result.rankings[1].rows[0].value,126);
  assert.ok(!JSON.stringify(result).includes('SOURCE_ONLY_NOT_FOR_PROVIDER'));
  assert.ok(JSON.stringify(result).length < JSON.stringify(input).length * 0.05);
  assert.ok(context.bulkEvidence);
  assert.ok(!tools.getVectorTools({allowServer:false}).some(t=>t.name==='server_json_rankings'));
  assert.ok(tools.getVectorTools({allowServer:true}).some(t=>t.name==='server_json_rankings'));
});

test('incomplete scans, truncated items and invalid JSON never become complete rankings',async()=>{
  const cases=[{complete:false},{truncated:true},{scan_truncated:true},{files_returned:42},
    {items:[]},{files_discovered:0,files_returned:0,items:[]}];
  for(const change of cases) await assert.rejects(readServerJsonRankings(args(),async()=>({...dataset(),...change})),/every source/);
  const truncated=dataset();truncated.items[0].truncated=true;
  await assert.rejects(readServerJsonRankings(args(),async()=>truncated),/every source/);
  const invalid=dataset();invalid.items[0].content='{';
  await assert.rejects(readServerJsonRankings(args(),async()=>invalid),/valid JSON/);
  const duplicate=dataset();duplicate.items[1].relative_path=duplicate.items[0].relative_path;
  await assert.rejects(readServerJsonRankings(args(),async()=>duplicate),/duplicate source/);
});

test('missing and invalid numbers are excluded and reported, never zero-filled',async()=>{
  const bulk=dataset(3);
  bulk.items[0].content=JSON.stringify({stats:{'minecraft:custom':{}}});
  bulk.items[1].content=JSON.stringify({stats:{'minecraft:custom':{'minecraft:play_time':'not numeric'}}});
  const result=await readServerJsonRankings(args(),async()=>bulk);
  assert.equal(result.rankings[0].missing,1);
  assert.equal(result.rankings[0].invalid,1);
  assert.equal(result.rankings[0].valid_records,1);
  assert.equal(result.rankings[0].rows[0].value,2);
  assert.equal(result.rankings[1].missing,2);
});

test('invalid inputs, overlapping fields and unsafe values are rejected without reading a host',async()=>{
  let reads=0;const inspect=async()=>{reads++;return dataset();};
  for(const change of [{path:'/srv/../etc'}, {max_files:121}, {limit:51}, {metrics:[]}]) {
    await assert.rejects(readServerJsonRankings({...args(),...change},inspect));
  }
  for(const paths of [[['constructor']], [['a'],['a']], [['*'],['a']], [['a*b']]]){
    await assert.rejects(readServerJsonRankings({...args(),metrics:[{...args().metrics[0],value_paths:paths}]},inspect));
  }
  assert.equal(reads,0);
  const bulk=dataset(1);
  bulk.items[0].content=JSON.stringify({stats:{'minecraft:custom':{'minecraft:play_time':Number.MAX_SAFE_INTEGER+1}}});
  const result=await readServerJsonRankings(args(),async()=>bulk);
  assert.equal(result.rankings[0].invalid,1);
  assert.deepEqual(result.rankings[0].rows,[]);
});

test('the real agent sends compact rankings through privacy filtering and records per-call usage',async()=>{
  const input=dataset();const sent=[],renders=[];let n=0;
  const tools=load('../lib/tool-runtime.js',{readServerJsonRankings,crypto,
    assertRequestedArtifactFormat,hostInspect:async()=>input,
    createChatArtifact:async data=>{renders.push(data);return {artifact:{format:'pdf'}};},
    buildArtifactPlan:x=>x,summarizeArtifactPlan:x=>x},['getVectorTools','createToolContext','executeVectorTool']);
  const {runVectorAgent}=load('../lib/agent-runtime.js',{
    ...tools,assertRequestedArtifactFormat,toolsForArtifactFormat,
    sanitizeForExternal:text=>({sanitized:text,mappings:[]}),savePrivacyMappings:async()=>{},
    requestProviderResponse:async({payload})=>{
      sent.push(structuredClone(payload));n++;
      return {id:`fixture${n}`,status:'completed',usage:{input_tokens:100,output_tokens:20,
        input_tokens_details:{cached_tokens:10},output_tokens_details:{reasoning_tokens:5}},
        output:n===1?[{type:'function_call',name:'server_json_rankings',call_id:'rank',arguments:JSON.stringify(args())}]:
          [{type:'message',content:[{type:'output_text',text:'# Fixture ranking\n\nVerified fixture results.'}]}]};
    }
  },['runVectorAgent']);
  const request='Erstelle ein PDF mit den Ranglisten von meinem Server.';
  const result=await runVectorAgent({model:'fixture',mode:'normal',messages:[{role:'user',content:request}],
    originalUserMessage:request,maxOutputTokens:1400,allowServer:true,conversationId:'fixture',
    userId:'fixture',jobId:'fixture',
    executionClass:'artifact',toolDomains:{server:true},roundLimit:2});
  assert.equal(renders.length,1);
  assert.equal(sent.length,2);
  assert.ok(sent[0].tools.some(t=>t.name==='server_json_rankings'));
  assert.ok(!JSON.stringify(sent).includes('SOURCE_ONLY_NOT_FOR_PROVIDER'));
  assert.equal(result.providerCalls.length,2);
  assert.equal(result.providerCalls[0].phase,'agent-turn');
  assert.equal(result.providerCalls[0].reasoningTokens,5);
  assert.equal(result.providerCalls[0].cachedTokens,10);
  assert.equal(result.inputTokens,200);
  assert.equal(result.outputTokens,40);
  assert.equal(result.cachedTokens,20);
  const trace=result.toolTrace.find(t=>t.tool==='server_json_rankings');
  assert.ok(trace.sentCharacters>0);
  assert.ok(trace.sentCharacters<JSON.stringify(input).length*0.05);
});
