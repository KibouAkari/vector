import { resolveTarget, ScanError } from "./targets.mjs";
import { tcpProbe, webAudit, minecraftProbe } from "./probes.mjs";
import {
  packageAdvisories,
  serviceAdvisories,
  serviceCpes,
} from "./advisories.mjs";
export async function runActiveScan(
  asset,
  {
    onProgress = async () => {},
    signal: externalSignal,
    resolve = resolveTarget,
    tcp = tcpProbe,
    web = webAudit,
    minecraft = minecraftProbe,
    osv = packageAdvisories,
    nvd = serviceAdvisories,
  } = {},
) {
  const signal = AbortSignal.any([
      externalSignal || new AbortController().signal,
      AbortSignal.timeout(75000),
    ]),
    started = Date.now();
  signal.throwIfAborted();
  const addresses = await resolve(asset.target);
  if (JSON.stringify(addresses) !== JSON.stringify(asset.addresses))
    throw new ScanError("TARGET_CHANGED_REAUTHORIZE");
  const ports = [],
    sites = [],
    games = [];
  const jobs = addresses.flatMap((address) =>
    asset.target.ports.map((port) => ({ address, port })),
  );
  let cursor = 0,
    completed = 0;
  await onProgress({ stage: "ports", completed, total: jobs.length });
  await Promise.all(
    Array.from({ length: 4 }, async () => {
      while (cursor < jobs.length && !signal.aborted) {
        const job = jobs[cursor++];
        ports.push(await tcp(job.address, job.port, { signal }));
        completed++;
        if (completed % 8 === 0)
          await onProgress({ stage: "ports", completed, total: jobs.length });
      }
    }),
  );
  const open = ports
    .filter((p) => p.state === "open")
    .sort((a, b) => a.address.localeCompare(b.address) || a.port - b.port);
  let webCount = 0;
  for (const port of open) {
    if (signal.aborted) break;
    const secure =
      [443, 8443, 9443].includes(port.port) ||
      (asset.target.scheme === "https" &&
        asset.target.explicitPort === port.port);
    const httpPort =
      [80, 443, 3000, 8000, 8080, 8443, 9090, 9443].includes(port.port) ||
      (asset.target.scheme && asset.target.explicitPort === port.port);
    if (httpPort && webCount < 6) {
      await onProgress({
        stage: "web",
        port: port.port,
        completed,
        total: jobs.length,
      });
      sites.push(
        await web(port.address, port.port, asset.target.host, secure, {
          signal,
        }),
      );
      webCount++;
    }
    if (
      port.port === 25565 ||
      (asset.kind === "minecraft" &&
        (asset.target.explicitPort === port.port ||
          asset.target.ports.length === 1))
    ) {
      await onProgress({ stage: "minecraft", port: port.port });
      games.push({
        address: port.address,
        port: port.port,
        ...(await minecraft(port.address, port.port, asset.target.host, {
          signal,
        })),
      });
    }
  }
  const findings = sites.flatMap((site) =>
    site.findings.map((f) => ({
      ...f,
      id: `${site.address}:${site.port}:${f.id}`,
      target: `${asset.target.host}:${site.port}`,
    })),
  );
  let advisories = { status: "not-requested", lookups: [] };
  if (asset.checkAdvisories && !signal.aborted) {
    await onProgress({ stage: "advisories" });
    const packages = await osv(asset.packages || [], { signal });
    const services = await nvd(serviceCpes(open, sites), { signal });
    findings.push(...packages.findings, ...services.findings);
    const lookups = [...packages.lookups, ...services.lookups];
    advisories = {
      status: lookups.some((l) => l.status !== "completed")
        ? "partial"
        : lookups.length
          ? "completed"
          : "no-identifiable-version",
      lookups,
    };
  }
  const counts = Object.fromEntries(
    ["critical", "high", "medium", "low", "info"].map((level) => [
      level,
      findings.filter((f) => f.severity === level).length,
    ]),
  );
  return {
    schemaVersion: 1,
    host: asset.target.host,
    addresses,
    startedAt: new Date(started).toISOString(),
    finishedAt: new Date().toISOString(),
    durationMs: Date.now() - started,
    complete: !signal.aborted && completed === jobs.length,
    ports: ports.sort((a, b) => a.port - b.port),
    web: sites,
    minecraft: games,
    findings,
    counts,
    advisories,
    coverage: {
      portsAttempted: completed,
      portsRequested: jobs.length,
      webEndpoints: sites.length,
      webEndpointLimit: 6,
    },
    limitations: [
      "At most six HTTP endpoints and three detected products are audited per run.",
      "TCP connect and bounded probes only. No exploitation, credential checks, UDP scan or authenticated assessment.",
      "Version advisory matches can be affected by spoofed banners or vendor backports.",
      "Minecraft status does not expose online-mode or prove authentication.",
    ],
  };
}
export function scanMarkdown(asset, result) {
  const escape = (value) =>
    String(value ?? "")
      .replace(/[\\`*_{}[\]<>|#!]/g, "\\$&")
      .replace(/[\r\n]/g, " ");
  const lines = [
    `# Security scan · ${escape(asset.name)}`,
    "",
    `Target: ${escape(result.host)}`,
    `Completed: ${escape(result.finishedAt)}`,
    `Coverage: ${result.complete ? "Completed requested TCP probes" : "Partial; timeout or cancellation"}`,
    "",
    "## Open ports",
    "",
    "| Address | Port | Banner |",
    "| --- | --- | --- |",
    ...result.ports
      .filter((p) => p.state === "open")
      .map((p) => `| ${escape(p.address)} | ${p.port} | ${escape(p.banner)} |`),
    "",
    "## Findings",
    "",
  ];
  for (const finding of result.findings)
    lines.push(
      `### ${escape(finding.severity.toUpperCase())} · ${escape(finding.title)}`,
      `Confidence: ${escape(finding.confidence)}`,
      `Evidence: ${escape(finding.evidence)}`,
      `Remediation: ${escape(finding.remediation)}`,
      "",
    );
  lines.push(
    "## Limitations",
    "",
    ...result.limitations.map(escape),
    "",
    "Advisory sources: NVD / OSV when explicitly requested; lookup failures are not a clean result.",
  );
  return lines.join("\n");
}
