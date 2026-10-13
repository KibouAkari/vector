/**
 * Privacy-minimal provider attempt measurement.
 * No database calls, API requests, prompt content, or secrets.
 */

function shortIdentifier(value, limit) {
  return typeof value === 'string' && value.trim()
    ? value.trim().slice(0, limit)
    : null;
}

function positiveInteger(value) {
  return (
    typeof value === 'number' &&
    Number.isSafeInteger(value) &&
    value >= 0
  ) ? value : null;
}

function httpStatus(error) {
  const candidate =
    error?.status ??
    error?.statusCode ??
    error?.response?.status;

  return (
    Number.isInteger(candidate) &&
    candidate >= 100 &&
    candidate <= 599
  ) ? candidate : null;
}

function errorCategory(error, status) {
  if (status === 429) return 'rate-limit';

  if (status !== null) {
    return status >= 500
      ? 'upstream-5xx'
      : 'upstream-4xx';
  }

  if (
    error?.name === 'AbortError' ||
    error?.code === 'ETIMEDOUT'
  ) {
    return 'timeout';
  }

  if ([
    'ECONNRESET',
    'ECONNREFUSED',
    'ENOTFOUND',
    'EAI_AGAIN',
  ].includes(error?.code)) {
    return 'network';
  }

  return 'other';
}

/**
 * Fixed allowlisted fields only.
 * Ignore request bodies, credentials and exception messages.
 */
export function buildProviderMetric({
  runtime,
  response,
  error,
  failed = error !== undefined,
  elapsedMs,
}) {
  const providerConfigId =
    shortIdentifier(runtime?.id, 128);

  const provider =
    shortIdentifier(runtime?.provider, 64);

  const model =
    shortIdentifier(runtime?.model, 160);

  if (!providerConfigId || !provider || !model) {
    return null;
  }

  const usage =
    !failed &&
    response?.usage &&
    typeof response.usage === 'object'
      ? response.usage
      : null;

  const status = failed ? httpStatus(error) : null;

  return {
    providerConfigId,
    provider,
    model,
    adapter: shortIdentifier(runtime?.adapter, 48),
    success: !failed,
    elapsedMs: Math.min(
      2147483647,
      Math.max(
        0,
        Math.round(
          Number.isFinite(elapsedMs) ? elapsedMs : 0
        )
      )
    ),
    httpStatus: status,
    errorCategory:
      failed ? errorCategory(error, status) : null,
    inputTokens: positiveInteger(
      usage?.input_tokens
    ),
    outputTokens: positiveInteger(
      usage?.output_tokens
    ),
    cachedTokens: positiveInteger(
      usage?.input_tokens_details?.cached_tokens
    ),
  };
}

/**
 * Observe one provider attempt without changing its result.
 */
export async function measureProviderCall({
  runtime,
  execute,
  record,
  now = () => performance.now(),
}) {
  const start = now();

  const safelyRecord = (value) => {
    try {
      const metric = buildProviderMetric({
        runtime,
        ...value,
        elapsedMs: now() - start,
      });

      if (metric) record(metric);
    } catch {
      // Telemetry must never affect provider behavior.
    }
  };

  try {
    const response = await execute();

    safelyRecord({ response });

    return response;
  } catch (error) {
    safelyRecord({ error, failed: true });

    throw error;
  }
}
