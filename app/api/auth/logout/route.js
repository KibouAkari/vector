import {
  clearSessionCookie,
  getSession
} from "../../../../lib/auth";

import {
  writeAudit
} from "../../../../lib/audit";

export const runtime = "nodejs";

export async function POST() {
  const session =
    await getSession();

  await clearSessionCookie();

  if (session) {
    await writeAudit({
      actor:
        session.username,

      action:
        "auth.logout",

      source:
        "web"
    });
  }

  return Response.json({
    ok: true
  });
}
