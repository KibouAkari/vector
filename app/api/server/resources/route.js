import { getSession, hasFeature } from "../../../../lib/auth";
import { hostResources } from "../../../../lib/traffic/store";
export async function GET() {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (!hasFeature(session, "server"))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    return Response.json(await hostResources(), {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch {
    return Response.json(
      { error: "HOST_METRICS_UNAVAILABLE" },
      { status: 503 },
    );
  }
}
