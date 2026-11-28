import { db, initializeDatabase } from "../db";
export async function ownActivity(userId) {
  await initializeDatabase();
  const tables = (
    await db.query(
      "SELECT to_regclass('agent_jobs') AS jobs,to_regclass('security_scan_runs') AS scans",
    )
  ).rows[0];
  const jobs = tables.jobs
    ? (
        await db.query(
          "SELECT j.id,j.conversation_id,j.status,j.progress,j.created_at,j.started_at,j.completed_at AS finished_at,c.title FROM agent_jobs j LEFT JOIN conversations c ON c.id=j.conversation_id AND COALESCE(to_jsonb(c)->>'user_id',c.owner_user_id)=j.user_id WHERE j.user_id=$1 ORDER BY j.created_at DESC LIMIT 12",
          [userId],
        )
      ).rows
    : [];
  const scans = tables.scans
    ? (
        await db.query(
          "SELECT r.id,r.status,r.progress,r.created_at,r.started_at,r.finished_at,a.name FROM security_scan_runs r JOIN security_assets a ON a.id=r.asset_id AND a.owner_user_id=r.user_id WHERE r.user_id=$1 ORDER BY r.created_at DESC LIMIT 12",
          [userId],
        )
      ).rows
    : [];
  const counts = tables.jobs
    ? (
        await db.query(
          "SELECT COUNT(*) FILTER(WHERE status='running')::int AS running,COUNT(*) FILTER(WHERE status='queued')::int AS queued,COUNT(*) FILTER(WHERE status='completed')::int AS completed,COUNT(*) FILTER(WHERE status='failed')::int AS failed FROM agent_jobs WHERE user_id=$1 AND (created_at>NOW()-INTERVAL '24 hours' OR status IN('running','queued'))",
          [userId],
        )
      ).rows[0]
    : null;
  return {
    counts,
    jobs: jobs.map((row) => ({
      id: row.id,
      conversationId: row.conversation_id,
      title: row.title || "Untitled task",
      status: row.status,
      stage:
        typeof row.progress?.stage === "string" ? row.progress.stage : null,
      createdAt: row.created_at,
      startedAt: row.started_at,
      finishedAt: row.finished_at,
    })),
    scans: scans.map((row) => ({
      id: row.id,
      name: row.name,
      status: row.status,
      stage: row.progress?.stage || null,
      createdAt: row.created_at,
      startedAt: row.started_at,
      finishedAt: row.finished_at,
    })),
  };
}
