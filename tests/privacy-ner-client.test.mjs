import test from 'node:test';
import assert from 'node:assert/strict';
import {requestPrivacyScan,validateNerResponse,PRIVACY_NER_MODEL,PRIVACY_NER_REV} from '../lib/privacy-ner-client.mjs';

const text='Bitte schreibe an Zoë Beispiel.';
const body=()=>({model:PRIVACY_NER_MODEL,model_revision:PRIVACY_NER_REV,
  findings:[{type:'PERSON',value:'Zoë Beispiel'}],chunks:1,primary_chunks:1,context_rechecks:0,
  processed_text_tokens:9,max_chunk_words:6,max_chunk_text_tokens:9,
  span_decoding:'nested',token_count_kind:'raw_text_subwords_including_overlap_and_rechecks',
  generation:1,cold:true,load_seconds:9.5,scan_seconds:0.15});
const readToken=async()=>'a'.repeat(64)+'\n';

test('private adapter sends only exact text to the fixed service and keeps encoder metrics separate',async()=>{
  const result=await requestPrivacyScan(text,{readToken,fetchImpl:async(url,init)=>{
    assert.equal(url,'http://vector-privacy-ner:8091/scan');assert.equal(init.redirect,'error');
    assert.equal(init.headers.Authorization,'Bearer '+'a'.repeat(64));
    assert.deepEqual(JSON.parse(init.body),{text});return Response.json(body());
  }});
  assert.deepEqual(result.findings,[{type:'PERSON',value:'Zoë Beispiel'}]);
  assert.equal(result.metrics.processedTextTokens,9);
  assert.ok(!JSON.stringify(result.metrics).includes('Zoë'));
  assert.equal(result.metrics.outputTokens,undefined);
});
test('wrong model, incomplete coverage metadata, invented spans and non-PERSON responses are rejected',()=>{
  for(const change of [{model:'other'},{model_revision:'other'},{findings:[{type:'PERSON',value:'Zoe Beispiel'}]},
    {findings:[{type:'EMAIL',value:'Zoë Beispiel'}]},{chunks:0},{primary_chunks:0},{context_rechecks:33},
    {processed_text_tokens:-1},{max_chunk_words:65},{max_chunk_text_tokens:193},{generation:0},
    {token_count_kind:'provider_tokens'},{scan_seconds:Infinity}]) {
    assert.throws(()=>validateNerResponse(text,{...body(),...change}));
  }
});
test('service/auth/redirect/size errors never cause fallback and hide error response content',async()=>{
  for(const fetchImpl of [async()=>Response.json({text:'private-error-value'},{status:503}),
      async()=>{throw Error('private-error-value');},async()=>new Response('x'.repeat(1000001),{headers:{'content-type':'application/json'}})]) {
    await assert.rejects(requestPrivacyScan(text,{readToken,fetchImpl}),error=>!error.message.includes('private-error-value')&&/nichts extern/.test(error.message));
  }
  let called=false;
  for(const options of [{readToken:async()=>'short'},{readToken:async()=>{throw Error('missing');}}]) {
    await assert.rejects(requestPrivacyScan(text,{...options,fetchImpl:async()=>{called=true;}}));
  }
  await assert.rejects(requestPrivacyScan('é'.repeat(80001),{readToken,fetchImpl:async()=>{called=true;}}));
  assert.equal(called,false);
});
