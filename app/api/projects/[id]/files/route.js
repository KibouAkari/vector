import { canAccessProject, canEditProject } from "../../../../../lib/identity";
import crypto
  from "node:crypto";

import {
  getSession
} from "../../../../../lib/auth";

import {
  db
} from "../../../../../lib/db";

import {
  cleanFilename,
  extensionFor,
  initializeFileDatabase,
  isPreviewable,
  maxUploadBytes,
  sha256,
  writeEncryptedFile
} from "../../../../../lib/project-files";

import {
  indexProjectTextFile
} from "../../../../../lib/project-index";

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
    id:
      projectId
  } =
    await context.params;

  if (!await canAccessProject(session, (await context.params).id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  await initializeFileDatabase();

  const result =
    await db.query(
      `
        SELECT
          id,
          original_name,
          mime_type,
          extension,
          size_bytes,
          sha256,
          previewable,
          created_at

        FROM project_files

        WHERE
          project_id = $1

        ORDER BY
          created_at DESC
      `,
      [
        projectId
      ]
    );

  return Response.json({
    files:
      result.rows.map(
        (
          file
        ) => ({
          ...file,

          size_bytes:
            Number(
              file.size_bytes
            )
        })
      )
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


  await initializeFileDatabase();

  const project =
    await db.query(
      `
        SELECT
          id,
          privacy_level
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

  let formData;

  try {
    formData =
      await request.formData();
  } catch {
    return Response.json(
      {
        error:
          "Invalid upload."
      },
      {
        status:
          400
      }
    );
  }

  const uploaded =
    formData.get(
      "file"
    );

  if (
    !uploaded ||
    typeof uploaded
      .arrayBuffer !==
      "function"
  ) {
    return Response.json(
      {
        error:
          "No file supplied."
      },
      {
        status:
          400
      }
    );
  }

  const limit =
    maxUploadBytes();

  if (
    uploaded.size >
    limit
  ) {
    return Response.json(
      {
        error:
          `File exceeds the current ${Math.round(
            limit /
            1024 /
            1024
          )} MB upload limit.`
      },
      {
        status:
          413
      }
    );
  }

  const originalName =
    cleanFilename(
      uploaded.name
    );

  const mimeType =
    String(
      uploaded.type ||
      "application/octet-stream"
    )
      .slice(
        0,
        200
      );

  const buffer =
    Buffer.from(
      await uploaded.arrayBuffer()
    );

  /*
   * Do not trust the browser-reported size.
   */
  if (
    buffer.length >
    limit
  ) {
    return Response.json(
      {
        error:
          "File exceeds upload limit."
      },
      {
        status:
          413
      }
    );
  }

  const fileId =
    crypto.randomUUID();

  let stored;

  try {
    stored =
      await writeEncryptedFile({
        projectId,
        fileId,
        buffer
      });

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
          $9,
          1
        )
      `,
      [
        fileId,
        projectId,
        originalName,
        stored.storedName,
        mimeType,
        extensionFor(
          originalName
        ),
        buffer.length,
        sha256(
          buffer
        ),
        isPreviewable({
          filename:
            originalName,

          mimeType
        })
      ]
    );

  } catch (
    error
  ) {
    return Response.json(
      {
        error:
          `Upload failed: ${error.message}`
      },
      {
        status:
          500
      }
    );
  }

  if (
    isPreviewable({
      filename:
        originalName,

      mimeType
    })
  ) {
    try {
      await indexProjectTextFile({
        projectId,
        fileId,

        text:
          buffer.toString(
            "utf8"
          )
      });
    } catch (
      indexError
    ) {
      console.error(
        "Vector indexing failed:",
        indexError
      );
    }
  }

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
      "file.uploaded",

    resource:
      fileId,

    details: {
      projectId,
      name:
        originalName,
      size:
        buffer.length,
      sha256:
        sha256(
          buffer
        ),
      encrypted:
        true
    },

    source:
      "web"
  });

  return Response.json({
    ok:
      true,

    file: {
      id:
        fileId,

      name:
        originalName,

      size:
        buffer.length,

      mimeType,

      previewable:
        isPreviewable({
          filename:
            originalName,

          mimeType
        })
    }
  });
}
