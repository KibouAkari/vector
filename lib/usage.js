import crypto from "crypto";

import {
  db,
  initializeDatabase
} from "./db";

export async function recordUsage({
  provider,
  model,
  taskId = null,
  inputTokens,
  outputTokens,
  cachedTokens,
  costChf
}) {
  await initializeDatabase();

  await db.query(
    `
      INSERT INTO usage_events (
        id,
        provider,
        model,
        task_id,
        input_tokens,
        output_tokens,
        cached_tokens,
        cost_chf
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        $7,
        $8
      )
    `,
    [
      crypto.randomUUID(),
      provider,
      model,
      taskId,
      Number(inputTokens || 0),
      Number(outputTokens || 0),
      Number(cachedTokens || 0),
      Number(costChf || 0)
    ]
  );
}
