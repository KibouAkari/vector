import {literalReplace} from './privacy-review-core.mjs';
import crypto from "node:crypto";

import {
  db,
  initializeDatabase
} from "./db";

function encryptionKey() {
  const raw =
    process.env.FILE_ENCRYPTION_KEY;

  if (!raw) {
    throw new Error(
      "FILE_ENCRYPTION_KEY is missing."
    );
  }

  const key =
    Buffer.from(
      raw,
      "hex"
    );

  if (key.length !== 32) {
    throw new Error(
      "FILE_ENCRYPTION_KEY must be 32 bytes."
    );
  }

  return key;
}

function encrypt(value) {
  const iv =
    crypto.randomBytes(12);

  const cipher =
    crypto.createCipheriv(
      "aes-256-gcm",
      encryptionKey(),
      iv
    );

  const encrypted =
    Buffer.concat([
      cipher.update(
        String(value),
        "utf8"
      ),
      cipher.final()
    ]);

  const tag =
    cipher.getAuthTag();

  return [
    iv.toString("base64"),
    tag.toString("base64"),
    encrypted.toString("base64")
  ].join(".");
}

function decrypt(payload) {
  const [
    ivRaw,
    tagRaw,
    encryptedRaw
  ] =
    String(payload).split(".");

  const iv =
    Buffer.from(
      ivRaw,
      "base64"
    );

  const tag =
    Buffer.from(
      tagRaw,
      "base64"
    );

  const encrypted =
    Buffer.from(
      encryptedRaw,
      "base64"
    );

  const decipher =
    crypto.createDecipheriv(
      "aes-256-gcm",
      encryptionKey(),
      iv
    );

  decipher.setAuthTag(tag);

  const decrypted =
    Buffer.concat([
      decipher.update(encrypted),
      decipher.final()
    ]);

  return decrypted.toString(
    "utf8"
  );
}

export async function initializePrivacyVault() {
  await initializeDatabase();

  await db.query(`
    CREATE TABLE IF NOT EXISTS privacy_vault (
      id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,
      placeholder TEXT NOT NULL,
      value_type TEXT NOT NULL,
      encrypted_value TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (
        conversation_id,
        placeholder
      )
    );
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_privacy_vault_conversation
    ON privacy_vault(conversation_id);
  `);
}

export async function savePrivacyMappings({
  conversationId,
  mappings
}) {
  if (
    !mappings ||
    mappings.length === 0
  ) {
    return;
  }

  await initializePrivacyVault();

  for (
    const mapping
    of mappings
  ) {
    await db.query(
      `
        INSERT INTO privacy_vault (
          id,
          conversation_id,
          placeholder,
          value_type,
          encrypted_value
        )
        VALUES (
          $1,
          $2,
          $3,
          $4,
          $5
        )
        ON CONFLICT (
          conversation_id,
          placeholder
        )
        DO NOTHING
      `,
      [
        crypto.randomUUID(),
        conversationId,
        mapping.placeholder,
        mapping.type,
        encrypt(
          mapping.value
        )
      ]
    );
  }
}

export async function getPrivacyMappings(
  conversationId
) {
  await initializePrivacyVault();

  const result =
    await db.query(
      `
        SELECT
          placeholder,
          value_type,
          encrypted_value
        FROM privacy_vault
        WHERE conversation_id = $1
        ORDER BY created_at ASC
      `,
      [
        conversationId
      ]
    );

  return result.rows.map(
    (row) => ({
      placeholder:
        row.placeholder,

      type:
        row.value_type,

      value:
        decrypt(
          row.encrypted_value
        )
    })
  );
}

export async function restorePrivateValues({
  conversationId,
  text
}) {
  if (!conversationId) {
    return String(
      text || ""
    );
  }

  let restored =
    String(
      text || ""
    );

  const mappings =
    await getPrivacyMappings(
      conversationId
    );

  return literalReplace(restored, mappings, true);
}
