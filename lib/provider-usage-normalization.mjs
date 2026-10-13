/**
 * Pure provider usage normalizers used by the actual request adapters.
 * The non-enumerable presence marker is visible to telemetry only.
 */

export function markUsagePresence(normalized, usage) {
  const supplied = value =>
    value !== undefined && value !== null;

  Object.defineProperty(normalized, '__vectorTelemetryPresence', {
    value: {
      inputTokens:
        supplied(usage?.prompt_tokens) ||
        supplied(usage?.input_tokens),
      outputTokens:
        supplied(usage?.completion_tokens) ||
        supplied(usage?.output_tokens),
      cachedTokens:
        supplied(usage?.prompt_tokens_details?.cached_tokens) ||
        supplied(usage?.input_tokens_details?.cached_tokens) ||
        supplied(usage?.cache_read_input_tokens) ||
        supplied(usage?.cached_tokens),
    },
    enumerable: false,
  });

  return normalized;
}

export function normalizedOpenAiUsage(usage) {
  return markUsagePresence({
    input_tokens: Number(
      usage?.prompt_tokens ?? usage?.input_tokens ?? 0
    ),
    output_tokens: Number(
      usage?.completion_tokens ?? usage?.output_tokens ?? 0
    ),
    input_tokens_details: {
      cached_tokens: Number(
        usage?.prompt_tokens_details?.cached_tokens ??
        usage?.input_tokens_details?.cached_tokens ??
        usage?.cache_read_input_tokens ??
        usage?.cached_tokens ??
        0
      ),
    },
  }, usage);
}

export function normalizedAnthropicUsage(usage) {
  return markUsagePresence({
    input_tokens: Number(usage?.input_tokens ?? 0),
    output_tokens: Number(usage?.output_tokens ?? 0),
    input_tokens_details: {
      cached_tokens: Number(usage?.cache_read_input_tokens ?? 0),
    },
  }, usage);
}
