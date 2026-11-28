import { getSession } from "../../../../lib/auth";
import { hasFeature } from "../../../../lib/auth";
import { canAccessProject } from "../../../../lib/identity";
import { boundedJson } from "../../../../lib/bounded-json.mjs";
import {
  githubSkillUrl,
  parseAgentSkill,
} from "../../../../lib/skill-import.mjs";
import { connectorRequest } from "../../../../lib/connectors/http.mjs";
import { createSkill } from "../../../../lib/project-skills";
import { db } from "../../../../lib/db";
const reply = (data, status = 200) =>
  Response.json(data, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
export async function POST(request) {
  const session = await getSession();
  if (
    !session ||
    session.role === "readonly" ||
    !hasFeature(session, "projects")
  )
    return reply({ error: "Forbidden" }, 403);
  try {
    const input = await boundedJson(request, { maxBytes: 4096 });
    if (input.projectId && !(await canAccessProject(session, input.projectId)))
      return reply({ error: "Forbidden" }, 403);
    const source = githubSkillUrl(input.url);
    const commit = await connectorRequest(
      "https://api.github.com",
      `repos/${source.owner}/${source.repo}/commits/${source.ref}`,
    );
    if (!/^[a-f0-9]{40}$/.test(commit.sha))
      throw Error("SKILL_COMMIT_UNAVAILABLE");
    const text = await connectorRequest(
      "https://raw.githubusercontent.com",
      `${source.owner}/${source.repo}/${commit.sha}/${source.path}`,
      { raw: true },
    );
    const parsed = parseAgentSkill(text),
      provenance = {
        url: input.url,
        commit: commit.sha,
        path: source.path,
        sha256: parsed.contentSha256,
        license: parsed.license,
        compatibility: parsed.compatibility,
        declaredTools: parsed.declaredTools,
      };
    if (input.action === "preview")
      return reply({ skill: parsed, source: provenance });
    if (
      input.action !== "import" ||
      input.commit !== commit.sha ||
      input.contentSha256 !== parsed.contentSha256 ||
      input.acceptLicense !== true
    )
      throw Error("SKILL_SOURCE_CHANGED_OR_UNACKNOWLEDGED");
    const skill = await createSkill(input.projectId || null, session, parsed);
    await db.query(
      "ALTER TABLE project_skills ADD COLUMN IF NOT EXISTS import_source JSONB",
    );
    await db.query("UPDATE project_skills SET import_source=$2 WHERE id=$1", [
      skill.id,
      JSON.stringify(provenance),
    ]);
    return reply({ skill, source: provenance });
  } catch (error) {
    return reply(
      {
        error: /^(INVALID_|SKILL_)/.test(error.message)
          ? error.message
          : "SKILL_IMPORT_FAILED",
      },
      400,
    );
  }
}
