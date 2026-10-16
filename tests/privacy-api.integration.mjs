/** Owner-run only: real built app + native NER + a new disposable PostgreSQL. */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';

const origin='http://privacy-test-app:3000';
const database=new URL(process.env.DATABASE_URL || 'postgres://missing');
if(process.env.VECTOR_PRIVACY_API_EVALUATION!=='1' || database.hostname!=='privacy-test-db' ||
   database.pathname!=='/vector_privacy_api_test' || process.env.FILE_STORAGE_PATH!=='/tmp/vector-privacy-api-files') {
  throw Error('Refusing privacy API tests outside the disposable evaluation.');
}
const {Client}=createRequire('/app/package.json')('pg');
const db=new Client({connectionString:database.href,connectionTimeoutMillis:5000});
const cookies={};const ids={};const checks=[];const timings={};
const phase=process.env.VECTOR_PRIVACY_API_PHASE || 'normal';
const check=name=>checks.push(name);
async function call(path,{as='alice',method='GET',body,form,status=200}={}) {
  const headers={};if(cookies[as])headers.cookie=cookies[as];
  if(body!==undefined)headers['Content-Type']='application/json';
  const response=await fetch(origin+path,{method,headers,body:form || (body===undefined?undefined:JSON.stringify(body)),
    redirect:'manual',signal:AbortSignal.timeout(130000)});
  // Keep synthetic content and cookies out of assertion/error logs.
  assert.equal(response.status,status,`${method} ${path}: unexpected HTTP status`);
  return response;
}
async function login(as) {
  const response=await call('/api/auth/login',{as:null,method:'POST',body:{username:as,password:process.env.VECTOR_PRIVACY_TEST_PASSWORD}});
  const cookie=response.headers.get('set-cookie');assert.ok(cookie?.startsWith('vector_session='));
  cookies[as]=cookie.split(';')[0];
}
async function counts() {
  const tables=['conversations','messages','agent_jobs','privacy_vault','usage_events'];const result={};
  for(const name of tables) {
    if(!(await db.query('SELECT to_regclass($1) AS t',[name])).rows[0].t){result[name]=0;continue;}
    result[name]=Number((await db.query(`SELECT COUNT(*) AS n FROM ${name}`)).rows[0].n);
  }
  return result;
}
function noNewChat(before,after) {
  for(const name of ['conversations','messages','agent_jobs','privacy_vault'])assert.equal(after[name],before[name],name+': write before consent');
}
async function review(path,body,as='alice') {
  const before=await counts();
  const response=await call(path,{as,method:'POST',body,status:409});
  assert.equal(response.headers.get('cache-control'),'no-store');
  const data=await response.json();assert.equal(data.error,'PRIVACY_REVIEW_REQUIRED');
  noNewChat(before,await counts());return data.privacyReview;
}
async function queued(path,body,as='alice') {
  const data=await (await call(path,{as,method:'POST',body,status:202})).json();
  const {rows}=await db.query('SELECT * FROM agent_jobs WHERE id=$1',[data.jobId]);
  assert.equal(rows.length,1);assert.equal(rows[0].status,'queued');assert.equal(rows[0].attempts,0);
  return {data,job:rows[0]};
}
function privateValuesAbsent(value,values,path='payload') {
  const sensitive=text=>values.some(v=>text.includes(v));
  if(typeof value==='string')assert.ok(!sensitive(value),'Unmasked private value at '+path);
  else if(Array.isArray(value))value.forEach((item,index)=>privateValuesAbsent(item,values,path+'['+index+']'));
  else if(value&&typeof value==='object')for(const [key,item] of Object.entries(value)) {
    assert.ok(!sensitive(key),'Unmasked private object key at '+path);
    privateValuesAbsent(item,values,path+'.'+key);
  }
}

async function usage() {
  return Number((await db.query("SELECT COUNT(*) AS n FROM usage_events WHERE metadata->>'kind'='local-privacy-scan'")).rows[0].n);
}

try {
  await db.connect();
  let ready=false;
  for(let n=0;n<100;n++) {
    try {const r=await fetch(origin+'/api/projects',{signal:AbortSignal.timeout(3000)});if(r.status===401){ready=true;break;}}catch{}
    await new Promise(r=>setTimeout(r,150));
  }
  assert.ok(ready,'Built application did not become ready.');
  if(phase==='normal') {
    await db.query('ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT');
    for(const as of ['alice','bob','disabled']) {
      ids[as]=crypto.randomUUID();const salt=crypto.randomBytes(24).toString('hex');
      const hash=crypto.scryptSync(process.env.VECTOR_PRIVACY_TEST_PASSWORD,salt,64).toString('hex');
      await db.query(`INSERT INTO vector_users(id,username,password_salt,password_hash,role,enabled,features)
        VALUES($1,$2,$3,$4,'member',TRUE,$5::jsonb)`,[ids[as],as,salt,hash,JSON.stringify({chat:as!=='disabled',projects:as!=='disabled'})]);
    }
  }
  for(const as of ['alice','bob','disabled'])await login(as);
  const prompt='Bitte schreibe Erika Muster eine E-Mail an erika@example.invalid. Passwort: "synthetic privacy phrase".';
  const values=['Erika Muster','erika@example.invalid','synthetic privacy phrase'];
  const beforeOff=await usage();
  const off=await queued('/api/chat',{message:prompt+' Expliziter Datenschutz-Aus-Test '+phase,mode:'normal',privacyEnabled:false});
  assert.equal(off.job.payload.privacyDestination,'cloud');
  assert.equal(typeof off.job.payload.privacyPolicy,'string');assert.ok(off.job.payload.privacyPolicy.length>32);
  assert.ok(off.job.payload.messages.some(m=>values.every(value=>m.content.includes(value))));
  assert.equal(off.job.payload.privacy.disabled,true);assert.equal(await usage(),beforeOff);
  check('explicit-off-preserves-original-and-skips-detector-'+phase);
  if(phase==='outage') {
    const before=await counts();
    const result=await (await call('/api/chat',{method:'POST',body:{message:prompt+' Noch nicht geprüfte neue Nachricht.',mode:'normal'},status:503})).json();
    assert.equal(result.error,'PRIVACY_REVIEW_FAILED');privateValuesAbsent(result,values);
    noNewChat(before,await counts());assert.equal((await counts()).usage_events,before.usage_events);
    check('native-service-outage-blocks-cloud-send-before-writes');
    const local=await queued('/api/chat',{message:prompt,mode:'local'});
    assert.equal(local.job.payload.privacyDestination,'local');check('local-request-remains-quiet-during-detector-outage');
  } else {
    const beforeUnauthorized=await counts();
    await call('/api/chat',{as:null,method:'POST',body:{message:prompt},status:401});
    await call('/api/chat',{as:'disabled',method:'POST',body:{message:prompt},status:403});
    noNewChat(beforeUnauthorized,await counts());assert.equal(await usage(),0);check('authorization-precedes-detection');
    const input={message:prompt,mode:'normal'};
    const initialStarted=performance.now();
    const approval=await review('/api/chat',input);timings.initialReviewMs=Math.round(performance.now()-initialStarted);
    assert.ok(approval.canReplace);assert.ok(approval.findings.some(f=>f.displayValue==='Erika Muster'));
    assert.ok(approval.findings.some(f=>f.displayValue==='erika@example.invalid'));
    assert.ok(approval.findings.some(f=>f.type==='PASSWORD'&&f.displayValue==='••••••••'));
    assert.ok(!JSON.stringify(approval).includes('synthetic privacy phrase'));
    check('pre-send-review-and-cancel-have-no-chat-or-job-writes');
    const beforeBad=await counts();
    await call('/api/chat',{as:'bob',method:'POST',body:{...input,privacyDecision:'replace',privacyReviewToken:approval.token},status:503});
    await call('/api/chat',{method:'POST',body:{...input,message:prompt+' Changed.',privacyDecision:'replace',privacyReviewToken:approval.token},status:503});
    noNewChat(beforeBad,await counts());check('consent-is-bound-to-user-and-exact-request');
    const beforeConfirm=await usage();
    const replaced=await queued('/api/chat',{...input,privacyDecision:'replace',privacyReviewToken:approval.token});
    assert.equal(await usage(),beforeConfirm,'Confirmation must not scan again.');
    privateValuesAbsent(replaced.job.payload,values);assert.equal(replaced.data.userMessage.content,prompt);
    assert.equal(replaced.job.user_id,ids.alice);
    const vault=(await db.query('SELECT * FROM privacy_vault WHERE conversation_id=$1',[replaced.data.conversationId])).rows;
    assert.ok(vault.length>=3);privateValuesAbsent(vault,values);
    const person=vault.find(v=>v.value_type==='PERSON');assert.ok(person);
    // Synthetic assistant fixture tests actual response restoration, without a cloud call.
    await db.query("INSERT INTO messages(id,conversation_id,role,content) VALUES($1,$2,'assistant',$3)",
      [crypto.randomUUID(),replaced.data.conversationId,'Antwort für '+person.placeholder]);
    const restored=await (await call('/api/conversations/'+replaced.data.conversationId)).json();
    assert.ok(restored.messages.some(m=>m.role==='assistant'&&m.content==='Antwort für Erika Muster'));
    await call('/api/conversations/'+replaced.data.conversationId,{as:'bob',status:404});
    await call('/api/conversations/'+replaced.data.conversationId,{as:null,status:401});
    check('confirmed-job-is-masked-vault-encrypted-response-restored-and-account-isolated');
    const offHistory=await queued('/api/chat',{message:'Bitte fasse die Nachricht kurz zusammen.',mode:'normal',
      privacyEnabled:false,conversationId:replaced.data.conversationId});
    assert.ok(offHistory.job.payload.messages.some(m=>m.content==='Antwort für Erika Muster'));
    assert.ok(!JSON.stringify(offHistory.job.payload.messages).includes(person.placeholder));
    assert.equal(await usage(),beforeConfirm);check('off-restores-owned-historical-placeholders-without-rescan');
    const original=await queued('/api/chat',{...input,privacyDecision:'original',privacyReviewToken:approval.token});
    assert.ok(original.job.payload.messages.some(m=>m.content===prompt));assert.equal(original.job.payload.privacyDestination,'cloud');
    assert.equal(await usage(),beforeConfirm);check('explicit-unchanged-send-preserves-original-without-rescan');
    const beforeLocal=await usage();const local=await queued('/api/chat',{message:prompt,mode:'local'});
    assert.equal(local.job.payload.privacyDestination,'local');assert.equal(local.job.payload.privacyPolicy,null);
    assert.equal(local.data.userMessage.content,prompt);assert.equal(await usage(),beforeLocal);check('fully-local-request-has-no-review-or-detector-call');
    const historyId=crypto.randomUUID();
    await db.query('INSERT INTO conversations(id,user_id,owner_user_id,title) VALUES($1,$2,$2,$3)',[historyId,ids.alice,'Synthetic history']);
    await db.query("INSERT INTO messages(id,conversation_id,role,content) VALUES($1,$2,'user',$3)",[crypto.randomUUID(),historyId,'Bitte verbessere die Nachricht an Zoë Beispiel. Ihre E-Mail ist zoe@example.invalid.']);
    const history=await review('/api/chat',{message:'Antworte kurz.',mode:'normal',conversationId:historyId});
    assert.ok(history.contextFindings.some(f=>f.displayValue==='Zoë Beispiel'));
    assert.equal(history.preview,'Antworte kurz.');assert.equal(history.findings.length,0);
    const scans=await usage();await call('/api/chat',{as:'bob',method:'POST',body:{message:'Antworte kurz.',conversationId:historyId},status:404});
    assert.equal(await usage(),scans);check('included-history-is-inspected-only-after-ownership-check');
    const upload=async(name,type,content)=>{
      const form=new FormData();form.set('file',new File([content],name,{type}));
      return (await (await call('/api/chat/attachments',{method:'POST',form,status:201})).json()).attachment.id;
    };
    const attachment=await upload('contact.txt','text/plain','Kontakt: erika@example.invalid. Passwort: "synthetic privacy phrase".');
    const attached=await review('/api/chat',{message:'Bitte formuliere die Nachricht.',mode:'normal',attachmentIds:[attachment]});
    assert.ok(attached.contextFindings.some(f=>f.displayValue==='erika@example.invalid'));
    assert.equal(attached.preview,'Bitte formuliere die Nachricht.');
    assert.ok(!JSON.stringify(attached).includes('synthetic privacy phrase'));check('uploaded-text-is-reviewed-with-hidden-credentials');
    const image=await upload('pixel.png','image/png',Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII=','base64'));
    const imageBody={message:'Beschreibe das Bild.',mode:'normal',attachmentIds:[image]};
    const imageReview=await review('/api/chat',imageBody);assert.equal(imageReview.canReplace,false);assert.equal(imageReview.uninspectable,true);
    await call('/api/chat',{method:'POST',body:{...imageBody,privacyDecision:'replace',privacyReviewToken:imageReview.token},status:503});
    check('images-require-explicit-unchanged-consent');
    const project=await (await call('/api/projects',{method:'POST',body:{name:'Synthetic project',privacyLevel:'personal'}})).json();
    const pid=project.project.id;
    await call(`/api/projects/${pid}/files/create`,{method:'POST',body:{name:'contact.txt',content:'Kontakt: erika@example.invalid. Passwort: "synthetic privacy phrase".'}});
    const projectBody={message:'Bitte formuliere die Kontakt Nachricht.',mode:'normal'};
    const projectReview=await review(`/api/projects/${pid}/chat`,projectBody);
    assert.ok(projectReview.contextFindings.some(f=>f.displayValue==='erika@example.invalid'));
    assert.equal(projectReview.preview,projectBody.message);
    const projectJob=await queued(`/api/projects/${pid}/chat`,{...projectBody,privacyDecision:'replace',privacyReviewToken:projectReview.token});
    privateValuesAbsent(projectJob.job.payload,['erika@example.invalid','synthetic privacy phrase']);
    const projectScans=await usage();
    await call(`/api/projects/${pid}/chat`,{as:'bob',method:'POST',body:projectBody,status:404});assert.equal(await usage(),projectScans);
    const localProject=await (await call('/api/projects',{method:'POST',body:{name:'Local synthetic project',privacyLevel:'local_only'}})).json();
    const localJob=await queued(`/api/projects/${localProject.project.id}/chat`,input);
    assert.equal(localJob.job.payload.privacyDestination,'local');assert.equal(await usage(),projectScans);
    const offLocalProject=await queued(`/api/projects/${localProject.project.id}/chat`,{...input,privacyEnabled:false});
    assert.equal(offLocalProject.job.payload.privacyDestination,'local');assert.equal(await usage(),projectScans);
    check('privacy-off-cannot-override-local-only-project');
    check('project-retrieval-consent-ownership-and-local-only-routing');
    const reset='Hilf mir bei einer Mail zum password reset für security-demo.invalid.\n'+
      'der username ist benno beispiel und das password Demo-456\nbitte gib benno bescheid.';
    const resetReview=await review('/api/chat',{message:reset,mode:'normal',conversationId:historyId});
    for(const value of ['benno beispiel','benno'])assert.ok(resetReview.findings.some(f=>f.displayValue===value));
    assert.ok(resetReview.findings.some(f=>f.type==='PASSWORD'&&f.displayValue==='••••••••'));
    assert.ok(!resetReview.preview.includes('Demo-456'));assert.ok(!resetReview.preview.includes('Zoë'));
    const resetJob=await queued('/api/chat',{message:reset,mode:'normal',conversationId:historyId,
      privacyDecision:'replace',privacyReviewToken:resetReview.token});
    privateValuesAbsent(resetJob.job.payload,['benno','Demo-456','Zoë Beispiel','zoe@example.invalid']);
    const beforeCached=await usage();
    const followupStarted=performance.now();
    await review('/api/chat',{message:'Weitere neue Nachricht.',mode:'normal',conversationId:historyId});
    timings.followupReviewMs=Math.round(performance.now()-followupStarted);
    const afterNew=await usage();assert.equal(afterNew,beforeCached+1);
    const cachedStarted=performance.now();
    await review('/api/chat',{message:'Weitere neue Nachricht.',mode:'normal',conversationId:historyId});
    timings.cachedReviewMs=Math.round(performance.now()-cachedStarted);
    assert.equal(await usage(),afterNew,'Unchanged reviewed segments must not trigger another scan.');
    check('natural-reset-credentials-current-preview-and-exact-context-cache');
    const events=(await db.query('SELECT * FROM usage_events')).rows;
    assert.ok(events.length>0);assert.ok(events.every(e=>e.provider==='local'&&Number(e.cost_chf)===0&&Number(e.input_tokens)===0&&Number(e.output_tokens)===0&&e.metadata.kind==='local-privacy-scan'&&e.metadata.processedTextTokens>0));
    privateValuesAbsent(events.map(e=>e.metadata),values);check('real-ledger-has-separate-encoder-metrics-zero-api-fees-and-no-private-text');
  }
  const jobs=(await db.query('SELECT status,attempts FROM agent_jobs')).rows;
  assert.ok(jobs.every(j=>j.status==='queued'&&j.attempts===0));
  console.log(JSON.stringify({passed:true,phase,checks,timings,queued_synthetic_jobs:jobs.length,
    executed_jobs:0,cloud_calls:0,api_cost_chf:0,isolated_database_writes:true,production_activated:false}));
} finally {await db.end();}

