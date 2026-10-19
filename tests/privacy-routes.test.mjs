process.env.VECTOR_MINECRAFT_DATA_PATH='/srv/example-minecraft/data';
import {boundedLocalContext} from '../lib/local-context.mjs';
import {requestDestination} from '../lib/chat-controls.mjs';
import {localServerStatistics} from '../lib/local-server-statistics.mjs';
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
  const deps={crypto,requestDestination,getSession:async()=>({userId:'alice',role:'owner'}),hasFeature:()=>true,
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
  assert.equal(api.reviews[0].previewText,'Hi Erika Muster');
  assert.equal(api.reviews[0].scanSegments.join('\n\n'),api.reviews[0].text);
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
  const {classifyExecution}=load('../lib/execution-router.js',{},['classifyExecution']);
  const {executeLocalPrivateJob}=load('../lib/local-private-chat.js',{crypto,boundedLocalContext,providerUsageTotals,classifyExecution,localServerStatistics,hostInspect:async()=>{throw Error('unexpected read')},
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
  assert.equal(calls[0].model,'vector-qwen3:1.7b-q8');assert.equal(calls[0].tools,undefined);assert.equal(calls[0].messages[0].role,'system');assert.match(calls[0].messages[0].content,/keine Emojis/);
  assert.equal(finished.length,1);nativeFails=true;
  await assert.rejects(executeLocalPrivateJob(job,{events}),/local unavailable/);assert.equal(finished.length,1);assert.equal(failed.length,1);
  nativeFails=false;cancelled=true;
  const writesBefore=calls.filter(Array.isArray).length;
  assert.deepEqual(await executeLocalPrivateJob(job,{events}),{cancelled:true});
  assert.equal(calls.filter(Array.isArray).length,writesBefore);
  assert.equal(finished.length,1);assert.equal(events.length,1,'a job cancelled before execution must not start inference');
  nativeFails=true;
  assert.deepEqual(await executeLocalPrivateJob(job,{events}),{cancelled:true});
  assert.equal(failed.length,1,'late native errors cannot overwrite cancellation');
});

test('confirmed project jobs keep originals out of finding metadata and retrieved filenames',async()=>{
  const core=await import('../lib/privacy-review-core.mjs');
  const email='erika@example.invalid',password='synthetic privacy phrase';
  const jobs=[];
  const chunks=[{original_name:email,start_line:1,end_line:1,content:`Passwort: "${password}".`}];
  const deps={crypto,requestDestination,getSession:async()=>({userId:'alice',role:'owner',username:'alice'}),
    canAccessProject:async()=>true,initializeDatabase:async()=>{},assertUserBudget:async()=>({allowed:true}),
    db:{query:async sql=>/SELECT \*/.test(sql)?{rowCount:1,rows:[{privacy_level:'personal'}]}:{rowCount:1,rows:[]}},
    searchProjectChunks:async()=>chunks,
    reviewPrivacyRequest:async({text})=>{
      const plan=core.makePrivacyPlan(text,core.deterministicFindings(text));
      return {...plan,apply:value=>core.literalReplace(value,plan.mappings),destination:'cloud',policy:'encrypted-policy-fixture'};
    },determineTaskMode:()=> 'normal',getModelForMode:()=> 'fixed-model',shouldUseWebSearch:()=>false,
    getMaximumOutputTokens:()=>100,estimateRequestCost:()=>({chf:0}),usdToChf:()=>0,
    checkCost:async()=>({allowed:true}),savePrivacyMappings:async()=>{},findRecentDuplicate:async()=>null,
    makeRequestHash:()=> 'hash',enqueueAgentJob:async args=>{jobs.push(args);return 'job';},
    restorePrivateValues:async({text})=>text};
  const api=load('../app/api/projects/[id]/chat/route.js',deps,['POST']);
  const response=await api.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({message:'Bitte Kontakt Nachricht.',mode:'normal'})}),{params:{id:'project'}});
  assert.equal(response.status,202);assert.equal(jobs.length,1);
  const wire=JSON.stringify(jobs[0].payload);
  assert.ok(!wire.includes(email),'Email must not survive in durable finding or retrieval metadata.');
  assert.ok(!wire.includes(password),'Credential must not survive in durable job metadata.');
  const meta=jobs[0].payload.privacy.values;
  assert.ok(meta.some(m=>m.type==='PASSWORD'&&m.displayValue==='••••••••'));
  assert.ok(meta.some(m=>m.type==='EMAIL'&&m.displayValue===m.placeholder));
  assert.match(jobs[0].payload.retrieval[0].file,/<VEC_EMAIL_/);
});


function acceptedChat({role='owner',budgetAllowed=true}={}) {
  const jobs=[],reviews=[],queries=[];
  const deps={crypto,requestDestination,getSession:async()=>({userId:'alice',role,features:{chat:true}}),hasFeature:()=>true,
    initializeDatabase:async()=>{},initializeChatAttachmentDatabase:async()=>{},
    assertUserBudget:async()=>({allowed:budgetAllowed}),
    prepareChatAttachmentContext:async()=>({context:'',attachments:[]}),CHAT_ATTACHMENT_CONTEXT_MARKER:'\nATTACHMENTS\n',
    db:{query:async(sql,params)=>{queries.push([sql,params]);return {rowCount:1,rows:[]};}},
    reviewPrivacyRequest:async args=>{reviews.push(args);return {destination:args.destination,policy:'bound-policy',
      apply:value=>value,mappings:[],totalFindings:0,findings:[],wasSanitized:false};},
    determineTaskMode:()=> 'normal',getModelForMode:()=> 'cloud-fixture',getMaximumOutputTokens:()=>1400,
    shouldUseWebSearch:()=>false,estimateRequestCost:()=>({chf:0}),usdToChf:()=>0,
    checkCost:async()=>({allowed:true}),savePrivacyMappings:async()=>{},findRecentDuplicate:async()=>null,
    makeRequestHash:args=>args.message,bindChatAttachments:async()=>{},restorePrivateValues:async({text})=>text,
    enqueueAgentJob:async args=>{jobs.push(args);return 'job';}};
  return {...load('../app/api/chat/route.js',deps,['POST']),jobs,reviews,queries};
}
test('actual chat Auto queues local statistics while explicit Normal retains cloud tools permission',async()=>{
  const previous=process.env.VECTOR_LOCAL_WORKERS;process.env.VECTOR_LOCAL_WORKERS='1';
  try {
    for(const [mode,destination] of [['auto','local'],['normal','cloud'],['local','local']]) {
      const api=acceptedChat();
      const response=await api.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({mode,
        message:'Welche Rekorde hat ExampleOne auf Minecraft?',privacyEnabled:false})}));
      assert.equal(response.status,202);assert.equal(api.jobs.length,1);
      assert.equal(api.jobs[0].payload.privacyDestination,destination);
      assert.equal(api.jobs[0].payload.privacyPolicy,'bound-policy');
      assert.equal(api.jobs[0].payload.allowServer,true);
      assert.match(api.jobs[0].requestHash,/privacy:.*:off$/);
      assert.equal(api.reviews[0].body.privacyEnabled,false);
    }
  } finally {if(previous===undefined)delete process.env.VECTOR_LOCAL_WORKERS;else process.env.VECTOR_LOCAL_WORKERS=previous;}
});
test('privacy off cannot grant server permission and malformed preferences cause no enqueue',async()=>{
  const api=acceptedChat({role:'member'});
  const response=await api.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({mode:'normal',message:'Hallo',privacyEnabled:false})}));
  assert.equal(response.status,202);assert.equal(api.jobs[0].payload.allowServer,false);
  const invalid=acceptedChat();
  assert.equal((await invalid.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({message:'Hallo',privacyEnabled:'false'})}))).status,400);
  assert.equal(invalid.jobs.length,0);assert.equal(invalid.reviews.length,0);
});

test('actual local executor reads fixed statistics without inference, scans or provider usage',async()=>{
  const {classifyExecution}=load('../lib/execution-router.js',{},['classifyExecution']);
  const reads=[],writes=[],finished=[];
  const uuid='00000000-0000-0000-0000-000000000001';
  const complete=items=>({complete:true,files_discovered:items.length,files_returned:items.length,items});
  const inspect=async args=>{reads.push(args);return complete([{relative_path:uuid+'.json',content:JSON.stringify(
    args.pattern==='usercache.json'?[{uuid,name:'ExampleOne'}]:{stats:{'minecraft:custom':{'minecraft:mob_kills':42}}})}]);};
  const {executeLocalPrivateJob}=load('../lib/local-private-chat.js',{crypto,boundedLocalContext,providerUsageTotals,classifyExecution,localServerStatistics,
    hostInspect:inspect,db:{query:async(...args)=>writes.push(args)},restorePrivateValues:async({text})=>text,
    heartbeatAgentJob:async()=>{},getAgentJob:async()=>({status:'running'}),completeAgentJob:async args=>finished.push(args),
    failAgentJob:async()=>{},requestLocalChat:()=>{throw Error('unexpected inference')},
    withLocalWorkerSlot:()=>{throw Error('unexpected model slot')},captureProviderUsage:()=>{throw Error('unexpected usage event')}},['executeLocalPrivateJob']);
  process.env.VECTOR_LOCAL_WORKERS='1';
  const result=await executeLocalPrivateJob({id:'job',payload:{allowServer:true,conversationId:'c',messages:[{role:'user',content:'Welche Rekorde hat ExampleOne auf Minecraft?'}]}},{events:[]});
  assert.match(result.text,/42 Kills/);assert.equal(result.meta.model,'vector-local-statistics');
  assert.equal(result.meta.costChf,0);assert.equal(result.meta.inputTokens,0);assert.equal(result.meta.outputTokens,0);
  assert.equal(reads.length,2);assert.equal(finished.length,1);assert.equal(writes.length,2);
  const projectResult=await executeLocalPrivateJob({id:'project-job',payload:{allowServer:true,conversationId:'c',
    safeOriginalMessage:'Welche Rekorde hat ExampleOne auf Minecraft?',messages:[{role:'user',content:'Welche Rekorde hat ExampleOne auf Minecraft? PROJECT CONTEXT: ExampleTwo und eine Mail.'}]}},{events:[]});
  assert.match(projectResult.text,/Minecraft · ExampleOne/);assert.doesNotMatch(projectResult.text,/ExampleTwo/);
  assert.equal(reads.length,4);assert.equal(finished.length,2);
});

test('Auto statistics remain available without cloud budget while external tasks stay blocked',async()=>{
  const previous=process.env.VECTOR_LOCAL_WORKERS;process.env.VECTOR_LOCAL_WORKERS='1';
  try {
    for(const [mode,status] of [['auto',202],['normal',402]]) {
      const api=acceptedChat({budgetAllowed:false});
      const response=await api.POST(new Request('http://vector.test',{method:'POST',body:JSON.stringify({mode,message:'Welche Rekorde hat ExampleOne auf Minecraft?'})}));
      assert.equal(response.status,status);assert.equal(api.jobs.length,status===202?1:0);
    }
  } finally {if(previous===undefined)delete process.env.VECTOR_LOCAL_WORKERS;else process.env.VECTOR_LOCAL_WORKERS=previous;}
});
