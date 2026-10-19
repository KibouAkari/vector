import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {boundedLocalContext} from '../lib/local-context.mjs';

test('real local executor processes a short current request after a long conversation',async()=>{
  const source=readFileSync(new URL('../lib/local-private-chat.js',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const calls=[];
  const deps={boundedLocalContext,localServerStatistics:async()=>null,hostInspect:async()=>{throw Error('unexpected host call');},
    classifyExecution:()=>({requirements:{}}),crypto:{randomUUID:()=> 'synthetic-id'},
    db:{query:async()=>({rows:[]})},requestLocalChat:async body=>{calls.push(body);return {done:true,done_reason:'stop',message:{content:'A short local answer.'}};},
    withLocalWorkerSlot:fn=>fn(),captureProviderUsage:async()=>{},providerUsageTotals:()=>({inputTokens:0,outputTokens:0}),
    normalizedOpenAiUsage:()=>({}),completeAgentJob:async()=>{},failAgentJob:async()=>{},heartbeatAgentJob:async()=>{},
    getAgentJob:async()=>({status:'running'}),restorePrivateValues:async({text})=>text};
  const execute=new Function(...Object.keys(deps),source+';return executeLocalPrivateJob')(...Object.values(deps));
  const previous=process.env.VECTOR_LOCAL_WORKERS;process.env.VECTOR_LOCAL_WORKERS='1';
  try {
    const result=await execute({id:'job',payload:{conversationId:'conversation',messages:[
      {role:'user',content:'old '.repeat(3000)},{role:'assistant',content:'old reply'},
      {role:'user',content:'Please write a short email.'}]}},{events:[]});
    assert.equal(calls.length,1);
    assert.deepEqual(calls[0].messages.slice(1),[{role:'user',content:'Please write a short email.'}]);
    assert.equal(result.meta.fullyLocal,true);
  } finally {if(previous===undefined)delete process.env.VECTOR_LOCAL_WORKERS;else process.env.VECTOR_LOCAL_WORKERS=previous;}
});
