import crypto from "node:crypto";
import { db, initializeDatabase } from "./db";
import { freeInferenceEligible } from "./free-inference-policy.mjs";
let initialized;
export function initializeBudgets() {
  if (!initialized)
    initialized = (async () => {
      await initializeDatabase();
      await db.query(`CREATE TABLE IF NOT EXISTS budget_limits (
 scope TEXT PRIMARY KEY,currency TEXT NOT NULL CHECK(currency IN ('CHF','USD')),monthly_hard NUMERIC NOT NULL CHECK(monthly_hard>=0),monthly_warning NUMERIC NOT NULL CHECK(monthly_warning>=0),updated_by TEXT NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)`);
      await db.query(`CREATE TABLE IF NOT EXISTS budget_call_reservations (
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL,project_id TEXT,reserved_chf NUMERIC NOT NULL,reserved_usd NUMERIC NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','released','uncertain')),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),settled_at TIMESTAMPTZ
)`);
      await db.query(
        "CREATE INDEX IF NOT EXISTS idx_budget_reservations_active ON budget_call_reservations(status,created_at)",
      );
    })().catch((error) => {
      initialized = undefined;
      throw error;
    });
  return initialized;
}
const price = (value) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
export function reserveQuote(runtime, payload) {
  if (freeInferenceEligible(runtime.provider, runtime.model, runtime.apiBase))
    return { usd: 0, chf: 0 };
  const pricing = runtime.pricing || {},
    input = price(pricing.inputPerMillionUsd),
    output = price(pricing.outputPerMillionUsd),
    fee = price(pricing.requestFeeUsd) || 0;
  if (
    input === null ||
    output === null ||
    (input === 0 && output === 0 && fee === 0)
  )
    throw Object.assign(
      Error(
        "No trustworthy price is configured for this model. Configure rates before using a hard budget.",
      ),
      { code: "BUDGET_PRICE_UNKNOWN" },
    );
  const maxOutput = Number(payload.max_output_tokens);
  if (!Number.isSafeInteger(maxOutput) || maxOutput < 1 || maxOutput > 200000)
    throw Error("INVALID_OUTPUT_BUDGET");
  // Conservative text-token envelope, separate from actual usage. Includes
  // tool schemas/protocol margin; images/opaque attachments can over-reserve.
  const inputBound = Buffer.byteLength(JSON.stringify(payload), "utf8") + 8192;
  const inputRate = Math.max(
    input,
    price(pricing.cachedInputPerMillionUsd) || 0,
    price(pricing.cacheWriteInputPerMillionUsd) || 0,
  );
  const usd =
    (inputBound / 1e6) * inputRate +
    (maxOutput / 1e6) * output +
    fee +
    (payload.tools?.some((t) => String(t.type).startsWith("web_search"))
      ? 0.1
      : 0);
  const fx = Number(process.env.USD_TO_CHF_RATE || 0.85);
  if (!Number.isFinite(fx) || fx <= 0) throw Error("INVALID_EXCHANGE_RATE");
  return { usd, chf: usd * fx };
}
export async function reserveProviderBudget(runtime, payload) {
  if (!runtime.requestingUserId) return null;
  await initializeBudgets();
  const quote = reserveQuote(runtime, payload);
  const client = await db.connect();
  const id = crypto.randomUUID(),
    userId = runtime.requestingUserId,
    projectId = runtime.projectId || null;
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-provider-budget'))",
    );
    const user = (
      await client.query(
        "SELECT enabled,role,monthly_budget_chf,total_budget_chf FROM vector_users WHERE id=$1 FOR UPDATE",
        [userId],
      )
    ).rows[0];
    if (!user?.enabled || user.role === "readonly")
      throw Error("EXECUTION_FORBIDDEN");
    const limits = (
      await client.query(
        "SELECT * FROM budget_limits WHERE scope=ANY($1::text[])",
        [
          [
            "workspace",
            "user:" + userId,
            ...(projectId ? ["project:" + projectId] : []),
          ],
        ],
      )
    ).rows;
    const sum = async (scope, since, currency = "CHF") => {
      const field =
        currency === "USD"
          ? "COALESCE((metadata->>'costUsd')::numeric,cost_chf/" +
            Number(process.env.USD_TO_CHF_RATE || 0.85) +
            ")"
          : "cost_chf";
      const held = currency === "USD" ? "reserved_usd" : "reserved_chf";
      let clause = "",
        reservationClause = "",
        args = [];
      if (scope.startsWith("user:")) {
        args = [scope.slice(5)];
        clause = " AND user_id=$1";
        reservationClause = clause;
      }
      if (scope.startsWith("project:")) {
        args = [scope.slice(8)];
        clause = " AND metadata->>'projectId'=$1";
        reservationClause = " AND project_id=$1";
      }
      const filter = since
        ? " AND created_at>=DATE_TRUNC('" + since + "',NOW())"
        : "";
      const spent = (
        await client.query(
          `SELECT COALESCE(SUM(${field}),0)::numeric AS n FROM usage_events WHERE TRUE${clause}${filter}`,
          args,
        )
      ).rows[0].n;
      // Pending/uncertain calls survive period boundaries until accounted for.
      const pending = (
        await client.query(
          `SELECT COALESCE(SUM(${held}),0)::numeric AS n FROM budget_call_reservations WHERE status IN ('pending','uncertain')${reservationClause}`,
          args,
        )
      ).rows[0].n;
      return Number(spent) + Number(pending);
    };
    const number = (name, fallback) => {
      const value = process.env[name];
      return value === undefined ? fallback : Number(value);
    };
    for (const [period, limit] of [
      ["day", number("DAILY_HARD_LIMIT_CHF", 5)],
      ["month", number("MONTHLY_HARD_LIMIT_CHF", 25)],
    ])
      if (
        !Number.isFinite(limit) ||
        limit < 0 ||
        (await sum("workspace", period)) + quote.chf > limit
      )
        throw Object.assign(Error("Workspace " + period + " budget reached."), {
          code: "BUDGET_LIMIT",
        });
    for (const row of limits) {
      const requested = row.currency === "USD" ? quote.usd : quote.chf;
      if (
        (await sum(row.scope, "month", row.currency)) + requested >
        Number(row.monthly_hard)
      )
        throw Object.assign(
          Error("Monthly " + row.scope.split(":")[0] + " budget reached."),
          { code: "BUDGET_LIMIT" },
        );
    }
    for (const [period, limit] of [
      ["month", user.monthly_budget_chf],
      [null, user.total_budget_chf],
    ])
      if (
        limit !== null &&
        (await sum("user:" + userId, period)) + quote.chf > Number(limit)
      )
        throw Object.assign(Error("Account budget reached."), {
          code: "BUDGET_LIMIT",
        });
    await client.query(
      "INSERT INTO budget_call_reservations(id,user_id,project_id,reserved_chf,reserved_usd,status) VALUES ($1,$2,$3,$4,$5,'pending')",
      [id, userId, projectId, quote.chf, quote.usd],
    );
    await client.query("COMMIT");
    return { id };
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
export async function settleProviderBudget(ticket, accounted) {
  if (!ticket) return;
  await db.query(
    "UPDATE budget_call_reservations SET status=$2,settled_at=NOW() WHERE id=$1 AND status='pending'",
    [ticket.id, accounted ? "released" : "uncertain"],
  );
}
export async function listBudgets(session) {
  await initializeBudgets();
  const owner = session.role === "owner";
  const args = owner ? [] : [session.userId];
  const limits = (
    await db.query(
      "SELECT * FROM budget_limits" +
        (owner ? "" : " WHERE scope='user:'||$1 OR scope='workspace'") +
        " ORDER BY scope",
      args,
    )
  ).rows;
  const rows = (
    await db.query(
      `SELECT id,user_id,project_id,reserved_chf,reserved_usd,status,created_at FROM budget_call_reservations WHERE status IN ('pending','uncertain')${owner ? "" : " AND user_id=$1"} ORDER BY created_at DESC LIMIT 100`,
      args,
    )
  ).rows;
  for (const limit of limits) {
    if (!owner && limit.scope === "workspace") continue;
    let filter = "",
      args = [];
    if (limit.scope.startsWith("user:")) {
      filter = " AND user_id=$1";
      args = [limit.scope.slice(5)];
    } else if (limit.scope.startsWith("project:")) {
      filter = " AND metadata->>'projectId'=$1";
      args = [limit.scope.slice(8)];
    }
    const field =
      limit.currency === "USD"
        ? "COALESCE((metadata->>'costUsd')::numeric,cost_chf/" +
          Number(process.env.USD_TO_CHF_RATE || 0.85) +
          ")"
        : "cost_chf";
    limit.spent = Number(
      (
        await db.query(
          `SELECT COALESCE(SUM(${field}),0) AS n FROM usage_events WHERE created_at>=DATE_TRUNC('month',NOW())${filter}`,
          args,
        )
      ).rows[0].n,
    );
    const held = limit.currency === "USD" ? "reserved_usd" : "reserved_chf";
    const heldFilter = limit.scope.startsWith("project:")
      ? " AND project_id=$1"
      : filter;
    limit.held = Number(
      (
        await db.query(
          `SELECT COALESCE(SUM(${held}),0) AS n FROM budget_call_reservations WHERE status IN ('pending','uncertain')${heldFilter}`,
          args,
        )
      ).rows[0].n,
    );
    limit.warningReached =
      limit.spent + limit.held >= Number(limit.monthly_warning);
  }
  return {
    limits,
    reservations: rows,
    canManage: owner,
    environmentCeilings: {
      dailyChf: Number(process.env.DAILY_HARD_LIMIT_CHF || 5),
      monthlyChf: Number(process.env.MONTHLY_HARD_LIMIT_CHF || 25),
    },
  };
}
export async function saveBudget(session, input) {
  if (session.role !== "owner") throw Error("FORBIDDEN");
  await initializeBudgets();
  if (
    !["CHF", "USD"].includes(input.currency) ||
    typeof input.scope !== "string" ||
    !/^(workspace|user:[a-f0-9-]{36}|project:[a-f0-9-]{36})$/i.test(input.scope)
  )
    throw Error("INVALID_BUDGET");
  const hard = Number(input.monthlyHard),
    warning = Number(input.monthlyWarning);
  if (
    input.monthlyHard === "" ||
    input.monthlyWarning === "" ||
    !Number.isFinite(hard) ||
    !Number.isFinite(warning) ||
    hard < 0 ||
    hard > 100000 ||
    warning < 0 ||
    warning > hard
  )
    throw Error("INVALID_BUDGET");
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-provider-budget'))",
    );
    if (input.scope !== "workspace") {
      const [kind, id] = input.scope.split(":");
      if (
        !(
          await client.query(
            kind === "user"
              ? "SELECT id FROM vector_users WHERE id=$1"
              : "SELECT id FROM projects WHERE id=$1",
            [id],
          )
        ).rowCount
      )
        throw Error("INVALID_BUDGET_SCOPE");
    }
    await client.query(
      "INSERT INTO budget_limits(scope,currency,monthly_hard,monthly_warning,updated_by) VALUES ($1,$2,$3,$4,$5) ON CONFLICT(scope) DO UPDATE SET currency=$2,monthly_hard=$3,monthly_warning=$4,updated_by=$5,updated_at=NOW()",
      [input.scope, input.currency, hard, warning, session.userId],
    );
    await client.query(
      "INSERT INTO audit_log(id,actor,action,resource,details,source) VALUES ($1,$2,'budget.updated',$3,$4,'web')",
      [
        crypto.randomUUID(),
        session.username,
        input.scope,
        JSON.stringify({ currency: input.currency, hard, warning }),
      ],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
