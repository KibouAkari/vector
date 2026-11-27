import crypto from "node:crypto";
import { db, initializeDatabase } from "../db";
import { encryptSecret, decryptSecret } from "../model-config";
import { writeAudit } from "../audit";
import { keywordHashes, memoryInput, renderMemories } from "./retrieval.mjs";
let initialization;
export function initializeBrain() {
  if (!initialization)
    initialization = (async () => {
      await initializeDatabase();
      await db.query(`CREATE TABLE IF NOT EXISTS brain_memories (
 id TEXT PRIMARY KEY,owner_user_id TEXT NOT NULL,title TEXT NOT NULL,encrypted_body TEXT NOT NULL,tags TEXT[] NOT NULL DEFAULT '{}',keywords TEXT[] NOT NULL DEFAULT '{}',pinned BOOLEAN NOT NULL DEFAULT FALSE,source TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,expires_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
 CREATE INDEX IF NOT EXISTS idx_brain_owner ON brain_memories(owner_user_id,updated_at DESC); CREATE INDEX IF NOT EXISTS idx_brain_keywords ON brain_memories USING GIN(keywords);`);
    })().catch((error) => {
      initialization = undefined;
      throw error;
    });
  return initialization;
}
const publicMemory = (row) => ({
  id: row.id,
  title: row.title,
  body: decryptSecret(row.encrypted_body),
  tags: row.tags,
  pinned: row.pinned,
  source: row.source,
  revision: row.revision,
  expiresAt: row.expires_at,
  updatedAt: row.updated_at,
});
function secretKey() {
  if (!process.env.FILE_ENCRYPTION_KEY)
    throw Error("BRAIN_ENCRYPTION_UNAVAILABLE");
  return process.env.FILE_ENCRYPTION_KEY;
}
export async function listMemories(userId) {
  await initializeBrain();
  secretKey();
  return (
    await db.query(
      "SELECT * FROM brain_memories WHERE owner_user_id=$1 AND (expires_at IS NULL OR expires_at>NOW()) ORDER BY pinned DESC,updated_at DESC LIMIT 200",
      [userId],
    )
  ).rows.map(publicMemory);
}
export async function saveMemory(session, input) {
  if (session.role === "readonly") throw Error("FORBIDDEN");
  const value = memoryInput(input),
    key = secretKey();
  await initializeBrain();
  const id = input.id || crypto.randomUUID();
  let row;
  if (input.id) {
    if (!Number.isInteger(input.revision)) throw Error("MEMORY_CONFLICT");
    row = (
      await db.query(
        `UPDATE brain_memories SET title=$3,encrypted_body=$4,tags=$5,keywords=$6,pinned=$7,source=$8,expires_at=$9,revision=revision+1,updated_at=NOW() WHERE id=$1 AND owner_user_id=$2 AND revision=$10 RETURNING *`,
        [
          id,
          session.userId,
          value.title,
          encryptSecret(value.body),
          value.tags,
          keywordHashes(
            value.title + " " + value.body + " " + value.tags.join(" "),
            key,
          ),
          value.pinned,
          value.source,
          value.expiresAt,
          input.revision,
        ],
      )
    ).rows[0];
    if (!row) throw Error("MEMORY_CONFLICT");
  } else {
    const client = await db.connect();
    try {
      await client.query("BEGIN");
      await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [
        "brain:" + session.userId,
      ]);
      const count = (
        await client.query(
          "SELECT COUNT(*)::int AS n FROM brain_memories WHERE owner_user_id=$1",
          [session.userId],
        )
      ).rows[0].n;
      if (count >= 200) throw Error("MEMORY_LIMIT");
      row = (
        await client.query(
          `INSERT INTO brain_memories(id,owner_user_id,title,encrypted_body,tags,keywords,pinned,source,expires_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *`,
          [
            id,
            session.userId,
            value.title,
            encryptSecret(value.body),
            value.tags,
            keywordHashes(
              value.title + " " + value.body + " " + value.tags.join(" "),
              key,
            ),
            value.pinned,
            value.source,
            value.expiresAt,
          ],
        )
      ).rows[0];
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
  await writeAudit({
    actor: session.username || session.userId,
    action: input.id ? "brain.correct" : "brain.create",
    resource: id,
    details: { revision: row.revision },
  });
  return publicMemory(row);
}
export async function forgetMemory(session, input) {
  if (session.role === "readonly") throw Error("FORBIDDEN");
  await initializeBrain();
  const result = await db.query(
    "DELETE FROM brain_memories WHERE owner_user_id=$1 AND id=$2 AND revision=$3 RETURNING id",
    [session.userId, input.id, input.revision],
  );
  if (!result.rowCount) throw Error("MEMORY_CONFLICT");
  await writeAudit({
    actor: session.username || session.userId,
    action: "brain.forget",
    resource: input.id,
  });
}
export async function brainContext(userId, query, enabled = true) {
  if (enabled === false || !process.env.FILE_ENCRYPTION_KEY) return "";
  await initializeBrain();
  const hashes = keywordHashes(query, secretKey());
  const rows = (
    await db.query(
      `SELECT *,cardinality(ARRAY(SELECT unnest(keywords) INTERSECT SELECT unnest($2::text[]))) AS score FROM brain_memories WHERE owner_user_id=$1 AND (expires_at IS NULL OR expires_at>NOW()) AND (pinned OR keywords && $2::text[]) ORDER BY pinned DESC,score DESC,updated_at DESC LIMIT 6`,
      [userId, hashes],
    )
  ).rows;
  return renderMemories(rows.map(publicMemory));
}
