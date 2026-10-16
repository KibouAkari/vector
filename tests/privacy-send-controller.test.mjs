import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createPrivacySender} from '../lib/privacy-send-controller.mjs';
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const review=()=>Response.json({error:'PRIVACY_REVIEW_REQUIRED',privacyReview:{token:'synthetic-review',findings:[],preview:'fixture'}},{status:409});
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('checking is visible before a pending request and persists until review, with explicit confirmation only',async()=>{
  const states=[],calls=[],first=deferred(),choice=deferred();
  const sender=createPrivacySender({now:()=>123,onState:s=>states.push(s),requestChoice:()=>choice.promise,
    fetchImpl:(url,args)=>{calls.push(args);return calls.length===1?first.promise:Promise.resolve(Response.json({jobId:'job'}));}});
  const result=sender.send('/chat',{message:'fixture'});
  assert.deepEqual(states,[{phase:'checking',startedAt:123}]);assert.equal(calls.length,1);
  await assert.rejects(sender.send('/chat',{message:'duplicate'}),/bereits/);
  first.resolve(review());await tick();assert.equal(states.at(-1).phase,'review');assert.equal(calls.length,1);
  choice.resolve('replace');assert.equal((await result).ok,true);
  assert.deepEqual(JSON.parse(calls[1].body),{message:'fixture',privacyDecision:'replace',privacyReviewToken:'synthetic-review'});
  assert.deepEqual(states.map(s=>s.phase),['checking','review','sending','idle']);
});

test('cancel and changed scope never submit the confirmation',async()=>{
  for(const invalidate of [false,true]){
    const calls=[],choice=deferred();let current=true;
    const sender=createPrivacySender({onState:()=>{},requestChoice:()=>choice.promise,
      fetchImpl:async(url,args)=>{calls.push(args);return review();}});
    const response=sender.send('/chat',{message:'fixture'},{isCurrent:()=>current});
    await tick();if(invalidate)current=false;choice.resolve(invalidate?'original':null);
    assert.equal((await (await response).json()).privacyCancelled,true);assert.equal(calls.length,1);
  }
});

test('scope cancellation aborts the obsolete request without clearing a newer pending status',async()=>{
  const states=[],requests=[];
  const sender=createPrivacySender({onState:s=>states.push(s),requestChoice:async()=>null,
    fetchImpl:(url,args)=>{const task=deferred();requests.push({args,...task});return task.promise;}});
  const old=sender.send('/chat',{message:'old'});sender.cancel();
  assert.equal(requests[0].args.signal.aborted,true);
  const newer=sender.send('/chat',{message:'new'});
  requests[0].resolve(Response.json({jobId:'old-job'}));await old;
  assert.equal(states.at(-1).phase,'checking');
  requests[1].resolve(Response.json({jobId:'new-job'}));assert.equal((await newer).ok,true);
  assert.equal(states.at(-1).phase,'idle');
});

test('fully local destinations stay quiet and errors clear the progress indicator',async()=>{
  for(const options of [{localOnly:true},{}]){
    const states=[];const sender=createPrivacySender({onState:s=>states.push(s),requestChoice:async()=>null,
      fetchImpl:async()=>Response.json({jobId:'local'})});
    await sender.send('/chat',{message:'fixture',mode:options.localOnly?'normal':'local'},options);
    assert.ok(states.every(s=>s.phase==='idle'));
  }
  const states=[];const sender=createPrivacySender({onState:s=>states.push(s),requestChoice:async()=>null,
    fetchImpl:async()=>{throw Error('network unavailable');}});
  await assert.rejects(sender.send('/chat',{message:'fixture'}),/network unavailable/);
  assert.deepEqual(states.map(s=>s.phase),['checking','idle']);
});

test('both composers place the compact review beside the input, without a modal or eyebrow',()=>{
  const ui=readFileSync(new URL('../components/ui/privacy-review-dialog.js',import.meta.url),'utf8');
  assert.ok(!ui.includes('showModal')&&!ui.includes('<dialog')&&!ui.includes('Vor dem externen Versand'));
  assert.ok(ui.includes('Vector überprüft die Anfrage'));assert.ok(ui.includes('prefers-reduced-motion'));
  const chat=readFileSync(new URL('../app/chat/chat-client.js',import.meta.url),'utf8');
  const project=readFileSync(new URL('../app/projects/[id]/project-workspace.js',import.meta.url),'utf8');
  for(const source of [chat,project])assert.ok(source.indexOf('{privacyDialog}')>source.indexOf('<form'));
  assert.match(project,/localOnly:project\.privacy_level==='local_only'/);
});


test('an already obsolete scope performs no network request',async()=>{
  const sender=createPrivacySender({onState:()=>{},requestChoice:async()=>null,
    fetchImpl:()=>assert.fail('Obsolete scope must not post')});
  assert.equal((await (await sender.send('/chat',{message:'fixture'},{isCurrent:()=>false})).json()).privacyCancelled,true);
});


test('send timer restarts after consent and excludes time spent reading the review',async()=>{
  let now=100;const states=[],choice=deferred();let calls=0;
  const sender=createPrivacySender({now:()=>now,onState:s=>states.push(s),requestChoice:()=>choice.promise,
    fetchImpl:async()=>++calls===1?review():Response.json({jobId:'job'})});
  const pending=sender.send('/chat',{message:'fixture'});await tick();
  now=30100;choice.resolve('original');await pending;
  assert.equal(states.find(s=>s.phase==='checking').startedAt,100);
  assert.equal(states.find(s=>s.phase==='sending').startedAt,30100);
});
