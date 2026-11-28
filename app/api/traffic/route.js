import { getSession } from "../../../lib/auth";
import { verifyTrafficSignature } from "../../../lib/traffic/events.mjs";
import { ingestTraffic, trafficOverview } from "../../../lib/traffic/store";
const reply = (data, status = 200) =>
  Response.json(data, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
export async function GET() {
  const session = await getSession();
  if (!session || !["owner", "admin"].includes(session.role))
    return reply({ error: "Forbidden" }, 403);
  try {
    return reply(await trafficOverview());
  } catch {
    return reply({ error: "TRAFFIC_UNAVAILABLE" }, 503);
  }
}
export async function POST(request) {
  if (!process.env.VECTOR_TRAFFIC_INGEST_TOKEN)
    return reply({ error: "INGEST_NOT_CONFIGURED" }, 503);
  try {
    const reader = request.body?.getReader();
    if (!reader) return reply({ error: "INVALID_REQUEST" }, 400);
    let bytes = 0;
    const parts = [];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.length;
      if (bytes > 256000) {
        await reader.cancel();
        return reply({ error: "REQUEST_LIMIT" }, 413);
      }
      parts.push(Buffer.from(value));
    }
    const body = Buffer.concat(parts),
      nonce = request.headers.get("x-vector-nonce");
    if (
      !verifyTrafficSignature({
        body,
        timestamp: request.headers.get("x-vector-timestamp"),
        nonce,
        signature: request.headers.get("x-vector-signature"),
        key: process.env.VECTOR_TRAFFIC_INGEST_TOKEN,
      })
    )
      return reply({ error: "Unauthorized" }, 401);
    return reply(await ingestTraffic(JSON.parse(body.toString("utf8")), nonce));
  } catch (error) {
    return reply(
      {
        error: [
          "TRAFFIC_REPLAY",
          "TRAFFIC_RATE_LIMIT",
          "INVALID_TRAFFIC_EVENT",
          "INVALID_TRAFFIC_EVENTS",
        ].includes(error.message)
          ? error.message
          : "INGEST_FAILED",
      },
      400,
    );
  }
}
