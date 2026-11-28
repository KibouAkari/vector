import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeSource, normalizeVitals } from "../lib/traffic/telemetry.mjs";
import { normalizeTraffic } from "../lib/traffic/events.mjs";
import { summarizeTraffic } from "../lib/traffic/summary.mjs";
import { humanBytes, fallbackVitals } from "../lib/host-vitals.mjs";
const now = Date.now(),
  at = new Date(now).toISOString();
const flow = {
  connectionId: "a".repeat(64),
  sourceIp: "198.51.100.10",
  destinationIp: "203.0.113.2",
  sourcePort: 52001,
  destinationPort: 25565,
  transport: "tcp",
  service: "Game",
  state: "ESTABLISHED",
  country: "CH",
  observedAt: at,
};
const source = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Fixture host",
  observedAt: at,
  connectionSampleAt: at,
  readers: [{ kind: "conntrack", status: "ok" }],
  dropped: 0,
  geoipProvider: "db-ip",
};
const vitals = {
  observedAt: at,
  cpuPercent: 25,
  logicalCpus: 8,
  memory: { totalBytes: 1000, availableBytes: 400 },
  storage: [{ name: "System", totalBytes: 10000, availableBytes: 9000 }],
};
test("host metrics validate ranges and preserve unknown CPU without inventing it", () => {
  assert.equal(normalizeVitals(vitals, now).memory.usedBytes, 600);
  assert.equal(
    normalizeVitals({ ...vitals, cpuPercent: null }, now).cpuPercent,
    null,
  );
  for (const invalid of [
    { cpuPercent: 101 },
    { cpuPercent: undefined },
    { logicalCpus: 0 },
    { memory: { totalBytes: 100, availableBytes: 101 } },
    { observedAt: new Date(now + 120000).toISOString() },
  ])
    assert.throws(() => normalizeVitals({ ...vitals, ...invalid }, now));
});
test("collector snapshots retain exact service tuples and reject malformed batches", () => {
  const result = normalizeSource({ source, connections: [flow], vitals }, now);
  assert.equal(result.connections[0].destinationPort, 25565);
  assert.equal(result.geoipProvider, "db-ip");
  assert.equal(result.connections[0].sourceIp, "198.51.100.10");
  for (const invalid of [null, {}, "invalid", Array(2001).fill(flow)])
    assert.throws(() => normalizeSource({ source, connections: invalid }, now));
  assert.throws(() =>
    normalizeSource(
      { source, connections: [{ ...flow, destinationIp: "metadata.invalid" }] },
      now,
    ),
  );
});
test("fresh connections and HTTP request counts are independent; stale samples disappear", () => {
  const events = normalizeTraffic({
    events: [
      {
        ...flow,
        kind: "http-request",
        method: "GET",
        status: 200,
        path: "/account?secret=hidden",
        durationMs: 11,
      },
      { ...flow, kind: "connection-open" },
      { ...flow, kind: "network-attempt" },
    ],
  });
  assert.equal(events[0].path, "/account");
  assert.equal(JSON.stringify(events).includes("hidden"), false);
  const fresh = {
    ...normalizeSource({ source, connections: [flow] }, now),
    receivedAt: at,
  };
  const summary = summarizeTraffic(events, [fresh], { now });
  assert.equal(summary.requests, 1);
  assert.equal(summary.attempts, 1);
  assert.equal(summary.activeConnectionCount, 1);
  assert.equal(summary.uniqueClients, 1);
  assert.equal(
    summary.timeline.reduce((sum, row) => sum + row.requests, 0),
    1,
  );
  assert.equal(
    summarizeTraffic(events, [fresh], { now: now + 46000 })
      .activeConnectionCount,
    0,
  );
  assert.equal(
    summarizeTraffic(
      events,
      [{ ...fresh, receivedAt: new Date(now - 21000).toISOString() }],
      { now },
    ).sources[0].stale,
    true,
  );
});
test("connection caps and unlocated countries are reported honestly", () => {
  const sample = {
    ...source,
    receivedAt: at,
    connectionsTruncated: true,
    connections: [
      flow,
      { ...flow, connectionId: "b".repeat(64), country: null },
    ],
  };
  const summary = summarizeTraffic([], [sample], { now, limit: 1 });
  assert.equal(summary.activeConnectionCount, 2);
  assert.equal(summary.activeConnections.length, 1);
  assert.equal(summary.activeTruncated, true);
  assert.deepEqual(summary.countries, []);
});
test("host-agent fallback parses binary human units and does not sum Docker CPU", () => {
  assert.equal(humanBytes("1.5Gi"), 1.5 * 1024 ** 3);
  assert.equal(humanBytes("4096"), 4096);
  assert.equal(humanBytes("invalid"), null);
  const result = fallbackVitals({
    memory: "Mem: 62Gi 20Gi 2Gi 0B 40Gi 39Gi",
    disk: "Filesystem Size Used Avail Use% Mounted on\n/dev/example 100G 10G 90G 10% /",
    containerResources: [{ cpuPercent: 90 }],
  });
  assert.equal(result.cpuPercent, null);
  assert.equal(result.memory.usedBytes, 23 * 1024 ** 3);
  assert.equal(result.storage[0].totalBytes, 100 * 1024 ** 3);
  assert.equal(result.approximate, true);
});
test("world geometry is pinned public-domain geography with valid bounds", () => {
  const world = JSON.parse(
    readFileSync(
      new URL("../public/vector-assets/maps/world-110m.json", import.meta.url),
    ),
  );
  assert.ok(world.features.length > 170);
  assert.equal(
    new Set(world.features.map((row) => row.id)).size,
    world.features.length,
  );
  for (const row of world.features) {
    assert.match(row.id, /^(?:[A-Z]{2}|ne-[a-z-]+)$/);
    for (const polygon of row.polygons)
      for (const ring of polygon)
        for (const [lon, lat] of ring) {
          assert.ok(lon >= -180 && lon <= 180);
          assert.ok(lat >= -90 && lat <= 90);
        }
  }
});
