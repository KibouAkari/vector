import crypto from 'node:crypto';
import {AsyncLocalStorage} from 'node:async_hooks';
import {digest, deterministicFindings, displayFinding, literalReplace, localScanPayload,
  makePrivacyPlan, openPrivacy, sealPrivacy, validateLocalFindings} from './privacy-review-core.mjs';
import {requestLocalChat} from './local-worker-core.mjs';
import {withLocalWorkerSlot} from './local-worker-runtime';
import {getPrivacyMappings, savePrivacyMappings} from './privacy-vault';
import {providerUsageEvent,captureProviderUsage} from './provider-call-usage.mjs';
import {normalizedOpenAiUsage} from './provider-usage-normalization.mjs';
import {recordUsage} from './usage';

const scopes = new AsyncLocalStorage();
export const privacyReviewEnabled = () => process.env.VECTOR_PRIVACY_REVIEW === '1';
const key = () => Buffer.from(process.env.FILE_ENCRYPTION_KEY || '', 'hex');

export async function detectPrivateLocally(text, {userId, jobId = null, request = requestLocalChat, accountInJob = false} = {}) {
  if (Buffer.byteLength(text) > 160000) throw new Error('Der Kontext ist zu gross für die lokale Datenschutzprüfung. Bitte den Kontext verkleinern.');
  const findings = deterministicFindings(text);
  // Complete coverage, no truncation. Context overlap retains entities at a
  // chunk boundary; deterministic secrets are always detected on the whole input.
  const chunks = [];
  for (let i = 0; i < text.length; i += 2800) chunks.push(text.slice(i, i + 3200));
  await withLocalWorkerSlot(async () => {
    for (const chunk of chunks) {
      const body = await request(localScanPayload(chunk));
      const runtime = {provider:'local', model:'vector-qwen3:1.7b-q8',
        pricing:{inputPerMillionUsd:0, outputPerMillionUsd:0, cachedInputPerMillionUsd:0}};
      const response = {id:crypto.randomUUID(), usage: normalizedOpenAiUsage({prompt_tokens:body.prompt_eval_count,
        completion_tokens:body.eval_count}), output:[]};
      // Include rejected/truncated detector responses in the local token ledger.
      if (accountInJob) await captureProviderUsage(runtime,response);
      else await recordUsage(providerUsageEvent({runtime,response,userId,jobId,exchangeRate:1}));
      if (!body.done || body.done_reason !== 'stop' || typeof body.message?.content !== 'string') {
        throw new Error('Die lokale Datenschutzprüfung konnte nicht abgeschlossen werden. Es wurde nichts extern versendet.');
      }
      let parsed;
      try { parsed = JSON.parse(body.message.content); }
      catch { throw new Error('Die lokale Datenschutzprüfung lieferte ungültiges JSON. Es wurde nichts extern versendet.'); }
      findings.push(...validateLocalFindings(chunk, parsed));
    }
  });
  return findings;
}

export async function reviewPrivacyRequest({text, body, session, scope, conversationId, destination = 'cloud', uninspectable = false}) {
  const enabled = privacyReviewEnabled();
  if (destination === 'local') {
    if (!enabled || process.env.VECTOR_LOCAL_WORKERS !== '1') throw new Error('Der lokale Chat ist noch nicht aktiviert.');
    if (uninspectable) throw new Error('Das lokale Textmodell kann keine Bilder verarbeiten.');
    return {...makePrivacyPlan('', []), sanitized:text, apply:value=>String(value), destination:'local', policy:null};
  }
  const existing = conversationId ? await getPrivacyMappings(conversationId) : [];
  if (!enabled) {
    const plan = makePrivacyPlan(text, deterministicFindings(text), existing);
    return {...plan, apply:value=>literalReplace(value,plan.mappings), destination:'cloud', policy:null};
  }
  const fingerprint = digest(JSON.stringify({userId:session.userId,scope,conversationId,
    message:body.message,mode:body.mode || 'auto',attachmentIds:body.attachmentIds || [],text,uninspectable}));
  let plan;
  let decision = body.privacyDecision;
  if (body.privacyReviewToken && ['replace','original'].includes(decision)) {
    const review = openPrivacy(body.privacyReviewToken, key(), {kind:'review',userId:session.userId,fingerprint});
    plan = review.plan;
    if (uninspectable && decision === 'replace') throw new Error('Bilder können hier nicht zuverlässig anonymisiert werden. Entferne sie oder bestätige den unveränderten Versand.');
  } else {
    const findings = await detectPrivateLocally(text, {userId:session.userId});
    plan = makePrivacyPlan(text, findings, existing);
    if (plan.totalFindings || uninspectable) {
      return {response:Response.json({error:'PRIVACY_REVIEW_REQUIRED',
        message:'Prüfe die erkannten Angaben vor dem externen Versand.',
        privacyReview:{token:sealPrivacy({kind:'review',userId:session.userId,fingerprint,
          expires:Date.now()+10*60*1000,plan},key()), findings:plan.selected.map(displayFinding),
          canReplace:!uninspectable, uninspectable,
          preview:plan.sanitized.slice(0,12000)}}, {status:409,headers:{'Cache-Control':'no-store'}})};
    }
    decision = 'reviewed';
  }
  const replace = decision !== 'original';
  const mappings = replace ? plan.mappings : existing;
  return {...plan, mappings, sanitized:replace?plan.sanitized:text,
    wasSanitized:replace && plan.wasSanitized,
    apply:value=>replace ? literalReplace(value,mappings) : String(value),destination:'cloud',
    policy:sealPrivacy({kind:'job',userId:session.userId,scope,decision,
      mappings:replace?plan.mappings:[],approved:plan.selected},key())};
}

export async function withJobPrivacy(payload, execute) {
  if (!privacyReviewEnabled()) return execute();
  if (payload.privacyDestination === 'local') return execute();
  const policy = openPrivacy(payload.privacyPolicy,key(),{kind:'job',userId:payload.userId});
  const mappings = await getPrivacyMappings(payload.conversationId);
  return scopes.run({...policy,mappings,conversationId:payload.conversationId},execute);
}

export function protectProviderPayload(payload) {
  const scope = scopes.getStore();
  if (!scope) return payload;
  const visit = value => {
    if (typeof value === 'string') {
      const safe = scope.decision !== 'original' ? literalReplace(value,scope.mappings) : value;
      const remaining = literalReplace(safe,scope.approved || []);
      if (deterministicFindings(remaining).length) throw new Error('Neue vertrauliche Angaben im Aufgabenkontext. Externer Versand wurde blockiert.');
      return safe;
    }
    if (Array.isArray(value)) return value.map(visit);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,visit(v)]));
    return value;
  };
  // Never rewrite protocol fields, model IDs, tool schemas or provider credentials.
  return {...payload, ...(payload.instructions ? {instructions:visit(payload.instructions)} : {}),
    ...(payload.input ? {input:visit(payload.input)} : {})};
}

export async function protectToolEvidence(rawOutput) {
  const scope = scopes.getStore();
  if (!scope) return null;
  let parsed;
  try { parsed=JSON.parse(rawOutput); } catch { parsed=rawOutput; }
  const strings=[];
  const collect=value=>{
    if(typeof value==='string') strings.push(value);
    else if(Array.isArray(value)) value.forEach(collect);
    else if(value&&typeof value==='object') Object.entries(value).forEach(([k,v])=>{strings.push(k);collect(v);});
  };
  collect(parsed);
  const text=strings.join('\n\n');
  const knownSafe = literalReplace(text,scope.mappings);
  const findings = await detectPrivateLocally(knownSafe,{userId:scope.userId,accountInJob:true});
  const plan = makePrivacyPlan(knownSafe,findings,scope.mappings);
  const approved = new Set(scope.approved.map(m=>m.value));
  if (plan.selected.some(m=>!approved.has(m.value)) && scope.decision !== 'replace') {
    throw new Error('Neue vertrauliche Tool-Daten erfordern eine neue Datenschutzfreigabe. Es wurde nichts extern versendet.');
  }
  if (scope.decision === 'original') return {...plan,mappings:scope.mappings,sanitized:rawOutput};
  await savePrivacyMappings({conversationId:scope.conversationId,mappings:plan.mappings});
  scope.mappings = plan.mappings;
  const replace=value=>typeof value==='string'?literalReplace(value,plan.mappings)
    :Array.isArray(value)?value.map(replace)
    :value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[literalReplace(k,plan.mappings),replace(v)])):value;
  return {...plan,sanitized:typeof parsed==='string'?literalReplace(rawOutput,plan.mappings):JSON.stringify(replace(parsed))};
}

export function restoreLocalToolArguments(name, args) {
  const scope = scopes.getStore();
  const localTools = new Set(['server_snapshot','server_inspect','server_json_rankings',
    'project_search','project_read_file','artifact_create','artifact_create_from_server_json','server_local_worker']);
  if (!scope || !localTools.has(name)) return args;
  const restore = value => typeof value === 'string' ? literalReplace(value,scope.mappings,true)
    : Array.isArray(value) ? value.map(restore)
    : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([k,v])=>[k,restore(v)])) : value;
  // Existing authorization and argument validation still execute after restoration.
  // Never restore credentials into web search, external fetches or sandbox commands.
  return restore(args);
}
