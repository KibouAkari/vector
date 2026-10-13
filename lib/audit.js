import crypto from "crypto";

import {
  db,
  initializeDatabase
} from "./db";

export async function writeAudit({
  actor,
  action,
  resource = null,
  details = null,
  source = "web"
}) {
  await initializeDatabase();

  await db.query(
    `
      INSERT INTO audit_log (
        id,
        actor,
        action,
        resource,
        details,
        source
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6
      )
    `,
    [
      crypto.randomUUID(),
      actor,
      action,
      resource,
      details
        ? JSON.stringify(details)
        : null,
      source
    ]
  );
}
