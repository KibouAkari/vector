export function summarizeTraffic(
  rows,
  sources = [],
  { now = Date.now(), windowMinutes = 60, limit = 500 } = {},
) {
  const cutoff = now - windowMinutes * 60000,
    events = rows.filter((row) => Date.parse(row.observedAt) >= cutoff),
    groups = new Map(),
    services = new Map(),
    countries = new Map();
  const buckets = Array.from({ length: 30 }, (_, i) => ({
    time: new Date(cutoff + i * windowMinutes * 2000).toISOString(),
    requests: 0,
    connections: 0,
    attempts: 0,
  }));
  for (const row of events) {
    const key = [row.sourceIp, row.service, row.kind].join("|");
    if (!groups.has(key)) groups.set(key, { ...row, observations: 0 });
    groups.get(key).observations++;
    if (!services.has(row.service))
      services.set(row.service, {
        name: row.service,
        requests: 0,
        connections: 0,
        attempts: 0,
      });
    const field =
      row.kind === "http-request"
        ? "requests"
        : row.kind === "network-attempt"
          ? "attempts"
          : "connections";
    services.get(row.service)[field]++;
    if (row.country)
      countries.set(row.country, (countries.get(row.country) || 0) + 1);
    const index = Math.min(
      29,
      Math.max(
        0,
        Math.floor(
          (Date.parse(row.observedAt) - cutoff) / (windowMinutes * 2000),
        ),
      ),
    );
    buckets[index][field]++;
  }
  const active = [];
  const readerSources = sources.map((source) => {
    const age = now - Date.parse(source.receivedAt),
      sampleAge = now - Date.parse(source.connectionSampleAt || "");
    const stale = age > 20000;
    const validSample = !stale && sampleAge <= 45000 && sampleAge >= -60000;
    if (validSample)
      active.push(
        ...(source.connections || []).map((row) => ({
          ...row,
          collectorId: source.id,
          collectorName: source.name,
        })),
      );
    return {
      id: source.id,
      name: source.name,
      geoipProvider: source.geoipProvider || null,
      readers: source.readers,
      dropped: source.dropped,
      receivedAt: source.receivedAt,
      observedAt: source.observedAt,
      connectionSampleAt: source.connectionSampleAt,
      stale,
      sampleStale: !validSample,
      connectionsTruncated: source.connectionsTruncated,
      hasVitals: Boolean(source.vitals),
    };
  });
  const unique = new Map();
  for (const row of active)
    unique.set(row.collectorId + ":" + row.connectionId, row);
  const allActive = [...unique.values()];
  return {
    clients: [...groups.values()].slice(0, limit),
    activeConnections: allActive.slice(0, limit),
    activeConnectionCount: allActive.length,
    activeTruncated:
      allActive.length > limit ||
      readerSources.some((row) => row.connectionsTruncated),
    observations: events.length,
    uniqueClients: new Set(events.map((row) => row.sourceIp)).size,
    requests: events.filter((row) => row.kind === "http-request").length,
    attempts: events.filter((row) => row.kind === "network-attempt").length,
    services: [...services.values()].sort(
      (a, b) => b.requests + b.connections - a.requests - a.connections,
    ),
    countries: [...countries].map(([country, observations]) => ({
      country,
      observations,
    })),
    timeline: buckets,
    windowMinutes,
    sources: readerSources,
    latestAt: events[0]?.observedAt || null,
    recentEvents: events.slice(0, 80),
    clientsTruncated: groups.size > limit,
  };
}
