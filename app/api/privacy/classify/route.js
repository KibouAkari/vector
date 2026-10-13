import crypto from "crypto";

import {
  getSession
} from "../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../lib/db";

import {
  classifyPrivacy,
  externalAIAllowed
} from "../../../../lib/privacy";

export const runtime = "nodejs";

export async function POST(request) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error: "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  const body =
    await request.json();

  const result =
    classifyPrivacy(
      body.text || ""
    );

  await initializeDatabase();

  await db.query(
    `
      INSERT INTO privacy_events (
        id,
        actor,
        classification,
        finding_count,
        finding_types,
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
      session.username,
      result.classification,
      result.findings.reduce(
        (sum, finding) =>
          sum + finding.count,
        0
      ),
      JSON.stringify(
        result.findings.map(
          (finding) =>
            finding.type
        )
      ),
      "web"
    ]
  );

  return Response.json({
    ...result,

    externalAIAllowed:
      externalAIAllowed(
        result.classification
      )
  });
}
