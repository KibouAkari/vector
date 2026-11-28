"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  ChevronDown,
  Globe2,
  Network,
  Search,
  ShieldCheck,
  Radio,
  X,
} from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import {
  Page,
  Panel,
  Empty,
  Status,
} from "../../components/operations/primitives";
import WorldMap from "../../components/operations/world-map";
import { useObservatory } from "../../components/operations/use-observatory";
import { useInterfaceMotion } from "../../components/operations/use-interface-motion";
const time = (value) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
const number = (value) => Number(value || 0).toLocaleString();
const labels = {
  "connection-open": "Opened",
  "connection-close": "Closed",
  "network-attempt": "Attempt",
  "connection-snapshot": "Snapshot",
  "http-request": "Request",
};
export default function Traffic() {
  const [minutes, setMinutes] = useState(60),
    [mode, setMode] = useState("connections"),
    [service, setService] = useState(""),
    [country, setCountry] = useState(null),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState(null);
  const {
      traffic: data,
      loading,
      errors,
    } = useObservatory({ server: false, minutes }),
    reduced = useInterfaceMotion();
  const recent = data?.recentEvents || [],
    connections = errors.traffic ? [] : data?.activeConnections || [],
    groups = data?.clients || [];
  const matches = (row) =>
    (!service || row.service === service) &&
    (!country || row.country === country) &&
    [
      row.sourceIp,
      row.destinationIp,
      row.country,
      row.service,
      row.destinationPort,
    ]
      .join(" ")
      .toLowerCase()
      .includes(query.trim().toLowerCase());
  const mapRows = (
    mode === "connections"
      ? connections
      : groups.filter((row) =>
          mode === "requests"
            ? row.kind === "http-request"
            : row.kind === "network-attempt",
        )
  ).filter(
    (row) =>
      (!service || row.service === service) &&
      [row.sourceIp, row.service, row.country]
        .join(" ")
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const tableRows = (
    mode === "connections"
      ? connections
      : recent.filter((row) =>
          mode === "requests"
            ? row.kind === "http-request"
            : row.kind === "network-attempt",
        )
  ).filter(matches);
  const services = useMemo(
    () =>
      [
        ...new Set([
          ...(data?.services || []).map((row) => row.name),
          ...connections.map((row) => row.service),
        ]),
      ].sort(),
    [data],
  );
  const liveSources = errors.traffic
      ? []
      : data?.sources?.filter((row) => !row.stale) || [],
    degraded = data?.sources?.some(
      (row) =>
        row.stale ||
        row.dropped ||
        row.readers?.some((reader) =>
          ["degraded", "unavailable"].includes(reader.status),
        ),
    );
  const scans = data?.activity?.scans || [];
  return (
    <Page
      title="Traffic"
      actions={
        <>
          <span className={"ob-live" + (!liveSources.length ? " muted" : "")}>
            <i />
            {liveSources.length ? "Updating every 5 seconds" : "No live source"}
          </span>
          <select
            className="op-field"
            aria-label="Traffic time range"
            value={minutes}
            onChange={(event) => setMinutes(Number(event.target.value))}
          >
            {[
              [15, "Last 15 min"],
              [60, "Last hour"],
              [360, "Last 6 hours"],
              [1440, "Last 24 hours"],
            ].map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </>
      }
    >
      {errors.traffic && (
        <p role="alert" className="op-error">
          Traffic is unavailable. Previously loaded data may be out of date.
        </p>
      )}
      <div className="ob-traffic-stats">
        <div>
          <span>Tracked flows</span>
          <strong>
            {loading
              ? "—"
              : errors.traffic
                ? "—"
                : number(data?.activeConnectionCount)}
          </strong>
          <small>Fresh TCP sessions and UDP flows</small>
        </div>
        <div>
          <span>HTTP requests</span>
          <strong>{loading ? "—" : number(data?.requests)}</strong>
          <small>Selected time range</small>
        </div>
        <div>
          <span>Observed clients</span>
          <strong>{loading ? "—" : number(data?.uniqueClients)}</strong>
          <small>{data?.countries?.length || 0} located countries</small>
        </div>
        <div>
          <span>Connection attempts</span>
          <strong>{loading ? "—" : number(data?.attempts)}</strong>
          <small>Observed starts and state changes</small>
        </div>
      </div>
      <div className="ob-traffic-layout">
        <section className="ob-traffic-map">
          <div className="ob-map-heading">
            <div
              className="op-segment"
              role="group"
              aria-label="Traffic measurement"
            >
              {[
                ["connections", "Connections"],
                ["requests", "Requests"],
                ["attempts", "Attempts"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  aria-pressed={mode === key}
                  onClick={() => {
                    setMode(key);
                    setSelected(null);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="ob-period">
              {mode === "connections"
                ? "Current sample"
                : "Selected time range"}
            </span>
          </div>
          <WorldMap
            dbip={data?.sources?.some(
              (source) => source.geoipProvider === "db-ip",
            )}
            rows={mapRows}
            selectedCountry={country}
            onCountry={setCountry}
            mode={mode}
          />
          <div
            className="ob-traffic-chart"
            role="img"
            aria-label="Requests and connection observations over the selected time range"
          >
            <ResponsiveContainer width="100%" height={85}>
              <BarChart data={data?.timeline || []} barCategoryGap="20%">
                <XAxis dataKey="time" hide />
                <Tooltip
                  labelFormatter={time}
                  contentStyle={{
                    background: "#07090c",
                    border: "1px solid #ffffff20",
                    borderRadius: 6,
                    fontSize: 10,
                  }}
                />
                <Bar
                  dataKey="requests"
                  name="HTTP requests"
                  fill="#a4bbc8"
                  isAnimationActive={!reduced}
                />
                <Bar
                  dataKey="connections"
                  name="Connection observations"
                  fill="#4c6d74"
                  isAnimationActive={!reduced}
                />
                <Bar
                  dataKey="attempts"
                  name="Attempts"
                  fill="#b6a68c"
                  isAnimationActive={!reduced}
                />
              </BarChart>
            </ResponsiveContainer>
            <div className="ob-chart-ends">
              <span>{time(data?.timeline?.[0]?.time)}</span>
              <span>{time(data?.serverTime)}</span>
            </div>
          </div>
        </section>
        <aside className="ob-traffic-sources">
          <h2>Collection</h2>
          {data?.sources?.length ? (
            data.sources.map((source) => (
              <details
                key={source.id}
                className="ob-source"
                open={source.stale || undefined}
              >
                <summary>
                  <Radio size={13} />
                  <span>{source.name}</span>
                  <Status
                    value={
                      source.stale
                        ? "stale"
                        : source.readers.some(
                              (row) =>
                                row.status === "unavailable" ||
                                row.status === "degraded",
                            )
                          ? "degraded"
                          : "connected"
                    }
                  />
                  <ChevronDown size={12} />
                </summary>
                <dl>
                  <div>
                    <dt>Heartbeat</dt>
                    <dd>{time(source.receivedAt)}</dd>
                  </div>
                  <div>
                    <dt>Network sample</dt>
                    <dd>
                      {source.sampleStale
                        ? "Out of date"
                        : time(source.connectionSampleAt)}
                    </dd>
                  </div>
                  <div>
                    <dt>Dropped events</dt>
                    <dd>{number(source.dropped)}</dd>
                  </div>
                </dl>
                {source.readers.map((reader, index) => (
                  <p key={reader.kind + index}>
                    <span>{reader.kind}</span>
                    <small data-status={reader.status}>{reader.status}</small>
                    {reader.message && <em>{reader.message}</em>}
                  </p>
                ))}
                {source.connectionsTruncated && (
                  <p className="op-muted">
                    Connection sample reached its limit.
                  </p>
                )}
              </details>
            ))
          ) : (
            <div className="ob-source-empty">
              <Network size={22} strokeWidth={1} />
              <p>The local collector is not sending yet.</p>
              <span>
                Host metrics, nginx requests and forwarded Minecraft connections
                appear here after installation.
              </span>
            </div>
          )}
          <div className="ob-coverage-note">
            <ShieldCheck size={14} />
            <p>
              Metadata only. No message bodies, credentials or packet payloads.
              Locations are approximate.
            </p>
          </div>
          {degraded && (
            <p className="ob-coverage-warning">
              Coverage is incomplete. Expand a source for details.
            </p>
          )}
          <Link href="/connections" className="op-link">
            Manage connections
            <ArrowUpRight size={12} />
          </Link>
        </aside>
      </div>
      <Panel
        title={
          mode === "connections"
            ? "Current connections"
            : mode === "requests"
              ? "Recent HTTP requests"
              : "Recent connection attempts"
        }
        subtitle={
          mode === "connections"
            ? "Fresh samples only. UDP entries represent tracked flows."
            : "Latest 80 events from the selected time range."
        }
        actions={
          <div className="ob-traffic-filters">
            <label className="ob-filter-search">
              <Search size={13} />
              <input
                aria-label="Search traffic"
                placeholder="IP or service…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <select
              className="op-field"
              aria-label="Filter by service"
              value={service}
              onChange={(event) => setService(event.target.value)}
            >
              <option value="">All services</option>
              {services.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            {country && (
              <button
                className="op-button"
                onClick={() => setCountry(null)}
                aria-label="Clear country filter"
              >
                {country}
                <X size={11} />
              </button>
            )}
          </div>
        }
      >
        {tableRows.length ? (
          <div className="op-table-scroll">
            <table className="op-table ob-traffic-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Country</th>
                  <th>Service</th>
                  <th>{mode === "requests" ? "Request" : "Destination"}</th>
                  <th>{mode === "requests" ? "Status" : "State"}</th>
                  <th>{mode === "requests" ? "Latency" : "Observed"}</th>
                  <th>
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, index) => (
                  <tr key={(row.connectionId || row.sourceIp) + index}>
                    <td>
                      <code>{row.sourceIp}</code>
                    </td>
                    <td>{row.country || "Unlocated"}</td>
                    <td>{row.service}</td>
                    <td>
                      {mode === "requests" ? (
                        row.method || "HTTP"
                      ) : (
                        <code>
                          {row.destinationPort
                            ? `${row.transport?.toUpperCase() || "TCP"} / ${row.destinationPort}`
                            : "—"}
                        </code>
                      )}
                    </td>
                    <td>
                      {mode === "requests"
                        ? row.status || "—"
                        : row.state || labels[row.kind]}
                    </td>
                    <td>
                      {mode === "requests"
                        ? row.durationMs === undefined
                          ? "—"
                          : Math.round(row.durationMs) + " ms"
                        : time(row.observedAt)}
                    </td>
                    <td>
                      <button
                        className="op-icon"
                        aria-label={`View details for ${row.sourceIp}`}
                        onClick={() => setSelected(row)}
                      >
                        <ArrowUpRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Network}
            title={
              loading
                ? "Loading traffic…"
                : country || service || query
                  ? "No matching observations"
                  : "No observations yet"
            }
            description={
              mode === "connections"
                ? "Only fresh connection samples are listed."
                : "New events appear as the collector sends them."
            }
          />
        )}
        {((data?.activeTruncated && mode === "connections") ||
          data?.capped) && (
          <p className="op-muted">
            The collection or display limit was reached. This is a bounded view
            of observed traffic.
          </p>
        )}
      </Panel>
      <Panel
        title="Scan activity"
        actions={
          <Link href="/security" className="op-link">
            Open scanner
            <ArrowUpRight size={12} />
          </Link>
        }
      >
        {scans.length ? (
          <div className="ob-scan-activity">
            {scans.slice(0, 5).map((scan) => (
              <Link href="/security" key={scan.id}>
                <ShieldCheck size={14} />
                <div>
                  <strong>{scan.name}</strong>
                  <span>{scan.stage || time(scan.createdAt)}</span>
                </div>
                <Status value={scan.status} />
                <ArrowUpRight size={12} />
              </Link>
            ))}
          </div>
        ) : (
          <p className="op-muted">
            Your scans will appear here. Opening this page does not start a
            scan.
          </p>
        )}
      </Panel>
      <ObservationDetails
        selected={selected}
        onClose={() => setSelected(null)}
      />
    </Page>
  );
}

function ObservationDetails({ selected, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    if (!selected) return;
    const previous = document.activeElement;
    dialog.current?.showModal();
    return () => {
      dialog.current?.close();
      previous?.focus?.();
    };
  }, [selected]);
  return (
    <dialog
      ref={dialog}
      className="ob-detail-backdrop"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
    >
      {selected && (
        <aside className="ob-traffic-detail" aria-label="Observation details">
          <header>
            <h2>Observation</h2>
            <button
              autoFocus
              className="op-icon"
              aria-label="Close details"
              onClick={onClose}
            >
              <X size={18} />
            </button>
          </header>
          <dl>
            {Object.entries({
              Client: selected.sourceIp,
              Country: selected.country || "Unlocated",
              Service: selected.service,
              Destination: selected.destinationIp,
              Port: selected.destinationPort,
              Transport: selected.transport,
              Measurement: labels[selected.kind],
              State: selected.state,
              Method: selected.method,
              Status: selected.status,
              "Latency (ms)": selected.durationMs,
              "Bytes sent": selected.bytesSent,
              Observed: time(selected.observedAt),
              Collector: selected.collectorName,
            })
              .filter(([, value]) => value !== undefined && value !== null)
              .map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
          </dl>
        </aside>
      )}
    </dialog>
  );
}
