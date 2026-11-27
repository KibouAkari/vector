import { getSession, hasFeature } from "../../../lib/auth";
import { db } from "../../../lib/db";
import { initializeTeams } from "../../../lib/teams/runtime";
export async function GET() {
  const session = await getSession();
  if (!session || !hasFeature(session, "projects"))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  await initializeTeams();
  return Response.json(
    {
      steps: (
        await db.query(
          "SELECT s.job_id,s.role,s.status,s.provider,s.model,s.started_at,s.finished_at,l.used_calls,l.max_calls FROM agent_team_steps s JOIN agent_team_limits l ON l.job_id=s.job_id WHERE s.owner_user_id=$1 ORDER BY s.started_at DESC LIMIT 60",
          [session.userId],
        )
      ).rows,
    },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
