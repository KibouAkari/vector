import { getSession } from "../../../../lib/auth";
import { boundedJson } from "../../../../lib/bounded-json.mjs";
import {
  scannerOverview,
  saveSecurityAsset,
  revokeSecurityAsset,
} from "../../../../lib/security/scan-store";
import { ScanError } from "../../../../lib/security/targets.mjs";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const reply = (data, status = 200) =>
  Response.json(data, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
export async function GET() {
  const session = await getSession();
  if (!session || !["owner", "admin"].includes(session.role))
    return reply({ error: "Forbidden" }, 403);
  return reply(await scannerOverview(session));
}
export async function POST(request) {
  const session = await getSession();
  if (session?.role === "readonly")
    return Response.json({ error: "READ_ONLY_ACCOUNT" }, { status: 403 });
  if (!session || !["owner", "admin"].includes(session.role))
    return reply({ error: "Forbidden" }, 403);
  try {
    return reply(
      await saveSecurityAsset(session, await boundedJson(request)),
      201,
    );
  } catch (error) {
    return reply(
      {
        error:
          error instanceof ScanError
            ? error.code
            : ["INVALID_PACKAGES", "INVALID_REQUEST", "REQUEST_LIMIT"].includes(
                  error.message,
                )
              ? error.message
              : "ASSET_SAVE_FAILED",
      },
      400,
    );
  }
}
export async function DELETE(request) {
  const session = await getSession();
  if (session?.role === "readonly")
    return Response.json({ error: "READ_ONLY_ACCOUNT" }, { status: 403 });
  if (!session || !["owner", "admin"].includes(session.role))
    return reply({ error: "Forbidden" }, 403);
  try {
    const input = await boundedJson(request);
    if (typeof input.id !== "string")
      return reply({ error: "INVALID_ASSET" }, 400);
    await revokeSecurityAsset(session, input.id);
    return reply({ ok: true });
  } catch {
    return reply({ error: "ASSET_REVOKE_FAILED" }, 400);
  }
}
