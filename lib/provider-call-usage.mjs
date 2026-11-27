import {AsyncLocalStorage} from 'node:async_hooks';
import crypto from 'node:crypto';

const contexts = new AsyncLocalStorage();

export function withProviderUsageScope(record, execute) {
  const scope = {events: [], seen: new Set(), record};
  return contexts.run(scope, () => execute(scope));
}

export async function captureProviderUsage(runtime, response) {
  const scope = contexts.getStore();
  if (!scope) return;
  let event;
  try { event = await scope.record(runtime, response); }
  catch {
    // A provider response already exists. Never misclassify this as a provider
    // outage and pay for a failover merely because the usage ledger is down.
    throw Object.assign(new Error('Provider usage persistence failed after a response; automatic provider replay is disabled.'),
      {code:'VECTOR_USAGE_PERSISTENCE_FAILED'});
  }
  if (!scope.seen.has(event.eventId)) {
    scope.seen.add(event.eventId);
    scope.events.push(event);
  }
  return event;
}

function tokenCount(value) {
  const number = Number(value);
  return (typeof value==='number'||typeof value==='string'&&/^\d+$/.test(value)) && Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function rate(value) {
  const number = Number(value);
  return (typeof value==='number'||typeof value==='string'&&/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value)) && Number.isFinite(number) && number >= 0 ? number : null;
}

export function providerUsageEvent({runtime, response, userId, jobId, projectId=null, exchangeRate, fallbackPricing = {}}) {
  const presence = response?.usage?.__vectorTelemetryPresence;
  const input = presence?.inputTokens===false?null:tokenCount(response?.usage?.input_tokens);
  const output = presence?.outputTokens===false?null:tokenCount(response?.usage?.output_tokens);
  const usageKnown = input !== null && output !== null &&
    presence?.inputTokens !== false && presence?.outputTokens !== false;
  const cached = tokenCount(response?.usage?.input_tokens_details?.cached_tokens) ?? 0;
  const writes = tokenCount(response?.usage?.input_tokens_details?.cache_write_tokens) ?? 0;
  const cacheValid = cached + writes <= (input ?? 0);
  const pricing = runtime?.pricing || fallbackPricing;
  const inputPrice = rate(pricing.inputPerMillionUsd);
  const cachePrice = rate(pricing.cachedInputPerMillionUsd);
  const writePrice = rate(pricing.cacheWriteInputPerMillionUsd);
  const outputPrice = rate(pricing.outputPerMillionUsd);
  const requestFee = rate(pricing.requestFeeUsd) ?? 0;
  const fx = rate(exchangeRate);
  if (fx === null || fx <= 0) throw new Error('Invalid USD to CHF accounting rate.');
  const knownPricing = inputPrice !== null && outputPrice !== null &&
    (runtime?.provider === 'local' || inputPrice > 0 || outputPrice > 0 || requestFee > 0) &&
    (cached === 0 || cachePrice !== null) && (writes === 0 || writePrice !== null);
  const searches = (response?.output || []).filter(item => item?.type === 'web_search_call').length;
  const searchFeeUsd = runtime?.provider === 'openai' ? searches * 0.01 : 0;
  const calculatedUsd = (Math.max(0, (input ?? 0) - cached - writes) * (inputPrice ?? 0) +
    cached * (cachePrice ?? 0) + writes * (writePrice ?? 0) +
    (output ?? 0) * (outputPrice ?? 0)) / 1_000_000 + requestFee + searchFeeUsd;
  const reportedUsd=runtime?.provider==='openrouter'?rate(response?.usage?.__vectorProviderCostUsd ?? response?.usage?.cost):null;
  const local=runtime?.provider==='local';
  const usd=local?0:reportedUsd ?? calculatedUsd;
  const costStatus=local?'local-no-api':reportedUsd!==null?'reported':usageKnown&&cacheValid&&knownPricing?'estimated':'incomplete';
  const responseId = response?.id || crypto.randomUUID();
  const eventId = 'call_' + crypto.createHash('sha256')
    .update(JSON.stringify([userId || null, runtime?.id || null, runtime?.provider, responseId])).digest('hex');
  return {
    eventId, userId: userId || null, provider: runtime?.provider || 'unknown', model: typeof response?.model==='string'&&response.model?response.model.slice(0,160):runtime?.model || 'unknown',
    inputTokens: input ?? 0, outputTokens: output ?? 0, cachedTokens: cacheValid ? cached : 0,
    costChf: usd * fx,
    metadata: {
      kind: 'provider-call', elapsedMs:typeof response?.__vectorElapsedMs==='number'?response.__vectorElapsedMs:null,projectId, jobId: jobId || null, responseId,requestedModel:runtime?.model || null,
      costStatus,costSource:local?'local-execution':reportedUsd!==null?'provider-response':'configured-rates',
      reportedCostUsd:reportedUsd,estimatedCostUsd:local?null:calculatedUsd,
      usageKnown, cacheValid, pricingKnown: knownPricing,
      costUsd: usd, usdToChfRate: fx,
      pricing: {inputPrice, cachePrice, writePrice, outputPrice, requestFee},
      searchCalls: searches, searchFeeUsd,
      cacheWriteTokens: writes,
      reasoningTokens: tokenCount(response?.usage?.output_tokens_details?.reasoning_tokens),
      responseStatus: response?.status || 'unknown',
      stopReason: response?.incomplete_details?.reason || null,
      serviceTier: response?.service_tier || null,
      // Never add reasoning tokens again: providers include them in output_tokens.
      basis:local?'No external inference API fee; host and energy costs are not included.':reportedUsd!==null?'USD charge reported in the provider response. CHF uses the configured exchange rate; not a reconciled invoice.':'Provider-reported tokens and configured rates; not a reconciled invoice.'
    }
  };
}

export function providerUsageTotals(events) {
  return events.reduce((total, event) => ({
    inputTokens: total.inputTokens + event.inputTokens,
    outputTokens: total.outputTokens + event.outputTokens,
    cachedTokens: total.cachedTokens + event.cachedTokens,
    costChf: total.costChf + event.costChf,
    webSearchCalls: total.webSearchCalls + event.metadata.searchCalls,
    incompleteCalls: total.incompleteCalls + (event.metadata.costStatus === 'incomplete' ? 1 : 0)
  }), {inputTokens:0,outputTokens:0,cachedTokens:0,costChf:0,webSearchCalls:0,incompleteCalls:0});
}
