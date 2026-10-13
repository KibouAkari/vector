import { canEditProject } from "../../../../lib/identity";
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


  const taskProject = await db.query(
    "SELECT project_id FROM tasks WHERE id = $1 LIMIT 1", [id]
  );
  if (
    taskProject.rowCount !== 1 ||
    !await canEditProject(session, taskProject.rows[0].project_id)
  ) {
    return Response.json({ error: "Task not found." }, { status: 404 });
  }

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
          AND project_id = $3

        RETURNING *
      `,
      [
        id,
        status,
        taskProject.rows[0].project_id
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
