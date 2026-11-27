import crypto from "node:crypto";
import { db, initializeDatabase } from "./db";
import { normalizeRolePolicy, roleAllows, ROLES } from "./role-policy.mjs";
let initialized;
export function initializeAccessPolicies() {
  if (!initialized)
    initialized = (async () => {
      await initializeDatabase();
      await db.query(
        `CREATE TABLE IF NOT EXISTS role_capability_policies (role TEXT PRIMARY KEY,policy JSONB NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_by TEXT NOT NULL)`,
      );
    })().catch((error) => {
      initialized = undefined;
      throw error;
    });
  return initialized;
}
export async function executionAccount(userId) {
  await initializeAccessPolicies();
  const row = (
    await db.query(
      "SELECT u.id,u.role,u.enabled,u.expires_at,p.policy FROM vector_users u LEFT JOIN role_capability_policies p ON p.role=u.role WHERE u.id=$1",
      [userId],
    )
  ).rows[0];
  if (
    !row ||
    !row.enabled ||
    (row.expires_at && new Date(row.expires_at) <= new Date()) ||
    row.role === "readonly"
  )
    throw Object.assign(Error("This account cannot execute tasks."), {
      code: "EXECUTION_FORBIDDEN",
    });
  return row;
}
export async function assertModelAccess(runtime) {
  if (!runtime?.requestingUserId) return;
  const row = await executionAccount(runtime.requestingUserId);
  if (
    row.role !== "owner" &&
    !roleAllows(row.policy, "models", runtime.provider + "/" + runtime.model)
  )
    throw Object.assign(Error("This model is not allowed for your role."), {
      code: "MODEL_POLICY_DENIED",
    });
}
export async function assertToolAccess(userId, name) {
  if (!userId) return;
  const row = await executionAccount(userId);
  if (row.role !== "owner" && !roleAllows(row.policy, "tools", name))
    throw Object.assign(Error("This tool is not allowed for your role."), {
      code: "TOOL_POLICY_DENIED",
    });
}
export async function setRolePolicy(session, role, input) {
  if (session?.role !== "owner" || !ROLES.includes(role) || role === "owner")
    throw Error("FORBIDDEN");
  const policy = normalizeRolePolicy(input);
  await initializeAccessPolicies();
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "INSERT INTO role_capability_policies(role,policy,updated_by) VALUES ($1,$2,$3) ON CONFLICT(role) DO UPDATE SET policy=$2,updated_by=$3,updated_at=NOW()",
      [role, JSON.stringify(policy), session.userId],
    );
    await client.query(
      "INSERT INTO audit_log(id,actor,action,resource,details,source) VALUES ($1,$2,'policy.role.updated',$3,$4,'web')",
      [crypto.randomUUID(), session.username, role, JSON.stringify(policy)],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
