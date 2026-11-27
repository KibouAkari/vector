import { getSession } from "../../../lib/auth";
import { boundedJson } from "../../../lib/bounded-json.mjs";
import {
  listConnections,
  saveConnection,
  syncConnection,
  deleteConnection,
  requestConnectionAction,
  executeConnectionAction,
} from "../../../lib/connectors/store";
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
    return reply(await listConnections(session));
  } catch {
    return reply({ error: "CONNECTIONS_UNAVAILABLE" }, 503);
  }
}
export async function POST(request) {
  const session = await getSession();
  if (!session || !["owner", "admin"].includes(session.role))
    return reply({ error: "Forbidden" }, 403);
  try {
    const input = await boundedJson(request, { maxBytes: 24000 });
    const result =
      input.action === "sync"
        ? await syncConnection(session, input.id)
        : input.action === "remove"
          ? await deleteConnection(session, input.id)
          : input.action === "request-action"
            ? await requestConnectionAction(session, input.id, input.spec)
            : input.action === "execute"
              ? await executeConnectionAction(session, input.id)
              : input.action === "create"
                ? await saveConnection(session, input)
                : (() => {
                    throw Error("INVALID_ACTION");
                  })();
    return reply(result || { ok: true });
  } catch (error) {
    const code = /^[A-Z][A-Z_0-9]+$/.test(error.message)
      ? error.message
      : "CONNECTION_REQUEST_FAILED";
    return reply({ error: code }, 400);
  }
}
