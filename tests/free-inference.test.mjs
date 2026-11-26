import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {freeInferenceEligible,enforceFreeInference} from '../lib/free-inference-policy.mjs';
import {normalizedOpenAiUsage,normalizedAnthropicUsage} from '../lib/provider-usage-normalization.mjs';
const load=(path,deps,names)=>new Function(...Object.keys(deps),readFileSync(new URL(path,import.meta.url),'utf8').replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'')+`\nreturn {${names.join(',')}};`)(...Object.values(deps));
test('free inference requires an explicit free model on the official endpoint',()=>{
 assert.ok(freeInferenceEligible('local','installed','http://vector-local-inference:11434/v1'));
 for(const model of ['openrouter/free','fixture/model:free'])assert.ok(freeInferenceEligible('openrouter',model,'https://openrouter.ai/api/v1'));
 for(const [provider,model,url] of [['local','paid','https://api.openai.com/v1'],['openrouter','fixture/paid','https://openrouter.ai/api/v1'],['google','fixture/free','https://google.invalid'],['openrouter','fixture/model:free','https://openrouter.ai.evil.invalid/api/v1'],['openrouter','openrouter/free','http://openrouter.ai/api/v1']]){
  assert.equal(freeInferenceEligible(provider,model,url),false);assert.throws(()=>enforceFreeInference({freeOnly:true,provider,model,apiBase:url}),{code:'FREE_INFERENCE_UNAVAILABLE'});
 }
});
test('actual adapter sends a zero price ceiling without paid fallbacks and rejects paid routing before fetch',async()=>{
 let bodies=[];const {requestProviderResponse}=load('../lib/provider-runtime.js',{normalizedOpenAiUsage,normalizedAnthropicUsage,enforceFreeInference,protectProviderPayload:p=>p,captureProviderUsage:async()=>{},observeProviderRequest:({execute})=>execute(),fetch:async(_url,options)=>{bodies.push(JSON.parse(options.body));return {ok:true,text:async()=>JSON.stringify({id:'fixture-free',choices:[{message:{content:'Offline answer'},finish_reason:'stop'}],usage:{prompt_tokens:2,completion_tokens:1,cost:0}})};}},['requestProviderResponse']);
 const runtime={freeOnly:true,provider:'openrouter',adapter:'openai-chat',apiBase:'https://openrouter.ai/api/v1',apiKey:'fixture-not-a-key',model:'fixture/model:free',supportsTools:true};
 await requestProviderResponse({providerRuntime:runtime,payload:{input:[{role:'user',content:'Synthetic request'}],max_output_tokens:20}});
 assert.deepEqual(bodies[0].provider,{max_price:{prompt:0,completion:0},allow_fallbacks:false});assert.equal(bodies[0].model,'fixture/model:free');
 await assert.rejects(requestProviderResponse({providerRuntime:{...runtime,model:'fixture/paid'},payload:{input:[]}}),{code:'FREE_INFERENCE_UNAVAILABLE'});assert.equal(bodies.length,1);
});

test('real resolver keeps the free-only constraint across selection and exhausted candidates',async()=>{
 const crypto=await import('node:crypto');process.env.FILE_ENCRYPTION_KEY='07'.repeat(32);let rows=[];
 const db={query:async(sql,args)=>{
  if(/FROM vector_users\s+WHERE id/.test(sql))return {rows:[{role:'owner'}]};
  if(/SELECT\s+p\.\*/.test(sql)){assert.match(sql,/p.owner_user_id = \$1/);assert.equal(args[0],'alice');return {rows};}
  return {rows:[],rowCount:0};
 }};
 const api=load('../lib/model-config.js',{crypto,db,initializeDatabase:async()=>{},freeInferenceEligible,MODEL_CATALOG:[],getCatalogModel:()=>null,automaticPricingFor:()=>null,classifyVectorTask:()=>({primary:'general'}),routingExplanation:()=> 'fixture',chooseCatalogModel:()=>({model:'fixture/paid'}),scoreCatalogModel:()=>50},['resolveProviderForTask','encryptSecret']);
 const key=api.encryptSecret('fixture-not-real');
 rows=[{id:'paid',provider:'openai',default_model:'paid',api_key_encrypted:key,owner_user_id:'alice'},{id:'free',provider:'openrouter',default_model:'fixture/model:free',api_key_encrypted:key,owner_user_id:'alice'}];
 const result=await api.resolveProviderForTask({userId:'alice',billingPolicy:'free-only',preferredProviderId:'paid'});assert.equal(result.id,'free');assert.equal(result.freeOnly,true);assert.equal(result.model,'fixture/model:free');
 await assert.rejects(api.resolveProviderForTask({userId:'alice',billingPolicy:'free-only',excludeProviders:['openrouter']}),/Paid fallback is disabled/);
});
