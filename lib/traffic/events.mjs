import crypto from "node:crypto";
import { isIP } from "node:net";
export function verifyTrafficSignature({
  body,
  timestamp,
  nonce,
  signature,
  key,
  now = Date.now(),
}) {
  if (
    !key ||
    key.length < 32 ||
    !/^\d{13}$/.test(timestamp || "") ||
    Math.abs(now - Number(timestamp)) > 60000 ||
    !/^[a-f0-9-]{36}$/i.test(nonce || "") ||
    !/^[a-f0-9]{64}$/.test(signature || "")
  )
    return false;
  const digest = crypto
    .createHmac("sha256", key)
    .update(timestamp + "\n" + nonce + "\n")
    .update(body)
    .digest("hex");
  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(signature));
}
export function normalizeTraffic(input, now = Date.now()) {
  if (
    !Array.isArray(input.events) ||
    input.events.length < 1 ||
    input.events.length > 500
  )
    throw Error("INVALID_TRAFFIC_EVENTS");
  return input.events.map((row) => {
    const at = new Date(row.observedAt),
      kind = row.kind;
    const service = String(row.service || "").trim();
    if (
      !isIP(row.sourceIp) ||
      service.length < 1 ||
      service.length > 100 ||
      /[\x00-\x1f]/.test(service) ||
      !["http-request", "connection-snapshot"].includes(kind) ||
      !Number.isFinite(at.getTime()) ||
      at.getTime() > now + 60000 ||
      at.getTime() < now - 86400000
    )
      throw Error("INVALID_TRAFFIC_EVENT");
    const country =
      typeof row.country === "string" && /^[A-Z]{2}$/.test(row.country)
        ? row.country
        : null;
    const coordinates =
      country &&
      Number.isFinite(row.latitude) &&
      Number.isFinite(row.longitude) &&
      Math.abs(row.latitude) <= 90 &&
      Math.abs(row.longitude) <= 180
        ? { latitude: row.latitude, longitude: row.longitude }
        : {};
    return {
      sourceIp: row.sourceIp,
      service,
      kind,
      observedAt: at.toISOString(),
      country,
      ...coordinates,
    };
  });
}
