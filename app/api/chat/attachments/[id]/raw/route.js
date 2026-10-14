import {
  getSession,
  hasFeature
} from "../../../../../../lib/auth";

import {
  getChatAttachmentForOwner,
  readChatAttachment
} from "../../../../../../lib/chat-attachments";


export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


function asciiFilename(name) {
  return String(
    name ||
    "attachment"
  )
    .replace(
      /[^\x20-\x7E]/g,
      "_"
    )
    .replace(
      /["\\]/g,
      "_"
    );
}


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
        status: 401
      }
    );
  }

  if (!hasFeature(session, "chat")) {
    return new Response("Forbidden", { status: 403 });
  }

  const {
    id
  } =
    await context.params;

  const attachment =
    await getChatAttachmentForOwner({
      ownerUserId:
        session.userId,

      attachmentId:
        id
    });

  if (!attachment) {
    return new Response(
      "Attachment not found",
      {
        status: 404
      }
    );
  }

  const buffer =
    await readChatAttachment(
      attachment
    );

  const originalName =
    attachment.original_name ||
    "attachment";

  const encodedName =
    encodeURIComponent(
      originalName
    );

  return new Response(
    buffer,
    {
      headers: {
        "Content-Type":
          attachment.mime_type ||
          "application/octet-stream",

        "Content-Length":
          String(
            buffer.length
          ),

        "Content-Disposition":
          `attachment; filename="${asciiFilename(
            originalName
          )}"; filename*=UTF-8''${encodedName}`,

        "Cache-Control":
          "private, no-store",

        "X-Content-Type-Options":
          "nosniff",

        "Content-Security-Policy":
          "sandbox"
      }
    }
  );
}
