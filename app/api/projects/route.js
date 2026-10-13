import crypto
  from "node:crypto";

import {
  getSession,
  hasFeature
} from "../../../lib/auth";

import {
  db
} from "../../../lib/db";

import {
  initializeFileDatabase
} from "../../../lib/project-files";

import {
  writeAudit
} from "../../../lib/audit";

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

export async function GET() {
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

  if (!hasFeature(session, "projects")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeFileDatabase();

  const result =
    await db.query(`
      SELECT
        p.id,
        p.name,
        p.description,
        p.privacy_level,
        p.created_at,
        p.updated_at,

        COUNT(
          pf.id
        )::int AS file_count,

        COALESCE(
          SUM(
            pf.size_bytes
          ),
          0
        )::bigint AS storage_bytes

      FROM projects p

      LEFT JOIN project_files pf
        ON
          pf.project_id =
          p.id

      WHERE (
        $1::boolean
        OR p.owner_user_id = $2
        OR EXISTS (
          SELECT 1 FROM project_members pm
          WHERE pm.project_id = p.id AND pm.user_id = $2
        )
      )

      GROUP BY
        p.id

      ORDER BY
        p.updated_at DESC
    `, [session.role === "owner", session.userId]);

  return Response.json({
    projects:
      result.rows
  });
}

export async function POST(
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
        status:
          401
      }
    );
  }

  let body;

  try {
    body =
      await request.json();
  } catch {
    return Response.json(
      {
        error:
          "Invalid request"
      },
      {
        status:
          400
      }
    );
  }

  const name =
    String(
      body.name ||
      ""
    )
      .trim()
      .slice(
        0,
        100
      );

  const description =
    String(
      body.description ||
      ""
    )
      .trim()
      .slice(
        0,
        1000
      );

  const privacyLevel =
    String(
      body.privacyLevel ||
      "personal"
    );

  if (!name) {
    return Response.json(
      {
        error:
          "Project name is required."
      },
      {
        status:
          400
      }
    );
  }

  if (
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

  if (!hasFeature(session, "projects")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeFileDatabase();

  const id =
    crypto.randomUUID();

  await db.query(
    `
      INSERT INTO projects (
        id,
        name,
        description,
        privacy_level,
        owner_user_id,
        created_at,
        updated_at
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        NOW(),
        NOW()
      )
    `,
    [
      id,
      name,
      description ||
        null,
      privacyLevel,
      session.userId
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "project.created",

    resource:
      id,

    details: {
      name,
      privacyLevel
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true,

    project: {
      id,
      name,
      description,
      privacyLevel
    }
  });
}
