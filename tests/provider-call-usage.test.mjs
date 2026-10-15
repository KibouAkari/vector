import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import crypto from 'node:crypto';
import {withProviderUsageScope,captureProviderUsage,providerUsageEvent,providerUsageTotals} from '../lib/provider-call-usage.mjs';
import {normalizedOpenAiUsage,normalizedAnthropicUsage} from '../lib/provider-usage-normalization.mjs';
import {runLocalWorker} from '../lib/local-worker-core.mjs';

function load(path, bindings, names) {
  const source=readFileSync(new URL(path,import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
  return new Function(...Object.keys(bindings),source+`\nreturn {${names.join(',')}};`)(...Object.values(bindings));
}
const runtime={id:'fixture-config',provider:'openai',model:'fixture-model',adapter:'openai-chat',
  apiBase:'https://fixture.invalid',supportsTools:true,
  pricing:{inputPerMillionUsd:2,cachedInputPerMillionUsd:0.2,outputPerMillionUsd:10}};
const response=(id='fixture-response')=>({id,status:'completed',usage:{input_tokens:100,output_tokens:10,
  input_tokens_details:{cached_tokens:20},output_tokens_details:{reasoning_tokens:7}},output:[]});
const quote=(r=runtime,s=response(),userId='fixture-user')=>providerUsageEvent({runtime:r,response:s,userId,
  jobId:'fixture-job',exchangeRate:0.8,fallbackPricing:{inputPerMillionUsd:99,outputPerMillionUsd:99}});

test('configured rates, cache hits and reasoning produce one per-call USD/CHF estimate',()=>{
  const event=quote();
  assert.ok(Math.abs(event.metadata.costUsd-0.000264)<1e-12);
  assert.ok(Math.abs(event.costChf-0.0002112)<1e-12);
  assert.equal(event.outputTokens,10); // Includes reasoning; do not add seven again.
  assert.equal(event.metadata.reasoningTokens,7);
  assert.equal(event.metadata.costStatus,'estimated');
  assert.equal(event.metadata.usdToChfRate,0.8);
  assert.equal(quote().eventId,event.eventId);
  assert.notEqual(quote(runtime,response(),'another-user').eventId,event.eventId);
  assert.ok(!JSON.stringify(event).includes('apiBase'));
});

test('every request fee and built-in search call is charged per response',()=>{
  const r={...runtime,pricing:{...runtime.pricing,requestFeeUsd:0.05}};
  const s={...response(),output:[{type:'web_search_call'},{type:'web_search_call'}]};
  assert.ok(Math.abs(quote(r,s).metadata.costUsd-(0.000264+0.07))<1e-12);
});

test('unknown usage, unknown remote pricing and invalid cache totals remain visibly incomplete',()=>{
  assert.equal(quote(runtime,{id:'missing',usage:normalizedOpenAiUsage()}).metadata.costStatus,'incomplete');
  assert.equal(quote({...runtime,pricing:{inputPerMillionUsd:0,outputPerMillionUsd:0}}).metadata.costStatus,'incomplete');
  const invalid=response();invalid.usage.input_tokens_details.cached_tokens=101;
  assert.equal(quote(runtime,invalid).metadata.costStatus,'incomplete');
  assert.equal(quote({...runtime,provider:'local',pricing:{inputPerMillionUsd:0,cachedInputPerMillionUsd:0,outputPerMillionUsd:0}}).costChf,0);
  assert.throws(()=>providerUsageEvent({runtime,response:response(),exchangeRate:NaN}),/accounting rate/);
});

test('cache writes and Anthropic input totals remain distinct from cached reads',()=>{
  const usage=normalizedAnthropicUsage({input_tokens:70,cache_read_input_tokens:20,cache_creation_input_tokens:10,output_tokens:10});
  assert.equal(usage.input_tokens,100);
  assert.equal(usage.input_tokens_details.cached_tokens,20);
  assert.equal(usage.input_tokens_details.cache_write_tokens,10);
  const priced={...runtime,pricing:{...runtime.pricing,cacheWriteInputPerMillionUsd:2.5}};
  const event=quote(priced,{id:'writes',usage});
  assert.ok(Math.abs(event.metadata.costUsd-0.000269)<1e-12);
  assert.equal(quote(runtime,{id:'missing-write-rate',usage}).metadata.costStatus,'incomplete');
});

test('real compatible provider captures normalized reasoning and persists before a renderer failure',async()=>{
  const persisted=[];
  const {requestProviderResponse}=load('../lib/provider-runtime.js',{
    normalizedOpenAiUsage,normalizedAnthropicUsage,captureProviderUsage,
    observeProviderRequest:({execute})=>execute(),
    fetch:async()=>({ok:true,text:async()=>JSON.stringify({id:'fixture-adapter',
      choices:[{finish_reason:'stop',message:{content:'Private fixture document'}}],
      usage:{prompt_tokens:100,completion_tokens:10,prompt_tokens_details:{cached_tokens:20},
        completion_tokens_details:{reasoning_tokens:7}}})})
  },['requestProviderResponse']);
  await assert.rejects(withProviderUsageScope(async(r,s)=>{
    const event=quote(r,s);persisted.push(event);return event;
  },async scope=>{
    await requestProviderResponse({providerRuntime:runtime,payload:{input:[],tools:[],max_output_tokens:1400}});
    assert.equal(scope.events[0].metadata.reasoningTokens,7);
    throw new Error('Fixture renderer failed');
  }),/renderer failed/);
  assert.equal(persisted.length,1);
  assert.equal(persisted[0].inputTokens,100);
  assert.ok(!JSON.stringify(persisted).includes('Private fixture document'));
});

test('parallel jobs keep usage isolated and duplicate response IDs are counted once in a scope',async()=>{
  const results=await Promise.all(['user-a','user-b'].map(userId=>withProviderUsageScope(
    async(r,s)=>quote(r,s,userId),async scope=>{
      await Promise.resolve();
      await captureProviderUsage(runtime,response(userId));
      await captureProviderUsage(runtime,response(userId));
      return scope.events;
    })));
  assert.equal(results[0].length,1);assert.equal(results[1].length,1);
  assert.equal(results[0][0].userId,'user-a');assert.equal(results[1][0].userId,'user-b');
  assert.equal(providerUsageTotals(results[0]).inputTokens,100);
});

test('ledger persistence failure is distinct from a retryable provider outage',async()=>{
  await assert.rejects(withProviderUsageScope(async()=>{throw new Error('Fixture ledger unavailable');},
    async()=>captureProviderUsage(runtime,response())),error=>{
      assert.equal(error.code,'VECTOR_USAGE_PERSISTENCE_FAILED');
      assert.equal(error.status,undefined);
      assert.match(error.message,/automatic provider replay is disabled/);
      return true;
    });
});

test('workflow repairs retain initial execution as well as planning, review and repair usage',async()=>{
  let simple=0,agent=0;
  const {runAutonomousWorkflow}=load('../lib/workflow-runtime.js',{
    extractAuthorizedTargets:()=>[],createToolContext:()=>({}),
    requestSimpleProviderText:async()=>({text:++simple===1?'Fixture plan':'REPAIR: Fix fixture',
      inputTokens:simple===1?5:7,outputTokens:1,cachedTokens:1}),
    runVectorAgent:async()=>({text:'Fixture result',toolTrace:[{tool:'fixture',success:true}],
      inputTokens:++agent*10,outputTokens:agent*2,cachedTokens:agent,providerCalls:[{phase:'fixture-'+agent}]})
  },['runAutonomousWorkflow']);
  const result=await runAutonomousWorkflow({model:'fixture',mode:'deep',messages:[{role:'user',content:'Analyse fixture'}],
    originalUserMessage:'Analyse fixture',maxOutputTokens:1400});
  assert.equal(agent,2);assert.equal(simple,2);
  assert.equal(result.inputTokens,42);
  assert.equal(result.outputTokens,8);
  assert.equal(result.cachedTokens,5);
  assert.equal(result.providerCalls.length,2);
});

test('actual worker records each provider response once on both success and post-provider failure',async()=>{
  for(const fail of [false,true]){
    const persisted=[],audits=[],completed=[],failed=[];
    const {executeAgentJob}=load('../lib/background-executor.js',{
      crypto,withProviderUsageScope,providerUsageEvent,providerUsageTotals,
      MODEL_PRICING:{},calculateModelCost:()=>({chf:99}),usdToChf:x=>x,
      calculateConfiguredProviderCost:()=>({chf:99}),
      db:{query:async()=>({rows:[],rowCount:0})},
      recordUsage:async event=>{persisted.push(event);},
      writeAudit:async entry=>{audits.push(entry);},
      buildVisionInputs:async()=>[],heartbeatAgentJob:async()=>{},getAgentJob:async()=>({status:'running'}),
      completeAgentJob:async result=>{completed.push(result);},failAgentJob:async result=>{failed.push(result);},
      bindGeneratedArtifactsToMessage:async()=>[],resolveProviderForTask:async()=>runtime,
      classifyExecution:()=>({class:'artifact',reason:'fixture',requirements:{server:true},limits:{rounds:2}}),
      runVectorAgent:async()=>{
        await captureProviderUsage(runtime,response('fixture-first'));
        await captureProviderUsage(runtime,response('fixture-second'));
        if(fail)throw new Error('Fixture renderer failed after paid responses');
        return {text:'Fixture result',artifactCreated:true,inputTokens:1,outputTokens:1,cachedTokens:0,toolTrace:[]};
      }
    },['executeAgentJob']);
    const job={id:'fixture-job',user_id:'fixture-user',payload:{conversationId:'fixture-thread',mode:'normal',
      safeOriginalMessage:'Create a PDF',messages:[{role:'user',content:'Create a PDF'}]}};
    if(fail){
      await assert.rejects(executeAgentJob(job),/renderer failed/);
      assert.equal(failed.length,1);assert.equal(completed.length,0);
    }else{
      const result=await executeAgentJob(job);
      assert.equal(completed.length,1);
      assert.equal(result.meta.providerCalls.length,2);
      assert.equal(result.meta.usageAccounting.providerResponses,2);
      assert.ok(Math.abs(result.meta.costChf-persisted.reduce((n,e)=>n+e.costChf,0))<1e-12);
      const audit=audits.find(e=>e.action==='ai.request.completed');
      assert.equal(audit.details.inputTokens,200);
      assert.equal(audit.details.outputTokens,20);
    }
    assert.equal(persisted.length,2,'no aggregate third charge');
    assert.ok(persisted.every(e=>e.userId==='fixture-user' && e.metadata.jobId==='fixture-job'));
  }
});

test('artifact provider failover shares the two-attempt local-worker budget',async()=>{
  const fallback={...runtime,id:'fixture-fallback',provider:'anthropic'};
  const budgets=[],failed=[];
  let agentAttempts=0,workerCalls=0;
  const workerArgs={role:'extract',task:'Return the value.',evidence:'value 3',fields:[{name:'value',type:'integer'}]};
  const {executeAgentJob}=load('../lib/background-executor.js',{
    crypto,withProviderUsageScope,providerUsageEvent,providerUsageTotals,
    MODEL_PRICING:{},calculateModelCost:()=>({chf:0}),usdToChf:x=>x,
    calculateConfiguredProviderCost:()=>({chf:0}),
    db:{query:async()=>({rows:[],rowCount:0})},
    recordUsage:async()=>{},writeAudit:async()=>{},
    buildVisionInputs:async()=>[],heartbeatAgentJob:async()=>{},getAgentJob:async()=>({status:'running'}),
    completeAgentJob:async()=>{},failAgentJob:async result=>{failed.push(result);},
    bindGeneratedArtifactsToMessage:async()=>[],
    resolveProviderForTask:async({excludeProviderIds})=>excludeProviderIds.length?fallback:runtime,
    classifyExecution:()=>({class:'artifact',reason:'fixture',requirements:{server:true},limits:{rounds:2}}),
    runVectorAgent:async({localWorkerBudget})=>{
      agentAttempts++;
      const workerContext={userId:'fixture-user',jobId:'fixture-job',allowLocalWorkers:true,localWorkerBudget};
      const dependencies={enabled:true,exclusive:execute=>execute(),request:async()=>({
        done:true,done_reason:'stop',message:{content:'{"value":3}'},prompt_eval_count:1,eval_count:1
      }),record:async()=>{}};
      if(agentAttempts===1){
        budgets.push(localWorkerBudget);
        await runLocalWorker(workerArgs,workerContext,dependencies);workerCalls++;
        await runLocalWorker(workerArgs,workerContext,dependencies);workerCalls++;
        throw new Error('Provider returned HTTP 503');
      }
      budgets.push(localWorkerBudget);
      await runLocalWorker(workerArgs,workerContext,dependencies);
    }
  },['executeAgentJob']);
  const job={id:'fixture-job',user_id:'fixture-user',payload:{conversationId:'fixture-thread',mode:'normal',
    safeOriginalMessage:'Create a PDF',messages:[{role:'user',content:'Create a PDF'}]}};
  await assert.rejects(executeAgentJob(job),/two calls/);
  assert.equal(agentAttempts,2);
  assert.equal(workerCalls,2);
  assert.equal(budgets[0],budgets[1]);
  assert.equal(budgets[0].calls,2);
  assert.equal(failed.length,1);
});
