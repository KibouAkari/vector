import {
  db,
  initializeDatabase
} from "./db";

function numberEnv(name, fallback) {
  const value =
    Number(process.env[name]);

  return Number.isFinite(value)
    ? value
    : fallback;
}

export function getCostLimits() {
  return {
    quickTask:
      numberEnv(
        "DEFAULT_QUICK_TASK_BUDGET_CHF",
        0.03
      ),

    normalTask:
      numberEnv(
        "DEFAULT_NORMAL_TASK_BUDGET_CHF",
        0.10
      ),

    deepTask:
      numberEnv(
        "DEFAULT_DEEP_TASK_BUDGET_CHF",
        0.40
      ),

    maxTask:
      numberEnv(
        "DEFAULT_MAX_TASK_BUDGET_CHF",
        1.00
      ),

    dailySoft:
      numberEnv(
        "DAILY_SOFT_LIMIT_CHF",
        3
      ),

    dailyHard:
      numberEnv(
        "DAILY_HARD_LIMIT_CHF",
        5
      ),

    monthlySoft:
      numberEnv(
        "MONTHLY_SOFT_LIMIT_CHF",
        20
      ),

    monthlyHard:
      numberEnv(
        "MONTHLY_HARD_LIMIT_CHF",
        25
      )
  };
}

export async function getCurrentUsage() {
  await initializeDatabase();

  const daily =
    await db.query(`
      SELECT
        COALESCE(
          SUM(cost_chf),
          0
        )::numeric AS total
      FROM usage_events
      WHERE created_at >=
        DATE_TRUNC(
          'day',
          NOW()
        )
    `);

  const monthly =
    await db.query(`
      SELECT
        COALESCE(
          SUM(cost_chf),
          0
        )::numeric AS total
      FROM usage_events
      WHERE created_at >=
        DATE_TRUNC(
          'month',
          NOW()
        )
    `);

  return {
    daily:
      Number(daily.rows[0].total),

    monthly:
      Number(monthly.rows[0].total)
  };
}

export async function checkCost({
  estimatedCost,
  taskBudget,
  taskSpent = 0
}) {
  const limits =
    getCostLimits();

  const usage =
    await getCurrentUsage();

  const estimated =
    Number(estimatedCost || 0);

  const budget =
    Number(taskBudget || limits.normalTask);

  if (
    taskSpent + estimated >
    budget
  ) {
    return {
      allowed: false,
      reason: "TASK_BUDGET_EXCEEDED",
      usage,
      limits
    };
  }

  if (
    usage.daily + estimated >
    limits.dailyHard
  ) {
    return {
      allowed: false,
      reason: "DAILY_HARD_LIMIT",
      usage,
      limits
    };
  }

  if (
    usage.monthly + estimated >
    limits.monthlyHard
  ) {
    return {
      allowed: false,
      reason: "MONTHLY_HARD_LIMIT",
      usage,
      limits
    };
  }

  return {
    allowed: true,
    reason: null,
    usage,
    limits
  };
}
