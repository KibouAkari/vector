import { writeUsageEvent } from "./usage-store.mjs";

import {
  db,
  initializeDatabase
} from "./db";

export async function recordUsage({
  provider,
  model,
  taskId = null,
  userId = null,
  inputTokens,
  outputTokens,
  cachedTokens,
  costChf,
  eventId = null,
  metadata = {}
}) {
  await initializeDatabase();

  return writeUsageEvent(db, {
    provider, model, taskId, userId,
    inputTokens, outputTokens, cachedTokens, costChf,
    eventId, metadata,
  });
}

