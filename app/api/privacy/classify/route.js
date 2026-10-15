import crypto from "crypto";
import {detectPrivateLocally,privacyReviewEnabled} from '../../../../lib/privacy-review';
import {makePrivacyPlan} from '../../../../lib/privacy-review-core.mjs';

import {
  getSession,hasFeature
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

  if (!hasFeature(session,'chat')) return Response.json({error:'Forbidden'},{status:403});
  if (typeof body.text !== 'string' || body.text.length > 100000) {
    return Response.json({error:'Text must be at most 100000 characters.'},{status:400});
  }

  let result;
  if (privacyReviewEnabled()) {
    try {
      const plan = makePrivacyPlan(body.text,await detectPrivateLocally(body.text,{userId:session.userId}));
      result={classification:plan.totalFindings?'confidential':'internal',findings:plan.findings,
        totalFindings:plan.totalFindings,wasRedacted:plan.wasSanitized,originalLength:body.text.length,redacted:plan.sanitized};
    } catch { return Response.json({error:'Local privacy scan unavailable'},{status:503,headers:{'Cache-Control':'no-store'}}); }
  } else result=classifyPrivacy(body.text);

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
