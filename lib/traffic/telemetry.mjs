import { isIP } from "node:net";
const finite = (v, min = 0, max = Number.MAX_SAFE_INTEGER) =>
  typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
const text = (v, max) =>
  typeof v === "string" && v.length <= max && !/[\x00-\x1f]/.test(v);
const at = (v, now) => {
  const date = new Date(v);
  if (
    !Number.isFinite(date.getTime()) ||
    date.getTime() > now + 60000 ||
    date.getTime() < now - 86400000
  )
    throw Error("INVALID_SAMPLE_TIME");
  return date.toISOString();
};
export function normalizeVitals(value, now = Date.now()) {
  if (
    !value ||
    (!finite(value.cpuPercent, 0, 100) && value.cpuPercent !== null) ||
    !finite(value.logicalCpus, 1, 4096)
  )
    throw Error("INVALID_HOST_METRICS");
  const memory = value.memory;
  if (
    !memory ||
    !finite(memory.totalBytes, 1) ||
    !finite(memory.availableBytes) ||
    memory.availableBytes > memory.totalBytes
  )
    throw Error("INVALID_HOST_METRICS");
  if (!Array.isArray(value.storage) || value.storage.length > 16)
    throw Error("INVALID_HOST_METRICS");
  return {
    observedAt: at(value.observedAt, now),
    cpuPercent: value.cpuPercent,
    logicalCpus: value.logicalCpus,
    memory: {
      totalBytes: memory.totalBytes,
      availableBytes: memory.availableBytes,
      usedBytes: memory.totalBytes - memory.availableBytes,
    },
    storage: value.storage.map((disk) => {
      if (
        !text(disk.name, 100) ||
        !finite(disk.totalBytes, 1) ||
        !finite(disk.availableBytes) ||
        disk.availableBytes > disk.totalBytes
      )
        throw Error("INVALID_HOST_METRICS");
      return {
        name: disk.name,
        totalBytes: disk.totalBytes,
        availableBytes: disk.availableBytes,
        usedBytes: disk.totalBytes - disk.availableBytes,
      };
    }),
  };
}
export function normalizeConnection(row, now = Date.now()) {
  if (
    !row ||
    !isIP(row.sourceIp) ||
    !isIP(row.destinationIp) ||
    !text(row.service, 100) ||
    !row.service ||
    !["tcp", "udp"].includes(row.transport) ||
    !Number.isInteger(row.sourcePort) ||
    row.sourcePort < 1 ||
    row.sourcePort > 65535 ||
    !Number.isInteger(row.destinationPort) ||
    row.destinationPort < 1 ||
    row.destinationPort > 65535 ||
    !/^[a-f0-9]{64}$/.test(row.connectionId || "")
  )
    throw Error("INVALID_CONNECTION_SAMPLE");
  return {
    connectionId: row.connectionId,
    sourceIp: row.sourceIp,
    destinationIp: row.destinationIp,
    sourcePort: row.sourcePort,
    destinationPort: row.destinationPort,
    service: row.service,
    transport: row.transport,
    state: text(row.state, 24) ? row.state : "observed",
    observedAt: at(row.observedAt, now),
    country: /^[A-Z]{2}$/.test(row.country || "") ? row.country : null,
    ...(finite(row.latitude, -90, 90) && finite(row.longitude, -180, 180)
      ? {
          latitude: row.latitude,
          longitude: row.longitude,
          locationPrecision:
            row.locationPrecision === "city" ? "city" : "country",
        }
      : {}),
  };
}
export function normalizeSource(input, now = Date.now()) {
  if (!input.source) return null;
  const source = input.source;
  if (
    !/^[a-f0-9-]{36}$/i.test(source.id || "") ||
    !text(source.name, 80) ||
    !source.name ||
    !Array.isArray(source.readers) ||
    source.readers.length > 8 ||
    !finite(source.dropped, 0) ||
    !Number.isSafeInteger(source.dropped)
  )
    throw Error("INVALID_COLLECTOR_SOURCE");
  const readers = source.readers.map((row) => {
    if (
      !["nginx", "conntrack", "sockets", "metrics", "geoip"].includes(
        row.kind,
      ) ||
      !["ok", "degraded", "unavailable", "disabled"].includes(row.status)
    )
      throw Error("INVALID_COLLECTOR_SOURCE");
    return {
      kind: row.kind,
      status: row.status,
      message: text(row.message, 160) ? row.message : "",
    };
  });
  const connections =
    input.connections === undefined ? undefined : input.connections;
  if (
    connections !== undefined &&
    (!Array.isArray(connections) || connections.length > 2000)
  )
    throw Error("CONNECTION_SAMPLE_LIMIT");
  return {
    id: source.id,
    name: source.name,
    geoipProvider: ["db-ip", "maxmind", "local"].includes(source.geoipProvider)
      ? source.geoipProvider
      : null,
    readers,
    dropped: source.dropped,
    observedAt: at(source.observedAt, now),
    connectionSampleAt: source.connectionSampleAt
      ? at(source.connectionSampleAt, now)
      : null,
    connections: connections?.map((row) => normalizeConnection(row, now)),
    connectionsTruncated: source.connectionsTruncated === true,
    vitals: input.vitals ? normalizeVitals(input.vitals, now) : null,
  };
}
export function trafficExtras(row) {
  const extra = {};
  if (["tcp", "udp"].includes(row.transport)) extra.transport = row.transport;
  for (const key of ["sourcePort", "destinationPort"])
    if (Number.isInteger(row[key]) && row[key] >= 1 && row[key] <= 65535)
      extra[key] = row[key];
  if (row.destinationIp && isIP(row.destinationIp))
    extra.destinationIp = row.destinationIp;
  if (/^[a-f0-9]{64}$/.test(row.connectionId || ""))
    extra.connectionId = row.connectionId;
  if (text(row.state, 24)) extra.state = row.state;
  if (text(row.method, 12) && /^[A-Z]+$/.test(row.method))
    extra.method = row.method;
  if (text(row.path, 240) && row.path.startsWith("/"))
    extra.path = row.path.split(/[?#]/, 1)[0];
  if (Number.isInteger(row.status) && row.status >= 100 && row.status <= 599)
    extra.status = row.status;
  if (finite(row.durationMs, 0, 3600000)) extra.durationMs = row.durationMs;
  if (finite(row.bytesSent)) extra.bytesSent = row.bytesSent;
  return extra;
}
