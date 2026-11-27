import crypto from "node:crypto";
import { db, initializeDatabase } from "../db";
import { encryptSecret, decryptSecret } from "../model-config";
import { normalizeTraffic } from "./events.mjs";
let initialization;
export function initializeTraffic() {
  if (!initialization)
    initialization = (async () => {
      await initializeDatabase();
      await db.query(
        `CREATE TABLE IF NOT EXISTS traffic_ingest_nonces(nonce TEXT PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS traffic_observations(id TEXT PRIMARY KEY,encrypted_event TEXT NOT NULL,observed_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()); CREATE INDEX IF NOT EXISTS idx_traffic_time ON traffic_observations(observed_at DESC);`,
      );
    })().catch((error) => {
      initialization = undefined;
      throw error;
    });
  return initialization;
}
export async function ingestTraffic(input, nonce) {
  const events = normalizeTraffic(input);
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
    await client.query(
      "INSERT INTO traffic_observations(id,encrypted_event,observed_at) SELECT * FROM unnest($1::text[],$2::text[],$3::timestamptz[])",
      [
        events.map(() => crypto.randomUUID()),
        events.map((event) => encryptSecret(JSON.stringify(event))),
        events.map((event) => event.observedAt),
      ],
    );
    await client.query(
      "DELETE FROM traffic_observations WHERE observed_at<NOW()-INTERVAL '24 hours'; DELETE FROM traffic_ingest_nonces WHERE created_at<NOW()-INTERVAL '5 minutes'",
    );
    await client.query("COMMIT");
    return { accepted: events.length };
  } catch (error) {
    await client.query("ROLLBACK");
    if (error.code === "23505") throw Error("TRAFFIC_REPLAY");
    throw error;
  } finally {
    client.release();
  }
}
export async function trafficOverview() {
  await initializeTraffic();
  const rows = (
    await db.query(
      "SELECT encrypted_event FROM traffic_observations WHERE observed_at>NOW()-INTERVAL '24 hours' ORDER BY observed_at DESC LIMIT 10000",
    )
  ).rows.map((row) => JSON.parse(decryptSecret(row.encrypted_event)));
  const groups = new Map();
  for (const event of rows) {
    const key = event.sourceIp + "|" + event.service + "|" + event.kind;
    if (!groups.has(key)) groups.set(key, { ...event, observations: 0 });
    groups.get(key).observations++;
  }
  return {
    clients: [...groups.values()],
    observations: rows.length,
    capped: rows.length === 10000,
    retentionHours: 24,
    configured: Boolean(process.env.VECTOR_TRAFFIC_INGEST_TOKEN),
    latestAt: rows[0]?.observedAt || null,
  };
}
