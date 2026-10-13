import {
  getSession
} from "../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../lib/db";

import {
  restorePrivateValues
} from "../../../../lib/privacy-vault";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


async function ownedConversation(
  id,
  userId
) {
  return db.query(
    `
      SELECT
        id,
        title,
        created_at,
        updated_at

      FROM conversations

      WHERE
        id = $1
        AND
        user_id = $2
        AND
        project_id IS NULL

      LIMIT 1
    `,
    [
      id,
      userId
    ]
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
        status: 401
      }
    );
  }

  const {
    id
  } =
    await context.params;

  await initializeDatabase();

  const conversation =
    await ownedConversation(
      id,
      session.userId
    );

  if (
    conversation.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Conversation not found"
      },
      {
        status: 404
      }
    );
  }

  const messageResult =
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
        id
      ]
    );

  const messages = [];

  for (
    const message
    of messageResult.rows
  ) {
    messages.push({
      id:
        message.id,

      role:
        message.role,

      content:
        await restorePrivateValues({
          conversationId:
            id,

          text:
            message.content
        }),

      model:
        message.model,

      costChf:
        Number(
          message.cost_chf ||
          0
        ),

      createdAt:
        message.created_at
    });
  }

  return Response.json({
    conversation:
      conversation.rows[0],

    messages
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
        DELETE FROM conversations

        WHERE
          id = $1
          AND
          user_id = $2
          AND
          project_id IS NULL

        RETURNING id
      `,
      [
        id,
        session.userId
      ]
    );

  if (
    result.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Conversation not found"
      },
      {
        status: 404
      }
    );
  }

  return Response.json({
    ok:
      true
  });
}
