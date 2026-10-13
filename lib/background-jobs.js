import crypto from "node:crypto";

import {
  db,
  initializeDatabase
} from "./db";


export async function initializeBackgroundJobs() {
  await initializeDatabase();

  await db.query(`
    CREATE TABLE IF NOT EXISTS agent_jobs (
      id TEXT PRIMARY KEY,
      user_id TEXT,
      conversation_id TEXT,
      project_id TEXT,
      user_message_id TEXT,
      assistant_message_id TEXT,
      request_hash TEXT,
      status TEXT NOT NULL DEFAULT 'queued',
      progress JSONB NOT NULL DEFAULT '{}'::jsonb,
      payload JSONB NOT NULL,
      result JSONB,
      error TEXT,
      attempts INTEGER NOT NULL DEFAULT 0,
      worker_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      completed_at TIMESTAMPTZ,
      heartbeat_at TIMESTAMPTZ,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_agent_jobs_status_created
    ON agent_jobs (status, created_at)
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_agent_jobs_conversation
    ON agent_jobs (conversation_id, created_at DESC)
  `);
}


export function makeRequestHash({
  userId,
  conversationId,
  message
}) {
  return crypto
    .createHash("sha256")
    .update(
      `${userId || ""}\n${conversationId || ""}\n${message || ""}`
    )
    .digest("hex");
}


export async function findRecentDuplicate({
  userId,
  conversationId,
  requestHash
}) {
  await initializeBackgroundJobs();

  const result =
    await db.query(
      `
        SELECT *
        FROM agent_jobs
        WHERE
          user_id = $1
          AND conversation_id = $2
          AND request_hash = $3
          AND (
            (
              status IN ('queued', 'running')
              AND created_at > NOW() - INTERVAL '45 minutes'
            )
            OR
            (
              status = 'completed'
              AND created_at > NOW() - INTERVAL '20 seconds'
            )
          )
        ORDER BY created_at DESC
        LIMIT 1
      `,
      [
        userId,
        conversationId,
        requestHash
      ]
    );

  return result.rows[0] || null;
}


export async function enqueueAgentJob({
  userId,
  conversationId,
  projectId = null,
  userMessageId,
  requestHash,
  payload
}) {
  await initializeBackgroundJobs();

  const id = crypto.randomUUID();

  await db.query(
    `
      INSERT INTO agent_jobs (
        id,
        user_id,
        conversation_id,
        project_id,
        user_message_id,
        request_hash,
        status,
        payload,
        progress
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        'queued',
        $7::jsonb,
        '{"stage":"queued","message":"Waiting for Vector worker"}'::jsonb
      )
    `,
    [
      id,
      userId,
      conversationId,
      projectId,
      userMessageId,
      requestHash,
      JSON.stringify(payload)
    ]
  );

  return id;
}


export async function getAgentJob(id) {
  await initializeBackgroundJobs();

  const result =
    await db.query(
      `
        SELECT *
        FROM agent_jobs
        WHERE id = $1
        LIMIT 1
      `,
      [id]
    );

  return result.rows[0] || null;
}


export async function waitForAgentJob(
  id,
  timeoutMs = 15 * 60 * 1000
) {
  const started = Date.now();

  while (
    Date.now() - started < timeoutMs
  ) {
    const job =
      await getAgentJob(id);

    if (!job) {
      throw new Error(
        "Background job disappeared."
      );
    }

    if (
      [
        "completed",
        "failed",
        "cancelled"
      ].includes(job.status)
    ) {
      return job;
    }

    await new Promise(
      (resolve) =>
        setTimeout(resolve, 650)
    );
  }

  return await getAgentJob(id);
}


export async function claimNextAgentJob(
  workerId
) {
  await initializeBackgroundJobs();

  /*
   * If an app/worker restart interrupted execution,
   * allow a stale job to be picked up again.
   */
  await db.query(`
    UPDATE agent_jobs
    SET
      status = 'queued',
      worker_id = NULL,
      started_at = NULL,
      heartbeat_at = NULL,
      updated_at = NOW(),
      progress = '{"stage":"queued","message":"Recovered after interruption"}'::jsonb
    WHERE
      status = 'running'
      AND COALESCE(
        heartbeat_at,
        started_at,
        updated_at
      ) < NOW() - INTERVAL '10 minutes'
  `);

  const client =
    await db.connect();

  try {
    await client.query("BEGIN");

    const found =
      await client.query(`
        SELECT *
        FROM agent_jobs
        WHERE status = 'queued'
        ORDER BY created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
      `);

    if (
      found.rowCount === 0
    ) {
      await client.query("COMMIT");
      return null;
    }

    const job = found.rows[0];

    await client.query(
      `
        UPDATE agent_jobs
        SET
          status = 'running',
          worker_id = $2,
          attempts = attempts + 1,
          started_at = COALESCE(started_at, NOW()),
          heartbeat_at = NOW(),
          updated_at = NOW(),
          progress = '{"stage":"running","message":"Vector is working"}'::jsonb
        WHERE id = $1
      `,
      [
        job.id,
        workerId
      ]
    );

    await client.query("COMMIT");

    return {
      ...job,
      status: "running",
      worker_id: workerId
    };

  } catch (error) {
    await client.query("ROLLBACK");
    throw error;

  } finally {
    client.release();
  }
}


export async function heartbeatAgentJob({
  id,
  progress = null
}) {
  await initializeBackgroundJobs();

  await db.query(
    `
      UPDATE agent_jobs
      SET
        heartbeat_at = NOW(),
        updated_at = NOW(),
        progress = COALESCE(
          $2::jsonb,
          progress
        )
      WHERE
        id = $1
        AND status = 'running'
    `,
    [
      id,
      progress
        ? JSON.stringify(progress)
        : null
    ]
  );
}


export async function completeAgentJob({
  id,
  assistantMessageId,
  result
}) {
  /*
   * VECTOR_COMPLETE_GUARD_566
   */
  if (
    !assistantMessageId ||
    !String(
      result?.text ||
      ""
    ).trim()
  ) {
    throw new Error(
      "Cannot complete an AI job without a persisted assistant response."
    );
  }

  await initializeBackgroundJobs();

  await db.query(
    `
      UPDATE agent_jobs
      SET
        status = 'completed',
        assistant_message_id = $2,
        result = $3::jsonb,
        progress = '{"stage":"completed","message":"Done"}'::jsonb,
        completed_at = NOW(),
        heartbeat_at = NOW(),
        updated_at = NOW()
      WHERE id = $1
        AND status = 'running'
    `,
    [
      id,
      assistantMessageId,
      JSON.stringify(result)
    ]
  );
}


export async function failAgentJob({
  id,
  error
}) {
  await initializeBackgroundJobs();

  const message =
    String(
      error?.message ||
      error ||
      "Unknown error"
    ).slice(0, 12000);

  await db.query(
    `
      UPDATE agent_jobs
      SET
        status = 'failed',
        error = $2,
        progress = '{"stage":"failed","message":"Vector could not complete the task"}'::jsonb,
        completed_at = NOW(),
        heartbeat_at = NOW(),
        updated_at = NOW()
      WHERE id = $1
    `,
    [
      id,
      message
    ]
  );
}



/*
 * VECTOR_SAME_JOB_RETRY_57710
 *
 * Retry a failed job in-place.
 *
 * Important:
 *   - job ID stays the same
 *   - user_message_id stays the same
 *   - payload stays the same
 *   - request_hash stays the same
 *   - attempts is NOT reset
 *
 * Therefore retrying does not create another user message.
 */
export async function retryAgentJob({
  id,
  userId
}) {
  await initializeBackgroundJobs();

  const result =
    await db.query(
      `
        UPDATE agent_jobs
        SET
          status = 'queued',
          progress = '{"stage":"queued","message":"Retrying previous request"}'::jsonb,
          result = NULL,
          error = NULL,
          assistant_message_id = NULL,
          worker_id = NULL,
          started_at = NULL,
          completed_at = NULL,
          heartbeat_at = NULL,
          updated_at = NOW()
        WHERE
          id = $1
          AND user_id = $2
          AND status = 'failed'
        RETURNING *
      `,
      [
        id,
        userId
      ]
    );

  return (
    result.rows[0] ||
    null
  );
}


export async function cancelAgentJob({
  id,
  userId
}) {
  await initializeBackgroundJobs();

  const result =
    await db.query(
      `
        UPDATE agent_jobs
        SET
          status = 'cancelled',
          progress = '{"stage":"cancelled","message":"Cancelled"}'::jsonb,
          completed_at = NOW(),
          updated_at = NOW()
        WHERE
          id = $1
          AND user_id = $2
          AND status IN ('queued', 'running')
        RETURNING id
      `,
      [
        id,
        userId
      ]
    );

  return result.rowCount > 0;
}
