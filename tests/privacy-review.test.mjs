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

test('email-shaped credentials promote every legacy alias without revealing them in previews',()=>{
  const value='erika@example.invalid';
  const input=`Passwort: "${value}"`;
  const existing=[{value,type:'EMAIL',placeholder:'<EMAIL_A1B2C3>'},
    {value,type:'PASSWORD',placeholder:'<PASSWORD_A1B2C4>'},
    {value,type:'EMAIL',placeholder:'<EMAIL_A1B2C5>'}];
  for(const previous of [[],[existing[0]],existing]) {
    const plan=core.makePrivacyPlan(input,core.deterministicFindings(input),previous);
    assert.equal(plan.selected.length,1);
    assert.match(plan.selected[0].type,/PASSWORD|KEY|TOKEN/);
    assert.equal(core.displayFinding(plan.selected[0]).displayValue,'••••••••');
    for(const mapping of plan.mappings) assert.match(mapping.type,/PASSWORD|KEY|TOKEN/);
    if(previous.length) assert.equal(plan.selected[0].placeholder,previous[0].placeholder);
    assert.ok(plan.sanitized.includes(plan.selected[0].placeholder));
  }
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

function loadRuntime({fail=false,truncated=false,extraFindings=[]}={}) {
  const source=readFileSync(new URL('../lib/privacy-review.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];\s*/gm,'').replace(/^export\s+/gm,'');
  const vault=new Map();const usage=[];const requests=[];
  const requestLocalChat=async payload=>{
    requests.push(payload);
    if(fail)throw Error('native service unavailable');
    const chunk=JSON.parse(payload.messages[1].content).text;
    return {done:true,done_reason:truncated?'length':'stop',prompt_eval_count:45,eval_count:12,
      message:{content:JSON.stringify({findings:[...learned,...extraFindings].filter(f=>chunk.includes(f.value))})}};
  };
  const deps={crypto,AsyncLocalStorage,...core,requestLocalChat,withLocalWorkerSlot:execute=>execute(),
    getPrivacyMappings:async id=>vault.get(id)||[],savePrivacyMappings:async({conversationId,mappings})=>vault.set(conversationId,mappings),
    providerUsageEvent:({userId,response})=>({userId,inputTokens:response.usage.input_tokens,outputTokens:response.usage.output_tokens,costChf:0}),
    normalizedOpenAiUsage:value=>({input_tokens:value.prompt_tokens,output_tokens:value.completion_tokens}),recordUsage:async event=>usage.push(event),
    captureProviderUsage:async(_runtime,response)=>usage.push({inputTokens:response.usage.input_tokens,outputTokens:response.usage.output_tokens,costChf:0})};
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
    const outbound=runtime.protectProviderPayload({input:[{type:'function_call_output',call_id:'user',output:safe.sanitized}]});
    assert.doesNotThrow(()=>JSON.parse(outbound.input[0].output));
    assert.equal(outbound.input[0].call_id,'user');
  });
});

test('masking never changes roles, tool names, identifiers or content-part types',async()=>{
  const runtime=loadRuntime();
  const request={...args(),text:'password=user',body:{message:'password=user'}};
  const data=await (await runtime.reviewPrivacyRequest(request)).response.json();
  const plan=await runtime.reviewPrivacyRequest({...request,body:{...request.body,privacyDecision:'replace',privacyReviewToken:data.privacyReview.token}});
  runtime.vault.set('chat',plan.mappings);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    const out=runtime.protectProviderPayload({model:'user',input:[
      {role:'user',type:'message',id:'user',content:[{type:'input_text',text:'password=user'}]},
      {type:'function_call',id:'user',call_id:'user',name:'user',arguments:'{"name":"user"}'}]});
    assert.equal(out.model,'user');assert.equal(out.input[0].role,'user');assert.equal(out.input[0].id,'user');
    assert.equal(out.input[0].content[0].type,'input_text');assert.ok(!out.input[0].content[0].text.endsWith('=user'));
    assert.equal(out.input[1].call_id,'user');assert.equal(out.input[1].name,'user');
    assert.notEqual(JSON.parse(out.input[1].arguments).name,'user');
  });
});

test('unchanged-send cannot export a vaulted identity absent from this job approval',async()=>{
  const runtime=loadRuntime();
  const previous=core.makePrivacyPlan('Erika Muster',learned).mappings;
  runtime.vault.set('chat',previous);
  const request={...args(),text:'password=another-synthetic-value',conversationId:'chat',body:{message:'password=another-synthetic-value'}};
  const data=await (await runtime.reviewPrivacyRequest(request)).response.json();
  const plan=await runtime.reviewPrivacyRequest({...request,body:{...request.body,privacyDecision:'original',privacyReviewToken:data.privacyReview.token}});
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    await assert.rejects(runtime.protectToolEvidence('{"name":"Erika Muster"}'),/Datenschutzfreigabe/);
    assert.throws(()=>runtime.protectProviderPayload({input:[{role:'user',content:'Erika Muster'}]}),/freigegebene/);
  });
});

test('sensitive numeric tool leaves are inspected and masked consistently',async()=>{
  const runtime=loadRuntime({extraFindings:[{type:'ACCOUNT',value:'81234567'}]});
  const request={...args(),text:'Passwort: "unrelated-synthetic-value"',body:{message:'Passwort: "unrelated-synthetic-value"'}};
  const data=await (await runtime.reviewPrivacyRequest(request)).response.json();
  const plan=await runtime.reviewPrivacyRequest({...request,body:{...request.body,privacyDecision:'replace',privacyReviewToken:data.privacyReview.token}});
  runtime.vault.set('chat',plan.mappings);
  await runtime.withJobPrivacy({userId:'alice',conversationId:'chat',privacyPolicy:plan.policy},async()=>{
    const safe=await runtime.protectToolEvidence('{"account":81234567,"summary":"not a measurement"}');
    const parsed=JSON.parse(safe.sanitized);
    assert.equal(typeof parsed.account,'string');assert.match(parsed.account,/<VEC_ACCOUNT_/);
    assert.ok(!safe.sanitized.includes('81234567'));
    const out=runtime.protectProviderPayload({input:[{type:'function_call_output',call_id:'c',output:'{"account":81234567}'}]});
    assert.ok(!out.input[0].output.includes('81234567'));
  });
});

test('a secret inside a longer email-shaped finding cannot leak through previews or saved aliases',()=>{
  const password='synthetic_phrase';
  const wrapped=password+'@db.example.invalid';
  const source='postgres://demo:'+wrapped+'/database';
  const existing=[{type:'EMAIL',value:wrapped,placeholder:'<EMAIL_A1B2C3>'}];
  const plan=core.makePrivacyPlan(source,core.deterministicFindings(source),existing);
  assert.ok(!plan.sanitized.includes(password));
  assert.equal(core.literalReplace(plan.sanitized,plan.mappings,true),source);
  assert.ok(plan.selected.map(core.displayFinding).every(f=>!f.displayValue.includes(password)));
  assert.equal(plan.mappings.find(m=>m.placeholder==='<EMAIL_A1B2C3>').type,'PASSWORD');
});
