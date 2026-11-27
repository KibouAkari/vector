import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {boundedLocalContext} from '../lib/local-context.mjs';
import {localServerStatistics} from '../lib/local-server-statistics.mjs';
import {roleAllows} from '../lib/role-policy.mjs';
import crypto from 'node:crypto';

test('real local executor processes a short current request after a long conversation',async()=>{
  const source=readFileSync(new URL('../lib/local-private-chat.js',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const calls=[];
  const deps={boundedLocalContext,localServerStatistics:async()=>null,hostInspect:async()=>{throw Error('unexpected host call');},
    assertModelAccess:async()=>{},assertToolAccess:async()=>{},
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

test('local execution enforces live role policies before inference and each server read',async()=>{
  const load=(path,deps,name)=>new Function(...Object.keys(deps),
    readFileSync(new URL(path,import.meta.url),'utf8')
      .replace(/^import .*;\n/gm,'').replace(/^export /gm,'')+`;return ${name}`)(...Object.values(deps));
  let role='member',policy={models:[],tools:[]},modelCalls=0,reads=0,failures=0,revokeAfterRead=false;
  const users=[];
  const db={query:async(sql,args)=>{
    if(sql.includes('SELECT u.id,u.role')) {
      users.push(args[0]);
      return {rows:[{id:args[0],role,enabled:true,policy}]};
    }
    return {rows:[]};
  }};
  const access=load('../lib/access-controls.js',{crypto,db,initializeDatabase:async()=>{},roleAllows},'{assertModelAccess,assertToolAccess}');
  const uuid='00000000-0000-0000-0000-000000000001';
  const execute=load('../lib/local-private-chat.js',{...access,crypto,db,boundedLocalContext,localServerStatistics,
    hostInspect:async args=>{
      reads++;
      if(revokeAfterRead) policy={...policy,tools:[]};
      const content=args.pattern==='usercache.json'?[{uuid,name:'ExampleOne'}]:{stats:{'minecraft:custom':{}}};
      return {complete:true,files_discovered:1,files_returned:1,items:[{relative_path:uuid+'.json',content:JSON.stringify(content)}]};
    },
    classifyExecution:()=>({requirements:{}}),requestLocalChat:async()=>{
      modelCalls++;return {done:true,done_reason:'stop',message:{content:'Local answer'}};
    },withLocalWorkerSlot:fn=>fn(),captureProviderUsage:async()=>{},providerUsageTotals:()=>({inputTokens:0,outputTokens:0}),
    normalizedOpenAiUsage:()=>({}),completeAgentJob:async()=>{},failAgentJob:async()=>{failures++;},
    heartbeatAgentJob:async()=>{},getAgentJob:async()=>({status:'running'}),restorePrivateValues:async({text})=>text,
  },'executeLocalPrivateJob');
  const keys=['VECTOR_LOCAL_WORKERS','VECTOR_MINECRAFT_DATA_PATH'];
  const previous=keys.map(key=>process.env[key]);
  process.env.VECTOR_LOCAL_WORKERS='1';process.env.VECTOR_MINECRAFT_DATA_PATH='/srv/fixture';
  const job=(text,extra={})=>({id:'job',user_id:'fixture-user',payload:{conversationId:'c',allowServer:true,messages:[{role:'user',content:text}],...extra}});
  const text='Please write a short email.';
  const stats='Welche Rekorde hat ExampleOne auf Minecraft?';
  try {
    await assert.rejects(execute(job(text),{events:[]}),{code:'MODEL_POLICY_DENIED'});
    assert.equal(modelCalls,0);assert.equal(reads,0);
    await assert.rejects(execute(job(stats),{events:[]}),{code:'TOOL_POLICY_DENIED'});
    assert.equal(reads,0);assert.equal(modelCalls,0);
    policy={models:['local/vector-qwen3:1.7b-q8'],tools:[]};
    await execute(job(text,{userId:'payload-user'}),{events:[]});
    assert.equal(modelCalls,1);assert.equal(users.at(-1),'payload-user');
    policy={models:[],tools:['server_inspect']};
    await execute(job(stats),{events:[]});
    assert.equal(reads,2);assert.equal(modelCalls,1);
    assert.deepEqual(users.slice(-2),['fixture-user','fixture-user']);
    revokeAfterRead=true;
    await assert.rejects(execute(job(stats),{events:[]}),{code:'TOOL_POLICY_DENIED'});
    assert.equal(reads,3);assert.equal(modelCalls,1);
    revokeAfterRead=false;
    role='owner';policy={models:[],tools:[]};
    await execute(job(text),{events:[]});
    await execute(job(stats),{events:[]});
    assert.equal(modelCalls,2);assert.equal(reads,5);
    assert.equal(failures,3);
  } finally {
    keys.forEach((key,i)=>previous[i]===undefined?delete process.env[key]:process.env[key]=previous[i]);
  }
});
