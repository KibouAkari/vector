import { getSession } from "../../../lib/auth";
import { boundedJson } from "../../../lib/bounded-json.mjs";
import { listBudgets, saveBudget } from "../../../lib/provider-budgets";
export const dynamic = "force-dynamic";
export async function GET() {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  return Response.json(await listBudgets(session), {
    headers: { "Cache-Control": "private, no-store" },
  });
}
export async function POST(request) {
  const session = await getSession();
  if (session?.role !== "owner")
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    await saveBudget(session, await boundedJson(request));
    return Response.json({ ok: true });
  } catch {
    return Response.json({ error: "INVALID_BUDGET" }, { status: 400 });
  }
}
