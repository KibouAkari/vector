import {
  getSession
} from "../../../lib/auth";

import {
  db
} from "../../../lib/db";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


export async function GET(
  request
) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  const url =
    new URL(
      request.url
    );

  const conversationId =
    url.searchParams.get(
      "conversationId"
    );

  const projectId =
    url.searchParams.get(
      "projectId"
    );

  const activeOnly =
    url.searchParams.get(
      "active"
    ) ===
    "1";

  const params = [
    session.userId
  ];

  const where = [
    "user_id = $1"
  ];

  if (
    conversationId
  ) {
    params.push(
      conversationId
    );

    where.push(
      `conversation_id = $${params.length}`
    );
  }

  if (
    projectId
  ) {
    params.push(
      projectId
    );

    where.push(
      `project_id = $${params.length}`
    );
  }

  if (
    activeOnly
  ) {
    where.push(
      "status IN ('queued','running')"
    );
  }

  const result =
    await db.query(
      `
        SELECT
          id,
          conversation_id,
          project_id,
          status,
          progress,
          created_at,
          started_at,
          completed_at,
          error

        FROM agent_jobs

        WHERE
          ${where.join(
            " AND "
          )}

        ORDER BY
          created_at DESC

        LIMIT 20
      `,
      params
    );

  return Response.json({
    jobs:
      result.rows.map(
        (
          row
        ) => ({
          id:
            row.id,
          conversationId:
            row.conversation_id,
          projectId:
            row.project_id,
          status:
            row.status,
          progress:
            row.progress,
          createdAt:
            row.created_at,
          startedAt:
            row.started_at,
          completedAt:
            row.completed_at,
          error:
            row.error
        })
      )
  });
}
