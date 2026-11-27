import crypto from 'node:crypto';
import {initializeConnections} from '../../../lib/connectors/store';
import {decryptSecret} from '../../../lib/model-config';
import { getSession } from "../../../lib/auth";
import { db, initializeDatabase } from "../../../lib/db";
import { initializeScanner } from "../../../lib/security/scan-store";
import { securityApprovalScope } from "../../../lib/security/approval-scope.mjs";
export const dynamic = "force-dynamic";
export async function GET(request) {
  const session = await getSession();
  if (!session || session.role !== "owner")
    return Response.json({ error: "Forbidden" }, { status: 403 });
  await initializeDatabase();
  const count = await db.query(
    "SELECT COUNT(*)::int AS n FROM approvals WHERE status='pending' AND (expires_at IS NULL OR expires_at>NOW())",
  );
  const headers = { "Cache-Control": "private, no-store" };
  if (new URL(request.url).searchParams.get("summary") === "1")
    return Response.json({ pendingCount: count.rows[0].n }, { headers });
  await initializeScanner();

  const rows = await db.query(
    `SELECT p.id,p.permission,p.action,p.description,p.status,p.requested_at,p.decided_at,p.decided_by,p.resource_type,p.resource_id,p.expires_at,p.consumed_at,
      p.requested_by,u.username AS requester,p.scope_digest,a.id AS asset_id,a.approval_id,a.owner_user_id,a.active,a.scope,a.scope_digest AS asset_scope_digest
      FROM approvals p LEFT JOIN vector_users u ON u.id=p.requested_by
      LEFT JOIN security_assets a ON p.resource_type='security-asset' AND a.id=p.resource_id AND a.approval_id=p.id
      ORDER BY p.requested_at DESC LIMIT 100`,
  );
  if(rows.rows.some(row=>row.resource_type==='connector-action'))await initializeConnections();
  const connectorRows=rows.rows.some(row=>row.resource_type==='connector-action')?(await db.query(`SELECT c.id,c.approval_id,c.scope_digest,c.encrypted_spec,n.name,n.base,n.id AS connection_id FROM connector_actions c JOIN connector_connections n ON n.id=c.connection_id JOIN approvals p ON p.id=c.approval_id WHERE p.resource_type='connector-action' ORDER BY c.created_at DESC LIMIT 100`)).rows:[];
  const connectorScopes=new Map(connectorRows.map(row=>{const spec=JSON.parse(decryptSecret(row.encrypted_spec));const digest=crypto.createHash('sha256').update(JSON.stringify({connectionId:row.connection_id,base:row.base,spec})).digest('hex');return[row.approval_id,digest===row.scope_digest?{...spec,connection:row.name,base:row.base,digest}:null]}));
  const approvals = rows.rows.map(({ scope, asset_scope_digest, asset_id, approval_id, owner_user_id, active, ...row }) => {
    const verified = row.resource_type === "security-asset"
      ? securityApprovalScope({ ...row, scope, asset_scope_digest, asset_id, approval_id, owner_user_id, active })
      : null;
    const connectorScope=row.resource_type==='connector-action'?connectorScopes.get(row.id):null;
    if(row.resource_type==='connector-action')return{...row,scope_digest:connectorScope?.digest||null,scope:connectorScope||null};
    return { ...row, scope_digest: verified ? row.scope_digest : null, ...(row.resource_type === "security-asset" ? { scope: verified } : {}) };
  });
  return Response.json(
    { approvals, pendingCount: count.rows[0].n },
    { headers },
  );
}
