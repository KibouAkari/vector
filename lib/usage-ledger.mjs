const amount = (value) =>
  (typeof value === "number" ||
    (typeof value === "string" && value.trim() !== "")) &&
  Number.isFinite(Number(value)) &&
  Number(value) >= 0
    ? Number(value)
    : null;
const count = (value) => {
  const n = amount(value);
  return n !== null && Number.isSafeInteger(n) ? n : null;
};
export function publicUsageCall(row) {
  const m = row.metadata || {},
    known = m.usageKnown === true;
  const status = [
    "reported",
    "estimated",
    "incomplete",
    "local-no-api",
  ].includes(m.costStatus)
    ? m.costStatus
    : "incomplete";
  return {
    id: row.id,
    createdAt: row.created_at,
    provider: row.provider,
    model: row.model,
    jobId: m.jobId || null,
    projectId: typeof m.projectId === "string" ? m.projectId : null,
    elapsedMs: count(m.elapsedMs),
    inputTokens: known ? count(row.input_tokens) : null,
    outputTokens: known ? count(row.output_tokens) : null,
    cachedTokens:
      known && m.cacheValid !== false ? count(row.cached_tokens) : null,
    cacheWriteTokens: known ? count(m.cacheWriteTokens) : null,
    reasoningTokens: known ? count(m.reasoningTokens) : null,
    costStatus: status,
    reportedCostUsd: status === "reported" ? amount(m.reportedCostUsd) : null,
    estimatedCostUsd:
      status === "estimated" ? amount(m.estimatedCostUsd ?? m.costUsd) : null,
    convertedCostChf: ["reported", "estimated", "local-no-api"].includes(status)
      ? amount(m.costUsd) === null || amount(m.usdToChfRate) === null
        ? null
        : amount(m.costUsd) * amount(m.usdToChfRate)
      : null,
    usdToChfRate: amount(m.usdToChfRate),
    responseStatus:
      typeof m.responseStatus === "string" ? m.responseStatus : "unknown",
  };
}
export async function listUsageCalls(
  db,
  userId,
  { after = null, project = null, model = null } = {},
) {
  if (project !== null && !/^[a-f0-9-]{36}$/i.test(project))
    throw Error("INVALID_FILTER");
  if (
    model !== null &&
    (typeof model !== "string" || !model.trim() || model.length > 200)
  )
    throw Error("INVALID_FILTER");
  if (
    after !== null &&
    (typeof after !== "string" ||
      after.length > 100 ||
      !/^[a-zA-Z0-9_-]+$/.test(after))
  )
    throw Error("INVALID_CURSOR");
  if (
    after &&
    !(
      await db.query(
        "SELECT id FROM usage_events WHERE id=$1 AND user_id=$2 AND metadata->>'kind'='provider-call'",
        [after, userId],
      )
    ).rowCount
  )
    throw Error("INVALID_CURSOR");
  const rows = (
    await db.query(
      `SELECT id,created_at,provider,model,input_tokens,output_tokens,cached_tokens,metadata
    FROM usage_events WHERE user_id=$1 AND metadata->>'kind'='provider-call'
      AND ($2::text IS NULL OR (created_at,id)<(SELECT created_at,id FROM usage_events WHERE id=$2 AND user_id=$1))
      AND ($3::text IS NULL OR metadata->>'projectId'=$3)
      AND ($4::text IS NULL OR model=$4)
    ORDER BY created_at DESC,id DESC LIMIT 51`,
      [userId, after, project, model],
    )
  ).rows;
  return {
    calls: rows.slice(0, 50).map(publicUsageCall),
    nextCursor: rows.length > 50 ? rows[49].id : null,
  };
}
