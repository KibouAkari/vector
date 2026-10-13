/**
 * Vector Model Broker — pure, offline policy kernel.
 *
 * No network, secrets, database writes or provider calls.
 * NOT connected to live routing yet.
 */

const WEIGHTS = Object.freeze({
  balanced: {
    quality: .50,
    cost: .20,
    latency: .15,
    reliability: .15,
  },
  economy: {
    quality: .30,
    cost: .45,
    latency: .15,
    reliability: .10,
  },
  quality: {
    quality: .75,
    cost: .05,
    latency: .05,
    reliability: .15,
  },
  speed: {
    quality: .30,
    cost: .10,
    latency: .45,
    reliability: .15,
  },
});

const number = (value) =>
  typeof value === 'number' && Number.isFinite(value)
    ? value
    : null;

const ratio = (value, fallback = .5) => {
  const v = number(value);
  return v === null
    ? fallback
    : Math.min(1, Math.max(0, v));
};

/**
 * Calculate model performance from application observations.
 * Unknown measurements are never treated as zero.
 */
export function summarizeObservations(rows = []) {
  if (!Array.isArray(rows)) {
    throw new TypeError('observations must be an array');
  }

  const groups = new Map();

  for (const row of rows) {
    if (
      !row ||
      typeof row.modelId !== 'string' ||
      typeof row.success !== 'boolean'
    ) continue;

    const group = groups.get(row.modelId) || {
      count: 0,
      successes: 0,
      costs: [],
      latencies: [],
      quality: [],
    };

    group.count++;

    if (row.success) group.successes++;

    if (
      number(row.costChf) !== null &&
      row.costChf >= 0
    ) {
      group.costs.push(row.costChf);
    }

    if (
      number(row.latencyMs) !== null &&
      row.latencyMs >= 0
    ) {
      group.latencies.push(row.latencyMs);
    }

    if (
      row.qualityVerified === true &&
      number(row.qualityScore) !== null &&
      row.qualityScore >= 0 &&
      row.qualityScore <= 1
    ) {
      group.quality.push(row.qualityScore);
    }

    groups.set(row.modelId, group);
  }

  const average = (values) =>
    values.length
      ? values.reduce((a, b) => a + b, 0) / values.length
      : null;

  const percentile = (values, fraction) => {
    if (!values.length) return null;

    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.ceil(fraction * sorted.length) - 1];
  };

  return Object.fromEntries(
    [...groups].map(([modelId, group]) => [
      modelId,
      {
        sampleCount: group.count,
        successRate: group.successes / group.count,
        meanCostChf: average(group.costs),
        p50LatencyMs: percentile(group.latencies, .5),
        p95LatencyMs: percentile(group.latencies, .95),
        verifiedQuality: average(group.quality),
        verifiedQualitySamples: group.quality.length,
      },
    ])
  );
}

/**
 * Filter models using hard constraints before calculating
 * utility scores.
 *
 * Input must contain only sanitized model metadata,
 * never API keys or provider runtime objects.
 */
export function rankCandidates(
  task,
  candidates,
  observations = {}
) {
  if (!task || !Array.isArray(candidates)) {
    throw new TypeError('task and candidates required');
  }

  const weights =
    WEIGHTS[task.preference] || WEIGHTS.balanced;

  const required = new Set(
    task.requiredCapabilities || []
  );

  const allowed = task.allowedModelIds
    ? new Set(task.allowedModelIds)
    : null;

  const maxCost = number(task.maxCostChf);
  const scored = [];
  const rejected = [];

  for (const model of candidates) {
    if (
      !model ||
      typeof model.id !== 'string' ||
      typeof model.provider !== 'string'
    ) continue;

    const reasons = [];

    // Unknown provider locality is considered external.
    const external = model.external !== false;

    if (
      external &&
      (
        task.allowExternal !== true ||
        task.sensitive === true
      )
    ) {
      reasons.push('privacy');
    }

    if (allowed && !allowed.has(model.id)) {
      reasons.push('permission');
    }

    if (
      (task.excludedProviderIds || []).includes(
        model.providerId ?? model.provider
      )
    ) {
      reasons.push('provider-excluded');
    }

    if (
      model.health === 'down' ||
      model.health === 'disabled' ||
      model.enabled === false
    ) {
      reasons.push('provider-unavailable');
    }

    for (const capability of required) {
      if (
        !(model.capabilities || []).includes(capability)
      ) {
        reasons.push('missing-capability');
        break;
      }
    }

    const metrics = observations[model.id] || {};
    const sufficient = metrics.sampleCount >= 5;

    const costChf =
      sufficient &&
      number(metrics.meanCostChf) !== null
        ? metrics.meanCostChf
        : number(model.estimatedCostChf);

    if (
      maxCost !== null &&
      (
        maxCost < 0 ||
        costChf === null ||
        costChf > maxCost
      )
    ) {
      reasons.push('budget');
    }

    if (reasons.length) {
      rejected.push({
        modelId: model.id,
        reasons,
      });
      continue;
    }

    const quality =
      sufficient &&
      metrics.verifiedQualitySamples >= 5
        ? ratio(metrics.verifiedQuality)
        : ratio(model.qualityEstimate);

    const reliability = sufficient
      ? ratio(metrics.successRate)
      : ratio(model.reliabilityEstimate, .8);

    const latency =
      sufficient &&
      number(metrics.p95LatencyMs) !== null
        ? metrics.p95LatencyMs
        : number(model.estimatedLatencyMs);

    const costScore =
      costChf === null
        ? .35
        : 1 / (1 + costChf / .05);

    const latencyScore =
      latency === null || latency < 0
        ? .35
        : 1 / (1 + latency / 12000);

    const score =
      quality * weights.quality +
      costScore * weights.cost +
      latencyScore * weights.latency +
      reliability * weights.reliability -
      (model.health === 'degraded' ? .12 : 0);

    scored.push({
      modelId: model.id,
      provider: model.provider,
      score: Number(score.toFixed(6)),
      inputs: {
        quality,
        reliability,
        costChf,
        latencyMs: latency,
        measured: sufficient,
      },
    });
  }

  scored.sort(
    (a, b) =>
      b.score - a.score ||
      a.modelId.localeCompare(b.modelId)
  );

  return {
    selected: scored[0] || null,
    ranked: scored,
    rejected,
  };
}

/**
 * This only evaluates retry safety.
 * It NEVER performs a retry or fallback.
 */
export function safeToRetry({
  status,
  errorType,
  attempts = 0,
  maxAttempts = 2,
  streamedOutput = false,
  sideEffectsStarted = false,
  idempotent = true,
} = {}) {
  if (
    attempts >= maxAttempts ||
    streamedOutput ||
    sideEffectsStarted ||
    !idempotent
  ) {
    return false;
  }

  if (
    [400, 401, 402, 403, 404, 422].includes(status)
  ) {
    return false;
  }

  return (
    status === 429 ||
    (
      Number.isInteger(status) &&
      status >= 500 &&
      status <= 599
    ) ||
    [
      'timeout',
      'network',
      'connection-reset',
    ].includes(errorType)
  );
}
