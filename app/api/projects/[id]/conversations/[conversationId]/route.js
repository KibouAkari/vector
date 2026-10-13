import {
  getSession
} from "../../../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../../../lib/db";

import {
  restorePrivateValues
} from "../../../../../../lib/privacy-vault";


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
    id,
    conversationId
  } =
    await context.params;

  await initializeDatabase();

  const conversation =
    await db.query(
      `
        SELECT id

        FROM conversations

        WHERE
          id = $1
          AND
          project_id = $2
          AND
          user_id = $3

        LIMIT 1
      `,
      [
        conversationId,
        id,
        session.userId
      ]
    );

  if (
    conversation.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Conversation not found."
      },
      {
        status: 404
      }
    );
  }

  const messages =
    await db.query(
      `
        SELECT
          id,
          role,
          content,
          model,
          cost_chf,
          created_at

        FROM messages

        WHERE
          conversation_id = $1

        ORDER BY
          created_at ASC
      `,
      [
        conversationId
      ]
    );

  const restored = [];

  for (
    const message
    of messages.rows
  ) {
    restored.push({
      ...message,

      content:
        await restorePrivateValues({
          conversationId,

          text:
            message.content
        })
    });
  }

  return Response.json({
    messages:
      restored
  });
}
