import crypto from "node:crypto";
import { db, initializeDatabase } from "../db";
import { parseTarget, resolveTarget, ScanError } from "./targets.mjs";
import { validatePackages } from "./advisories.mjs";
import { runActiveScan } from "./active-scan.mjs";
import { securityApprovalScope } from "./approval-scope.mjs";
let initialized;
export function initializeScanner() {
  if (!initialized)
    initialized = (async () => {
      await initializeDatabase();
      await db.query(`CREATE TABLE IF NOT EXISTS security_assets (
 id TEXT PRIMARY KEY,owner_user_id TEXT NOT NULL,request_id TEXT NOT NULL,request_digest TEXT NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,scope JSONB NOT NULL,scope_digest TEXT NOT NULL,
 approval_id TEXT REFERENCES approvals(id),active BOOLEAN NOT NULL DEFAULT TRUE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)`);
      await db.query(`CREATE TABLE IF NOT EXISTS security_scan_runs (
 id TEXT PRIMARY KEY,asset_id TEXT NOT NULL REFERENCES security_assets(id),user_id TEXT NOT NULL,scope_digest TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled')),progress JSONB NOT NULL DEFAULT '{}',
 result JSONB,error TEXT,cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),started_at TIMESTAMPTZ,finished_at TIMESTAMPTZ
)`);
      await db.query(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_security_asset_request ON security_assets(owner_user_id,request_id)",
      );
      await db.query(
        "CREATE INDEX IF NOT EXISTS idx_security_scan_queue ON security_scan_runs(status,created_at)",
      );
    })().catch((error) => {
      initialized = undefined;
      throw error;
    });
  return initialized;
}
const digest = (scope) =>
  crypto.createHash("sha256").update(JSON.stringify(scope)).digest("hex");
const assertOperator = (session) => {
  if (!session?.userId || !["owner", "admin"].includes(session.role))
    throw new ScanError("FORBIDDEN");
};
const assetRow = (row) => ({
  id: row.id,
  name: row.name,
  kind: row.kind,
  scope: row.scope,
  active: row.active,
  approvalId: row.approval_id,
  approvalStatus: row.approval_status,
  createdAt: row.created_at,
});
async function audit(client, session, action, id) {
  await client.query(
    "INSERT INTO audit_log (id,actor,action,resource,details,source) VALUES ($1,$2,$3,$4,'{}','web')",
    [crypto.randomUUID(), session.username || session.userId, action, id],
  );
}
export async function scannerOverview(session) {
  assertOperator(session);
  await initializeScanner();
  const [assets, runs] = await Promise.all([
    db.query(
      "SELECT a.*,p.status AS approval_status FROM security_assets a LEFT JOIN approvals p ON p.id=a.approval_id WHERE a.owner_user_id=$1 AND a.active=TRUE ORDER BY a.created_at DESC LIMIT 50",
      [session.userId],
    ),
    db.query(
      "SELECT id,asset_id,status,progress,error,created_at,started_at,finished_at,result FROM security_scan_runs WHERE user_id=$1 ORDER BY created_at DESC LIMIT 30",
      [session.userId],
    ),
  ]);
  return {
    assets: assets.rows.map(assetRow),
    runs: runs.rows.map((row) => ({
      ...row,
      result: row.result
        ? {
            counts: row.result.counts,
            complete: row.result.complete,
            durationMs: row.result.durationMs,
          }
        : null,
    })),
    privateTargetsConfigured: Boolean(
      process.env.VECTOR_SECURITY_PRIVATE_CIDRS,
    ),
  };
}
export async function saveSecurityAsset(session, input) {
  assertOperator(session);
  await initializeScanner();
  const name = typeof input.name === "string" ? input.name.trim() : "";
  if (
    name.length < 2 ||
    name.length > 100 ||
    !["web", "api", "minecraft", "nas", "network"].includes(input.kind) ||
    input.authorized !== true
  )
    throw new ScanError("ASSET_AUTHORIZATION_REQUIRED");
  if (
    typeof input.requestId !== "string" ||
    !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(input.requestId)
  )
    throw new ScanError("INVALID_REQUEST_ID");
  const target = parseTarget(input.target, input.ports),
    packages = validatePackages(input.packages);
  const requestHash = digest({
    name,
    kind: input.kind,
    target,
    packages,
    checkAdvisories: input.checkAdvisories === true,
  });
  const existing = (
    await db.query(
      "SELECT a.*,p.status AS approval_status FROM security_assets a JOIN approvals p ON p.id=a.approval_id WHERE a.owner_user_id=$1 AND a.request_id=$2",
      [session.userId, input.requestId],
    )
  ).rows[0];
  if (existing) {
    if (existing.request_digest !== requestHash)
      throw new ScanError("REQUEST_CONFLICT");
    return {
      id: existing.id,
      approvalId: existing.approval_id,
      approvalStatus: existing.approval_status,
    };
  }
  const addresses = await resolveTarget(target);
  const scope = {
    target,
    addresses,
    packages,
    checkAdvisories: input.checkAdvisories === true,
  };
  const scopeHash = digest(scope),
    id = crypto.randomUUID(),
    approvalId = crypto.randomUUID();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-security-assets'))",
    );
    const count = await client.query(
      "SELECT COUNT(*)::int AS n FROM security_assets WHERE owner_user_id=$1 AND active=TRUE",
      [session.userId],
    );
    if (count.rows[0].n >= 50) throw new ScanError("ASSET_LIMIT");
    const retry = (
      await client.query(
        "SELECT a.*,p.status AS approval_status FROM security_assets a JOIN approvals p ON p.id=a.approval_id WHERE a.owner_user_id=$1 AND a.request_id=$2",
        [session.userId, input.requestId],
      )
    ).rows[0];
    if (retry) {
      if (retry.request_digest !== requestHash)
        throw new ScanError("REQUEST_CONFLICT");
      await client.query("COMMIT");
      return {
        id: retry.id,
        approvalId: retry.approval_id,
        approvalStatus: retry.approval_status,
      };
    }
    // Owner confirmation grants this exact saved scope; admins request owner approval.
    const approved = session.role === "owner";
    await client.query(
      `INSERT INTO approvals (id,permission,action,description,status,resource_type,resource_id,scope_digest,requested_by,decided_by,decided_at)
   VALUES ($1,'network.scan',$2,$3,$4,'security-asset',$5,$6,$7,$8,CASE WHEN $4='approved' THEN NOW() ELSE NULL END)`,
      [
        approvalId,
        "Scan " + name,
        "Saved asset authorization for bounded TCP/web probes.",
        approved ? "approved" : "pending",
        id,
        scopeHash,
        session.userId,
        approved ? session.username : null,
      ],
    );
    await client.query(
      "INSERT INTO security_assets (id,owner_user_id,name,kind,scope,scope_digest,approval_id,request_id,request_digest) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
      [
        id,
        session.userId,
        name,
        input.kind,
        JSON.stringify(scope),
        scopeHash,
        approvalId,
        input.requestId,
        requestHash,
      ],
    );
    await audit(client, session, "security.asset.authorized", id);
    await client.query("COMMIT");
    return {
      id,
      approvalId,
      approvalStatus: approved ? "approved" : "pending",
    };
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
export async function queueSecurityScan(session, input) {
  assertOperator(session);
  await initializeScanner();
  if (typeof input.assetId !== "string") throw new ScanError("INVALID_ASSET");
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-security-queue'))",
    );
    const row = (
      await client.query(
        "SELECT a.*,p.id AS approval_record_id,p.resource_id AS approval_resource_id,p.requested_by,p.status AS approval_status,p.scope_digest AS approved_digest FROM security_assets a JOIN approvals p ON p.id=a.approval_id WHERE a.id=$1 AND a.owner_user_id=$2 AND a.active=TRUE FOR UPDATE OF a",
        [input.assetId, session.userId],
      )
    ).rows[0];
    if (!row) throw new ScanError("NOT_FOUND");
    if (
      row.approval_status !== "approved" ||
      !securityApprovalScope({ ...row, id: row.approval_record_id, resource_id: row.approval_resource_id, asset_id: row.id, scope_digest: row.approved_digest, asset_scope_digest: row.scope_digest })
    )
      throw new ScanError("APPROVAL_REQUIRED");
    const pending = (
      await client.query(
        "SELECT COUNT(*)::int AS n FROM security_scan_runs WHERE user_id=$1 AND status IN ('queued','running')",
        [session.userId],
      )
    ).rows[0].n;
    if (pending >= 3) throw new ScanError("SCAN_QUEUE_LIMIT");
    if (
      (
        await client.query(
          "SELECT id FROM security_scan_runs WHERE asset_id=$1 AND created_at>NOW()-INTERVAL '60 seconds' LIMIT 1",
          [row.id],
        )
      ).rowCount
    )
      throw new ScanError("SCAN_COOLDOWN");
    const id = crypto.randomUUID();
    await client.query(
      "INSERT INTO security_scan_runs(id,asset_id,user_id,scope_digest,status) VALUES ($1,$2,$3,$4,'queued')",
      [id, row.id, session.userId, row.scope_digest],
    );
    await audit(client, session, "security.scan.queued", id);
    await client.query("COMMIT");
    return { id, status: "queued" };
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
export async function getSecurityRun(session, id) {
  assertOperator(session);
  await initializeScanner();
  return (
    (
      await db.query(
        "SELECT r.*,a.name AS asset_name,a.scope FROM security_scan_runs r JOIN security_assets a ON a.id=r.asset_id WHERE r.id=$1 AND r.user_id=$2",
        [id, session.userId],
      )
    ).rows[0] || null
  );
}
export async function cancelSecurityRun(session, id) {
  assertOperator(session);
  await initializeScanner();
  await db.query(
    "UPDATE security_scan_runs SET cancel_requested=TRUE,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=$1 AND user_id=$2 AND status IN ('queued','running')",
    [id, session.userId],
  );
}
export async function revokeSecurityAsset(session, id) {
  assertOperator(session);
  await initializeScanner();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    const result = await client.query(
      "UPDATE security_assets SET active=FALSE WHERE id=$1 AND owner_user_id=$2 RETURNING approval_id",
      [id, session.userId],
    );
    if (!result.rowCount) throw new ScanError("NOT_FOUND");
    await client.query(
      "UPDATE approvals SET status='rejected',decided_at=NOW(),decided_by=$2 WHERE id=$1",
      [result.rows[0].approval_id, session.username],
    );
    await client.query(
      "UPDATE security_scan_runs SET cancel_requested=TRUE,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE asset_id=$1 AND status IN ('queued','running')",
      [id],
    );
    await audit(client, session, "security.asset.revoked", id);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
export async function runNextSecurityScan() {
  await initializeScanner();
  const client = await db.connect();
  let row;
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtext('vector-security-queue'))",
    );
    await client.query(
      "UPDATE security_scan_runs SET status='failed',error='WORKER_INTERRUPTED',finished_at=NOW() WHERE status='running' AND started_at<NOW()-INTERVAL '5 minutes'",
    );
    if (
      (
        await client.query(
          "SELECT id FROM security_scan_runs WHERE status='running' LIMIT 1",
        )
      ).rowCount
    ) {
      await client.query("COMMIT");
      return null;
    }
    row = (
      await client.query(
        "SELECT r.*,a.scope,a.kind,a.active,a.owner_user_id,a.approval_id,a.scope_digest AS current_digest,p.id AS approval_record_id,p.resource_id AS approval_resource_id,p.requested_by,p.status AS approval_status,p.scope_digest AS approved_digest,u.enabled,u.role FROM security_scan_runs r JOIN security_assets a ON a.id=r.asset_id JOIN approvals p ON p.id=a.approval_id JOIN vector_users u ON u.id=r.user_id WHERE r.status='queued' ORDER BY r.created_at LIMIT 1 FOR UPDATE OF r SKIP LOCKED",
      )
    ).rows[0];
    if (!row) {
      await client.query("COMMIT");
      return null;
    }
    await client.query(
      "UPDATE security_scan_runs SET status='running',started_at=NOW() WHERE id=$1",
      [row.id],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
  const controller = new AbortController();
  let cancelled = false;
  try {
    if (
      !row.active ||
      !row.enabled ||
      !["owner", "admin"].includes(row.role) ||
      row.approval_status !== "approved" ||
      row.scope_digest !== row.current_digest ||
      !securityApprovalScope({ ...row, id: row.approval_record_id, resource_id: row.approval_resource_id, scope_digest: row.approved_digest, asset_scope_digest: row.current_digest })
    )
      throw new ScanError("AUTHORIZATION_CHANGED");
    const result = await runActiveScan(
      { ...row.scope, kind: row.kind },
      {
        signal: controller.signal,
        onProgress: async (progress) => {
          const current = (
            await db.query(
              "SELECT r.cancel_requested,a.active,p.status,u.enabled,u.role FROM security_scan_runs r JOIN security_assets a ON a.id=r.asset_id JOIN approvals p ON p.id=a.approval_id JOIN vector_users u ON u.id=r.user_id WHERE r.id=$1",
              [row.id],
            )
          ).rows[0];
          if (
            !current?.active ||
            !current.enabled ||
            !["owner", "admin"].includes(current.role) ||
            current.status !== "approved" ||
            current.cancel_requested
          ) {
            cancelled = true;
            controller.abort();
            return;
          }
          await db.query(
            "UPDATE security_scan_runs SET progress=$2 WHERE id=$1",
            [row.id, JSON.stringify(progress)],
          );
        },
      },
    );
    const current = await db.query(
      "SELECT cancel_requested FROM security_scan_runs WHERE id=$1",
      [row.id],
    );
    cancelled = cancelled || current.rows[0]?.cancel_requested;
    await db.query(
      "UPDATE security_scan_runs SET status=$2,result=$3,finished_at=NOW() WHERE id=$1",
      [row.id, cancelled ? "cancelled" : "completed", JSON.stringify(result)],
    );
  } catch (error) {
    await db.query(
      "UPDATE security_scan_runs SET status=$2,error=$3,finished_at=NOW() WHERE id=$1",
      [
        row.id,
        cancelled ? "cancelled" : "failed",
        error instanceof ScanError ? error.code : "SCAN_FAILED",
      ],
    );
  }
  return { id: row.id };
}
