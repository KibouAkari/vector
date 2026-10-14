import { getSession } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";
import { initializeIdentity } from "../../../../../lib/identity";

const forbidden = () =>
  Response.json({ error: "Forbidden" }, { status: 403 });

export async function GET(request, context) {
  const session = await getSession();
  if (!session || session.role !== "owner") return forbidden();

  await initializeIdentity();

  const { id } = await context.params;
  const result = await db.query(`
    SELECT
      p.id, p.name, p.description,
      pm.access_role, (pm.user_id IS NOT NULL) AS shared
    FROM projects p
    LEFT JOIN project_members pm
      ON pm.project_id = p.id AND pm.user_id = $1
    ORDER BY LOWER(p.name)
  `, [id]);

  return Response.json({ projects: result.rows });
}

/**
 * Replace all shares atomically. Never delete existing permissions when
 * requested projects are invalid or when an insertion fails.
 */
export async function PUT(request, context) {
  const session = await getSession();
  if (!session || session.role !== "owner") return forbidden();

  await initializeIdentity();

  const { id } = await context.params;
  let body;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request" }, { status: 400 });
  }

  if (!Array.isArray(body?.projectIds) || body.projectIds.length > 250 ||
      body.projectIds.some(value => typeof value !== "string" || !value.trim())) {
    return Response.json({ error: "Invalid project list" }, { status: 400 });
  }

  const ids = [...new Set(body.projectIds)];
  const accessRole = body.accessRole === "editor" ? "editor" : "viewer";
  const client = await db.connect();

  try {
    await client.query("BEGIN");

    // Lock the account row so concurrent share updates serialize.
    const user = await client.query(
      "SELECT id FROM vector_users WHERE id = $1 FOR UPDATE",
      [id]
    );
    if (user.rowCount !== 1) {
      await client.query("ROLLBACK");
      return Response.json({ error: "User not found" }, { status: 404 });
    }

    if (ids.length) {
      const projects = await client.query(
        "SELECT id FROM projects WHERE id = ANY($1::text[])",
        [ids]
      );
      if (projects.rowCount !== ids.length) {
        await client.query("ROLLBACK");
        return Response.json({ error: "Unknown project in selection" }, {
          status: 400
        });
      }
    }

    await client.query(
      "DELETE FROM project_members WHERE user_id = $1",
      [id]
    );

    for (const projectId of ids) {
      await client.query(
        `INSERT INTO project_members (project_id, user_id, access_role)
         VALUES ($1, $2, $3)`,
        [projectId, id, accessRole]
      );
    }

    await client.query("COMMIT");
    return Response.json({ ok: true });

  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    console.error("Project sharing update failed:", error);
    return Response.json({ error: "Could not update project access" }, {
      status: 500
    });
  } finally {
    client.release();
  }
}
