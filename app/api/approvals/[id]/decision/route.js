import {decryptSecret} from '../../../../../lib/model-config';
import crypto from "node:crypto";
import { getSession } from "../../../../../lib/auth";
import { db, initializeDatabase } from "../../../../../lib/db";
import { boundedJson } from "../../../../../lib/bounded-json.mjs";
import { securityApprovalScope } from "../../../../../lib/security/approval-scope.mjs";
export const runtime = "nodejs";
export async function POST(request, context) {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (session.role !== "owner")
    return Response.json({ error: "Owner access required" }, { status: 403 });
  let body;
  try {
    body = await boundedJson(request, { maxBytes: 4096 });
  } catch {
    return Response.json({ error: "Invalid request" }, { status: 400 });
  }
  if (!["approved", "rejected"].includes(body.decision))
    return Response.json({ error: "Invalid decision" }, { status: 400 });
  const { id } = await context.params;
  await initializeDatabase();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    const result = await client.query(
      `UPDATE approvals SET status=$1,decided_at=NOW(),decided_by=$2 WHERE id=$3 AND status='pending' AND (expires_at IS NULL OR expires_at>NOW()) RETURNING permission,action,resource_type,resource_id,scope_digest`,
      [body.decision, session.username, id],
    );
    if (!result.rowCount) {
      await client.query("ROLLBACK");
      return Response.json(
        { error: "Approval not found, expired or already decided" },
        { status: 404 },
      );
    }
    if (result.rows[0].resource_type === "security-asset" && body.decision === "approved") {
      const asset = await client.query(
        `SELECT p.id,p.resource_id,p.requested_by,p.scope_digest,a.id AS asset_id,a.approval_id,a.owner_user_id,a.active,a.scope,a.scope_digest AS asset_scope_digest
         FROM approvals p JOIN security_assets a ON a.id=p.resource_id AND a.approval_id=p.id WHERE p.id=$1 FOR UPDATE OF a`,
        [id],
      );
      if (!asset.rowCount || body.scopeDigest !== result.rows[0].scope_digest || !securityApprovalScope(asset.rows[0])) {
        await client.query("ROLLBACK");
        return Response.json({ error: "ASSET_SCOPE_CHANGED" }, { status: 409 });
      }
    }
    if(result.rows[0].resource_type==='connector-action'&&body.decision==='approved'){
      const action=(await client.query(`SELECT c.scope_digest,c.encrypted_spec,n.id AS connection_id,n.base FROM connector_actions c JOIN connector_connections n ON n.id=c.connection_id WHERE c.id=$1 AND c.approval_id=$2 AND c.status='pending' FOR UPDATE OF c,n`,[result.rows[0].resource_id,id])).rows[0];
      const spec=action?JSON.parse(decryptSecret(action.encrypted_spec)):null;
      const digest=action?crypto.createHash('sha256').update(JSON.stringify({connectionId:action.connection_id,base:action.base,spec})).digest('hex'):null;
      if(!action||digest!==action.scope_digest||body.scopeDigest!==digest||result.rows[0].scope_digest!==digest){await client.query('ROLLBACK');return Response.json({error:'ACTION_SCOPE_CHANGED'},{status:409});}
    }
    await client.query(
      "INSERT INTO audit_log(id,actor,action,resource,details,source) VALUES ($1,$2,$3,$4,$5,'web')",
      [
        crypto.randomUUID(),
        session.username,
        "approval." + body.decision,
        id,
        JSON.stringify(result.rows[0]),
      ],
    );
    await client.query("COMMIT");
    return Response.json({ ok: true });
  } catch {
    await client.query("ROLLBACK");
    return Response.json({ error: "APPROVAL_UPDATE_FAILED" }, { status: 503 });
  } finally {
    client.release();
  }
}
