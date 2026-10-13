import {
  db,
  initializeDatabase
} from "../../../lib/db";

import {
  ensureRedis
} from "../../../lib/redis";

export const runtime = "nodejs";

export async function GET() {
  const status = {
    vector: "ok",
    database: "unknown",
    redis: "unknown"
  };

  try {
    await initializeDatabase();

    await db.query(
      "SELECT 1"
    );

    status.database = "ok";

  } catch (error) {
    status.database = "error";

    console.error(
      "Database health error:",
      error
    );
  }

  try {
    const client =
      await ensureRedis();

    const ping =
      await client.ping();

    status.redis =
      ping === "PONG"
        ? "ok"
        : "error";

  } catch (error) {
    status.redis = "error";

    console.error(
      "Redis health error:",
      error
    );
  }

  const healthy =
    status.database === "ok" &&
    status.redis === "ok";

  return Response.json(
    status,
    {
      status:
        healthy
          ? 200
          : 503
    }
  );
}
