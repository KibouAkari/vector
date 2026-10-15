/**
 * Verify production usage ledger and budget aggregation on isolated CI PostgreSQL.
 * This cannot run with a production database or outside CI.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import pg from "pg";
import { writeUsageEvent, getUserUsageTotals } from "../lib/usage-store.mjs";

const connection = new URL(process.env.DATABASE_URL || "postgres://unconfigured");
if (
  process.env.CI !== "true" ||
  !["127.0.0.1", "localhost"].includes(connection.hostname) ||
  connection.pathname !== "/vector_ci"
) {
  throw new Error("Usage attribution test requires isolated CI PostgreSQL.");
}

test("usage events belong to the correct user and budgets stay isolated", async () => {
  const db = new pg.Pool({ connectionString: process.env.DATABASE_URL, max: 2 });
  const userA = "fixture-usage-a", userB = "fixture-usage-b";
  const insert = (userId, costChf) => writeUsageEvent(db, {
    provider: "ci-usage-test", model: "offline-fixture",
    userId, inputTokens: 14, outputTokens: 2, cachedTokens: 3, costChf,
  });

  try {
    const first = await insert(userA, 0.4);
    const second = await insert(userA, 0.65);
    const other = await insert(userB, 4.25);
    const unattributed = await insert(null, 9);
    const omitted = await writeUsageEvent(db, {
      provider: "ci-usage-test", model: "offline-fixture",
      inputTokens: 0, outputTokens: 0, cachedTokens: 0, costChf: 0,
    });

    const rows = await db.query(
      "SELECT id, user_id, input_tokens, output_tokens, cached_tokens FROM usage_events WHERE id = ANY($1::text[])",
      [[first, second, other, unattributed, omitted]]
    );
    assert.equal(rows.rowCount, 5);
    const stored = Object.fromEntries(rows.rows.map(row => [row.id, row]));
    assert.equal(stored[first].user_id, userA);
    assert.equal(stored[first].input_tokens, "14");
    assert.equal(stored[first].output_tokens, "2");
    assert.equal(stored[first].cached_tokens, "3");
    assert.equal(stored[second].user_id, userA);
    assert.equal(stored[other].user_id, userB);
    assert.equal(stored[unattributed].user_id, null);
    assert.equal(stored[omitted].user_id, null);

    const a = await getUserUsageTotals(db, userA);
    const b = await getUserUsageTotals(db, userB);
    const empty = await getUserUsageTotals(db, "fixture-unrelated");
    assert.ok(Math.abs(a.total - 1.05) < 0.000001);
    assert.ok(Math.abs(a.month - 1.05) < 0.000001);
    assert.equal(b.total, 4.25);
    assert.deepEqual(empty, { total: 0, month: 0 });

    const bill = {eventId:'fixture-idempotent-provider-call', provider:'ci-usage-test', model:'offline-fixture',
      userId:userA,inputTokens:10,outputTokens:3,cachedTokens:2,costChf:0.1,
      metadata:{kind:'provider-call',jobId:'fixture-job',costStatus:'estimated',costUsd:0.125,usdToChfRate:0.8}};
    await writeUsageEvent(db,bill);
    await writeUsageEvent(db,bill);
    const billed=await db.query('SELECT COUNT(*)::int AS count, MAX(metadata::text)::jsonb AS metadata FROM usage_events WHERE id=$1',[bill.eventId]);
    assert.equal(billed.rows[0].count,1);
    assert.equal(billed.rows[0].metadata.kind,'provider-call');
    assert.ok(Math.abs((await getUserUsageTotals(db,userA)).total-1.15)<0.000001);

    const dashboardSource=readFileSync(new URL('../app/page.js',import.meta.url),'utf8');
    const queries=[...dashboardSource.matchAll(/scopedQuery\(`([\s\S]*?)`\)/g)].map(match=>match[1]);
    assert.equal(queries.length,3);
    const [summary,models,days]=await Promise.all(queries.map(sql=>db.query(sql,[false,userA])));
    const timelineSpend=days.rows.reduce((sum,row)=>sum+Number(row.spend_chf),0);
    assert.ok(Math.abs(Number(summary.rows[0].spend_chf)-timelineSpend)<0.000001);
    assert.ok(Math.abs(Number(summary.rows[0].spend_chf)-models.rows.reduce((sum,row)=>sum+Number(row.spend_chf),0))<0.000001);
    assert.equal(summary.rows[0].provider_calls,1);
    assert.equal(summary.rows[0].legacy_entries,2);

    const usageSource = readFileSync(new URL("../lib/usage.js", import.meta.url), "utf8");
    assert.match(usageSource, /userId\s*=\s*null/);
    assert.match(usageSource, /writeUsageEvent\(db,/);

    const worker = readFileSync(new URL("../lib/background-executor.js", import.meta.url), "utf8");
    assert.match(worker,/withProviderUsageScope/);
    assert.match(worker,/await recordUsage\(event\)/);
    assert.match(worker,/if \(!usageScope.events.length\) await recordUsage/);
  } finally {
    await db.end();
  }
});

