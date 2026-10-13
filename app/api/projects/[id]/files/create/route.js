import { canEditProject } from "../../../../../../lib/identity";
import crypto from "node:crypto";

import {
  getSession
} from "../../../../../../lib/auth";

import {
  db
} from "../../../../../../lib/db";

import {
  cleanFilename,
  extensionFor,
  initializeFileDatabase,
  sha256,
  writeEncryptedFile
} from "../../../../../../lib/project-files";

import {
  indexProjectTextFile
} from "../../../../../../lib/project-index";

import {
  writeAudit
} from "../../../../../../lib/audit";

export const runtime =
  "nodejs";

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

  const name =
    cleanFilename(
      body.name ||
      ""
    );

  const content =
    String(
      body.content ||
      ""
    );

  if (
    !name
  ) {
    return Response.json(
      {
        error:
          "Filename is required."
      },
      {
        status:
          400
      }
    );
  }

  const buffer =
    Buffer.from(
      content,
      "utf8"
    );

  await initializeFileDatabase();

  const project =
    await db.query(
      `
        SELECT id
        FROM projects
        WHERE id = $1
      `,
      [
        projectId
      ]
    );

  if (
    project.rowCount ===
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

  const fileId =
    crypto.randomUUID();

  const stored =
    await writeEncryptedFile({
      projectId,
      fileId,
      buffer
    });

  const extension =
    extensionFor(
      name
    );

  const mimeType =
    extension === "json"
      ? "application/json"
      : "text/plain";

  await db.query(
    `
      INSERT INTO project_files (
        id,
        project_id,
        original_name,
        stored_name,
        mime_type,
        extension,
        size_bytes,
        sha256,
        previewable,
        encryption_version
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        $7,
        $8,
        TRUE,
        1
      )
    `,
    [
      fileId,
      projectId,
      name,
      stored.storedName,
      mimeType,
      extension,
      buffer.length,
      sha256(
        buffer
      )
    ]
  );

  await indexProjectTextFile({
    projectId,
    fileId,
    text:
      content
  });

  await db.query(
    `
      UPDATE projects
      SET updated_at =
        NOW()
      WHERE id = $1
    `,
    [
      projectId
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "file.created",

    resource:
      fileId,

    details: {
      projectId,
      name
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true,

    id:
      fileId
  });
}
