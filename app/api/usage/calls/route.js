import { getSession } from "../../../../lib/auth";
import { db, initializeDatabase } from "../../../../lib/db";
import { listUsageCalls } from "../../../../lib/usage-ledger.mjs";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const reply = (body, status = 200) =>
  Response.json(body, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
export async function GET(request) {
  const session = await getSession();
  if (!session) return reply({ error: "Unauthorized" }, 401);
  try {
    await initializeDatabase();
    const params = new URL(request.url).searchParams;
    return reply(
      await listUsageCalls(db, session.userId, {
        after: params.get("after"),
        project: params.get("project"),
        model: params.get("model"),
      }),
    );
  } catch (error) {
    const invalid = ["INVALID_CURSOR", "INVALID_FILTER"].includes(
      error.message,
    );
    return reply(
      { error: invalid ? error.message : "USAGE_UNAVAILABLE" },
      invalid ? 400 : 503,
    );
  }
}
