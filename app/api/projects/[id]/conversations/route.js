import {
  getSession
} from "../../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../../lib/db";


export const dynamic =
  "force-dynamic";


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
        status: 401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  await initializeDatabase();

  const result =
    await db.query(
      `
        SELECT
          id,
          title,
          created_at,
          updated_at

        FROM conversations

        WHERE
          project_id = $1
          AND
          user_id = $2

        ORDER BY
          updated_at DESC

        LIMIT 100
      `,
      [
        id,
        session.userId
      ]
    );

  return Response.json({
    conversations:
      result.rows
  });
}
