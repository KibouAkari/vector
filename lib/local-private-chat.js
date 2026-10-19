import {boundedLocalContext} from './local-context.mjs';
import {localServerStatistics} from './local-server-statistics.mjs';
import {hostInspect} from './host-agent';
import {classifyExecution} from './execution-router';
import crypto from 'node:crypto';
import {db} from './db';
import {requestLocalChat} from './local-worker-core.mjs';
import {withLocalWorkerSlot} from './local-worker-runtime';
import {captureProviderUsage, providerUsageTotals} from './provider-call-usage.mjs';
import {normalizedOpenAiUsage} from './provider-usage-normalization.mjs';
import {completeAgentJob, failAgentJob, heartbeatAgentJob, getAgentJob} from './background-jobs';
import {restorePrivateValues} from './privacy-vault';

// A separate native Ollama path: never resolve a cloud provider, search, run
// arbitrary tools/workflows, or fail over. Deterministic statistics use fixed read-only sources. A cloud parent using local workers is NOT local.
export async function executeLocalPrivateJob(job, usageScope) {
  const payload = typeof job.payload === 'string' ? JSON.parse(job.payload) : job.payload;
  try {
    if (process.env.VECTOR_LOCAL_WORKERS !== '1') {
      throw new Error('Der lokale Chat ist nicht aktiviert. Es gibt keinen Cloud-Fallback.');
    }
    const messages = [];
    for (const message of payload.messages || []) {
      if (typeof message.content !== 'string') throw new Error('Der lokale Chat unterstützt nur Text.');
      messages.push({role:message.role === 'assistant' ? 'assistant' : 'user',
        content:await restorePrivateValues({conversationId:payload.conversationId,text:message.content})});
    }
    const lastUserIndex = messages.findLastIndex(m => m.role === 'user');
    const taskText=await restorePrivateValues({conversationId:payload.conversationId,
      text:payload.requestText ?? payload.safeOriginalMessage ?? messages[lastUserIndex]?.content ?? ''});
    const recentMessages=messages.slice(0,Math.max(0,lastUserIndex));
    if ((await getAgentJob(job.id))?.status !== 'running') return {cancelled:true};
    await heartbeatAgentJob({id:job.id,progress:{stage:'local',message:'Vector prüft die lokalen Daten'}});
    const statistics=await localServerStatistics({text:taskText,recentMessages,
      allowServer:Boolean(payload.allowServer),inspect:hostInspect});
    let text;
    let model='vector-local-statistics';
    if (statistics) text=statistics.text;
    else {
      const route = classifyExecution({taskText,allowServer:true,recentMessages});
      if (['server','web','network','sandbox','artifact'].some(name=>route.requirements?.[name])) {
        throw new Error('Diese Aufgabe benötigt weitere Datenwerkzeuge. Wähle Auto oder Normal für die vorhandenen Serverwerkzeuge. Es wurde kein Modell aufgerufen.');
      }
      const context=boundedLocalContext(messages);
      await heartbeatAgentJob({id:job.id,progress:{stage:'local',message:'Wird vollständig lokal verarbeitet'}});
      model='vector-qwen3:1.7b-q8';
      const body = await withLocalWorkerSlot(() => requestLocalChat({model,
        stream:false,think:false,keep_alive:'5m',messages:[{role:'system',content:'Du bist Vector. Antworte kurz, klar und in der Sprache der Anfrage. Verwende keine Emojis. Erfinde keine Daten, Quellen oder Webseiten. Wenn Belege fehlen, sage das kurz.'},...context.messages],
        options:{num_ctx:8192,num_predict:768,num_thread:2,temperature:0.2}}));
      const runtime = {provider:'local',model,
        pricing:{inputPerMillionUsd:0,outputPerMillionUsd:0,cachedInputPerMillionUsd:0}};
      await captureProviderUsage(runtime,{id:crypto.randomUUID(),usage:normalizedOpenAiUsage({
        prompt_tokens:body.prompt_eval_count,completion_tokens:body.eval_count}),output:[]});
      if (!body.done || body.done_reason !== 'stop' || !body.message?.content?.trim()) {
        throw new Error('Die lokale Antwort wurde nicht vollständig erstellt. Es wurde kein Cloud-Modell verwendet.');
      }
      text=body.message.content;
    }
    const current=await getAgentJob(job.id);
    if (!current || current.status !== 'running') return {cancelled:true};
    const assistantMessageId = crypto.randomUUID();
    await db.query(`INSERT INTO messages (id,conversation_id,role,content,model,cost_chf)
      VALUES ($1,$2,'assistant',$3,$4,0)`,[assistantMessageId,payload.conversationId,text,model]);
    await db.query('UPDATE conversations SET updated_at=NOW() WHERE id=$1',[payload.conversationId]);
    const totals = providerUsageTotals(usageScope.events);
    const result = {assistantMessageId,text,meta:{provider:'local',providerLabel:'Lokal',model,
      costChf:0,inputTokens:totals.inputTokens,outputTokens:totals.outputTokens,webSearchCalls:0,fullyLocal:true,localData:statistics?{files:statistics.files,readAt:statistics.readAt,source:'saved_player_statistics'}:null}};
    await completeAgentJob({id:job.id,assistantMessageId,result});
    return result;
  } catch (error) {
    if ((await getAgentJob(job.id))?.status==='cancelled') return {cancelled:true};
    await failAgentJob({id:job.id,error}); throw error;
  }
}

