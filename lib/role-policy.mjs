export const ROLES = ["owner", "admin", "member", "readonly"];
export const isReadOnly = (session) => session?.role === "readonly";
export const isOperator = (session) =>
  ["owner", "admin"].includes(session?.role);
export function normalizeRolePolicy(input = {}) {
  const list = (value, label) => {
    if (value === undefined || value === null) return null;
    if (
      !Array.isArray(value) ||
      value.length > 100 ||
      value.some(
        (item) => typeof item !== "string" || !item.trim() || item.length > 200,
      )
    )
      throw Error("INVALID_" + label);
    return [...new Set(value)];
  };
  return {
    models: list(input.models, "MODELS"),
    tools: list(input.tools, "TOOLS"),
  };
}
export function roleAllows(policy, kind, value) {
  const list = policy?.[kind];
  return list === null || list === undefined || list.includes(value);
}
