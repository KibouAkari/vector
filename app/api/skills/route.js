import { getSession } from "../../../lib/auth";
import { boundedJson } from "../../../lib/bounded-json.mjs";
import {
  listSkills,
  createSkill,
  reviewSkill,
} from "../../../lib/project-skills";
export const dynamic = "force-dynamic";
export async function GET() {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  return Response.json(
    {
      skills: await listSkills(null, true, session.userId),
      canReview: session.role !== "readonly",
    },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
export async function POST(request) {
  const session = await getSession();
  if (!session)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (session.role === "readonly")
    return Response.json({ error: "Forbidden" }, { status: 403 });
  try {
    const input = await boundedJson(request, { maxBytes: 65536 });
    return Response.json({
      skill: ["create", "revise"].includes(input.action)
        ? await createSkill(null, session, input)
        : await reviewSkill(null, session, input),
    });
  } catch (error) {
    return Response.json(
      {
        error: [
          "INVALID_SKILL",
          "SKILL_CONFLICT",
          "SKILL_LIMIT",
          "INVALID_PARAMETERS",
          "INVALID_FRONTMATTER",
          "INVALID_REQUEST",
        ].includes(error.message)
          ? error.message
          : "SKILL_UPDATE_FAILED",
      },
      { status: 400 },
    );
  }
}
