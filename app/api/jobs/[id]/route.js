import crypto from "node:crypto";

import {
  getSession
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  cancelAgentJob,
  getAgentJob,
  retryAgentJob
} from "../../../../lib/background-jobs";

import {
  restorePrivateValues
} from "../../../../lib/privacy-vault";

export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


async function ensureAssistantMessage({
  job,
  userId
}) {
  /*
   * VECTOR_COMPLETED_JOB_SELF_HEAL_566
   *
   * Strictly scoped to the authenticated owner of this job/conversation.
   * There is deliberately no owner-role bypass.
   */
  if (
    job.status !==
      "completed" ||
    !job.conversation_id ||
    !String(
      job.result?.text ||
      ""
    ).trim()
  ) {
    return (
      job.assistant_message_id ||
      null
    );
  }

  const ownedConversation =
    await db.query(
      `
        SELECT id
        FROM conversations
        WHERE
          id = $1
          AND user_id = $2
        LIMIT 1
      `,
      [
        job.conversation_id,
        userId
      ]
    );

  if (
    ownedConversation.rowCount ===
    0
  ) {
    return null;
  }

  const candidateId =
    job.assistant_message_id ||
    job.result
      ?.assistantMessageId ||
    null;

  if (
    candidateId
  ) {
    const byId =
      await db.query(
        `
          SELECT id
          FROM messages
          WHERE
            id = $1
            AND conversation_id = $2
            AND role = 'assistant'
          LIMIT 1
        `,
        [
          candidateId,
          job.conversation_id
        ]
      );

    if (
      byId.rowCount >
      0
    ) {
      return byId.rows[0].id;
    }
  }

  const matchingMessage =
    await db.query(
      `
        SELECT id
        FROM messages
        WHERE
          conversation_id = $1
          AND role = 'assistant'
          AND content = $2
          AND (
            $3::timestamptz IS NULL
            OR created_at >= $3::timestamptz
          )
        ORDER BY created_at DESC
        LIMIT 1
      `,
      [
        job.conversation_id,
        String(
          job.result.text
        ),
        job.started_at ||
        null
      ]
    );

  let assistantMessageId =
    matchingMessage.rows[0]
      ?.id ||
    null;

  if (
    !assistantMessageId
  ) {
    assistantMessageId =
      crypto.randomUUID();

    await db.query(
      `
        INSERT INTO messages (
          id,
          conversation_id,
          role,
          content,
          model,
          cost_chf
        )
        VALUES (
          $1,
          $2,
          'assistant',
          $3,
          $4,
          $5
        )
      `,
      [
        assistantMessageId,
        job.conversation_id,
        String(
          job.result.text
        ),
        job.result
          ?.meta
          ?.model ||
        null,
        Number(
          job.result
            ?.meta
            ?.costChf ||
          0
        )
      ]
    );

    await db.query(
      `
        UPDATE conversations
        SET updated_at = NOW()
        WHERE
          id = $1
          AND user_id = $2
      `,
      [
        job.conversation_id,
        userId
      ]
    );
  }

  await db.query(
    `
      UPDATE agent_jobs
      SET
        assistant_message_id = $2,
        updated_at = NOW()
      WHERE
        id = $1
        AND user_id = $3
    `,
    [
      job.id,
      assistantMessageId,
      userId
    ]
  );

  return assistantMessageId;
}


export async function GET(
  request,
  context
) {
  const session =
    await getSession();

  if (
    !session
  ) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status:
          401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  const job =
    await getAgentJob(
      id
    );

  if (
    !job ||
    job.user_id !==
      session.userId
  ) {
    return Response.json(
      {
        error:
          "Not found"
      },
      {
        status:
          404
      }
    );
  }

  await ensureAssistantMessage({
    job,
    userId:
      session.userId
  });

  let result =
    job.result ||
    null;

  if (
    result?.text &&
    job.conversation_id
  ) {
    result = {
      ...result,

      text:
        await restorePrivateValues({
          conversationId:
            job.conversation_id,

          text:
            result.text
        })
    };
  }

  return Response.json({
    id:
      job.id,

    status:
      job.status,

    progress:
      job.progress,

    conversationId:
      job.conversation_id,

    projectId:
      job.project_id,

    createdAt:
      job.created_at,

    startedAt:
      job.started_at,

    completedAt:
      job.completed_at,

    attempts:
      job.attempts,

    userMessageId:
      job.user_message_id,

    error:
      job.error,

    result
  });
}



/*
 * VECTOR_FAILED_JOB_RETRY_API_57710
 *
 * Requeue the exact same failed job.
 *
 * No message INSERT occurs here.
 * retryAgentJob() preserves the original user_message_id
 * and payload.
 */
export async function POST(
  request,
  context
) {
  const session =
    await getSession();

  if (
    !session
  ) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status:
          401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  const job =
    await getAgentJob(
      id
    );

  if (
    !job ||
    job.user_id !==
      session.userId
  ) {
    return Response.json(
      {
        error:
          "Not found"
      },
      {
        status:
          404
      }
    );
  }

  if (
    job.status !==
      "failed"
  ) {
    return Response.json(
      {
        error:
          "JOB_NOT_RETRYABLE",

        message:
          "Only failed jobs can be retried.",

        status:
          job.status
      },
      {
        status:
          409
      }
    );
  }

  const retried =
    await retryAgentJob({
      id:
        job.id,

      userId:
        session.userId
    });

  if (
    !retried
  ) {
    return Response.json(
      {
        error:
          "JOB_RETRY_CONFLICT",

        message:
          "The job is no longer in a retryable state."
      },
      {
        status:
          409
      }
    );
  }

  return Response.json(
    {
      ok:
        true,

      sameJob:
        true,

      sameUserMessage:
        true,

      id:
        retried.id,

      conversationId:
        retried.conversation_id,

      projectId:
        retried.project_id,

      status:
        retried.status,

      attempts:
        retried.attempts,

      progress:
        retried.progress
    },
    {
      status:
        202
    }
  );
}


export async function DELETE(
  request,
  context
) {
  const session =
    await getSession();

  if (
    !session
  ) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status:
          401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  const job =
    await getAgentJob(
      id
    );

  if (
    !job ||
    job.user_id !==
      session.userId
  ) {
    return Response.json(
      {
        error:
          "Not found"
      },
      {
        status:
          404
      }
    );
  }

  return Response.json({
    ok:
      await cancelAgentJob({
        id,
        userId:
          session.userId
      })
  });
}
