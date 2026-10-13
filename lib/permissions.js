import crypto from "crypto";

import {
  db,
  initializeDatabase
} from "./db";

export async function getPermissionPolicy(
  permission
) {
  await initializeDatabase();

  const result =
    await db.query(
      `
        SELECT
          permission,
          decision,
          description
        FROM permission_policies
        WHERE permission = $1
      `,
      [permission]
    );

  if (result.rowCount === 0) {
    return {
      permission,
      decision: "ASK",
      description:
        "Unknown permissions require approval by default."
    };
  }

  return result.rows[0];
}

export async function requestPermission({
  permission,
  action,
  description,
  taskId = null
}) {
  const policy =
    await getPermissionPolicy(permission);

  if (policy.decision === "ALLOW") {
    return {
      decision: "ALLOW",
      approvalId: null
    };
  }

  if (policy.decision === "DENY") {
    return {
      decision: "DENY",
      approvalId: null
    };
  }

  const approvalId =
    crypto.randomUUID();

  await db.query(
    `
      INSERT INTO approvals (
        id,
        task_id,
        permission,
        action,
        description,
        status
      )
      VALUES (
        $1,
        $2,
        $3,
        $4,
        $5,
        'pending'
      )
    `,
    [
      approvalId,
      taskId,
      permission,
      action,
      description
    ]
  );

  return {
    decision: "ASK",
    approvalId
  };
}
