/**
 * Pure presentation and authorization helpers.
 * No provider requests or database writes.
 */

export function canViewModelIntelligence(session) {
  return Boolean(
    session?.userId &&
    session.role === 'owner'
  );
}

export function modelIntelligenceRows(
  providers = [],
  metrics = []
) {
  const byId = new Map(
    metrics.map(metric => [metric.id, metric])
  );

  return providers
    .filter(
      provider =>
        provider.credential_scope === 'personal'
    )
    .map(provider => {
      const metric = byId.get(provider.id);

      const attempts = Number(metric?.attempts || 0);
      const successes = Number(metric?.successes || 0);

      return {
        id: provider.id,
        label: provider.label,
        provider: provider.provider,
        enabled: Boolean(provider.enabled),
        attempts,
        successes,

        successRate: attempts > 0
          ? Math.round(
              (1000 * successes) / attempts
            ) / 10
          : null,

        averageMs: attempts > 0
          ? (metric?.averageMs ?? null)
          : null,

        p95Ms: attempts > 0
          ? (metric?.p95Ms ?? null)
          : null,

        inputTokens: metric?.inputTokens ?? null,
        outputTokens: metric?.outputTokens ?? null,

        inputSamples: Number(
          metric?.inputSamples || 0
        ),

        outputSamples: Number(
          metric?.outputSamples || 0
        )
      };
    });
}
