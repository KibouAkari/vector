import {
  getSession
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  initializeFileDatabase,
  removeEncryptedFile
} from "../../../../lib/project-files";

import {
  writeAudit
} from "../../../../lib/audit";

export const runtime =
  "nodejs";

export async function DELETE(
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

  await initializeFileDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM project_files
        WHERE id = $1
      `,
      [
        id
      ]
    );

  if (
    result.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "File not found."
      },
      {
        status:
          404
      }
    );
  }

  const file =
    result.rows[0];

  await removeEncryptedFile(
    file
  );

  await db.query(
    `
      DELETE FROM project_files
      WHERE id = $1
    `,
    [
      id
    ]
  );

  await db.query(
    `
      UPDATE projects
      SET updated_at =
        NOW()
      WHERE id = $1
    `,
    [
      file.project_id
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "file.deleted",

    resource:
      id,

    details: {
      projectId:
        file.project_id,
      name:
        file.original_name
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true
  });
}
