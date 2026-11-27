import crypto from "node:crypto";
import { getSession } from "../../../../lib/auth";
import { db, initializeDatabase } from "../../../../lib/db";
import { boundedJson } from "../../../../lib/bounded-json.mjs";
import {
  initializeAccessPolicies,
  setRolePolicy,
} from "../../../../lib/access-controls";
export const dynamic = "force-dynamic";
export async function GET() {
  const session = await getSession();
  if (session?.role !== "owner")
    return Response.json({ error: "Forbidden" }, { status: 403 });
  await initializeAccessPolicies();
  const [permissions, roles] = await Promise.all([
    db.query(
      "SELECT permission,decision,description FROM permission_policies ORDER BY permission",
    ),
    db.query(
      "SELECT role,policy,updated_at FROM role_capability_policies ORDER BY role",
    ),
  ]);
  return Response.json(
    { permissions: permissions.rows, roles: roles.rows },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
export async function POST(request) {
  const session = await getSession();
  if (session?.role !== "owner")
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    const input = await boundedJson(request);
    if (input.role) {
      await setRolePolicy(session, input.role, input.policy);
      return Response.json({ ok: true });
    }
    if (
      !["network.scan", "sandbox.execute", "sandbox.write"].includes(
        input.permission,
      ) ||
      !["ALLOW", "ASK", "DENY"].includes(input.decision)
    )
      return Response.json({ error: "INVALID_POLICY" }, { status: 400 });
    await initializeDatabase();
    const client = await db.connect();
    try {
      await client.query("BEGIN");
      await client.query(
        "INSERT INTO permission_policies(permission,decision,description) VALUES ($1,$2,$3) ON CONFLICT(permission) DO UPDATE SET decision=$2",
        [input.permission, input.decision, "Execution policy"],
      );
      await client.query(
        "INSERT INTO audit_log(id,actor,action,resource,details,source) VALUES ($1,$2,'policy.permission.updated',$3,$4,'web')",
        [
          crypto.randomUUID(),
          session.username,
          input.permission,
          JSON.stringify({ decision: input.decision }),
        ],
      );
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
    return Response.json({ ok: true });
  } catch {
    return Response.json({ error: "INVALID_POLICY" }, { status: 400 });
  }
}
