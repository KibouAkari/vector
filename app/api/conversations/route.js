import {
  getSession,
  hasFeature
} from "../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../lib/db";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


export async function GET(
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
        status: 401
      }
    );
  }

  if (!hasFeature(session, "chat")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeDatabase();

  const url =
    new URL(
      request.url
    );

  const query =
    String(
      url.searchParams.get(
        "q"
      ) ||
      ""
    )
      .trim()
      .slice(
        0,
        200
      );

  let result;

  if (query) {
    result =
      await db.query(
        `
          SELECT DISTINCT ON (
            c.id
          )
            c.id,
            c.title,
            c.created_at,
            c.updated_at,

            COALESCE(
              (
                SELECT
                  m2.content

                FROM messages m2

                WHERE
                  m2.conversation_id =
                    c.id
                  AND
                  m2.content ILIKE
                    $2

                ORDER BY
                  m2.created_at DESC

                LIMIT 1
              ),
              (
                SELECT
                  m3.content

                FROM messages m3

                WHERE
                  m3.conversation_id =
                    c.id

                ORDER BY
                  m3.created_at DESC

                LIMIT 1
              )
            ) AS preview

          FROM conversations c

          LEFT JOIN messages m
            ON m.conversation_id =
              c.id

          WHERE
            c.user_id = $1
            AND
            c.project_id IS NULL
            AND
            (
              c.title ILIKE $2
              OR
              m.content ILIKE $2
            )

          ORDER BY
            c.id,
            c.updated_at DESC

          LIMIT 100
        `,
        [
          session.userId,
          `%${query}%`
        ]
      );

  } else {
    result =
      await db.query(
        `
          SELECT
            c.id,
            c.title,
            c.created_at,
            c.updated_at,

            (
              SELECT
                m.content

              FROM messages m

              WHERE
                m.conversation_id =
                  c.id

              ORDER BY
                m.created_at DESC

              LIMIT 1
            ) AS preview

          FROM conversations c

          WHERE
            c.user_id = $1
            AND
            c.project_id IS NULL

          ORDER BY
            c.updated_at DESC

          LIMIT 100
        `,
        [
          session.userId
        ]
      );
  }

  const conversations =
    result.rows.sort(
      (
        a,
        b
      ) =>
        new Date(
          b.updated_at
        ) -
        new Date(
          a.updated_at
        )
    );

  return Response.json({
    query,
    conversations
  });
}
