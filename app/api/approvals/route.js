import { getSession } from "../../../lib/auth";
import { db, initializeDatabase } from "../../../lib/db";
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
  const rows = await db.query(
    "SELECT id,permission,action,description,status,requested_at,decided_at,decided_by,resource_type,resource_id,expires_at,consumed_at FROM approvals ORDER BY requested_at DESC LIMIT 100",
  );
  return Response.json(
    { approvals: rows.rows, pendingCount: count.rows[0].n },
    { headers },
  );
}
