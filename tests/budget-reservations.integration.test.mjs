/** Actual PostgreSQL serialization; no provider, scanner, live DB or paid call. */
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { readFileSync } from "node:fs";
import pg from "pg";
import { freeInferenceEligible } from "../lib/free-inference-policy.mjs";
const url = new URL(process.env.DATABASE_URL || "postgres://missing");
if (
  process.env.CI !== "true" ||
  !["localhost", "127.0.0.1"].includes(url.hostname) ||
  url.pathname !== "/vector_ci"
)
  throw Error("Isolated CI PostgreSQL required");
test("parallel calls serialize reservations and uncertain usage retains the shared budget", async () => {
  const db = new pg.Pool({
    connectionString: process.env.DATABASE_URL,
    max: 3,
  });
  const userId = crypto.randomUUID();
  process.env.USD_TO_CHF_RATE = "1";
  const source = readFileSync(
    new URL("../lib/provider-budgets.js", import.meta.url),
    "utf8",
  )
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
    .replace(/^export\s+/gm, "");
  const api = new Function(
    "crypto",
    "db",
    "initializeDatabase",
    "freeInferenceEligible",
    source +
      "\nreturn {initializeBudgets,reserveProviderBudget,settleProviderBudget};",
  )(crypto, db, async () => {}, freeInferenceEligible);
  try {
    await api.initializeBudgets();
    await db.query(
      "INSERT INTO vector_users(id,username,password_salt,password_hash,role,enabled,monthly_budget_chf) VALUES ($1,$2,'fixture','fixture','member',TRUE,0.75)",
      [userId, "budget_fixture_" + userId],
    );
    process.env.DAILY_HARD_LIMIT_CHF = "100000";
    process.env.MONTHLY_HARD_LIMIT_CHF = "100000";
    const runtime = {
      requestingUserId: userId,
      provider: "openai",
      model: "fixture",
      pricing: { inputPerMillionUsd: 60, outputPerMillionUsd: 100 },
    };
    const payload = {
      input: [{ role: "user", content: "Fixture" }],
      max_output_tokens: 1000,
    };
    const attempts = await Promise.allSettled([
      api.reserveProviderBudget(runtime, payload),
      api.reserveProviderBudget(runtime, payload),
    ]);
    assert.equal(attempts.filter((r) => r.status === "fulfilled").length, 1);
    assert.equal(attempts.filter((r) => r.status === "rejected").length, 1);
    const ticket = attempts.find((r) => r.status === "fulfilled").value;
    await api.settleProviderBudget(ticket, false);
    await assert.rejects(api.reserveProviderBudget(runtime, payload), {
      code: "BUDGET_LIMIT",
    });
    const stored = await db.query(
      "SELECT status,reserved_chf FROM budget_call_reservations WHERE id=$1",
      [ticket.id],
    );
    assert.equal(stored.rows[0].status, "uncertain");
    assert.ok(Number(stored.rows[0].reserved_chf) > 0.5);
  } finally {
    await db.query("DELETE FROM budget_call_reservations WHERE user_id=$1", [
      userId,
    ]);
    await db.query("DELETE FROM vector_users WHERE id=$1", [userId]);
    await db.end();
  }
});
