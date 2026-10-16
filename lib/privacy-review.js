import crypto from 'node:crypto';
import {AsyncLocalStorage} from 'node:async_hooks';
import {digest, deterministicFindings, displayFinding, literalReplace,
  makePrivacyPlan, openPrivacy, sealPrivacy, normalizePersonFindings, createReviewScanCache} from './privacy-review-core.mjs';
import {requestPrivacyScan} from './privacy-ner-client.mjs';
import {withLocalWorkerSlot} from './local-worker-runtime';
import {getPrivacyMappings, savePrivacyMappings} from './privacy-vault';
import {recordUsage} from './usage';

const scopes = new AsyncLocalStorage();
const reviewScanCache = createReviewScanCache();
export const privacyReviewEnabled = () => process.env.VECTOR_PRIVACY_REVIEW === '1';
const key = () => Buffer.from(process.env.FILE_ENCRYPTION_KEY || '', 'hex');

export async function detectPrivateLocally(text, {userId, jobId = null, request = requestPrivacyScan} = {}) {
  if (typeof text !== 'string' || Buffer.byteLength(text) > 160000) throw new Error('Der Kontext ist zu gross für die lokale Datenschutzprüfung. Bitte den Kontext verkleinern.');
  const findings = deterministicFindings(text);
  const result = await withLocalWorkerSlot(() => request(text));
  // NER is an encoder, not a generative provider. Preserve actual text-token
  // metrics separately; never invent output tokens or add these to API totals.
  const event = {eventId:'ner_'+crypto.randomUUID(),userId:userId || null,provider:'local',
    model:result.metrics.model,inputTokens:0,outputTokens:0,cachedTokens:0,costChf:0,
    metadata:{kind:'local-privacy-scan',jobId,apiCostChf:0,searchCalls:0,costStatus:'local-no-api',
      ...result.metrics,basis:'Local encoder text subwords including overlap and rechecks; not generative or billable API tokens.'}};
  await recordUsage(event);
  return [...findings,...normalizePersonFindings(text,result.findings)];
}

async function detectReviewSegments(text, segments, userId) {
  const parts=segments || [text];
  if(!Array.isArray(parts) || parts.some(p=>typeof p!=='string') || parts.join('\n\n')!==text
      || Buffer.byteLength(text)>160000) throw new Error('Invalid privacy review snapshot.');
  const unique=[...new Set(parts.filter(p=>p.trim()))];
  const cached=new Map();const missing=[];
  for(const part of unique){
    const value=reviewScanCache.get(userId,part);
    if(value===undefined)missing.push(part);else cached.set(part,value);
  }
  if(missing.length){
    const findings=await detectPrivateLocally(missing.join('\n\n'),{userId});
    for(const part of missing){
      const selected=findings.filter(f=>part.includes(f.value));
      cached.set(part,selected);reviewScanCache.set(userId,part,selected);
    }
  }
  const whole=deterministicFindings(text);
  if(whole.some(f=>!parts.some(p=>p.includes(f.value))))
    throw new Error('Vertrauliche Angabe über mehrere Kontextteile. Es wurde nichts extern versendet.');
  return [...whole,...[...cached.values()].flat()];
}

export async function reviewPrivacyRequest({text, body, session, scope, conversationId, destination = 'cloud', uninspectable = false, scanSegments, previewText = body.message ?? text}) {
  const enabled = privacyReviewEnabled();
  if (body.privacyEnabled !== undefined && typeof body.privacyEnabled !== 'boolean') throw new Error('Invalid privacy preference.');
  if (destination === 'local') {
    if (process.env.VECTOR_LOCAL_WORKERS !== '1') throw new Error('Der lokale Chat ist noch nicht aktiviert.');
    if (uninspectable) throw new Error('Das lokale Textmodell kann keine Bilder verarbeiten.');
    return {...makePrivacyPlan('', []), sanitized:text, apply:value=>String(value), destination:'local', policy:null};
  }
  if (body.privacyEnabled === false) {
    return {...makePrivacyPlan('', []), sanitized:text, apply:value=>String(value), destination:'cloud',
      policy:sealPrivacy({kind:'job',userId:session.userId,scope,decision:'off',mappings:[],approved:[]},key())};
  }
  if (body.privacyEnabled === true && !enabled) throw new Error('Die lokale Datenschutzprüfung ist nicht aktiviert.');
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
    const findings = await detectReviewSegments(text, scanSegments, session.userId);
    plan = makePrivacyPlan(text, findings, existing);
    if (plan.totalFindings || uninspectable) {
      const current=plan.selected.filter(m=>literalReplace(previewText,[m])!==previewText);
      const other=plan.selected.filter(m=>!current.includes(m));
      return {response:Response.json({error:'PRIVACY_REVIEW_REQUIRED',
        message:'Prüfe die erkannten Angaben vor dem externen Versand.',
        privacyReview:{token:sealPrivacy({kind:'review',userId:session.userId,fingerprint,
          expires:Date.now()+10*60*1000,plan},key()), findings:current.map(displayFinding),
          contextFindings:other.map(displayFinding),
          canReplace:!uninspectable, uninspectable,
          preview:literalReplace(previewText,plan.mappings).slice(0,4000)}}, {status:409,headers:{'Cache-Control':'no-store'}})};
    }
    decision = 'reviewed';
  }
  const replace = decision !== 'original';
  const mappings = replace ? plan.mappings : existing.map(m=>
    plan.mappings.find(updated=>updated.placeholder===m.placeholder) || m);
  return {...plan, mappings, sanitized:replace?plan.sanitized:text,
    wasSanitized:replace && plan.wasSanitized,
    apply:value=>replace ? literalReplace(value,mappings) : String(value),destination:'cloud',
    policy:sealPrivacy({kind:'job',userId:session.userId,scope,decision,
      mappings:replace?plan.mappings:[],approved:plan.selected},key())};
}

export async function withJobPrivacy(payload, execute) {
  if (!privacyReviewEnabled() && !payload.privacyPolicy) return execute();
  if (payload.privacyDestination === 'local') return execute();
  const policy = openPrivacy(payload.privacyPolicy,key(),{kind:'job',userId:payload.userId});
  const mappings = await getPrivacyMappings(payload.conversationId);
  const usable=normalizePersonFindings(mappings.map(m=>m.value).join('\n'),mappings);
  const active=mappings.filter(m=>usable.some(f=>f.value===m.value));
  return scopes.run({...policy,mappings:active,restorationMappings:mappings,conversationId:payload.conversationId},execute);
}

export function protectProviderPayload(payload) {
  const scope = scopes.getStore();
  if (!scope || scope.decision === 'off') return payload;
  const approved = scope.approved || [];
  const protectText = text => {
    if(scope.decision==='original' && scope.mappings.some(m=>text.includes(m.value)
        && !approved.some(a=>a.value===m.value))) {
      throw new Error('Nicht freigegebene vertrauliche Angaben im Aufgabenkontext.');
    }
    const safe=scope.decision==='original'?text:literalReplace(text,scope.mappings);
    if(deterministicFindings(literalReplace(safe,approved)).length) {
      throw new Error('Neue vertrauliche Angaben im Aufgabenkontext. Externer Versand wurde blockiert.');
    }
    return safe;
  };
  const data = value => {
    if(typeof value==='string') return protectText(value);
    if(typeof value==='number') {
      const safe=protectText(String(value));
      return safe===String(value)?value:safe;
    }
    if(Array.isArray(value)) return value.map(data);
    if(value&&typeof value==='object') return Object.fromEntries(Object.entries(value).map(([k,v])=>[protectText(k),data(v)]));
    return value;
  };
  const structured = text => {
    let parsed;
    try { parsed=JSON.parse(text); } catch { return protectText(text); }
    return JSON.stringify(data(parsed));
  };
  const content = value => typeof value==='string'?protectText(value):Array.isArray(value)?value.map(part=>{
    if(part && ['input_text','output_text','text'].includes(part.type)) {
      if(typeof part.text!=='string') throw new Error('Invalid provider text part.');
      return {...part,text:protectText(part.text)};
    }
    if(part?.type==='input_image' && scope.decision!=='original') throw new Error('Bilder benötigen eine ausdrückliche Freigabe für unveränderten Versand.');
    // Image bytes and provider-owned opaque fields are not rewritten. Image
    // submission already required separate explicit unchanged-send approval.
    return part;
  }):value;
  const item = value => {
    if(typeof value==='string') return protectText(value);
    if(!value||typeof value!=='object') return value;
    const result={...value};
    if('content' in value) result.content=content(value.content);
    if(value.type==='function_call_output' && typeof value.output==='string') result.output=structured(value.output);
    if(value.type==='function_call' && typeof value.arguments==='string') result.arguments=structured(value.arguments);
    return result;
  };
  // Protocol identifiers, roles, part types, tool schemas, call IDs, signatures,
  // provider credentials and model IDs never participate in value substitution.
  return {...payload,...(payload.instructions?{instructions:protectText(payload.instructions)}:{}),
    ...('input' in payload?{input:typeof payload.input==='string'?protectText(payload.input)
      :Array.isArray(payload.input)?payload.input.map(item):payload.input}:{})};
}

export async function protectToolEvidence(rawOutput) {
  const scope = scopes.getStore();
  if (!scope) return null;
  if (scope.decision === 'off') return {...makePrivacyPlan('', []),sanitized:rawOutput};
  let parsed;
  try { parsed=JSON.parse(rawOutput); } catch { parsed=rawOutput; }
  const strings=[];
  const collect=value=>{
    if(typeof value==='string' || typeof value==='number') strings.push(String(value));
    else if(Array.isArray(value)) value.forEach(collect);
    else if(value&&typeof value==='object') Object.entries(value).forEach(([k,v])=>{strings.push(k);collect(v);});
  };
  collect(parsed);
  const text=strings.join('\n\n');
  const knownSafe = scope.decision==='original' ? text : literalReplace(text,scope.mappings);
  const findings = await detectPrivateLocally(knownSafe,{userId:scope.userId});
  const plan = makePrivacyPlan(knownSafe,findings,scope.mappings);
  const approved = new Set(scope.approved.map(m=>m.value));
  if (plan.selected.some(m=>!approved.has(m.value)) && scope.decision !== 'replace') {
    throw new Error('Neue vertrauliche Tool-Daten benötigen eine zusätzliche Datenschutzfreigabe. Diese neuen Tool-Daten wurden nicht extern versendet. Starte die Anfrage erneut und wähle Platzhalter verwenden, um auch neue Tool-Daten geschützt zu verarbeiten.');
  }
  if (scope.decision === 'original') return {...plan,mappings:scope.mappings,sanitized:rawOutput};
  await savePrivacyMappings({conversationId:scope.conversationId,mappings:plan.mappings});
  scope.mappings = plan.mappings;
  const replace=value=>typeof value==='string'?literalReplace(value,plan.mappings)
    :typeof value==='number'?(literalReplace(String(value),plan.mappings)===String(value)?value:literalReplace(String(value),plan.mappings))
    :Array.isArray(value)?value.map(replace)
    :value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[literalReplace(k,plan.mappings),replace(v)])):value;
  return {...plan,sanitized:typeof parsed==='string'?literalReplace(rawOutput,plan.mappings):JSON.stringify(replace(parsed))};
}

export function restoreLocalToolArguments(name, args) {
  const scope = scopes.getStore();
  const localTools = new Set(['server_snapshot','server_inspect','server_json_rankings',
    'project_search','project_read_file','artifact_create','artifact_create_from_server_json','server_local_worker']);
  if (!scope || !localTools.has(name)) return args;
  const restore = value => typeof value === 'string' ? literalReplace(value,[...(scope.restorationMappings || []),...scope.mappings],true)
    : Array.isArray(value) ? value.map(restore)
    : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([k,v])=>[k,restore(v)])) : value;
  // Existing authorization and argument validation still execute after restoration.
  // Never restore credentials into web search, external fetches or sandbox commands.
  return restore(args);
}

