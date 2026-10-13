import crypto from "node:crypto";

/** Persist the billable provider call with its actual user ownership. */
export async function writeUsageEvent(db, {
  provider, model, taskId = null, userId = null,
  inputTokens, outputTokens, cachedTokens, costChf,
}) {
  const id = crypto.randomUUID();
  await db.query(`
    INSERT INTO usage_events (
      id, provider, model, task_id, user_id,
      input_tokens, output_tokens, cached_tokens, cost_chf
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
  `, [
    id, provider, model, taskId, userId ?? null,
    Number(inputTokens || 0),
    Number(outputTokens || 0),
    Number(cachedTokens || 0),
    Number(costChf || 0),
  ]);
  return id;
}

/** Totals for the user budget; other users and unattributed usage stay excluded. */
export async function getUserUsageTotals(db, userId) {
  const result = await db.query(`
    SELECT
      COALESCE(SUM(cost_chf), 0)::numeric AS total_spent,
      COALESCE(SUM(cost_chf) FILTER (
        WHERE created_at >= DATE_TRUNC('month', NOW())
      ), 0)::numeric AS monthly_spent
    FROM usage_events WHERE user_id = $1
  `, [userId]);
  return {
    total: Number(result.rows[0]?.total_spent || 0),
    month: Number(result.rows[0]?.monthly_spent || 0),
  };
}
