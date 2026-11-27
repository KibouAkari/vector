import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import crypto from "node:crypto";
import { freeInferenceEligible } from "../lib/free-inference-policy.mjs";
const source = readFileSync(
  new URL("../lib/provider-budgets.js", import.meta.url),
  "utf8",
)
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
  .replace(/^export\s+/gm, "");
const { reserveQuote } = new Function(
  "crypto",
  "db",
  "initializeDatabase",
  "freeInferenceEligible",
  source + "\nreturn {reserveQuote};",
)(crypto, {}, async () => {}, freeInferenceEligible);
test("budget reservation is separate from actual usage and rejects unpriced calls", () => {
  process.env.USD_TO_CHF_RATE = "0.85";
  const runtime = {
    provider: "openai",
    pricing: { inputPerMillionUsd: 2, outputPerMillionUsd: 10 },
  };
  const quote = reserveQuote(runtime, {
    input: [{ role: "user", content: "Fixture" }],
    max_output_tokens: 100,
  });
  assert.ok(quote.usd > 0);
  assert.equal(quote.chf, quote.usd * 0.85);
  const larger = reserveQuote(runtime, {
    input: [{ role: "user", content: "Fixture".repeat(100) }],
    max_output_tokens: 100,
  });
  assert.ok(larger.usd > quote.usd);
  assert.throws(
    () => reserveQuote({ ...runtime, pricing: {} }, { max_output_tokens: 100 }),
    { code: "BUDGET_PRICE_UNKNOWN" },
  );
  assert.throws(() => reserveQuote(runtime, { max_output_tokens: -1 }));
  assert.deepEqual(
    reserveQuote(
      {
        provider: "openrouter",
        model: "fixture/model:free",
        apiBase: "https://openrouter.ai/api/v1",
      },
      {},
    ),
    { usd: 0, chf: 0 },
  );
});
test("failed and incomplete calls retain uncertain reservations rather than freeing capacity", async () => {
  const changes = [];
  const { settleProviderBudget } = new Function(
    "crypto",
    "db",
    "initializeDatabase",
    "freeInferenceEligible",
    source + "\nreturn {settleProviderBudget};",
  )(
    crypto,
    { query: async (_sql, args) => changes.push(args) },
    async () => {},
    freeInferenceEligible,
  );
  await settleProviderBudget({ id: "failed" }, false);
  await settleProviderBudget({ id: "accounted" }, true);
  assert.deepEqual(changes, [
    ["failed", "uncertain"],
    ["accounted", "released"],
  ]);
});
