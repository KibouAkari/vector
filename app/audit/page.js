import { requireFeature } from "../../lib/auth";
import { db } from "../../lib/db";
import Sidebar from "../../components/sidebar";
import ActivityClient from "./activity-client";

export const dynamic = "force-dynamic";

export default async function AuditPage() {
  const session = await requireFeature("activity");

  let result;

  if (session.role === "owner") {
    result = await db.query(`
      SELECT
        a.id,
        a.actor,
        COALESCE(u.display_name, a.actor) AS actor_display,
        a.action,
        a.resource,
        a.details,
        a.source,
        a.created_at
      FROM audit_log a
      LEFT JOIN vector_users u
        ON LOWER(u.username) = LOWER(a.actor)
      ORDER BY a.created_at DESC
      LIMIT 500
    `);
  } else {
    result = await db.query(
      `
        SELECT
          a.id,
          a.actor,
          COALESCE(u.display_name, a.actor) AS actor_display,
          a.action,
          a.resource,
          a.details,
          a.source,
          a.created_at
        FROM audit_log a
        LEFT JOIN vector_users u
          ON LOWER(u.username) = LOWER(a.actor)
        WHERE LOWER(a.actor) = LOWER($1)
        ORDER BY a.created_at DESC
        LIMIT 500
      `,
      [session.username]
    );
  }

  const items = result.rows.map((item) => ({
    id: item.id,
    actor: item.actor,
    actorDisplay: item.actor_display,
    action: item.action,
    resource: item.resource,
    details: item.details || {},
    source: item.source,
    createdAt:
      item.created_at?.toISOString?.() ||
      String(item.created_at)
  }));

  return (
    <div className="vector-shell">
      <Sidebar session={session} />

      <main className="main v5-main v55-page">
        <header className="v55-page-head">
          <div>
            <span>Activity</span>
            <h1>History</h1>
            <p>
              {session.role === "owner"
                ? "Events across Vector and all users."
                : "Your recent Vector activity."}
            </p>
          </div>
        </header>

        <ActivityClient
          items={items}
          owner={session.role === "owner"}
        />
      </main>
    </div>
  );
}
