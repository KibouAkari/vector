import crypto from "node:crypto";
import { db, initializeDatabase } from "../db";
import { encryptSecret, decryptSecret } from "../model-config";
import { normalizeTraffic } from "./events.mjs";
import { normalizeSource } from "./telemetry.mjs";
import { summarizeTraffic } from "./summary.mjs";
let initialization;
export function initializeTraffic() {
  if (!initialization)
    initialization = (async () => {
      await initializeDatabase();
      await db.query(
        `CREATE TABLE IF NOT EXISTS traffic_ingest_nonces(nonce TEXT PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS traffic_observations(id TEXT PRIMARY KEY,encrypted_event TEXT NOT NULL,observed_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE INDEX IF NOT EXISTS idx_traffic_time ON traffic_observations(observed_at DESC);CREATE TABLE IF NOT EXISTS traffic_sources(id TEXT PRIMARY KEY,encrypted_state TEXT NOT NULL,received_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS host_resource_samples(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,encrypted_sample TEXT NOT NULL,observed_at TIMESTAMPTZ NOT NULL);CREATE INDEX IF NOT EXISTS idx_host_samples_time ON host_resource_samples(observed_at DESC);`,
      );
    })().catch((error) => {
      initialization = undefined;
      throw error;
    });
  return initialization;
}
export async function ingestTraffic(input, nonce) {
  if (
    !input ||
    typeof input !== "object" ||
    (input.events !== undefined && !Array.isArray(input.events))
  )
    throw Error("INVALID_TRAFFIC_EVENTS");
  const source = normalizeSource(input);
  const events = input.events?.length ? normalizeTraffic(input) : [];
  if (!events.length && !source) throw Error("INVALID_TRAFFIC_EVENTS");
  await initializeTraffic();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-traffic-ingest'))",
    );
    const count = (
      await client.query(
        "SELECT COUNT(*)::int AS n FROM traffic_ingest_nonces WHERE created_at>NOW()-INTERVAL '1 minute'",
      )
    ).rows[0].n;
    if (count >= 60) throw Error("TRAFFIC_RATE_LIMIT");
    await client.query("INSERT INTO traffic_ingest_nonces(nonce) VALUES($1)", [
      nonce,
    ]);
    if (events.length)
      await client.query(
        "INSERT INTO traffic_observations(id,encrypted_event,observed_at) SELECT * FROM unnest($1::text[],$2::text[],$3::timestamptz[])",
        [
          events.map(() => crypto.randomUUID()),
          events.map((row) => encryptSecret(JSON.stringify(row))),
          events.map((row) => row.observedAt),
        ],
      );
    if (source) {
      if (
        !(
          await client.query("SELECT id FROM traffic_sources WHERE id=$1", [
            source.id,
          ])
        ).rowCount &&
        (await client.query("SELECT COUNT(*)::int AS n FROM traffic_sources"))
          .rows[0].n >= 20
      )
        throw Error("COLLECTOR_LIMIT");
      const previous = (
        await client.query(
          "SELECT encrypted_state FROM traffic_sources WHERE id=$1 FOR UPDATE",
          [source.id],
        )
      ).rows[0];
      const old = previous
        ? JSON.parse(decryptSecret(previous.encrypted_state))
        : null;
      if (old && Date.parse(old.observedAt) > Date.parse(source.observedAt))
        throw Error("STALE_COLLECTOR_SAMPLE");
      const state = {
        ...source,
        connections:
          source.connections === undefined
            ? old?.connections || []
            : source.connections,
        vitals: source.vitals || old?.vitals || null,
      };
      await client.query(
        "INSERT INTO traffic_sources(id,encrypted_state) VALUES($1,$2) ON CONFLICT(id) DO UPDATE SET encrypted_state=$2,received_at=NOW()",
        [source.id, encryptSecret(JSON.stringify(state))],
      );
      if (source.vitals)
        await client.query(
          "INSERT INTO host_resource_samples(id,source_id,encrypted_sample,observed_at) VALUES($1,$2,$3,$4)",
          [
            crypto.randomUUID(),
            source.id,
            encryptSecret(JSON.stringify(source.vitals)),
            source.vitals.observedAt,
          ],
        );
    }
    await client.query(
      "DELETE FROM traffic_observations WHERE observed_at<NOW()-INTERVAL '24 hours';DELETE FROM traffic_ingest_nonces WHERE created_at<NOW()-INTERVAL '5 minutes';DELETE FROM host_resource_samples WHERE observed_at<NOW()-INTERVAL '24 hours';DELETE FROM traffic_sources WHERE received_at<NOW()-INTERVAL '7 days'",
    );
    await client.query("COMMIT");
    return { accepted: events.length, sourceAccepted: Boolean(source) };
  } catch (error) {
    await client.query("ROLLBACK");
    if (error.code === "23505") throw Error("TRAFFIC_REPLAY");
    throw error;
  } finally {
    client.release();
  }
}
export async function sourceStates() {
  await initializeTraffic();
  return (
    await db.query(
      "SELECT encrypted_state,received_at FROM traffic_sources ORDER BY received_at DESC LIMIT 20",
    )
  ).rows.map((row) => ({
    ...JSON.parse(decryptSecret(row.encrypted_state)),
    receivedAt: row.received_at.toISOString(),
  }));
}
export async function trafficOverview({ windowMinutes = 60 } = {}) {
  await initializeTraffic();
  const [rows, sources] = await Promise.all([
    db.query(
      "SELECT encrypted_event FROM traffic_observations WHERE observed_at>NOW()-($1::int*INTERVAL '1 minute') ORDER BY observed_at DESC LIMIT 10000",
      [windowMinutes],
    ),
    sourceStates(),
  ]);
  const events = rows.rows.map((row) =>
    JSON.parse(decryptSecret(row.encrypted_event)),
  );
  return {
    ...summarizeTraffic(events, sources, { windowMinutes }),
    capped: events.length === 10000,
    retentionHours: 24,
    configured: Boolean(process.env.VECTOR_TRAFFIC_INGEST_TOKEN),
    serverTime: new Date().toISOString(),
  };
}
export async function hostResources() {
  const sources = await sourceStates(),
    selected = sources.find((row) => row.vitals);
  if (!selected) return { available: false, sources: [] };
  const history = (
    await db.query(
      "SELECT encrypted_sample FROM host_resource_samples WHERE source_id=$1 AND observed_at>NOW()-INTERVAL '1 hour' ORDER BY observed_at DESC LIMIT 120",
      [selected.id],
    )
  ).rows
    .map((row) => JSON.parse(decryptSecret(row.encrypted_sample)))
    .reverse();
  return {
    available: true,
    ...selected.vitals,
    sourceId: selected.id,
    sourceName: selected.name,
    receivedAt: selected.receivedAt,
    stale: Date.now() - Date.parse(selected.vitals.observedAt) > 20000,
    history,
  };
}
