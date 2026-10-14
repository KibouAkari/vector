import {
  getSession,
  hasFeature
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  cleanupPendingChatAttachments,
  initializeChatAttachmentDatabase,
  listConversationAttachments,
  storeChatAttachment
} from "../../../../lib/chat-attachments";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


async function ownsConversation({
  conversationId,
  userId
}) {
  const result =
    await db.query(
      `
        SELECT id
        FROM conversations
        WHERE
          id = $1
          AND user_id = $2
          AND project_id IS NULL
        LIMIT 1
      `,
      [
        conversationId,
        userId
      ]
    );

  return result.rowCount === 1;
}


export async function GET(request) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error: "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  if (!hasFeature(session, "chat")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeChatAttachmentDatabase();

  const url =
    new URL(
      request.url
    );

  const conversationId =
    String(
      url.searchParams.get(
        "conversationId"
      ) ||
      ""
    ).trim();

  if (!conversationId) {
    return Response.json(
      {
        error:
          "conversationId is required"
      },
      {
        status: 400
      }
    );
  }

  if (
    !await ownsConversation({
      conversationId,
      userId:
        session.userId
    })
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

  const attachments =
    await listConversationAttachments({
      ownerUserId:
        session.userId,

      conversationId
    });

  return Response.json({
    attachments
  });
}


export async function POST(request) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error: "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  if (!hasFeature(session, "chat")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeChatAttachmentDatabase();

  await cleanupPendingChatAttachments({
    ownerUserId:
      session.userId
  });

  let formData;

  try {
    formData =
      await request.formData();

  } catch {
    return Response.json(
      {
        error:
          "Invalid multipart upload"
      },
      {
        status: 400
      }
    );
  }

  const file =
    formData.get(
      "file"
    );

  if (
    !file ||
    typeof file.arrayBuffer !== "function"
  ) {
    return Response.json(
      {
        error:
          "A file is required"
      },
      {
        status: 400
      }
    );
  }

  try {
    const attachment =
      await storeChatAttachment({
        ownerUserId:
          session.userId,

        file
      });

    return Response.json(
      {
        ok: true,
        attachment
      },
      {
        status: 201
      }
    );

  } catch (error) {
    return Response.json(
      {
        error:
          error.message ||
          "Attachment upload failed"
      },
      {
        status: 400
      }
    );
  }
}
