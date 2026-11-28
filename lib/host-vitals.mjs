const numeric = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0;
export function humanBytes(value) {
  if (typeof value !== "string") return null;
  const match = /^([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?)(?:i?B?)$/i.exec(value);
  if (!match) return null;
  return (
    Number(match[1]) *
    1024 ** (match[2] ? "KMGTPE".indexOf(match[2].toUpperCase()) + 1 : 0)
  );
}
export function fallbackVitals(snapshot) {
  const line = String(snapshot?.memory || "")
    .split("\n")
    .find((row) => /^Mem:\s*/.test(row));
  const fields = line?.trim().split(/\s+/) || [];
  const total = humanBytes(fields[1]),
    available = humanBytes(fields[6]);
  const disks = String(snapshot?.disk || "")
    .split("\n")
    .map((row) => row.trim().split(/\s+/))
    .filter((row) => row.length >= 6 && row[5] === "/");
  const disk = disks[0];
  const diskTotal = disk ? humanBytes(disk[1]) : null,
    diskAvailable = disk ? humanBytes(disk[3]) : null;
  return {
    available: Boolean(total || diskTotal),
    observedAt: new Date().toISOString(),
    sourceName: "Host agent",
    approximate: true,
    cpuPercent: null,
    memory:
      total && available !== null && available <= total
        ? {
            totalBytes: total,
            availableBytes: available,
            usedBytes: total - available,
          }
        : null,
    storage:
      diskTotal && diskAvailable !== null && diskAvailable <= diskTotal
        ? [
            {
              name: "System",
              totalBytes: diskTotal,
              availableBytes: diskAvailable,
              usedBytes: diskTotal - diskAvailable,
            },
          ]
        : [],
    history: [],
  };
}
export const utilization = (used, total) =>
  numeric(used) && numeric(total) && total > 0
    ? Math.min(100, (100 * used) / total)
    : null;
