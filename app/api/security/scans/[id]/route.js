import { getSession } from "../../../../../lib/auth";
import {
  getSecurityRun,
  cancelSecurityRun,
} from "../../../../../lib/security/scan-store";
import { scanMarkdown } from "../../../../../lib/security/active-scan.mjs";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET(request, context) {
  const session = await getSession();
  if (!session || !["owner", "admin"].includes(session.role))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  const { id } = await context.params;
  const row = await getSecurityRun(session, id);
  if (!row) return Response.json({ error: "Not found" }, { status: 404 });
  const format = new URL(request.url).searchParams.get("format");
  const headers = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (format && row.result) {
    headers["Content-Disposition"] =
      'attachment; filename="vector-security-report.' +
      (format === "md" ? "md" : "json") +
      '"';
    return new Response(
      format === "md"
        ? scanMarkdown({ name: row.asset_name }, row.result)
        : JSON.stringify(row.result, null, 2),
      {
        headers: {
          ...headers,
          "Content-Type":
            format === "md"
              ? "text/markdown; charset=utf-8"
              : "application/json",
        },
      },
    );
  }
  return Response.json({ run: row }, { headers });
}
export async function DELETE(request, context) {
  const session = await getSession();
  if (session?.role === "readonly")
    return Response.json({ error: "READ_ONLY_ACCOUNT" }, { status: 403 });
  if (!session || !["owner", "admin"].includes(session.role))
    return Response.json({ error: "Forbidden" }, { status: 403 });
  const { id } = await context.params;
  await cancelSecurityRun(session, id);
  return Response.json({ ok: true });
}
