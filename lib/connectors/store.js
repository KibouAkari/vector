import crypto from "node:crypto";
import { db, initializeDatabase } from "../db";
import { encryptSecret, decryptSecret } from "../model-config";
import { writeAudit } from "../audit";
import {
  connectionInput,
  readConnector,
  actionSpec,
  connectorHeaders,
} from "./catalog.mjs";
import {
  connectionUrl,
  connectionAddresses,
  connectorRequest,
} from "./http.mjs";
let initialization;
export function initializeConnections() {
  if (!initialization)
    initialization = (async () => {
      await initializeDatabase();
      await db.query(
        `CREATE TABLE IF NOT EXISTS connector_connections(id TEXT PRIMARY KEY,owner_user_id TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,base TEXT NOT NULL,addresses JSONB NOT NULL,encrypted_credentials TEXT NOT NULL,config JSONB NOT NULL DEFAULT '{}',encrypted_snapshot TEXT,last_synced_at TIMESTAMPTZ,last_error TEXT,sync_claimed_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()); CREATE TABLE IF NOT EXISTS connector_actions(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL REFERENCES connector_connections(id) ON DELETE CASCADE,owner_user_id TEXT NOT NULL,approval_id TEXT NOT NULL REFERENCES approvals(id),scope_digest TEXT NOT NULL,encrypted_spec TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),finished_at TIMESTAMPTZ);`,
      );
    })().catch((error) => {
      initialization = undefined;
      throw error;
    });
  return initialization;
}
function assert(session) {
  if (!session?.userId || !["owner", "admin"].includes(session.role))
    throw Error("FORBIDDEN");
}
const clean = (row) => ({
  id: row.id,
  kind: row.kind,
  name: row.name,
  base: row.base,
  config: row.config,
  snapshot: row.encrypted_snapshot
    ? JSON.parse(decryptSecret(row.encrypted_snapshot))
    : null,
  lastSyncedAt: row.last_synced_at,
  lastError: row.last_error,
});
export async function listConnections(session) {
  assert(session);
  await initializeConnections();
  const rows = (
    await db.query(
      "SELECT * FROM connector_connections WHERE owner_user_id=$1 ORDER BY created_at",
      [session.userId],
    )
  ).rows;
  const actions = (
    await db.query(
      `SELECT c.id,c.connection_id,c.status,c.created_at,c.finished_at,c.scope_digest,c.encrypted_spec,p.status AS approval_status,p.id AS approval_id FROM connector_actions c JOIN approvals p ON p.id=c.approval_id WHERE c.owner_user_id=$1 ORDER BY c.created_at DESC LIMIT 30`,
      [session.userId],
    )
  ).rows;
  return {
    connections: rows.map(clean),
    actions: actions.map(({ encrypted_spec, ...row }) => ({
      ...row,
      spec: JSON.parse(decryptSecret(encrypted_spec)),
    })),
  };
}
export async function saveConnection(session, input) {
  assert(session);
  const value = connectionInput(input),
    url = connectionUrl(value.base),
    addresses = await connectionAddresses(url);
  await initializeConnections();
  const id = crypto.randomUUID();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [
      "connections:" + session.userId,
    ]);
    if (
      (
        await client.query(
          "SELECT COUNT(*)::int AS n FROM connector_connections WHERE owner_user_id=$1",
          [session.userId],
        )
      ).rows[0].n >= 30
    )
      throw Error("CONNECTION_LIMIT");
    await client.query(
      `INSERT INTO connector_connections(id,owner_user_id,kind,name,base,addresses,encrypted_credentials,config) VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,
      [
        id,
        session.userId,
        value.kind,
        value.name,
        url.href.replace(/\/$/, ""),
        JSON.stringify(addresses),
        encryptSecret(
          JSON.stringify({ username: value.username, secret: value.secret }),
        ),
        JSON.stringify({ readPath: value.readPath }),
      ],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
  await writeAudit({
    actor: session.username,
    action: "connection.create",
    resource: id,
    details: { kind: value.kind },
  });
  return { id };
}
async function owned(session, id) {
  assert(session);
  await initializeConnections();
  const row = (
    await db.query(
      "SELECT * FROM connector_connections WHERE id=$1 AND owner_user_id=$2",
      [id, session.userId],
    )
  ).rows[0];
  if (!row) throw Error("CONNECTION_NOT_FOUND");
  return row;
}
export async function syncConnection(session, id) {
  const row = await owned(session, id);
  const claim = await db.query(
    "UPDATE connector_connections SET sync_claimed_at=NOW() WHERE id=$1 AND (sync_claimed_at IS NULL OR sync_claimed_at<NOW()-INTERVAL '15 seconds') RETURNING id",
    [id],
  );
  if (!claim.rowCount) throw Error("CONNECTION_RATE_LIMIT");
  try {
    const snapshot = await readConnector(
      row,
      JSON.parse(decryptSecret(row.encrypted_credentials)),
      (path, options) =>
        connectorRequest(row.base, path, {
          ...options,
          addresses: row.addresses,
        }),
    );
    await db.query(
      "UPDATE connector_connections SET encrypted_snapshot=$2,last_synced_at=NOW(),last_error=NULL WHERE id=$1",
      [id, encryptSecret(JSON.stringify(snapshot))],
    );
    await writeAudit({
      actor: session.username,
      action: "connection.sync",
      resource: id,
    });
    return snapshot;
  } catch (error) {
    const code =
      /^(CONNECTOR_HTTP_\d+|CONNECTION_DNS_CHANGED|HTTPS_REQUIRED|WAZUH_\w+|SLACK_AUTH_FAILED|TARGET_ADDRESS_BLOCKED)$/.test(
        error.message,
      )
        ? error.message
        : "CONNECTOR_SYNC_FAILED";
    await db.query(
      "UPDATE connector_connections SET last_error=$2 WHERE id=$1",
      [id, code],
    );
    throw Error(code);
  }
}
export async function deleteConnection(session, id) {
  await owned(session, id);
  await db.query(
    "UPDATE approvals SET status='rejected',decided_at=NOW(),decided_by=$2 WHERE id IN(SELECT approval_id FROM connector_actions WHERE connection_id=$1) AND status='pending'",
    [id, session.username],
  );
  await db.query(
    "DELETE FROM connector_connections WHERE id=$1 AND owner_user_id=$2",
    [id, session.userId],
  );
  await writeAudit({
    actor: session.username,
    action: "connection.delete",
    resource: id,
  });
}
export async function requestConnectionAction(session, connectionId, input) {
  const row = await owned(session, connectionId),
    spec = actionSpec(row.kind, input),
    id = crypto.randomUUID(),
    approvalId = crypto.randomUUID(),
    scopeDigest = crypto
      .createHash("sha256")
      .update(JSON.stringify({ connectionId, base: row.base, spec }))
      .digest("hex");
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [
      "connector-actions:" + session.userId,
    ]);
    const pending = (
      await client.query(
        "SELECT COUNT(*)::int AS n FROM connector_actions a JOIN approvals p ON p.id=a.approval_id WHERE a.owner_user_id=$1 AND a.status='pending' AND p.status IN('pending','approved') AND p.expires_at>NOW()",
        [session.userId],
      )
    ).rows[0].n;
    if (pending >= 20) throw Error("CONNECTION_ACTION_LIMIT");
    await client.query(
      `INSERT INTO approvals(id,permission,action,description,resource_type,resource_id,scope_digest,requested_by,expires_at) VALUES($1,'connector_write','connector.action',$2,'connector-action',$3,$4,$5,NOW()+INTERVAL '24 hours')`,
      [
        approvalId,
        `${row.name}: ${spec.method} ${spec.path}. Open Connections to inspect exact content before execution.`,
        id,
        scopeDigest,
        session.userId,
      ],
    );
    await client.query(
      `INSERT INTO connector_actions(id,connection_id,owner_user_id,approval_id,scope_digest,encrypted_spec) VALUES($1,$2,$3,$4,$5,$6)`,
      [
        id,
        connectionId,
        session.userId,
        approvalId,
        scopeDigest,
        encryptSecret(JSON.stringify(spec)),
      ],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
  await writeAudit({
    actor: session.username,
    action: "connection.action.request",
    resource: id,
    details: { scopeDigest },
  });
  return { id, approvalId };
}
export async function executeConnectionAction(session, id) {
  assert(session);
  await initializeConnections();
  const client = await db.connect();
  let row, action;
  try {
    await client.query("BEGIN");
    action = (
      await client.query(
        `SELECT c.* FROM connector_actions c JOIN approvals p ON p.id=c.approval_id WHERE c.id=$1 AND c.owner_user_id=$2 AND c.status='pending' AND p.status='approved' AND p.consumed_at IS NULL AND p.expires_at>NOW() AND p.scope_digest=c.scope_digest AND p.resource_type='connector-action' AND p.resource_id=c.id FOR UPDATE OF c,p`,
        [id, session.userId],
      )
    ).rows[0];
    if (!action) throw Error("APPROVED_ACTION_REQUIRED");
    row = (
      await client.query(
        "SELECT * FROM connector_connections WHERE id=$1 AND owner_user_id=$2 FOR UPDATE",
        [action.connection_id, session.userId],
      )
    ).rows[0];
    if (!row) throw Error("CONNECTION_NOT_FOUND");
    const spec = JSON.parse(decryptSecret(action.encrypted_spec));
    if (
      crypto
        .createHash("sha256")
        .update(JSON.stringify({ connectionId: row.id, base: row.base, spec }))
        .digest("hex") !== action.scope_digest
    )
      throw Error("ACTION_SCOPE_CHANGED");
    await client.query(
      "UPDATE connector_actions SET status='running' WHERE id=$1",
      [id],
    );
    await client.query("UPDATE approvals SET consumed_at=NOW() WHERE id=$1", [
      action.approval_id,
    ]);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
  try {
    const spec = JSON.parse(decryptSecret(action.encrypted_spec)),
      credentials = JSON.parse(decryptSecret(row.encrypted_credentials));
    const result = await connectorRequest(row.base, spec.path, {
      method: spec.method,
      headers: connectorHeaders(row.kind, credentials),
      body: spec.body,
      addresses: row.addresses,
    });
    if (row.kind === "slack" && result.ok !== true)
      throw Error("ACTION_REJECTED");
    await db.query(
      "UPDATE connector_actions SET status='completed',finished_at=NOW() WHERE id=$1",
      [id],
    );
    await writeAudit({
      actor: session.username,
      action: "connection.action.completed",
      resource: id,
    });
    return { ok: true };
  } catch {
    await db.query(
      "UPDATE connector_actions SET status='uncertain',finished_at=NOW() WHERE id=$1",
      [id],
    );
    await writeAudit({
      actor: session.username,
      action: "connection.action.uncertain",
      resource: id,
    });
    throw Error("ACTION_COMPLETION_UNCERTAIN_DO_NOT_RETRY");
  }
}
