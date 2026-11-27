import { parseDocument } from "yaml";
import crypto from "node:crypto";
export function githubSkillUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw Error("INVALID_SKILL_URL");
  }
  const parts = url.pathname.split("/").filter(Boolean);
  if (
    url.origin !== "https://github.com" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password ||
    parts.length < 5 ||
    parts[2] !== "blob" ||
    parts.at(-1) !== "SKILL.md" ||
    parts.some(
      (part) => !part || part === ".." || !/^[A-Za-z0-9_.-]+$/.test(part),
    )
  )
    throw Error("INVALID_SKILL_URL");
  return {
    owner: parts[0],
    repo: parts[1],
    ref: parts[3],
    path: parts.slice(4).join("/"),
  };
}
export function parseAgentSkill(source) {
  if (typeof source !== "string" || Buffer.byteLength(source) > 16000)
    throw Error("SKILL_IMPORT_LIMIT");
  source = source.replace(/\r\n/g, "\n");
  if (!source.startsWith("---\n")) throw Error("SKILL_FRONTMATTER_REQUIRED");
  const end = source.indexOf("\n---\n", 4);
  if (end < 0) throw Error("INVALID_FRONTMATTER");
  const document = parseDocument(source.slice(4, end), {
    uniqueKeys: true,
    maxAliasCount: 0,
    version: "1.2",
  });
  if (document.errors.length) throw Error("INVALID_FRONTMATTER");
  let fields;
  try {
    fields = document.toJS({ maxAliasCount: 0 });
  } catch {
    throw Error("INVALID_FRONTMATTER");
  }
  if (
    !fields ||
    typeof fields.name !== "string" ||
    typeof fields.description !== "string" ||
    !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(fields.name) ||
    fields.name.length > 64 ||
    fields.description.length > 300
  )
    throw Error("INVALID_SKILL_METADATA");
  const instructions = source.slice(end + 5).trim();
  if (instructions.length < 10 || instructions.length > 6000)
    throw Error("SKILL_INSTRUCTIONS_LIMIT");
  return {
    name: fields.name,
    description: fields.description,
    instructions,
    parameters: {},
    license:
      typeof fields.license === "string"
        ? fields.license.slice(0, 300)
        : "Not specified",
    compatibility:
      typeof fields.compatibility === "string"
        ? fields.compatibility.slice(0, 500)
        : null,
    declaredTools:
      typeof fields["allowed-tools"] === "string"
        ? fields["allowed-tools"].slice(0, 1000)
        : null,
    contentSha256: crypto.createHash("sha256").update(source).digest("hex"),
  };
}
