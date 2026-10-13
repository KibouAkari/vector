import { canAccessProject } from "../../../../../lib/identity";
import {
  getSession
} from "../../../../../lib/auth";

import {
  db
} from "../../../../../lib/db";

import {
  readEncryptedFile
} from "../../../../../lib/project-files";

export const runtime =
  "nodejs";

const SAFE_INLINE_TYPES =
  new Set([
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "application/pdf"
  ]);

export async function GET(
  request,
  context
) {
  const session =
    await getSession();

  if (!session) {
    return new Response(
      "Unauthorized",
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
    return new Response(
      "Not found",
      {
        status:
          404
      }
    );
  }

  const file =
    result.rows[0];
  if (!await canAccessProject(session, file.project_id)) {
    return new Response("Not found", { status: 404 });
  }


  const mime =
    String(
      file.mime_type ||
      "application/octet-stream"
    );

  if (
    !SAFE_INLINE_TYPES.has(
      mime
    )
  ) {
    return new Response(
      "Inline preview not supported.",
      {
        status:
          415
      }
    );
  }

  const buffer =
    await readEncryptedFile(
      file
    );

  return new Response(
    buffer,
    {
      headers: {
        "Content-Type":
          mime,

        "Content-Disposition":
          `inline; filename="${encodeURIComponent(
            file.original_name
          )}"`,

        "X-Content-Type-Options":
          "nosniff",

        "Cache-Control":
          "private, no-store"
      }
    }
  );
}
