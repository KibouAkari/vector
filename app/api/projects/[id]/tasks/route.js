import { canAccessProject, canEditProject } from "../../../../../lib/identity";
import crypto from "node:crypto";

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

export const runtime =
  "nodejs";

export async function GET(
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

  if (!await canAccessProject(session, (await context.params).id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  await initializeDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM tasks

        WHERE
          project_id = $1

        ORDER BY
          created_at DESC
      `,
      [
        id
      ]
    );

  return Response.json({
    tasks:
      result.rows
  });
}

export async function POST(
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
    id:
      projectId
  } =
    await context.params;

  if (!await canEditProject(session, (await context.params).id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  const body =
    await request.json();

  const title =
    String(
      body.title ||
      ""
    )
      .trim()
      .slice(
        0,
        200
      );

  if (!title) {
    return Response.json(
      {
        error:
          "Task title is required."
      },
      {
        status:
          400
      }
    );
  }

  await initializeDatabase();

  const taskId =
    crypto.randomUUID();

  await db.query(
    `
      INSERT INTO tasks (
        id,
        project_id,
        title,
        description,
        status,
        task_type,
        privacy_level,
        budget_chf,
        spent_chf,
        created_at,
        updated_at
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        'pending',
        'normal',
        'internal',
        0.10,
        0,
        NOW(),
        NOW()
      )
    `,
    [
      taskId,
      projectId,
      title,
      String(
        body.description ||
        ""
      )
        .trim()
        .slice(
          0,
          3000
        )
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "task.created",

    resource:
      taskId,

    details: {
      projectId,
      title
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true,

    id:
      taskId
  });
}
