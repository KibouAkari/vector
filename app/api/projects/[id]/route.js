import { canManageProject } from "../../../../lib/identity";
import {
  getSession
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  initializeFileDatabase,
  removeProjectFiles
} from "../../../../lib/project-files";

import {
  writeAudit
} from "../../../../lib/audit";

export const runtime =
  "nodejs";

const PRIVACY_LEVELS =
  new Set([
    "public",
    "personal",
    "internal",
    "confidential",
    "local_only"
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

  if (!await canManageProject(session, (await context.params).id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  const body =
    await request.json();

  const privacyLevel =
    body.privacyLevel
      ? String(
          body.privacyLevel
        )
      : null;

  if (
    privacyLevel &&
    !PRIVACY_LEVELS.has(
      privacyLevel
    )
  ) {
    return Response.json(
      {
        error:
          "Invalid privacy level."
      },
      {
        status:
          400
      }
    );
  }

  await initializeFileDatabase();

  const result =
    await db.query(
      `
        UPDATE projects

        SET
          name =
            COALESCE(
              $2,
              name
            ),

          description =
            COALESCE(
              $3,
              description
            ),

          privacy_level =
            COALESCE(
              $4,
              privacy_level
            ),

          updated_at =
            NOW()

        WHERE
          id = $1

        RETURNING *
      `,
      [
        id,

        body.name
          ? String(
              body.name
            )
              .trim()
              .slice(
                0,
                100
              )
          : null,

        body.description !==
        undefined
          ? String(
              body.description
            )
              .trim()
              .slice(
                0,
                1000
              )
          : null,

        privacyLevel
      ]
    );

  if (
    result.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Project not found."
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
      "project.updated",

    resource:
      id,

    details: {
      privacyLevel:
        result.rows[0]
          .privacy_level
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true,

    project:
      result.rows[0]
  });
}

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

  if (!await canManageProject(session, (await context.params).id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  await initializeFileDatabase();

  const existing =
    await db.query(
      `
        SELECT
          id,
          name
        FROM projects
        WHERE id = $1
      `,
      [
        id
      ]
    );

  if (
    existing.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Project not found."
      },
      {
        status:
          404
      }
    );
  }

  /*
   * Delete encrypted bytes first.
   *
   * If this fails, metadata remains so we
   * do not silently orphan files.
   */
  await removeProjectFiles(
    id
  );

  await db.query(
    `
      DELETE FROM projects
      WHERE id = $1
    `,
    [
      id
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "project.deleted",

    resource:
      id,

    details: {
      name:
        existing.rows[0]
          .name
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true
  });
}
