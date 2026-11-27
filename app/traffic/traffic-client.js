"use client";
import { useEffect, useState, Component } from "react";
import dynamic from "next/dynamic";
import { Globe2, Network, Radio, MapPin, Search } from "lucide-react";
import {
  Page,
  Panel,
  Metric,
  Empty,
  Refresh,
} from "../../components/operations/primitives";
const Globe = dynamic(
  () => import("../../components/operations/traffic-globe"),
  { ssr: false, loading: () => <div className="op-globe op-skeleton" /> },
);
class GlobeBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p className="op-muted">
        The globe is unavailable on this device. Use the observations below.
      </p>
    ) : (
      this.props.children
    );
  }
}
export default function Traffic() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState("");
  async function load() {
    setBusy(true);
    try {
      const response = await fetch("/api/traffic", { cache: "no-store" }),
        value = await response.json();
      if (!response.ok) throw Error(value.error);
      setData(value);
      setError("");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, 30000);
    return () => clearInterval(timer);
  }, []);
  const rows = (data?.clients || []).filter((row) =>
    (row.sourceIp + " " + row.service + " " + row.country)
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const countries = new Set(
      data?.clients.map((row) => row.country).filter(Boolean) || [],
    ),
    clients = new Set(data?.clients.map((row) => row.sourceIp) || []),
    services = new Set(data?.clients.map((row) => row.service) || []);
  return (
    <Page
      title="Traffic"
      eyebrow="Operations"
      description="Who reached which service."
      actions={<Refresh onClick={load} loading={busy} />}
    >
      {error && (
        <p className="op-error" role="alert">
          {error}
        </p>
      )}
      <div className="op-metrics">
        <Metric label="Observed clients" value={clients.size} icon={Network} />
        <Metric label="Services" value={services.size} icon={Radio} />
        <Metric
          label="Located countries"
          value={countries.size}
          icon={Globe2}
        />
        <Metric
          label="Observations"
          value={data?.observations || 0}
          icon={MapPin}
          detail={data?.capped ? "Most recent 10,000 only" : "Last 24 hours"}
        />
      </div>
      <div className="op-split">
        <Panel
          title="Locations"
          subtitle="Only collector-supplied coordinates are plotted"
        >
          <GlobeBoundary>
            <Globe clients={data?.clients || []} />
          </GlobeBoundary>
        </Panel>
        <Panel title="Sources">
          <StatusLine
            label="Signed collector"
            value={data?.configured ? "Configured" : "Not configured"}
          />
          <StatusLine
            label="Latest observation"
            value={
              data?.latestAt
                ? new Date(data.latestAt).toLocaleString()
                : "No data"
            }
          />
          <StatusLine label="Retention" value="24 hours" />
          <p className="op-muted">
            Requests and connection snapshots are separate measurements. A
            request count is not a count of simultaneous connections.
          </p>
          <details className="op-details">
            <summary>Connect a collector</summary>
            <p>
              Set VECTOR_TRAFFIC_INGEST_TOKEN on the app and collector. Run
              scripts/collectors/traffic.py against trusted nginx JSON logs with
              an exact service map. Country and coordinates can come from a
              local GeoIP database.
            </p>
          </details>
        </Panel>
      </div>
      <Panel
        title="Observed clients"
        actions={
          <div className="op-inline">
            <Search size={14} />
            <input
              className="op-field"
              aria-label="Filter observations"
              placeholder="IP, country or service…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        }
      >
        {rows.length ? (
          <div className="op-table-scroll">
            <table className="op-table">
              <thead>
                <tr>
                  <th>Source IP</th>
                  <th>Country</th>
                  <th>Service</th>
                  <th>Measurement</th>
                  <th>Observations</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.sourceIp + row.service + row.kind}>
                    <td>
                      <code>{row.sourceIp}</code>
                    </td>
                    <td>{row.country || "Unknown"}</td>
                    <td>{row.service}</td>
                    <td>
                      {row.kind === "http-request"
                        ? "HTTP request"
                        : "Connection snapshot"}
                    </td>
                    <td>{row.observations}</td>
                    <td>{new Date(row.observedAt).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Network}
            title="No observations yet"
            description="Connect a collector to show traffic from your own services."
          />
        )}
      </Panel>
    </Page>
  );
}
function StatusLine({ label, value }) {
  return (
    <dl className="op-facts">
      <div>
        <dt>{label}</dt>
        <dd>{value}</dd>
      </div>
    </dl>
  );
}
