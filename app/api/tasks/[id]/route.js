import {
  getSession
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  writeAudit
} from "../../../../lib/audit";

export const runtime =
  "nodejs";

const STATUSES =
  new Set([
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled"
  ]);

export async function PATCH(
  request,
  context
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
        status:
          401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  const body =
    await request.json();

  const status =
    String(
      body.status ||
      ""
    );

  if (
    !STATUSES.has(
      status
    )
  ) {
    return Response.json(
      {
        error:
          "Invalid status."
      },
      {
        status:
          400
      }
    );
  }

  const result =
    await db.query(
      `
        UPDATE tasks

        SET
          status = $2,
          updated_at = NOW()

        WHERE id = $1

        RETURNING *
      `,
      [
        id,
        status
      ]
    );

  if (
    result.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Task not found."
      },
      {
        status:
          404
      }
    );
  }

  await writeAudit({
    actor:
      session.username,

    action:
      "task.status.changed",

    resource:
      id,

    details: {
      projectId:
        result.rows[0]
          .project_id,

      status
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true
  });
}
