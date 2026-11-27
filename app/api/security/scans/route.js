import { getSession } from "../../../../lib/auth";
import { boundedJson } from "../../../../lib/bounded-json.mjs";
import { queueSecurityScan } from "../../../../lib/security/scan-store";
import { ScanError } from "../../../../lib/security/targets.mjs";
export const runtime = "nodejs";
export async function POST(request) {
  const session = await getSession();
  if (session?.role === "readonly")
    return Response.json({ error: "READ_ONLY_ACCOUNT" }, { status: 403 });
  if (!session || !["owner", "admin"].includes(session.role))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    return Response.json(
      await queueSecurityScan(session, await boundedJson(request)),
      { status: 202 },
    );
  } catch (error) {
    return Response.json(
      { error: error instanceof ScanError ? error.code : "SCAN_QUEUE_FAILED" },
      { status: error.code === "APPROVAL_REQUIRED" ? 403 : 400 },
    );
  }
}
