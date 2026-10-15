import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {localWorkerPayload,runLocalWorker,requestLocalChat,extractionSchema,validateExtraction} from '../lib/local-worker-core.mjs';
import {withProviderUsageScope,providerUsageEvent} from '../lib/provider-call-usage.mjs';
const args = {role:'extract',task:'Return players and deaths as JSON.',evidence:'players 3; deaths unknown',fields:[{name:'players',type:'integer'},{name:'deaths',type:'integer'}]};
const context = () => ({userId:'fixture-user',jobId:'fixture-job',allowLocalWorkers:true});
const body = () => ({done:true,done_reason:'stop',message:{content:'{"players":3,"deaths":null}'},prompt_eval_count:60,eval_count:13});
const options = {enabled:true,exclusive: execute=>execute(),request:async()=>body()};
function load(path, bindings, names) {
  const source=readFileSync(new URL(path,import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
  return new Function(...Object.keys(bindings),source+`\nreturn {${names.join(',')}};`)(...Object.values(bindings));
}

test('roles select fixed models and send no tools or cross-user memory',()=>{
  const payload=localWorkerPayload({...args,model:'cloud',tools:['shell'],userId:'other-user'});
  assert.equal(payload.model,'vector-qwen3:0.6b-q8');
  assert.equal(payload.tools,undefined);
  assert.equal(payload.options.num_thread,2);
  assert.equal(payload.options.num_ctx,4096);
  assert.ok(!JSON.stringify(payload).includes('other-user'));
  assert.equal(localWorkerPayload({...args,role:'summarize'}).model,'vector-hermes3:8b-q4km');
  assert.throws(()=>localWorkerPayload({...args,role:'__proto__'}));
  assert.throws(()=>localWorkerPayload({...args,evidence:'ü'.repeat(1500)}),/No data was truncated/);
});

test('permissions, identity, feature flag and shared job budget are enforced before I/O',async()=>{
  let calls=0;
  const deps={...options,request:async()=>{calls++;return body();}};
  for(const ctx of [{}, {...context(),userId:null}, {...context(),jobId:null}, {...context(),allowLocalWorkers:false}])
    await assert.rejects(runLocalWorker(args,ctx,deps),/authorized/);
  await assert.rejects(runLocalWorker(args,context(),{...deps,enabled:false}),/authorized/);
  assert.equal(calls,0);
  const ctx=context();
  await runLocalWorker(args,ctx,deps); await runLocalWorker(args,ctx,deps);
  await assert.rejects(runLocalWorker(args,ctx,deps),/two calls/);
  assert.equal(calls,2);
  const failed=context();
  for(let i=0;i<2;i++) await assert.rejects(runLocalWorker(args,failed,{...deps,request:async()=>{throw Error('offline');}}),/offline/);
  await assert.rejects(runLocalWorker(args,failed,deps),/two calls/);
});

test('real scoped ledger counts local tokens at zero API cost and retains rejected output usage',async()=>{
  const events=[];
  await withProviderUsageScope(async(runtime,response)=>{
    const event=providerUsageEvent({runtime,response,userId:'fixture-user',jobId:'fixture-job',exchangeRate:0.8});
    events.push(event); return event;
  }, async scope=>{
    const output=await runLocalWorker(args,context(),options);
    assert.equal(output.data.deaths,null);
    assert.equal(output.independently_verified,false);
    await assert.rejects(runLocalWorker(args,context(),{...options,request:async()=>({...body(),done_reason:'length'})}),/incomplete/);
    assert.equal(scope.events.length,2);
  });
  for(const event of events){assert.equal(event.inputTokens,60);assert.equal(event.outputTokens,13);
    assert.equal(event.costChf,0);assert.equal(event.metadata.usageKnown,true);}
  assert.ok(!JSON.stringify(events).includes('deaths'));
});

test('missing usage stays incomplete; invalid JSON and unsolicited tools are rejected without cloud requests',async()=>{
  let event;
  const record=async(runtime,response)=>{event=providerUsageEvent({runtime,response,exchangeRate:0.8});};
  await runLocalWorker(args,context(),{...options,record,request:async()=>({...body(),prompt_eval_count:undefined})});
  assert.equal(event.metadata.usageKnown,false);
  for(const change of [{content:'not json'},{content:'[]'},{content:'ok',tool_calls:[{name:'shell'}]},{content:''}]) {
    await assert.rejects(runLocalWorker(args,context(),{...options,request:async()=>({...body(),message:change})}));
  }
});

test('HTTP uses a fixed endpoint, no redirects/retries, a timeout and bounded chunked input',async()=>{
  let called=0;
  const out=await requestLocalChat(localWorkerPayload(args),{fetchImpl:async(url,init)=>{
    called++;assert.equal(url,'http://vector-local-inference:11434/api/chat');
    assert.equal(init.redirect,'error');assert.ok(init.signal);
    return new Response(JSON.stringify(body()));
  }});
  assert.equal(out.eval_count,13);assert.equal(called,1);
  await assert.rejects(requestLocalChat(localWorkerPayload(args),{fetchImpl:async()=>new Response('x'.repeat(65537))}),/oversized/);
  await assert.rejects(requestLocalChat(localWorkerPayload(args),{fetchImpl:async()=>new Response('private-error',{status:500})}),/HTTP 500/);
});

test('global scheduler rejects concurrent work and releases/discards the connection after failure',async()=>{
  const releases=[];
  let locked=false;
  const {withLocalWorkerSlot}=load('../lib/local-worker-runtime.js',{db:{connect:async()=>({
    query:async(sql)=>{if(sql.includes('pg_try')){if(locked)return {rows:[{locked:false}]};locked=true;return {rows:[{locked:true}]};}
      locked=false;return {rows:[{unlocked:true}]};},release:discard=>releases.push(discard)
  })}},['withLocalWorkerSlot']);
  let finish;
  const first=withLocalWorkerSlot(()=>new Promise(resolve=>{finish=resolve;}));
  await new Promise(resolve=>setImmediate(resolve));
  await assert.rejects(withLocalWorkerSlot(()=>assert.fail('second task must not start')),/busy/);
  finish('done');assert.equal(await first,'done');assert.equal(locked,false);
  await assert.rejects(withLocalWorkerSlot(async()=>{throw Error('fixture failure');}),/fixture failure/);
  assert.equal(locked,false);assert.equal(releases.length,3);
  const broken=load('../lib/local-worker-runtime.js',{db:{connect:async()=>({
    query:async(sql)=>{if(sql.includes('pg_try'))return {rows:[{locked:true}]};throw Error('DB down');},
    release:discard=>assert.equal(discard,true)
  })}},['withLocalWorkerSlot']);
  assert.equal(await broken.withLocalWorkerSlot(async()=>42),42);
});

test('actual tool registry hides worker by default and executor preserves authorized job context',async()=>{
  const previous=process.env.VECTOR_LOCAL_WORKERS;
  try {
    delete process.env.VECTOR_LOCAL_WORKERS;
    const tools=load('../lib/tool-runtime.js',{executeLocalWorker:async(a,c)=>({a,c})},['getVectorTools','executeVectorTool']);
    assert.ok(!tools.getVectorTools({allowServer:true}).some(t=>t.name==='server_local_worker'));
    process.env.VECTOR_LOCAL_WORKERS='1';
    assert.ok(!tools.getVectorTools({allowServer:false}).some(t=>t.name==='server_local_worker'));
    assert.ok(tools.getVectorTools({allowServer:true}).some(t=>t.name==='server_local_worker'));
    const ctx=context();const result=await tools.executeVectorTool({name:'server_local_worker',arguments:args,context:ctx});
    assert.equal(result.c,ctx);assert.equal(result.a,args);
  } finally {if(previous===undefined)delete process.env.VECTOR_LOCAL_WORKERS;else process.env.VECTOR_LOCAL_WORKERS=previous;}
});

test('actual agent overwrites spoofed worker permissions and preserves current-job scope',async()=>{
  const previous=process.env.VECTOR_LOCAL_WORKERS;
  const {assertRequestedArtifactFormat,toolsForArtifactFormat}=await import('../lib/artifact-format-policy.mjs');
  const crypto=(await import('node:crypto')).default;
  try {
    process.env.VECTOR_LOCAL_WORKERS='1';
    for(const allowServer of [true,false]){
      let count=0;
      const localWorkerBudget={calls:0};
      const tools=load('../lib/tool-runtime.js',{crypto,executeLocalWorker:async(a,c)=>{
        const result=await runLocalWorker(a,c,{...options,record:async()=>{}}); count++;
        assert.equal(c.userId,'current-user');assert.equal(c.jobId,'current-job');assert.equal(c.localWorkerBudget,localWorkerBudget);return result;
      }},['getVectorTools','createToolContext','executeVectorTool']);
      let round=0;
      const {runVectorAgent}=load('../lib/agent-runtime.js',{
        ...tools,assertRequestedArtifactFormat,toolsForArtifactFormat,
        sanitizeForExternal:text=>({sanitized:text,mappings:[]}),savePrivacyMappings:async()=>{},
        requestProviderResponse:async()=>({id:'fixture-'+(++round),status:'completed',usage:{input_tokens:10,output_tokens:10},
          output:round===1?[{type:'function_call',name:'server_local_worker',call_id:'local',arguments:JSON.stringify(args)}]:
          [{type:'message',content:[{type:'output_text',text:'Fixture conclusion.'}]}]})
      },['runVectorAgent']);
      const result=await runVectorAgent({model:'fixture',mode:'normal',messages:[{role:'user',content:'Interpret server evidence.'}],
        originalUserMessage:'Interpret server evidence.',maxOutputTokens:300,allowServer,
        providedToolContext:{...tools.createToolContext({userId:'current-user',jobId:'current-job',conversationId:'fixture'}),allowLocalWorkers:true},
        localWorkerBudget,userId:'current-user',jobId:'current-job',conversationId:'fixture',executionClass:'tool',toolDomains:{server:true},roundLimit:2});
      assert.equal(count,allowServer?1:0);
      assert.equal(localWorkerBudget.calls,allowServer?1:0);
      assert.equal(result.toolTrace.find(t=>t.tool==='server_local_worker').success,allowServer);
    }
  } finally {if(previous===undefined)delete process.env.VECTOR_LOCAL_WORKERS;else process.env.VECTOR_LOCAL_WORKERS=previous;}
});


test('constrained extraction rejects observed wrong arrays, translated keys and number strings',async()=>{
  const schema=extractionSchema(args.fields);
  for(const invalid of [{players:[],deaths:[]},{service:'7',temperature:'unbekannt'},
    {players:'3',deaths:null},{players:3},{players:3,deaths:null,extra:0},{players:3.5,deaths:null}]) {
    assert.throws(()=>validateExtraction(invalid,schema));
    let recorded=0;
    await assert.rejects(runLocalWorker(args,context(),{...options,record:async()=>{recorded++;},
      request:async()=>({...body(),message:{content:JSON.stringify(invalid)}})}));
    assert.equal(recorded,1);
  }
  assert.deepEqual(validateExtraction({players:0,deaths:null},schema),{players:0,deaths:null});
  assert.throws(()=>extractionSchema([{name:'x',type:'integer'},{name:'x',type:'integer'}]));
  assert.throws(()=>extractionSchema([{name:'constructor',type:'string'}]));
  assert.throws(()=>localWorkerPayload({...args,fields:[]}));
  assert.equal(localWorkerPayload(args).format.additionalProperties,false);
});


test('Hermes summaries use the same closed output contract and reject invented array structures',async()=>{
  const summary={role:'summarize',task:'Summarize service count and unknown state as JSON.',
    evidence:'3 services; state unknown',fields:[{name:'dienste',type:'integer'},{name:'status',type:'string'}]};
  const payload=localWorkerPayload(summary);
  assert.equal(payload.model,'vector-hermes3:8b-q4km');
  assert.deepEqual(payload.format.required,['dienste','status']);
  const good={...body(),message:{content:'{"dienste":3,"status":"unbekannt"}'}};
  const result=await runLocalWorker(summary,context(),{...options,request:async()=>good});
  assert.equal(result.data.dienste,3);
  await assert.rejects(runLocalWorker(summary,context(),{...options,request:async()=>({...body(),
    message:{content:'{"dienste":["Dienst 1","Dienst 2","Dienst 3"],"status":["unbekannt"]}'}})}),/field type/);
  await assert.rejects(runLocalWorker({...summary,fields:[]},context(),options),/explicit output fields/);
});
