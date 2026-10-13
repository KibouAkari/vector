import {
  getSession
} from "../../../../../lib/auth";

import {
  db
} from "../../../../../lib/db";

import {
  readEncryptedFile,
  removeEncryptedFile,
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

async function getFile(
  id
) {
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

  return (
    result.rows[0] ||
    null
  );
}

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

  const file =
    await getFile(
      id
    );

  if (!file) {
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

  if (
    !file.previewable
  ) {
    return Response.json(
      {
        error:
          "This file is not editable as text."
      },
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

  return Response.json({
    id:
      file.id,

    name:
      file.original_name,

    content:
      buffer.toString(
        "utf8"
      )
  });
}

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

  const file =
    await getFile(
      id
    );

  if (!file) {
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

  if (
    !file.previewable
  ) {
    return Response.json(
      {
        error:
          "This file cannot be edited as text."
      },
      {
        status:
          415
      }
    );
  }

  const body =
    await request.json();

  const content =
    String(
      body.content ||
      ""
    );

  const buffer =
    Buffer.from(
      content,
      "utf8"
    );

  await removeEncryptedFile(
    file
  );

  await writeEncryptedFile({
    projectId:
      file.project_id,

    fileId:
      file.id,

    buffer
  });

  await db.query(
    `
      UPDATE project_files

      SET
        size_bytes = $2,
        sha256 = $3

      WHERE
        id = $1
    `,
    [
      file.id,
      buffer.length,
      sha256(
        buffer
      )
    ]
  );

  await indexProjectTextFile({
    projectId:
      file.project_id,

    fileId:
      file.id,

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
      file.project_id
    ]
  );

  await writeAudit({
    actor:
      session.username,

    action:
      "file.updated",

    resource:
      file.id,

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
