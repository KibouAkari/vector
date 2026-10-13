import { canAccessProject } from "../../../../../lib/identity";
import {
  getSession
} from "../../../../../lib/auth";

import {
  db
} from "../../../../../lib/db";

import {
  initializeFileDatabase,
  previewMaxBytes,
  readEncryptedFile
} from "../../../../../lib/project-files";

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
  if (!await canAccessProject(session, file.project_id)) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }


  if (
    !file.previewable
  ) {
    return Response.json(
      {
        error:
          "This file type has no local text preview yet."
      },
      {
        status:
          415
      }
    );
  }

  const maximum =
    previewMaxBytes();

  if (
    Number(
      file.size_bytes
    ) >
    maximum
  ) {
    return Response.json(
      {
        error:
          `Local preview is currently limited to ${Math.round(
            maximum /
            1024 /
            1024
          )} MB. Large-file indexing arrives in Phase 4.1.`
      },
      {
        status:
          413
      }
    );
  }

  const plain =
    await readEncryptedFile(
      file
    );

  let content =
    plain.toString(
      "utf8"
    );

  const maxCharacters =
    250000;

  const truncated =
    content.length >
    maxCharacters;

  if (
    truncated
  ) {
    content =
      content.slice(
        0,
        maxCharacters
      );
  }

  return Response.json({
    id:
      file.id,

    name:
      file.original_name,

    mimeType:
      file.mime_type,

    size:
      Number(
        file.size_bytes
      ),

    sha256:
      file.sha256,

    content,

    truncated
  });
}
