import { getSession, hasFeature } from "../../../../lib/auth";
import { ownActivity } from "../../../../lib/traffic/activity";
export async function GET() {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (!hasFeature(session, "chat") && !hasFeature(session, "projects"))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    return Response.json(await ownActivity(session.userId), {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch {
    return Response.json({ error: "ACTIVITY_UNAVAILABLE" }, { status: 503 });
  }
}
