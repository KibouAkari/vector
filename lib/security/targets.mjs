import { isPublicAddress } from "../source-fetch.mjs";
import { isIP } from "node:net";
import { lookup } from "node:dns/promises";
export class ScanError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}
export const DEFAULT_PORTS = [
  21, 22, 25, 53, 80, 110, 139, 143, 443, 445, 465, 587, 993, 995, 1433, 2049,
  3000, 3306, 3389, 5432, 6379, 8080, 8443, 9090, 9443, 25565, 27017,
];
export function parseTarget(value, ports = DEFAULT_PORTS) {
  if (
    typeof value !== "string" ||
    value.length > 500 ||
    /[\s\u0000-\u001f]/.test(value)
  )
    throw new ScanError("INVALID_TARGET");
  let url;
  try {
    const raw = isIP(value) === 6 ? `[${value}]` : value;
    url = new URL(raw.includes("://") ? raw : "http://" + raw);
  } catch {
    throw new ScanError("INVALID_TARGET");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    !["", "/"].includes(url.pathname)
  )
    throw new ScanError("INVALID_TARGET");
  const host = url.hostname
    .replace(/^\[|\]$/g, "")
    .toLowerCase()
    .replace(/\.$/, "");
  if (
    !isIP(host) &&
    (!/^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$/.test(host) ||
      host
        .split(".")
        .some(
          (p) => !p || p.length > 63 || p.startsWith("-") || p.endsWith("-"),
        ))
  )
    throw new ScanError("INVALID_TARGET");
  const hasScheme = value.includes("://");
  const writtenPort =
    isIP(value) === 6 ? null : value.match(/(?:\]|[^:]):(\d+)\/?$/)?.[1];
  const explicitPort = writtenPort
    ? Number(writtenPort)
    : url.port
      ? Number(url.port)
      : hasScheme
        ? url.protocol === "https:"
          ? 443
          : 80
        : null;
  const list = Array.isArray(ports)
    ? ports
    : typeof ports === "string"
      ? ports.split(",").map((v) => Number(v.trim()))
      : [];
  const selected = [
    ...new Set([...list, ...(explicitPort ? [explicitPort] : [])]),
  ].sort((a, b) => a - b);
  if (
    !selected.length ||
    selected.length > 64 ||
    selected.some((p) => !Number.isInteger(p) || p < 1 || p > 65535)
  )
    throw new ScanError("INVALID_PORTS");
  return {
    host,
    ports: selected,
    scheme: hasScheme ? url.protocol.slice(0, -1) : null,
    explicitPort,
  };
}
function v4Number(ip) {
  return ip.split(".").reduce((n, p) => n * 256 + Number(p), 0);
}
function inPrivateAllowlist(ip, cidrs) {
  if (isIP(ip) !== 4) return false;
  return cidrs.some((entry) => {
    const [base, bitsText] = entry.trim().split("/");
    const bits = bitsText === undefined ? 32 : Number(bitsText);
    if (isIP(base) !== 4 || !Number.isInteger(bits) || bits < 8 || bits > 32)
      return false;
    const divisor = 2 ** (32 - bits);
    return (
      Math.floor(v4Number(ip) / divisor) ===
      Math.floor(v4Number(base) / divisor)
    );
  });
}
export function permittedAddress(ip, privateCidrs = []) {
  if (!isIP(ip) || ip === "168.63.129.16") return false;
  const [a, b] = ip.split(".").map(Number);
  if (
    isIP(ip) === 4 &&
    (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168))
  )
    return inPrivateAllowlist(ip, privateCidrs);
  return isPublicAddress(ip);
}
export async function resolveTarget(
  target,
  {
    lookupImpl = lookup,
    privateCidrs = (process.env.VECTOR_SECURITY_PRIVATE_CIDRS || "")
      .split(",")
      .filter(Boolean),
  } = {},
) {
  const addresses = isIP(target.host)
    ? [{ address: target.host, family: isIP(target.host) }]
    : await Promise.race([
        lookupImpl(target.host, { all: true, verbatim: true }),
        new Promise((_, reject) => {
          const timer = setTimeout(
            () => reject(new ScanError("DNS_TIMEOUT")),
            4000,
          );
          timer.unref?.();
        }),
      ]);
  if (
    !addresses.length ||
    addresses.length > 8 ||
    addresses.some((row) => !permittedAddress(row.address, privateCidrs))
  )
    throw new ScanError("TARGET_ADDRESS_BLOCKED");
  return [...new Set(addresses.map((row) => row.address))].sort();
}
