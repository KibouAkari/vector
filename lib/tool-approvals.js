import crypto from "node:crypto";
import { db, initializeDatabase } from "./db";
import {
  deterministicFindings,
  literalReplace,
  makePrivacyPlan,
} from "./privacy-review-core.mjs";
const permissions = {
  network_scan: "network.scan",
  sandbox_run: "sandbox.execute",
  sandbox_write_file: "sandbox.write",
};
function canonical(value) {
  return Array.isArray(value)
    ? value.map(canonical)
    : value && typeof value === "object"
      ? Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((key) => [key, canonical(value[key])]),
        )
      : value;
}
export async function toolApproval({ userId, projectId, name, args }) {
  const permission = permissions[name];
  if (!permission || !userId) return null;
  await initializeDatabase();
  const hash = crypto
    .createHash("sha256")
    .update(JSON.stringify([userId, projectId || null, name, canonical(args)]))
    .digest("hex");
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [
      "tool-approval:" + hash,
    ]);
    const policy = (
      await client.query(
        "SELECT decision FROM permission_policies WHERE permission=$1",
        [permission],
      )
    ).rows[0];
    if (policy?.decision === "DENY") {
      await client.query("COMMIT");
      return { ok: false, error: "TOOL_POLICY_DENIED" };
    }
    if (policy?.decision === "ALLOW") {
      await client.query("COMMIT");
      return null;
    }
    const grant = await client.query(
      "UPDATE approvals SET consumed_at=NOW() WHERE id=(SELECT id FROM approvals WHERE scope_digest=$1 AND requested_by=$2 AND resource_type='tool' AND status='approved' AND consumed_at IS NULL AND expires_at>NOW() ORDER BY requested_at DESC LIMIT 1 FOR UPDATE) RETURNING id",
      [hash, userId],
    );
    if (grant.rowCount) {
      await client.query(
        "INSERT INTO audit_log(id,actor,action,resource,details,source) VALUES ($1,$2,'approval.consumed',$3,'{}','worker')",
        [crypto.randomUUID(), userId, grant.rows[0].id],
      );
      await client.query("COMMIT");
      return null;
    }
    let pending = (
      await client.query(
        "SELECT id FROM approvals WHERE scope_digest=$1 AND requested_by=$2 AND resource_type='tool' AND status='pending' AND expires_at>NOW() LIMIT 1",
        [hash, userId],
      )
    ).rows[0];
    if (!pending) {
      const count = (
        await client.query(
          "SELECT COUNT(*)::int AS n FROM approvals WHERE requested_by=$1 AND status='pending' AND expires_at>NOW()",
          [userId],
        )
      ).rows[0].n;
      if (count >= 20) {
        await client.query("COMMIT");
        return { ok: false, error: "APPROVAL_QUEUE_LIMIT" };
      }
      const text = JSON.stringify(args);
      const plan = makePrivacyPlan(text, deterministicFindings(text));
      pending = { id: crypto.randomUUID() };
      await client.query(
        "INSERT INTO approvals(id,permission,action,description,status,resource_type,resource_id,scope_digest,requested_by,expires_at) VALUES ($1,$2,$3,$4,'pending','tool',$5,$6,$7,NOW()+INTERVAL '15 minutes')",
        [
          pending.id,
          permission,
          name,
          literalReplace(text, plan.mappings),
          projectId || null,
          hash,
          userId,
        ],
      );
    }
    await client.query("COMMIT");
    return {
      ok: false,
      error: "APPROVAL_REQUIRED",
      approvalId: pending.id,
      message:
        "Owner approval is required in Approvals. After approval, retry this exact action. Authorization expires after 15 minutes and can be used once.",
    };
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
