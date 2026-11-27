"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Plus, RefreshCw, ShieldCheck } from "lucide-react";
const levels = ["critical", "high", "medium", "low", "info"];
const errors = {
  TARGET_ADDRESS_BLOCKED:
    "This address is reserved or requires a private-network allowlist.",
  TARGET_CHANGED_REAUTHORIZE:
    "The target address changed. Revoke this asset and authorize its new address.",
  SCAN_COOLDOWN: "Wait one minute before scanning this asset again.",
  APPROVAL_REQUIRED: "Owner approval is pending.",
  SCAN_QUEUE_LIMIT: "Three scans are already queued or running.",
  ASSET_AUTHORIZATION_REQUIRED:
    "Confirm that you are authorized to check this target.",
};
async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: { "content-type": "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw Error(
      errors[data.error] || data.error || "The request could not be completed.",
    );
  return data;
}
const post = (path, data) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
export default function SecurityScanner() {
  const [assets, setAssets] = useState([]),
    [runs, setRuns] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [adding, setAdding] = useState(false),
    [selected, setSelected] = useState(null),
    [run, setRun] = useState(null),
    [level, setLevel] = useState("all");
  const [name, setName] = useState(""),
    [target, setTarget] = useState(""),
    [kind, setKind] = useState("web"),
    [ports, setPorts] = useState(""),
    [authorized, setAuthorized] = useState(false),
    [advisories, setAdvisories] = useState(false),
    [packages, setPackages] = useState("");
  const mutation = useRef(false),
    pending = useRef(null);
  async function refresh(signal) {
    const data = await api("/api/security/assets", { signal });
    if (!signal?.aborted) {
      setAssets(data.assets);
      setRuns(data.runs);
    }
    return data;
  }
  useEffect(() => {
    const chosen = new URL(window.location.href).searchParams.get("run");
    if (chosen && /^[a-f0-9-]{36}$/i.test(chosen)) setSelected(chosen);
    const controller = new AbortController();
    refresh(controller.signal)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    const timer = setInterval(() => {
      if (!document.hidden) refresh(controller.signal).catch(() => {});
    }, 5000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (!selected) {
      setRun(null);
      return;
    }
    const controller = new AbortController();
    setRun(null);
    const load = () =>
      api("/api/security/scans/" + selected, { signal: controller.signal })
        .then((data) => {
          if (!controller.signal.aborted) setRun(data.run);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    load();
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, 2500);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [selected]);
  async function mutate(fn) {
    if (mutation.current) return;
    mutation.current = true;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      mutation.current = false;
      setBusy(false);
    }
  }
  async function create(event) {
    event.preventDefault();
    await mutate(async () => {
      const dependencies = packages.trim()
        ? packages
            .trim()
            .split("\n")
            .map((line) => {
              const [ecosystem, name, version, ...rest] = line
                .trim()
                .split(/\s+/);
              if (rest.length || !version)
                throw Error("Use one package per line: npm next 16.4.6");
              return { ecosystem, name, version };
            })
        : [];
      const fields = {
        name,
        target,
        kind,
        authorized,
        checkAdvisories: advisories,
        packages: dependencies,
        ...(ports.trim()
          ? { ports }
          : kind === "minecraft"
            ? { ports: [25565] }
            : {}),
      };
      const fingerprint = JSON.stringify(fields);
      if (pending.current?.fingerprint !== fingerprint)
        pending.current = {
          fingerprint,
          body: { ...fields, requestId: crypto.randomUUID() },
        };
      const asset = await post("/api/security/assets", pending.current.body);
      pending.current = null;
      setAdding(false);
      setName("");
      setTarget("");
      setAuthorized(false);
      await refresh();
      window.dispatchEvent(new Event("vector:approvals"));
      if (asset.approvalStatus === "approved") {
        const job = await post("/api/security/scans", { assetId: asset.id });
        setSelected(job.id);
        await refresh();
      }
    });
  }
  async function start(assetId) {
    await mutate(async () => {
      const job = await post("/api/security/scans", { assetId });
      setSelected(job.id);
      await refresh();
    });
  }
  const result = run?.result;
  const findings = (result?.findings || []).filter(
    (f) => level === "all" || f.severity === level,
  );
  return (
    <div className="ctl-page">
      <header className="ctl-page-header">
        <div>
          <h1>Security Scanner</h1>
          <p>Check your websites, servers and infrastructure.</p>
        </div>
        <button
          className="ctl-primary"
          onClick={() => setAdding(!adding)}
          aria-expanded={adding}
        >
          <Plus size={16} />
          Add asset
        </button>
      </header>
      {error && (
        <div className="ctl-error" role="alert">
          {error}
        </div>
      )}
      {adding && (
        <section className="ctl-panel">
          <h2>Authorize an asset</h2>
          <form onSubmit={create}>
            <div className="ctl-split">
              <label>
                Name
                <input
                  required
                  value={name}
                  maxLength={100}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My website"
                />
              </label>
              <label>
                Domain, IP or host:port
                <input
                  required
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="example.com or nas.local:443"
                  autoCapitalize="none"
                  spellCheck={false}
                />
              </label>
            </div>
            <div className="ctl-split">
              <label>
                Type
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  {["web", "api", "minecraft", "nas", "network"].map((v) => (
                    <option key={v} value={v}>
                      {v === "web"
                        ? "Website"
                        : v === "api"
                          ? "API"
                          : v === "nas"
                            ? "NAS"
                            : v === "minecraft"
                              ? "Minecraft"
                              : "Network host"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                TCP ports
                <input
                  value={ports}
                  onChange={(e) => setPorts(e.target.value)}
                  placeholder={
                    kind === "minecraft"
                      ? "25565"
                      : "Common ports · optional comma-separated list"
                  }
                />
              </label>
            </div>
            <label className="ctl-check">
              <input
                type="checkbox"
                checked={advisories}
                onChange={(e) => setAdvisories(e.target.checked)}
              />
              Check versions against NVD and OSV. Product/package versions are
              sent to those services.
            </label>
            {advisories && (
              <label>
                Packages to check, optional
                <textarea
                  value={packages}
                  onChange={(e) => setPackages(e.target.value)}
                  placeholder={"npm next 16.4.6\nPyPI django 5.2.1"}
                />
                <small>
                  One ecosystem, package and exact version per line. Banner
                  matches are candidates, not verified exploits.
                </small>
              </label>
            )}
            <label className="ctl-check">
              <input
                type="checkbox"
                required
                checked={authorized}
                onChange={(e) => setAuthorized(e.target.checked)}
              />
              I own this target or have permission to perform these bounded
              checks. Authorization is saved for this asset until revoked or its
              address changes.
            </label>
            <div className="ctl-toolbar">
              <button type="submit" className="ctl-primary" disabled={busy}>
                {busy ? "Saving…" : "Authorize & scan"}
              </button>
              <button type="button" onClick={() => setAdding(false)}>
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}
      <div className="ctl-split">
        <div>
          <section className="ctl-panel">
            <h2>Assets</h2>
            {loading ? (
              <div aria-label="Loading assets" role="status">
                <div className="ctl-skeleton" />
                <div className="ctl-skeleton" />
              </div>
            ) : assets.length ? (
              assets.map((asset) => (
                <div className="ctl-asset" key={asset.id}>
                  <div>
                    <strong>{asset.name}</strong>
                    <small>{asset.scope.target.host}</small>
                    <details>
                      <summary>Settings</summary>
                      <p>Ports {asset.scope.target.ports.join(", ")}</p>
                      <p>
                        {asset.approvalStatus === "approved"
                          ? "Authorized"
                          : "Awaiting owner approval"}
                      </p>
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Revoke this asset and cancel its queued scans?",
                            )
                          )
                            mutate(async () => {
                              await api("/api/security/assets", {
                                method: "DELETE",
                                body: JSON.stringify({ id: asset.id }),
                              });
                              await refresh();
                              window.dispatchEvent(
                                new Event("vector:approvals"),
                              );
                            });
                        }}
                      >
                        Revoke authorization
                      </button>
                    </details>
                  </div>
                  <button
                    disabled={busy || asset.approvalStatus !== "approved"}
                    onClick={() => start(asset.id)}
                    aria-label={"Scan " + asset.name}
                  >
                    <RefreshCw size={14} />
                    Scan
                  </button>
                </div>
              ))
            ) : (
              <div className="ctl-empty">
                <ShieldCheck size={24} aria-hidden="true" />
                <p>Add an owned asset to run your first scan.</p>
              </div>
            )}
          </section>
          <section className="ctl-panel">
            <h2>Recent scans</h2>
            {runs.length ? (
              runs.map((row) => (
                <div className="ctl-asset" key={row.id}>
                  <div>
                    <strong>
                      {assets.find((a) => a.id === row.asset_id)?.name ||
                        "Archived asset"}
                    </strong>
                    <small>{new Date(row.created_at).toLocaleString()}</small>
                    <span className="ctl-status" data-state={row.status}>
                      {row.status}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      setSelected(row.id);
                      window.history.replaceState(
                        null,
                        "",
                        "/security?run=" + row.id,
                      );
                    }}
                    aria-label="Open scan report"
                  >
                    <ArrowUpRight size={16} />
                  </button>
                </div>
              ))
            ) : (
              <p>No scans yet.</p>
            )}
          </section>
        </div>
        <section className="ctl-panel" aria-live="polite">
          {!selected ? (
            <div className="ctl-empty">Select a scan to view its results.</div>
          ) : !run ? (
            <>
              <div className="ctl-skeleton" />
              <div className="ctl-skeleton" />
            </>
          ) : (
            <>
              <div className="ctl-page-header">
                <div>
                  <h2>{run.asset_name}</h2>
                  <span className="ctl-status" data-state={run.status}>
                    {run.status}
                  </span>
                </div>
                {["queued", "running"].includes(run.status) ? (
                  <button
                    disabled={busy}
                    onClick={() =>
                      mutate(() =>
                        api("/api/security/scans/" + run.id, {
                          method: "DELETE",
                        }),
                      )
                    }
                  >
                    Cancel scan
                  </button>
                ) : (
                  result && (
                    <div className="ctl-toolbar">
                      <a
                        className="ctl-button"
                        href={`/api/security/scans/${run.id}?format=json`}
                        download
                      >
                        JSON
                      </a>
                      <a
                        className="ctl-button"
                        href={`/api/security/scans/${run.id}?format=md`}
                        download
                      >
                        Markdown
                      </a>
                    </div>
                  )
                )}
              </div>
              {run.status === "queued" && (
                <p>
                  Queued for the background worker. Chat jobs have priority.
                </p>
              )}
              {run.status === "running" && (
                <>
                  <p>
                    {run.progress.stage || "Starting"}
                    {run.progress.completed !== undefined
                      ? ` · ${run.progress.completed}/${run.progress.total} TCP probes`
                      : ""}
                  </p>
                  <div className="ctl-skeleton" />
                </>
              )}
              {run.error && (
                <p className="ctl-error">{errors[run.error] || run.error}</p>
              )}
              {result && (
                <>
                  <div className="ctl-metrics">
                    {levels.map((v) => (
                      <div className="ctl-metric" key={v}>
                        <strong>{result.counts[v]}</strong>
                        <span>{v}</span>
                      </div>
                    ))}
                  </div>
                  <p>
                    {result.complete
                      ? "Requested TCP probes completed."
                      : "Partial coverage."}{" "}
                    {result.coverage.portsAttempted}/
                    {result.coverage.portsRequested} ports checked.{" "}
                    {Math.round(result.durationMs / 1000)} s.
                  </p>
                  <h3>Open ports</h3>
                  <div className="vector-table-wrap">
                    <table className="vector-table">
                      <thead>
                        <tr>
                          <th>Address</th>
                          <th>Port</th>
                          <th>Banner</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.ports
                          .filter((p) => p.state === "open")
                          .map((p) => (
                            <tr key={p.address + ":" + p.port}>
                              <td>{p.address}</td>
                              <td>{p.port}</td>
                              <td>{p.banner || "No banner"}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {!result.ports.some((p) => p.state === "open") && (
                    <p>No open ports observed in this scope.</p>
                  )}
                  {result.minecraft.map((game) => (
                    <div key={game.address + game.port} className="ctl-panel">
                      <h3>Minecraft · {game.port}</h3>
                      {game.error ? (
                        <p>{game.error}</p>
                      ) : (
                        <>
                          <p>{game.motd}</p>
                          <p>
                            {game.version} · {game.playersOnline ?? "Unknown"}/
                            {game.playersMax ?? "Unknown"} players
                          </p>
                          <small>
                            Authentication mode is not exposed by the status
                            protocol.
                          </small>
                        </>
                      )}
                    </div>
                  ))}
                  {result.web.map((site) => (
                    <details key={site.address + site.port}>
                      <summary>
                        {site.scheme.toUpperCase()} · {site.port} ·{" "}
                        {site.status || site.error}
                      </summary>
                      {site.tls && (
                        <p>
                          TLS {site.tls.protocol || site.tls.error} ·{" "}
                          {site.tls.verified
                            ? "Certificate verified"
                            : "Certificate not verified"}{" "}
                          · expires{" "}
                          {site.tls.validTo
                            ? new Date(site.tls.validTo).toLocaleDateString()
                            : "unknown"}
                        </p>
                      )}
                      <pre>{JSON.stringify(site.headers, null, 2)}</pre>
                    </details>
                  ))}
                  <div className="ctl-page-header" style={{ marginTop: 24 }}>
                    <h3>Findings</h3>
                    <label>
                      Severity
                      <select
                        value={level}
                        onChange={(e) => setLevel(e.target.value)}
                      >
                        <option value="all">All</option>
                        {levels.map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {findings.map((f, i) => (
                    <details className="ctl-panel" key={f.id + ":" + i}>
                      <summary>
                        <span className="ctl-status">{f.severity}</span>{" "}
                        {f.title}
                      </summary>
                      <p>{f.evidence}</p>
                      <p>{f.remediation}</p>
                      <small>{f.confidence}</small>
                      {f.references?.map((ref) => (
                        <p key={ref}>
                          <a href={ref} target="_blank" rel="noreferrer">
                            {f.id} advisory ↗
                          </a>
                        </p>
                      ))}
                    </details>
                  ))}
                  {!findings.length && (
                    <p>
                      No findings for this filter. This does not establish that
                      the target is secure.
                    </p>
                  )}
                  <details>
                    <summary>Coverage & limitations</summary>
                    {result.limitations.map((text) => (
                      <p key={text}>{text}</p>
                    ))}
                    <p>Advisory lookup: {result.advisories.status}</p>
                    {result.advisories.lookups.map((lookup, i) => (
                      <p key={i}>
                        {lookup.source} ·{" "}
                        {lookup.product || lookup.package?.name} ·{" "}
                        {lookup.status}
                      </p>
                    ))}
                  </details>
                </>
              )}
            </>
          )}
        </section>
      </div>
      <p>
        <a href="/security/evidence">Imported scan evidence</a>
      </p>
    </div>
  );
}
