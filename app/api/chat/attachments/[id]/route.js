import {
  getSession,
  hasFeature
} from "../../../../../lib/auth";

import {
  deletePendingChatAttachment
} from "../../../../../lib/chat-attachments";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


export async function DELETE(
  request,
  context
) {
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

  const {
    id
  } =
    await context.params;

  const result =
    await deletePendingChatAttachment({
      ownerUserId:
        session.userId,

      attachmentId:
        id
    });

  if (!result.deleted) {
    return Response.json(
      {
        error:
          result.reason ===
            "already_bound"
            ? "Attachment is already part of a message"
            : "Attachment not found"
      },
      {
        status:
          result.reason ===
            "already_bound"
            ? 409
            : 404
      }
    );
  }

  return Response.json({
    ok: true
  });
}
