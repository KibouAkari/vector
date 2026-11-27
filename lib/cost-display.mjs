export function callCostLabel(value, status = "estimated") {
  if (
    status === "incomplete" ||
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  )
    return "Cost unknown";
  if (status === "local-no-api") return "Local · no API fee";
  const n = Number(value),
    prefix = status === "reported" ? "" : "≈ ";
  return prefix + (n > 0 && n < 0.01 ? "< CHF 0.01" : `CHF ${n.toFixed(2)}`);
}
