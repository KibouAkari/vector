// Advisory matches are version-based candidates, never exploit verification.
const safe = (value) =>
  String(value || "")
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .slice(0, 500);
export function validatePackages(value = []) {
  if (!Array.isArray(value) || value.length > 10)
    throw Error("INVALID_PACKAGES");
  return value.map((row) => {
    if (
      !row ||
      ![
        "npm",
        "PyPI",
        "Go",
        "Maven",
        "crates.io",
        "RubyGems",
        "Packagist",
        "NuGet",
      ].includes(row.ecosystem) ||
      typeof row.name !== "string" ||
      !row.name.trim() ||
      row.name.length > 160 ||
      typeof row.version !== "string" ||
      !row.version.trim() ||
      row.version.length > 80 ||
      /[\s\u0000-\u001f]/.test(row.name + row.version)
    )
      throw Error("INVALID_PACKAGES");
    return { ecosystem: row.ecosystem, name: row.name, version: row.version };
  });
}
async function boundedJson(url, options, fetchImpl) {
  const response = await fetchImpl(url, { ...options, redirect: "error" });
  if (!response.ok) throw Error("ADVISORY_UNAVAILABLE");
  const reader = response.body.getReader();
  const parts = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 2 * 1024 * 1024) throw Error("ADVISORY_LIMIT");
      parts.push(Buffer.from(value));
    }
    return JSON.parse(Buffer.concat(parts).toString("utf8"));
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
export async function packageAdvisories(
  packages,
  { signal, fetchImpl = fetch } = {},
) {
  const findings = [],
    lookups = [];
  for (const pkg of validatePackages(packages)) {
    if (signal?.aborted) break;
    try {
      const data = await boundedJson(
        "https://api.osv.dev/v1/query",
        {
          method: "POST",
          signal: AbortSignal.any([
            signal || new AbortController().signal,
            AbortSignal.timeout(5000),
          ]),
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            package: { name: pkg.name, ecosystem: pkg.ecosystem },
            version: pkg.version,
          }),
        },
        fetchImpl,
      );
      if (
        (data.vulns !== undefined && !Array.isArray(data.vulns)) ||
        (data.vulns === undefined &&
          Object.keys(data).some((key) => key !== "next_page_token"))
      )
        throw Error("INVALID_ADVISORY_RESPONSE");
      lookups.push({
        source: "OSV",
        package: pkg,
        status: data.next_page_token ? "partial" : "completed",
        matches: (data.vulns || []).length,
      });
      for (const vuln of (data.vulns || []).slice(0, 40)) {
        const level = String(
          vuln.database_specific?.severity ||
            vuln.ecosystem_specific?.severity ||
            "",
        ).toLowerCase();
        const severity = ["critical", "high", "medium", "low"].includes(level)
          ? level
          : "info";
        const fixes = (vuln.affected || [])
          .flatMap((item) =>
            (item.ranges || []).flatMap((range) =>
              (range.events || [])
                .filter((e) => e.fixed)
                .map((e) => safe(e.fixed)),
            ),
          )
          .slice(0, 10);
        findings.push({
          id: safe(vuln.id),
          severity,
          title: safe(vuln.summary || vuln.id),
          confidence: "version-match",
          evidence: `${pkg.ecosystem} ${pkg.name}@${pkg.version}; operator-supplied version`,
          remediation: fixes.length
            ? "Review advisory applicability; published fixed versions: " +
              fixes.join(", ")
            : "Review the advisory and upgrade to a supported fixed version.",
          references: [
            `https://osv.dev/vulnerability/${encodeURIComponent(vuln.id)}`,
          ],
          aliases: (vuln.aliases || []).slice(0, 10).map(safe),
          source: "OSV",
        });
      }
    } catch {
      lookups.push({
        source: "OSV",
        package: pkg,
        status: "unavailable",
        matches: null,
      });
    }
  }
  return { findings, lookups };
}
const NVD_CPE = [
  [/\bnginx\/(\d+(?:\.\d+){1,3})/i, "nginx:nginx"],
  [/\bApache\/(\d+(?:\.\d+){1,3})/i, "apache:http_server"],
  [/\bOpenSSH[_/](\d+(?:\.\d+){1,3}(?:p\d+)?)/i, "openbsd:openssh"],
];
export function serviceCpes(ports, web) {
  const evidence = [
    ...ports.map((p) => p.banner),
    ...web.map((w) => w.headers?.server),
  ].filter(Boolean);
  const matches = new Map();
  for (const text of evidence)
    for (const [pattern, product] of NVD_CPE) {
      const match = pattern.exec(text);
      if (match) {
        const cpe = `cpe:2.3:a:${product}:${match[1]}:*:*:*:*:*:*:*`;
        matches.set(cpe, { cpe, evidence: safe(match[0]) });
      }
    }
  return [...matches.values()].slice(0, 3);
}
export async function serviceAdvisories(
  products,
  { signal, fetchImpl = fetch, apiKey = process.env.NVD_API_KEY } = {},
) {
  const findings = [],
    lookups = [];
  for (let i = 0; i < products.length; i++) {
    if (signal?.aborted) break;
    // Public NVD allowance is shared; limit this optional run to three products.
    if (i)
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, 6500);
        const stop = () => {
          clearTimeout(timer);
          resolve();
        };
        signal?.addEventListener("abort", stop, { once: true });
      });
    const product = products[i];
    try {
      const url =
        "https://services.nvd.nist.gov/rest/json/cves/2.0?" +
        new URLSearchParams({
          cpeName: product.cpe,
          isVulnerable: "",
          resultsPerPage: "20",
        });
      const data = await boundedJson(
        url,
        {
          signal: AbortSignal.any([
            signal || new AbortController().signal,
            AbortSignal.timeout(5000),
          ]),
          headers: apiKey ? { apiKey } : {},
        },
        fetchImpl,
      );
      if (
        !Number.isSafeInteger(data.totalResults) ||
        data.totalResults < 0 ||
        !Array.isArray(data.vulnerabilities)
      )
        throw Error("INVALID_ADVISORY_RESPONSE");
      lookups.push({
        source: "NVD",
        product: product.evidence,
        status: data.totalResults > 20 ? "partial" : "completed",
        matches: data.totalResults,
      });
      for (const entry of (data.vulnerabilities || []).slice(0, 20)) {
        const cve = entry.cve;
        const metric =
          cve.metrics?.cvssMetricV40?.[0] ||
          cve.metrics?.cvssMetricV31?.[0] ||
          cve.metrics?.cvssMetricV30?.[0];
        const level = String(
          metric?.cvssData?.baseSeverity || "",
        ).toLowerCase();
        findings.push({
          id: safe(cve.id),
          title: safe(
            cve.descriptions?.find((d) => d.lang === "en")?.value || cve.id,
          ),
          severity: ["critical", "high", "medium", "low"].includes(level)
            ? level
            : "info",
          confidence: "banner-version-match",
          source: "NVD",
          evidence: product.evidence,
          remediation:
            "Verify installed package, vendor patches and advisory conditions; banners alone do not confirm vulnerability. Upgrade if affected.",
          references: [
            `https://nvd.nist.gov/vuln/detail/${encodeURIComponent(cve.id)}`,
          ],
        });
      }
    } catch {
      lookups.push({
        source: "NVD",
        product: product.evidence,
        status: "unavailable",
        matches: null,
      });
    }
  }
  return { findings, lookups };
}
