import { getSession } from "../../../lib/auth";
import { boundedJson } from "../../../lib/bounded-json.mjs";
import {
  listMemories,
  saveMemory,
  forgetMemory,
} from "../../../lib/brain/store";
const reply = (data, status = 200) =>
  Response.json(data, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
export async function GET() {
  const session = await getSession();
  if (!session) return reply({ error: "Unauthorized" }, 401);
  try {
    return reply({
      memories: await listMemories(session.userId),
      canEdit: session.role !== "readonly",
      contextBytes: 2400,
    });
  } catch {
    return reply(
      {
        error:
          "Memory is unavailable. Configure FILE_ENCRYPTION_KEY and check the database.",
      },
      503,
    );
  }
}
async function mutate(request, remove) {
  const session = await getSession();
  if (!session) return reply({ error: "Unauthorized" }, 401);
  if (session.role === "readonly") return reply({ error: "Forbidden" }, 403);
  try {
    const input = await boundedJson(request, { maxBytes: 20000 });
    return reply(
      remove
        ? (await forgetMemory(session, input), { ok: true })
        : { memory: await saveMemory(session, input) },
    );
  } catch (error) {
    return reply(
      {
        error: [
          "INVALID_MEMORY",
          "INVALID_EXPIRY",
          "CREDENTIAL_MEMORY_BLOCKED",
          "MEMORY_CONFLICT",
          "MEMORY_LIMIT",
        ].includes(error.message)
          ? error.message
          : "MEMORY_UPDATE_FAILED",
      },
      error.message === "MEMORY_CONFLICT" ? 409 : 400,
    );
  }
}
export const POST = (request) => mutate(request, false);
export const DELETE = (request) => mutate(request, true);
