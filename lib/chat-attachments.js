import crypto
  from "node:crypto";

import {
  db,
  initializeDatabase
} from "./db";

import {
  cleanFilename,
  extensionFor,
  isPreviewable,
  maxUploadBytes,
  readEncryptedFile,
  removeEncryptedFile,
  sha256,
  writeEncryptedFile
} from "./project-files";


import {
  documentKindForAttachment,
  extractDocumentAttachment
} from "./document-extractors";


export const CHAT_ATTACHMENT_CONTEXT_MARKER =
  "\n\nVECTOR_CHAT_ATTACHMENT_CONTEXT_571\n";


function safeScopePart(value) {
  return String(value || "unknown")
    .replace(/[^A-Za-z0-9_-]/g, "_");
}


function storageScopeForUser(userId) {
  return `chat-${safeScopePart(userId)}`;
}


function storedFileShape(row) {
  return {
    project_id:
      row.storage_scope,

    stored_name:
      row.stored_name
  };
}


function publicAttachment(row) {
  return {
    id:
      row.id,

    messageId:
      row.message_id || null,

    conversationId:
      row.conversation_id || null,

    name:
      row.original_name,

    mimeType:
      row.mime_type ||
      "application/octet-stream",

    extension:
      row.extension || "",

    sizeBytes:
      Number(row.size_bytes || 0),

    previewable:
      Boolean(row.previewable),

    createdAt:
      row.created_at,

    downloadUrl:
      `/api/chat/attachments/${row.id}/raw`
  };
}


export async function initializeChatAttachmentDatabase() {
  await initializeDatabase();

  await db.query(`
    CREATE TABLE IF NOT EXISTS chat_attachments (
      id TEXT PRIMARY KEY,
      owner_user_id TEXT NOT NULL,

      conversation_id TEXT
        REFERENCES conversations(id)
        ON DELETE SET NULL,

      message_id TEXT
        REFERENCES messages(id)
        ON DELETE SET NULL,

      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL,
      storage_scope TEXT NOT NULL,

      mime_type TEXT,
      extension TEXT,

      size_bytes BIGINT NOT NULL,
      sha256 TEXT NOT NULL,

      previewable BOOLEAN NOT NULL DEFAULT FALSE,
      encryption_version INTEGER NOT NULL DEFAULT 1,

      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      bound_at TIMESTAMPTZ
    );
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_chat_attachments_owner
      ON chat_attachments(owner_user_id,created_at DESC);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_chat_attachments_conversation
      ON chat_attachments(conversation_id,created_at ASC);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_chat_attachments_message
      ON chat_attachments(message_id,created_at ASC);
  `);
}


export function maxChatAttachmentBytes() {
  const configuredMb =
    Number(
      process.env.VECTOR_CHAT_MAX_UPLOAD_MB ||
      25
    );

  const configured =
    Math.max(1,configuredMb) *
    1024 *
    1024;

  return Math.min(
    configured,
    maxUploadBytes()
  );
}


export async function cleanupPendingChatAttachments({
  ownerUserId
}) {
  await initializeChatAttachmentDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM chat_attachments
        WHERE
          owner_user_id = $1
          AND conversation_id IS NULL
          AND message_id IS NULL
          AND created_at < NOW() - INTERVAL '24 hours'
        ORDER BY created_at ASC
        LIMIT 100
      `,
      [
        ownerUserId
      ]
    );

  for (const row of result.rows) {
    try {
      await removeEncryptedFile(
        storedFileShape(row)
      );
    } catch (error) {
      console.error(
        "Pending attachment cleanup failed:",
        row.id,
        error
      );

      continue;
    }

    await db.query(
      `
        DELETE FROM chat_attachments
        WHERE
          id = $1
          AND owner_user_id = $2
      `,
      [
        row.id,
        ownerUserId
      ]
    );
  }

  return result.rowCount;
}


export async function storeChatAttachment({
  ownerUserId,
  file
}) {
  await initializeChatAttachmentDatabase();

  if (
    !file ||
    typeof file.arrayBuffer !== "function"
  ) {
    throw new Error(
      "A file is required."
    );
  }

  const buffer =
    Buffer.from(
      await file.arrayBuffer()
    );

  if (buffer.length === 0) {
    throw new Error(
      "Empty files are not supported."
    );
  }

  const limit =
    maxChatAttachmentBytes();

  if (buffer.length > limit) {
    throw new Error(
      `File is larger than the ${Math.round(
        limit / 1024 / 1024
      )} MB chat attachment limit.`
    );
  }

  const id =
    crypto.randomUUID();

  const name =
    cleanFilename(
      file.name ||
      "attachment"
    );

  const mimeType =
    String(
      file.type ||
      "application/octet-stream"
    )
      .trim()
      .toLowerCase()
      .slice(0,180);

  const extension =
    extensionFor(name);

  const previewable =
    isPreviewable({
      filename:
        name,

      mimeType
    });

  const storageScope =
    storageScopeForUser(
      ownerUserId
    );

  const stored =
    await writeEncryptedFile({
      projectId:
        storageScope,

      fileId:
        id,

      buffer
    });

  try {
    const result =
      await db.query(
        `
          INSERT INTO chat_attachments (
            id,
            owner_user_id,
            original_name,
            stored_name,
            storage_scope,
            mime_type,
            extension,
            size_bytes,
            sha256,
            previewable,
            encryption_version
          )
          VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1
          )
          RETURNING *
        `,
        [
          id,
          ownerUserId,
          name,
          stored.storedName,
          storageScope,
          mimeType,
          extension,
          buffer.length,
          sha256(buffer),
          previewable
        ]
      );

    return publicAttachment(
      result.rows[0]
    );

  } catch (error) {
    await removeEncryptedFile({
      project_id:
        storageScope,

      stored_name:
        stored.storedName
    });

    throw error;
  }
}


async function rowsForAttachmentIds({
  ownerUserId,
  attachmentIds
}) {
  const ids =
    [
      ...new Set(
        (attachmentIds || [])
          .map(
            (id) =>
              String(id || "").trim()
          )
          .filter(Boolean)
      )
    ].slice(0,6);

  if (ids.length === 0) {
    return [];
  }

  const result =
    await db.query(
      `
        SELECT *
        FROM chat_attachments
        WHERE
          owner_user_id = $1
          AND id = ANY($2::text[])
      `,
      [
        ownerUserId,
        ids
      ]
    );

  const byId =
    new Map(
      result.rows.map(
        (row) => [
          row.id,
          row
        ]
      )
    );

  const ordered =
    ids
      .map(
        (id) =>
          byId.get(id)
      )
      .filter(Boolean);

  if (ordered.length !== ids.length) {
    throw new Error(
      "One or more attachments are unavailable."
    );
  }

  return ordered;
}


export async function prepareChatAttachmentContext({
  ownerUserId,
  attachmentIds,
  conversationId
}) {
  await initializeChatAttachmentDatabase();

  const rows =
    await rowsForAttachmentIds({
      ownerUserId,
      attachmentIds
    });

  if (rows.length === 0) {
    return {
      attachments: [],
      context: ""
    };
  }

  for (const row of rows) {
    if (
      row.conversation_id &&
      row.conversation_id !== conversationId
    ) {
      throw new Error(
        "An attachment already belongs to another conversation."
      );
    }

    if (
      !conversationId &&
      row.conversation_id
    ) {
      throw new Error(
        "An attachment already belongs to an existing conversation."
      );
    }
  }

  const perFileLimit =
    Math.max(
      16384,
      Number(
        process.env
          .VECTOR_CHAT_ATTACHMENT_CONTEXT_BYTES ||
        131072
      )
    );

  const totalLimit =
    Math.max(
      perFileLimit,
      Number(
        process.env
          .VECTOR_CHAT_ATTACHMENT_CONTEXT_TOTAL_BYTES ||
        262144
      )
    );

  let totalBytes = 0;
  const sections = [];

  for (
    let index = 0;
    index < rows.length;
    index += 1
  ) {
    const row =
      rows[index];

    const meta = [
      `ATTACHMENT ${index + 1}`,
      `Name: ${row.original_name}`,
      `MIME: ${
        row.mime_type ||
        "application/octet-stream"
      }`,
      `Size: ${Number(
        row.size_bytes ||
        0
      )} bytes`
    ];

    if (
      row.previewable &&
      totalBytes < totalLimit
    ) {
      const buffer =
        await readEncryptedFile(
          storedFileShape(row)
        );

      const remaining =
        Math.max(
          0,
          totalLimit -
          totalBytes
        );

      const take =
        Math.min(
          buffer.length,
          perFileLimit,
          remaining
        );

      const selected =
        buffer.subarray(
          0,
          take
        );

      totalBytes +=
        selected.length;

      let body =
        selected.toString(
          "utf8"
        );

      if (take < buffer.length) {
        body +=
          "\n\n[Attachment content truncated by Vector.]";
      }

      sections.push(
        [
          ...meta,
          "Content:",
          body,
          `END ATTACHMENT ${index + 1}`
        ].join("\n")
      );

      continue;
    }

    /*
     * VECTOR_DOCUMENT_CONTEXT_573
     *
     * Documents are decrypted and extracted locally. The resulting
     * text becomes part of the normal attachment context and therefore
     * passes through Vector's existing privacy sanitizer before any
     * external provider sees it.
     */
    const documentKind =
      documentKindForAttachment({
        filename:
          row.original_name,

        mimeType:
          row.mime_type,

        extension:
          row.extension
      });

    if (documentKind) {
      const remaining =
        Math.max(
          0,
          totalLimit -
          totalBytes
        );

      if (remaining <= 0) {
        sections.push(
          [
            ...meta,
            `Document type: ${documentKind.toUpperCase()}`,
            "Content:",
            "[Document stored securely, but the attachment-context limit was already reached.]",
            `END ATTACHMENT ${index + 1}`
          ].join(
            "\n"
          )
        );

        continue;
      }

      const documentBuffer =
        await readEncryptedFile(
          storedFileShape(
            row
          )
        );

      let extracted;

      try {
        extracted =
          await extractDocumentAttachment({
            buffer:
              documentBuffer,

            filename:
              row.original_name,

            mimeType:
              row.mime_type,

            extension:
              row.extension
          });

      } catch (error) {
        sections.push(
          [
            ...meta,
            `Document type: ${documentKind.toUpperCase()}`,
            "Content:",
            `[Vector could not extract this document: ${
              error.message ||
              "unknown extraction error"
            }]`,
            `END ATTACHMENT ${index + 1}`
          ].join(
            "\n"
          )
        );

        continue;
      }

      if (extracted) {
        const raw =
          String(
            extracted.text ||
            ""
          );

        const rawBuffer =
          Buffer.from(
            raw,
            "utf8"
          );

        const take =
          Math.min(
            rawBuffer.length,
            perFileLimit,
            remaining
          );

        let body =
          rawBuffer
            .subarray(
              0,
              take
            )
            .toString(
              "utf8"
            );

        totalBytes +=
          Buffer.byteLength(
            body,
            "utf8"
          );

        if (
          take <
          rawBuffer.length
        ) {
          body +=
            "\n\n[Extracted document content truncated by Vector.]";
        }

        const metadata =
          extracted.metadata &&
          Object.keys(
            extracted.metadata
          ).length >
            0
            ? JSON.stringify(
                extracted.metadata
              )
            : null;

        sections.push(
          [
            ...meta,
            `Document type: ${extracted.kind}`,
            ...(metadata
              ? [
                  `Document metadata: ${metadata}`
                ]
              : []),
            "Extracted content:",
            body,
            `END ATTACHMENT ${index + 1}`
          ].join(
            "\n"
          )
        );

        continue;
      }
    }

    sections.push(
      [
        ...meta,
        "Content:",
        "[Binary attachment stored securely. Images are available to Vector vision; document extraction is handled separately.]",
        `END ATTACHMENT ${index + 1}`
      ].join("\n")
    );
  }

  return {
    attachments:
      rows.map(
        publicAttachment
      ),

    context:
      sections.join(
        "\n\n"
      )
  };
}


export async function bindChatAttachments({
  ownerUserId,
  attachmentIds,
  conversationId,
  messageId
}) {
  await initializeChatAttachmentDatabase();

  const rows =
    await rowsForAttachmentIds({
      ownerUserId,
      attachmentIds
    });

  if (rows.length === 0) {
    return [];
  }

  for (const row of rows) {
    if (
      row.conversation_id &&
      row.conversation_id !== conversationId
    ) {
      throw new Error(
        "An attachment belongs to another conversation."
      );
    }
  }

  const ids =
    rows.map(
      (row) =>
        row.id
    );

  const result =
    await db.query(
      `
        UPDATE chat_attachments
        SET
          conversation_id = $3,
          message_id = $4,
          bound_at = COALESCE(bound_at,NOW())
        WHERE
          owner_user_id = $1
          AND id = ANY($2::text[])
          AND (
            conversation_id IS NULL
            OR conversation_id = $3
          )
        RETURNING *
      `,
      [
        ownerUserId,
        ids,
        conversationId,
        messageId
      ]
    );

  if (result.rowCount !== ids.length) {
    throw new Error(
      "Could not bind all chat attachments."
    );
  }

  return result.rows.map(
    publicAttachment
  );
}


export async function listConversationAttachments({
  ownerUserId,
  conversationId
}) {
  await initializeChatAttachmentDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM chat_attachments
        WHERE
          owner_user_id = $1
          AND conversation_id = $2
        ORDER BY created_at ASC
      `,
      [
        ownerUserId,
        conversationId
      ]
    );

  return result.rows.map(
    publicAttachment
  );
}


export async function getChatAttachmentForOwner({
  ownerUserId,
  attachmentId
}) {
  await initializeChatAttachmentDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM chat_attachments
        WHERE
          owner_user_id = $1
          AND id = $2
        LIMIT 1
      `,
      [
        ownerUserId,
        attachmentId
      ]
    );

  return result.rows[0] || null;
}


export async function readChatAttachment(row) {
  return readEncryptedFile(
    storedFileShape(row)
  );
}


export async function deletePendingChatAttachment({
  ownerUserId,
  attachmentId
}) {
  await initializeChatAttachmentDatabase();

  const result =
    await db.query(
      `
        SELECT *
        FROM chat_attachments
        WHERE
          owner_user_id = $1
          AND id = $2
        LIMIT 1
      `,
      [
        ownerUserId,
        attachmentId
      ]
    );

  const row =
    result.rows[0];

  if (!row) {
    return {
      deleted: false,
      reason: "not_found"
    };
  }

  if (row.message_id) {
    return {
      deleted: false,
      reason: "already_bound"
    };
  }

  await removeEncryptedFile(
    storedFileShape(row)
  );

  await db.query(
    `
      DELETE FROM chat_attachments
      WHERE
        id = $1
        AND owner_user_id = $2
        AND message_id IS NULL
    `,
    [
      attachmentId,
      ownerUserId
    ]
  );

  return {
    deleted: true
  };
}

const VECTOR_VISION_MIME_TYPES =
  new Set([
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif"
  ]);


function normalizedVisionMime(row) {
  const mime =
    String(
      row.mime_type ||
      ""
    )
      .trim()
      .toLowerCase();

  if (
    VECTOR_VISION_MIME_TYPES.has(
      mime
    )
  ) {
    return mime;
  }

  const ext =
    String(
      row.extension ||
      ""
    ).toLowerCase();

  if (ext === ".png") return "image/png";
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".webp") return "image/webp";
  if (ext === ".gif") return "image/gif";

  return null;
}


export async function buildVisionInputs({
  ownerUserId,
  attachmentIds
}) {
  await initializeChatAttachmentDatabase();

  const rows =
    await rowsForAttachmentIds({
      ownerUserId,
      attachmentIds
    });

  const imageRows =
    rows.filter(
      (row) =>
        String(
          row.mime_type ||
          ""
        )
          .toLowerCase()
          .startsWith(
            "image/"
          ) ||
        [
          ".png",
          ".jpg",
          ".jpeg",
          ".webp",
          ".gif",
          ".svg"
        ].includes(
          String(
            row.extension ||
            ""
          ).toLowerCase()
        )
    );

  if (imageRows.length === 0) {
    return [];
  }

  if (imageRows.length > 4) {
    throw new Error(
      "Vector currently supports up to 4 images in one vision request."
    );
  }

  const maxImageBytes =
    Math.max(
      1,
      Number(
        process.env.VECTOR_VISION_MAX_IMAGE_MB ||
        10
      )
    ) *
    1024 *
    1024;

  const maxTotalBytes =
    Math.max(
      maxImageBytes,
      Number(
        process.env.VECTOR_VISION_MAX_TOTAL_MB ||
        20
      ) *
      1024 *
      1024
    );

  let totalBytes = 0;
  const result = [];

  for (const row of imageRows) {
    const mimeType =
      normalizedVisionMime(
        row
      );

    if (!mimeType) {
      throw new Error(
        `${row.original_name}: vision currently supports PNG, JPEG, WEBP and GIF.`
      );
    }

    if (!row.message_id) {
      throw new Error(
        "Vision input must belong to a submitted chat message."
      );
    }

    const size =
      Number(
        row.size_bytes ||
        0
      );

    if (size > maxImageBytes) {
      throw new Error(
        `${row.original_name} is larger than the ${Math.round(
          maxImageBytes / 1024 / 1024
        )} MB vision limit.`
      );
    }

    totalBytes += size;

    if (totalBytes > maxTotalBytes) {
      throw new Error(
        `The attached images exceed Vector's ${Math.round(
          maxTotalBytes / 1024 / 1024
        )} MB combined vision limit.`
      );
    }

    const buffer =
      await readEncryptedFile(
        storedFileShape(
          row
        )
      );

    result.push({
      id:
        row.id,

      name:
        row.original_name,

      mimeType,

      detail:
        "auto",

      dataUrl:
        `data:${mimeType};base64,${
          buffer.toString(
            "base64"
          )
        }`
    });
  }

  return result;
}
