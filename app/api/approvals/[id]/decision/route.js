import {
  getSession
} from "../../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../../lib/db";

import {
  writeAudit
} from "../../../../../lib/audit";

export const runtime = "nodejs";

export async function POST(
  request,
  context
) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error: "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  const {
    id
  } = await context.params;

  const body =
    await request.json();

  if (
    body.decision !== "approved" &&
    body.decision !== "rejected"
  ) {
    return Response.json(
      {
        error: "Invalid decision"
      },
      {
        status: 400
      }
    );
  }

  await initializeDatabase();

  const result =
    await db.query(
      `
        UPDATE approvals
        SET
          status = $1,
          decided_at = NOW(),
          decided_by = $2
        WHERE
          id = $3
          AND status = 'pending'
        RETURNING
          permission,
          action
      `,
      [
        body.decision,
        session.username,
        id
      ]
    );

  if (result.rowCount === 0) {
    return Response.json(
      {
        error:
          "Approval not found or already decided"
      },
      {
        status: 404
      }
    );
  }

  await writeAudit({
    actor:
      session.username,

    action:
      `approval.${body.decision}`,

    resource:
      id,

    details:
      result.rows[0],

    source:
      "web"
  });

  return Response.json({
    ok: true
  });
}
