export function skillDocument(input) {
  let name = typeof input.name === "string" ? input.name.trim() : "",
    description = "",
    parameters = input.parameters || {},
    instructions =
      typeof input.instructions === "string" ? input.instructions.trim() : "";
  if (input.document !== undefined) {
    if (typeof input.document !== "string" || input.document.length > 12000)
      throw Error("INVALID_SKILL");
    let source = input.document.replace(/\r\n/g, "\n");
    if (source.startsWith("---\n")) {
      const end = source.indexOf("\n---\n", 4);
      if (end < 0) throw Error("INVALID_FRONTMATTER");
      for (const line of source.slice(4, end).split("\n")) {
        if (!line.trim() || line.startsWith("#")) continue;
        const match = /^(name|description|parameters):\s*(.*)$/.exec(line);
        if (!match) throw Error("INVALID_FRONTMATTER");
        if (match[1] === "parameters") {
          try {
            parameters = JSON.parse(match[2]);
          } catch {
            throw Error("INVALID_PARAMETERS");
          }
        } else {
          const value = match[2].trim();
          if (match[1] === "name") name = value;
          else description = value;
        }
      }
      source = source.slice(end + 5);
    }
    instructions = source.trim();
  }
  if (
    name.length < 2 ||
    name.length > 80 ||
    description.length > 300 ||
    instructions.length < 10 ||
    instructions.length > 6000 ||
    !parameters ||
    typeof parameters !== "object" ||
    Array.isArray(parameters) ||
    Object.keys(parameters).length > 12
  )
    throw Error("INVALID_SKILL");
  const normalized = {};
  for (const [key, definition] of Object.entries(parameters)) {
    if (
      !/^[a-zA-Z][a-zA-Z0-9_]{0,31}$/.test(key) ||
      ["__proto__", "constructor", "prototype"].includes(key) ||
      !definition ||
      !["string", "number", "boolean"].includes(definition.type) ||
      typeof definition.default !== definition.type ||
      (typeof definition.default === "number" &&
        !Number.isFinite(definition.default)) ||
      String(definition.default).length > 1000
    )
      throw Error("INVALID_PARAMETERS");
    normalized[key] = { type: definition.type, default: definition.default };
  }
  return { name, description, instructions, parameters: normalized };
}
export function renderSkill(skill, values = {}) {
  if (
    !values ||
    typeof values !== "object" ||
    Array.isArray(values) ||
    Object.keys(values).some(
      (key) => !Object.hasOwn(skill.parameters || {}, key),
    )
  )
    throw Error("INVALID_SKILL_PARAMETERS");
  const parameters = skill.parameters || {};
  const result = {};
  for (const [key, definition] of Object.entries(parameters)) {
    const value = Object.hasOwn(values, key) ? values[key] : definition.default;
    if (
      typeof value !== definition.type ||
      (typeof value === "number" && !Number.isFinite(value)) ||
      String(value).length > 1000
    )
      throw Error("INVALID_SKILL_PARAMETERS");
    result[key] = String(value);
  }
  return skill.instructions.replace(
    /\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}/g,
    (match, key) => (Object.hasOwn(result, key) ? result[key] : match),
  );
}
