import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';
import {providerUsageTotals} from '../lib/provider-call-usage.mjs';

function load(path,bindings,names) {
  const source=readFileSync(new URL(path,import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];\s*/gm,'').replace(/^export\s+/gm,'');
  return new Function(...Object.keys(bindings),source+`\nreturn {${names.join(',')}};`)(...Object.values(bindings));
}
function route(path,{owned=true,projectAllowed=true,projectPrivacy='internal'}={}) {
  const queries=[],reviews=[],jobs=[];
  const deps={crypto,getSession:async()=>({userId:'alice',role:'owner'}),hasFeature:()=>true,
    assertUserBudget:async()=>({allowed:true}),initializeDatabase:async()=>{},initializeChatAttachmentDatabase:async()=>{},
    prepareChatAttachmentContext:async()=>({context:'attachment: hidden@example.invalid',attachments:[]}),
    CHAT_ATTACHMENT_CONTEXT_MARKER:'\nATTACHMENTS\n',canAccessProject:async()=>projectAllowed,
    searchProjectChunks:async()=>[{original_name:'document.txt',start_line:1,end_line:2,content:'Erika Muster'}],
    db:{query:async(sql,params)=>{
      queries.push([sql,params]);
      if(/FROM projects/.test(sql)) return {rowCount:1,rows:[{privacy_level:projectPrivacy}]};
      if(/FROM conversations/.test(sql))return {rowCount:owned?1:0,rows:owned?[{id:'conversation'}]:[]};
      if(/FROM messages/.test(sql))return {rowCount:1,rows:[{role:'user',content:'History: old@example.invalid'}]};
      throw Error('Review must precede any write');
    }},reviewPrivacyRequest:async args=>{reviews.push(args);return {response:Response.json({error:'PRIVACY_REVIEW_REQUIRED'},{status:409})};},
    enqueueAgentJob:async args=>jobs.push(args)};
  return {...load(path,deps,['POST']),queries,reviews,jobs};
}
test('normal chat reviews attachment and owned history before writes or enqueue',async()=>{
  const api=route('../app/api/chat/route.js');
  const response=await api.POST(new Request('http://vector.test/api/chat',{method:'POST',body:JSON.stringify({message:'Hi Erika Muster',conversationId:'conversation',attachmentIds:['file']})}));
  assert.equal(response.status,409);assert.equal(api.jobs.length,0);
  assert.match(api.reviews[0].text,/old@example.invalid/);assert.match(api.reviews[0].text,/hidden@example.invalid/);
  assert.equal(api.reviews[0].destination,'cloud');
  assert.ok(api.queries.every(([sql])=>! /INSERT|UPDATE/.test(sql)));
});
test('reviewed history reserves one message slot and respects the configured limit',async()=>{
  const previous=process.env.VECTOR_CHAT_HISTORY_MESSAGES;
  try {
    for(const [configured,expected] of [['2',1],['40',39],['invalid',23]]) {
      process.env.VECTOR_CHAT_HISTORY_MESSAGES=configured;
      const api=route('../app/api/chat/route.js');
      await api.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({message:'Hi',conversationId:'c'})}));
      assert.equal(api.queries.find(([sql])=>/FROM messages/.test(sql))[1][1],expected);
    }
  } finally {
    if(previous===undefined)delete process.env.VECTOR_CHAT_HISTORY_MESSAGES;
    else process.env.VECTOR_CHAT_HISTORY_MESSAGES=previous;
  }
});
test('conversation privacy metadata is never disclosed to a different account',async()=>{
  const api=route('../app/api/chat/route.js',{owned:false});
  const response=await api.POST(new Request('http://vector.test/api/chat',{method:'POST',body:JSON.stringify({message:'Hi',conversationId:'other'})}));
  assert.equal(response.status,404);assert.equal(api.reviews.length,0);
});
test('project access is checked before findings and local-only projects select the fixed local path',async()=>{
  const denied=route('../app/api/projects/[id]/chat/route.js',{projectAllowed:false});
  const request=()=>new Request('http://vector.test',{method:'POST',body:JSON.stringify({message:'Hi Erika Muster',conversationId:'conversation'})});
  assert.equal((await denied.POST(request(),{params:{id:'project'}})).status,404);assert.equal(denied.reviews.length,0);
  const api=route('../app/api/projects/[id]/chat/route.js',{projectPrivacy:'local_only'});
  assert.equal((await api.POST(request(),{params:{id:'project'}})).status,409);
  assert.equal(api.reviews[0].destination,'local');assert.match(api.reviews[0].text,/Erika Muster/);
  assert.match(api.reviews[0].text,/old@example.invalid/);assert.equal(api.jobs.length,0);
});
test('fully local executor uses native inference only and retains zero-cost token usage',async()=>{
  const calls=[],events=[],finished=[],failed=[];
  let nativeFails=false,cancelled=false;
  const {executeLocalPrivateJob}=load('../lib/local-private-chat.js',{crypto,providerUsageTotals,
    db:{query:async(...args)=>calls.push(args)},restorePrivateValues:async({text})=>text,
    withLocalWorkerSlot:execute=>execute(),heartbeatAgentJob:async()=>{},
    getAgentJob:async()=>({status:cancelled?'cancelled':'running'}),
    requestLocalChat:async payload=>{calls.push(payload);if(nativeFails)throw Error('local unavailable');
      return {done:true,done_reason:'stop',message:{content:'Hallo Erika Muster'},prompt_eval_count:30,eval_count:5};},
    normalizedOpenAiUsage:u=>({input_tokens:u.prompt_tokens,output_tokens:u.completion_tokens}),
    captureProviderUsage:async(runtime,response)=>events.push({inputTokens:response.usage.input_tokens,outputTokens:response.usage.output_tokens,cachedTokens:0,costChf:0,metadata:{searchCalls:0,costStatus:'estimated'}}),
    completeAgentJob:async args=>finished.push(args),failAgentJob:async args=>failed.push(args)},['executeLocalPrivateJob']);
  process.env.VECTOR_PRIVACY_REVIEW='1';process.env.VECTOR_LOCAL_WORKERS='1';
  const job={id:'job',payload:{conversationId:'conversation',messages:[{role:'user',content:'Hallo Erika Muster'}]}};
  const result=await executeLocalPrivateJob(job,{events});
  assert.equal(result.meta.fullyLocal,true);assert.equal(result.meta.costChf,0);assert.equal(result.meta.inputTokens,30);
  assert.equal(calls[0].model,'vector-qwen3:1.7b-q8');assert.equal(calls[0].tools,undefined);
  assert.equal(finished.length,1);nativeFails=true;
  await assert.rejects(executeLocalPrivateJob(job,{events}),/local unavailable/);assert.equal(finished.length,1);assert.equal(failed.length,1);
  nativeFails=false;cancelled=true;
  const writesBefore=calls.filter(Array.isArray).length;
  assert.deepEqual(await executeLocalPrivateJob(job,{events}),{cancelled:true});
  assert.equal(calls.filter(Array.isArray).length,writesBefore);
  assert.equal(finished.length,1);assert.equal(events.length,2,'cancelled inference still records native usage');
  nativeFails=true;
  assert.deepEqual(await executeLocalPrivateJob(job,{events}),{cancelled:true});
  assert.equal(failed.length,1,'late native errors cannot overwrite cancellation');
});
