import {readFile} from 'node:fs/promises';
import {validateLocalFindings} from './privacy-review-core.mjs';

export const PRIVACY_NER_MODEL = 'urchade/gliner_multi_pii-v1';
export const PRIVACY_NER_REV = '1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d';
const failure = () => new Error('Die lokale Datenschutzprüfung konnte nicht abgeschlossen werden. Es wurde nichts extern versendet.');
const count = value => Number.isSafeInteger(value) && value >= 0;

export function validateNerResponse(text, body) {
  if (!body || body.model !== PRIVACY_NER_MODEL || body.model_revision !== PRIVACY_NER_REV ||
      body.token_count_kind !== 'raw_text_subwords_including_overlap_and_rechecks' ||
      body.span_decoding !== 'nested' || !['chunks','primary_chunks','context_rechecks','processed_text_tokens',
        'max_chunk_words','max_chunk_text_tokens','generation'].every(key=>count(body[key])) ||
      body.chunks !== body.primary_chunks + body.context_rechecks || body.primary_chunks > 1024 ||
      body.context_rechecks > 32 || body.max_chunk_words > 64 || body.max_chunk_text_tokens > 192 ||
      (text.trim() && !body.primary_chunks) || body.generation < 1 || typeof body.cold !== 'boolean' ||
      !['scan_seconds','load_seconds'].every(key=>typeof body[key] === 'number' && Number.isFinite(body[key]) && body[key]>=0) ||
      !Array.isArray(body.findings) || body.findings.some(f=>f?.type!=='PERSON')) throw failure();
  const findings=validateLocalFindings(text,{findings:body.findings});
  // No raw findings, text, names, credentials or timing-dependent state in audit metadata.
  return {findings, metrics:{model:body.model,modelRevision:body.model_revision,
    processedTextTokens:body.processed_text_tokens,tokenCountKind:body.token_count_kind,
    chunks:body.chunks,primaryChunks:body.primary_chunks,contextRechecks:body.context_rechecks,
    cold:body.cold,loadSeconds:body.load_seconds,scanSeconds:body.scan_seconds}};
}

export async function requestPrivacyScan(text, {fetchImpl=fetch, readToken=()=>readFile('/run/secrets/vector_privacy_ner_token','utf8')}={}) {
  if (typeof text!=='string' || Buffer.byteLength(text)>160000) throw failure();
  let reader;
  try {
    const token=(await readToken()).trim();
    if (!/^[a-f0-9]{64}$/.test(token)) throw failure();
    const response=await fetchImpl('http://vector-privacy-ner:8091/scan',{
      method:'POST',redirect:'error',signal:AbortSignal.timeout(125000),
      headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({text})});
    if (!response.ok || !response.headers.get('content-type')?.startsWith('application/json')) throw failure();
    // Bounded body, including chunked HTTP responses. Never print response errors.
    reader=response.body.getReader();
    const buffers=[];let bytes=0;
    while (true) {
      const part=await reader.read();if(part.done)break;
      bytes+=part.value.byteLength;if(bytes>1000000)throw failure();
      buffers.push(Buffer.from(part.value));
    }
    return validateNerResponse(text,JSON.parse(Buffer.concat(buffers).toString('utf8')));
  } catch {
    throw failure();
  } finally {
    if(reader) {try {await reader.cancel();}catch{}}
  }
}
