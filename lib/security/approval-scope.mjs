import crypto from "node:crypto";

const hasKeys = (value, keys) =>
  value && typeof value === "object" && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));

export function securityApprovalScope(row) {
  const scope = row?.scope;
  const target = scope?.target;
  if (
    !row.active || row.requested_by !== row.owner_user_id ||
    row.resource_id !== row.asset_id || row.id !== row.approval_id ||
    !hasKeys(scope, ["target", "addresses", "packages", "checkAdvisories"]) ||
    !hasKeys(target, ["host", "ports", "scheme", "explicitPort"]) ||
    !Array.isArray(scope.addresses) || !Array.isArray(scope.packages) ||
    !scope.packages.every((pkg) => hasKeys(pkg, ["ecosystem", "name", "version"]))
  ) return null;

  const original = {
    target: { host: target.host, ports: target.ports, scheme: target.scheme, explicitPort: target.explicitPort },
    addresses: scope.addresses,
    packages: scope.packages.map((pkg) => ({ ecosystem: pkg.ecosystem, name: pkg.name, version: pkg.version })),
    checkAdvisories: scope.checkAdvisories,
  };
  const digest = crypto.createHash("sha256").update(JSON.stringify(original)).digest("hex");
  return digest === row.scope_digest && digest === row.asset_scope_digest ? original : null;
}
