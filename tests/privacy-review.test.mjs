import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {AsyncLocalStorage} from 'node:async_hooks';
import {readFileSync} from 'node:fs';
import * as core from '../lib/privacy-review-core.mjs';

const key=Buffer.alloc(32,7);
const secret='synthetic-password-for-privacy-tests';
const text=`Bitte schreibe Erika Muster an erika@example.invalid. Passwort: "${secret}". Erika Muster wartet.`;
const learned=[{type:'PERSON',value:'Erika Muster'}];

test('reversible placeholders preserve exact surrounding text, quotes and repeated identities',()=>{
  const plan=core.makePrivacyPlan(text,[...core.deterministicFindings(text),...learned]);
  for (const value of ['Erika Muster','erika@example.invalid',secret]) assert.ok(!plan.sanitized.includes(value));
  assert.equal(core.literalReplace(plan.sanitized,plan.mappings,true),text);
  const person=plan.mappings.find(m=>m.value==='Erika Muster');
  assert.equal(plan.sanitized.split(person.placeholder).length-1,2);
  assert.ok(plan.sanitized.includes('Passwort: "'));
  assert.match(person.placeholder,/^<VEC_PERSON_[a-f0-9]{32}>$/);
});

test('same original reuses its conversation token and substrings are restored in one pass',()=>{
  const first=core.makePrivacyPlan('Anna Müller und Anna',[{type:'PERSON',value:'Anna Müller'},{type:'PERSON',value:'Anna'}]);
  assert.equal(core.literalReplace(first.sanitized,first.mappings,true),'Anna Müller und Anna');
  const next=core.makePrivacyPlan('Anna kommt',[{type:'PERSON',value:'Anna'}],first.mappings);
  assert.ok(next.sanitized.includes(first.mappings.find(m=>m.value==='Anna').placeholder));
  const mappings=[{placeholder:'<A>',value:'<B>'},{placeholder:'<B>',value:'private'}];
  assert.equal(core.literalReplace('<A>',mappings,true),'<B>');
});

test('tickets are encrypted, authenticated, expire and bind user, scope and content fingerprint',()=>{
  const value={kind:'review',userId:'alice',fingerprint:'a',expires:200,secret};
  const token=core.sealPrivacy(value,key);
  assert.ok(!token.includes(secret));
  assert.deepEqual(core.openPrivacy(token,key,{kind:'review',userId:'alice',fingerprint:'a',now:100}),value);
  for (const options of [{kind:'review',userId:'bob',now:100},{kind:'job',userId:'alice',now:100},
    {kind:'review',userId:'alice',fingerprint:'b',now:100},{kind:'review',userId:'alice',now:201}]) {
    assert.throws(()=>core.openPrivacy(token,key,options));
  }
  const bytes=Buffer.from(token,'base64url');bytes[30]^=1;
  assert.throws(()=>core.openPrivacy(bytes.toString('base64url'),key,{kind:'review',userId:'alice',now:100}));
});

test('invented findings, unexpected types and placeholders are rejected',()=>{
  for (const finding of [{type:'PERSON',value:'Not in source'},{type:'COMMAND',value:'Erika Muster'},
    {type:'PERSON',value:'<VEC_PERSON_'+ 'a'.repeat(32)+'>'}]) {
    assert.throws(()=>core.validateLocalFindings(text,{findings:[finding]}));
  }
  assert.deepEqual(core.validateLocalFindings(text,{findings:learned}),learned);
  assert.equal(core.displayFinding({type:'PASSWORD',value:secret,placeholder:'x'}).displayValue,'••••••••');
});

function loadRuntime({fail=false,truncated=false}={}) {
  const source=readFileSync(new URL('../lib/privacy-review.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];\s*/gm,'').replace(/^export\s+/gm,'');
  const vault=new Map();const usage=[];const requests=[];
  const requestLocalChat=async payload=>{
    requests.push(payload);
    if(fail)throw Error('native service unavailable');
    const chunk=JSON.parse(payload.messages[1].content).text;
    return {done:true,done_reason:truncated?'length':'stop',prompt_eval_count:45,eval_count:12,
      message:{content:JSON.stringify({findings:learned.filter(f=>chunk.includes(f.value))})}};
  };
  const deps={crypto,AsyncLocalStorage,...core,requestLocalChat,withLocalWorkerSlot:execute=>execute(),
    getPrivacyMappings:async id=>vault.get(id)||[],savePrivacyMappings:async({conversationId,mappings})=>vault.set(conversationId,mappings),
    providerUsageEvent:({userId,response})=>({userId,inputTokens:response.usage.input_tokens,outputTokens:response.usage.output_tokens,costChf:0}),
    normalizedOpenAiUsage:value=>({input_tokens:value.prompt_tokens,output_tokens:value.completion_tokens}),recordUsage:async event=>usage.push(event)};
  const api=new Function(...Object.keys(deps),source+'\nreturn {reviewPrivacyRequest,withJobPrivacy,protectProviderPayload,protectToolEvidence,restoreLocalToolArguments};')(...Object.values(deps));
  return {...api,vault,usage,requests};
}
const args=()=>({text,body:{message:text,mode:'normal'},session:{userId:'alice'},scope:'chat',conversationId:null});
test('actual review runtime blocks enqueue until a bound explicit choice and never returns secret values in review metadata',async()=>{
  process.env.VECTOR_PRIVACY_REVIEW='1';process.env.VECTOR_LOCAL_WORKERS='1';process.env.FILE_ENCRYPTION_KEY=key.toString('hex');
  const runtime=loadRuntime();
  const review=await runtime.reviewPrivacyRequest(args());
  assert.equal(review.response.status,409);
  const data=await review.response.json();
  assert.ok(!JSON.stringify(data).includes(secret));
  assert.equal(runtime.requests.length,1);
  assert.deepEqual(runtime.usage,[{userId:'alice',inputTokens:45,outputTokens:12,costChf:0}]);
  const confirmed=args();confirmed.body={...confirmed.body,privacyDecision:'replace',privacyReviewToken:data.privacyReview.token};
  const plan=await runtime.reviewPrivacyRequest(confirmed);
  assert.equal(runtime.requests.length,1,'confirmation must reuse the encrypted local review');
  assert.ok(!plan.apply(text).includes(secret));
  runtime.vault.set('chat',plan.mappings);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    const outgoing=runtime.protectProviderPayload({model:'fixed',input:[{role:'user',content:text}]});
    assert.equal(outgoing.model,'fixed');
    for (const value of ['Erika Muster','erika@example.invalid',secret]) assert.ok(!JSON.stringify(outgoing).includes(value));
    assert.equal(runtime.restoreLocalToolArguments('server_inspect',{path:plan.apply('Erika Muster')} ).path,'Erika Muster');
    assert.notEqual(runtime.restoreLocalToolArguments('web_search',{query:plan.apply('Erika Muster')}).query,'Erika Muster');
    assert.throws(()=>runtime.protectProviderPayload({input:'password=unreviewed-sensitive-value'}));
  });
  for (const change of [{text:text+' changed'},{session:{userId:'bob'}},{scope:'project:other'}]) {
    await assert.rejects(runtime.reviewPrivacyRequest({...confirmed,...change}));
  }
});

test('unchanged send is explicit and preserved, while local full text bypasses detection and consent entirely',async()=>{
  const runtime=loadRuntime();
  const data=await (await runtime.reviewPrivacyRequest(args())).response.json();
  const confirmed=args();confirmed.body={...confirmed.body,privacyDecision:'original',privacyReviewToken:data.privacyReview.token};
  const plan=await runtime.reviewPrivacyRequest(confirmed);
  assert.equal(plan.apply(text),text);
  assert.equal(plan.wasSanitized,false);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    assert.equal(runtime.protectProviderPayload({input:text}).input,text);
  });
  const before=runtime.requests.length;
  const local=await runtime.reviewPrivacyRequest({...args(),destination:'local'});
  assert.equal(local.apply(text),text);assert.equal(local.response,undefined);
  assert.equal(runtime.requests.length,before);
  await assert.rejects(runtime.reviewPrivacyRequest({...args(),destination:'local',uninspectable:true}));
});

test('images require explicit unchanged permission and cannot be falsely declared anonymized',async()=>{
  const runtime=loadRuntime();
  const data=await (await runtime.reviewPrivacyRequest({...args(),uninspectable:true})).response.json();
  assert.equal(data.privacyReview.canReplace,false);
  const confirmed=args();confirmed.body={...confirmed.body,privacyDecision:'replace',privacyReviewToken:data.privacyReview.token};
  await assert.rejects(runtime.reviewPrivacyRequest({...confirmed,uninspectable:true}));
});

test('unavailable or truncated local detection fails closed, with returned usage recorded before rejection',async()=>{
  const failed=loadRuntime({fail:true});await assert.rejects(failed.reviewPrivacyRequest(args()));
  assert.equal(failed.usage.length,0);
  const partial=loadRuntime({truncated:true});await assert.rejects(partial.reviewPrivacyRequest(args()));
  assert.equal(partial.usage.length,1);
});

test('new tool evidence requires explicit masking consent and preserves JSON escapes',async()=>{
  const runtime=loadRuntime();
  const plain={...args(),text:'Berechne 2 plus 2',body:{message:'Berechne 2 plus 2'}};
  const noFindings=await runtime.reviewPrivacyRequest(plain);
  assert.equal(noFindings.response,undefined);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:noFindings.policy},async()=>{
    await assert.rejects(runtime.protectToolEvidence(JSON.stringify({name:'Erika Muster'})),/Datenschutzfreigabe/);
  });
  const data=await (await runtime.reviewPrivacyRequest(args())).response.json();
  const confirmed=args();confirmed.body={...confirmed.body,privacyDecision:'replace',privacyReviewToken:data.privacyReview.token};
  const plan=await runtime.reviewPrivacyRequest(confirmed);
  runtime.vault.set('chat',plan.mappings);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    const original={message:'Passwort: "another synthetic phrase"',person:'Erika Muster'};
    const safe=await runtime.protectToolEvidence(JSON.stringify(original));
    const parsed=JSON.parse(safe.sanitized);
    assert.ok(!safe.sanitized.includes('another synthetic phrase'));
    assert.equal(core.literalReplace(parsed.message,safe.mappings,true),original.message);
  });
});
