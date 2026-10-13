/**
 * Read-only comparison against authorized provider candidates.
 *
 * No runtime secrets, prompts, API calls, database access,
 * or mutations.
 */

import { rankCandidates } from './model-broker-policy.mjs';

const family = (value) => {
  const candidate = String(value || '').toLowerCase();

  return [
    'openai',
    'anthropic',
    'google',
    'gemini',
    'perplexity',
    'xai',
    'azure',
    'ollama',
  ].includes(candidate) ? candidate : 'other';
};

const percentage = (value) =>
  typeof value === 'number' &&
  Number.isFinite(value) &&
  value >= 0 &&
  value <= 100
    ? value / 100
    : null;

export function compareProviderCandidates({
  candidates,
  mode = 'normal',
  task = {},
  preferredProviderId = null,
} = {}) {
  if (!Array.isArray(candidates)) {
    return {
      status: 'insufficient-data',
      reason: 'invalid-candidates',
    };
  }

  if (preferredProviderId) {
    return {
      status: 'skipped',
      reason: 'explicit-provider-preference',
    };
  }

  if (candidates.length < 2) {
    return {
      status: 'insufficient-data',
      reason: 'too-few-candidates',
    };
  }

  const primary =
    typeof task?.primary === 'string'
      ? task.primary
      : 'general';

  const eligible = [];

  for (const [index, item] of candidates.entries()) {
    const runtime = item?.runtime;
    const profile = runtime?.benchmarkProfile;

    const skill = percentage(
      profile?.scores?.[primary] ??
      profile?.scores?.general
    );

    if (
      !runtime?.id ||
      !runtime?.provider ||
      !runtime?.model ||
      skill === null
    ) {
      if (index === 0) {
        return {
          status: 'insufficient-data',
          reason: 'missing-benchmark-profile',
        };
      }

      continue;
    }

    eligible.push({
      id: `${runtime.id}:${runtime.model}`,
      provider: String(runtime.provider),
      external: true,
      enabled: true,
      health: 'healthy',

      // The existing resolver already filters capabilities.
      capabilities: [],

      qualityEstimate: skill,
      reliabilityEstimate:
        percentage(profile?.reliability) ?? .8,

      // Unknown until trustworthy observations exist.
      estimatedCostChf: null,
      estimatedLatencyMs: null,
    });
  }

  if (eligible.length < 2) {
    return {
      status: 'insufficient-data',
      reason: 'too-few-usable-candidates',
    };
  }

  const preference =
    mode === 'quick'
      ? 'speed'
      : mode === 'deep'
        ? 'quality'
        : 'balanced';

  const outcome = rankCandidates(
    {
      allowExternal: true,
      preference,
    },
    eligible
  );

  const choice = outcome.selected;

  if (!choice) {
    return {
      status: 'insufficient-data',
      reason: 'no-ranked-model',
    };
  }

  // The existing resolver has already sorted its candidates.
  const existing = eligible[0];

  const proposed = eligible.find(
    item => item.id === choice.modelId
  );

  if (!proposed) {
    return {
      status: 'insufficient-data',
      reason: 'unmatched-model',
    };
  }

  return {
    status: 'compared',
    agreement: choice.modelId === existing.id,
    candidateCount: eligible.length,
    legacyFamily: family(existing.provider),
    shadowFamily: family(proposed.provider),
    evidence: 'catalog-estimates-only',
  };
}
