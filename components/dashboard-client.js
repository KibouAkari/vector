"use client";
import { useEffect, useState, Component } from "react";
import { conversationLabel } from "../lib/chat-presentation.mjs";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Activity,
  ArrowUpRight,
  ArrowDownToLine,
  ChevronRight,
  Plus,
  Clock3,
  FolderKanban,
  Check,
  CornerDownRight,
  Workflow,
  MessageSquare,
  Pause,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Page, Panel, Empty, Status, Sparkline } from "./operations/primitives";
import { useInterfaceMotion } from "./operations/use-interface-motion";
import { useObservatory } from "./operations/use-observatory";
import ServerVitals from "./operations/server-vitals";
import Donut from "./operations/donut";
import WorldMap from "./operations/world-map";
const Globe = dynamic(() => import("./operations/traffic-globe"), {
  ssr: false,
  loading: () => <div className="ob-globe" />,
});
class GlobeGuard extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="vc-geography-fallback">
        <WorldMap rows={this.props.clients} dbip={this.props.dbip} />
      </div>
    ) : (
      this.props.children
    );
  }
}
const number = (value) =>
  new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value) || 0);
const money = (value) => "CHF " + Number(value || 0).toFixed(2);
export default function DashboardClient({
  displayName,
  totals = {},
  models = [],
  timeline = [],
  projects = [],
  allowedPaths = null,
}) {
  const reduced = useInterfaceMotion(),
    allowChat = !allowedPaths || allowedPaths.includes("/chat"),
    allowProjects = !allowedPaths || allowedPaths.includes("/projects"),
    allowTraffic = !allowedPaths || allowedPaths.includes("/traffic"),
    allowServer = !allowedPaths || allowedPaths.includes("/server");
  const telemetry = useObservatory({
    traffic: allowTraffic,
    server: allowServer,
  });
  const [activity, setActivity] = useState(null),
    [metric, setMetric] = useState("requests"),
    [tab, setTab] = useState("recent");
  useEffect(() => {
    const controller = new AbortController();
    let active = true,
      inFlight = false;
    const load = async () => {
      if (document.hidden || inFlight) return;
      inFlight = true;
      try {
        const response = await fetch("/api/operations/activity", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (response.ok && active) setActivity(await response.json());
      } catch {
      } finally {
        inFlight = false;
      }
    };
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  const work =
      tab === "active" ? activity?.activeJobs || [] : activity?.jobs || [],
    traffic = telemetry.traffic;
  const uncached = Math.max(
    0,
    (totals.inputTokens || 0) - (totals.cachedTokens || 0),
  );
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { period: "30 UTC calendar days", totals, models, timeline },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "vector-usage.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <Page
      title="Overview"
      className="ob-dashboard"
      actions={
        <>
          <span className="ob-period">Last 30 days</span>
          {allowChat && (
            <Link href="/chat" className="op-button primary">
              <Plus size={14} />
              New conversation
            </Link>
          )}
          <button className="op-button" onClick={download}>
            <ArrowDownToLine size={14} />
            Export
          </button>
        </>
      }
    >
      <div className="ob-dashboard-layout">
        <div className="ob-work-column">
          <div className="ob-stat-line">
            <div>
              <span>Provider calls</span>
              <strong>{number(totals.providerCalls)}</strong>
              <Sparkline
                values={timeline.map((row) => row.requests)}
                height={28}
              />
            </div>
            <div>
              <span>Recorded spend</span>
              <strong>{money(totals.spend)}</strong>
              <small>
                {totals.incompleteCalls
                  ? `${totals.incompleteCalls} incomplete cost records`
                  : "Reported and configured rates"}
              </small>
            </div>
            <div>
              <span>Tokens</span>
              <strong>{number(totals.totalTokens)}</strong>
              <small>{number(totals.cachedTokens)} cached input</small>
            </div>
          </div>
          <div className="vc-overview-focus">
            <Panel
              title="My tasks"
              actions={
                <div className="op-segment">
                  <button
                    onClick={() => setTab("recent")}
                    aria-pressed={tab === "recent"}
                  >
                    Recent
                  </button>
                  <button
                    onClick={() => setTab("active")}
                    aria-pressed={tab === "active"}
                  >
                    Active{" "}
                    {activity?.counts
                      ? activity.counts.running + activity.counts.queued
                      : ""}
                  </button>
                </div>
              }
              className="ob-work-panel"
            >
              {work.length ? (
                <div className="ob-task-list">
                  {work.slice(0, 3).map((row) => (
                    <Link
                      key={row.id}
                      href={
                        row.projectId
                          ? row.conversationId
                            ? `/projects/${encodeURIComponent(row.projectId)}?conversation=${encodeURIComponent(row.conversationId)}`
                            : `/projects/${encodeURIComponent(row.projectId)}`
                          : row.conversationId
                            ? `/chat?conversation=${encodeURIComponent(row.conversationId)}`
                            : "/chat"
                      }
                    >
                      <span className={"ob-task-marker " + row.status}>
                        {row.status === "completed" ? (
                          <Check size={13} />
                        ) : row.status === "running" ? (
                          <Activity size={13} />
                        ) : (
                          <Clock3 size={13} />
                        )}
                      </span>
                      <div>
                        <strong>{conversationLabel(row.title)}</strong>
                        <span>
                          {row.stage && row.stage !== row.status
                            ? row.stage
                            : row.status}
                        </span>
                      </div>
                      <ChevronRight size={13} />
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="ob-quiet-empty">
                  <Workflow size={22} strokeWidth={1.1} />
                  <div>
                    <strong>
                      {activity
                        ? "No active tasks"
                        : "Your recent work appears here"}
                    </strong>
                    <p>Start a conversation or continue a project.</p>
                  </div>
                  <Link className="op-link" href="/teams">
                    Agent teams
                    <ArrowUpRight size={13} />
                  </Link>
                </div>
              )}
              <div className="ob-work-counts">
                <span>
                  <i className="dot-running" />
                  {activity?.counts?.running ?? "—"} running
                </span>
                <span>
                  <i />
                  {activity?.counts?.queued ?? "—"} queued
                </span>
                <span>
                  {activity?.counts?.completed ?? "—"} completed · 24h
                </span>
              </div>
            </Panel>
            <Panel
              title="Usage"
              subtitle="30 UTC calendar days"
              actions={
                <div className="op-segment">
                  {[
                    ["requests", "Entries"],
                    ["totalTokens", "Tokens"],
                    ["spend", "Spend"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      aria-pressed={metric === key}
                      onClick={() => setMetric(key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              }
            >
              <div
                className="ob-usage-chart"
                role="img"
                aria-label={metric + " over the last 30 days"}
              >
                <ResponsiveContainer width="100%" height={225}>
                  <AreaChart
                    data={timeline}
                    margin={{ top: 12, right: 4, left: -20, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id="ob-usage-fill"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop stopColor="#a5bdcc" stopOpacity={0.13} />
                        <stop offset="1" stopColor="#a5bdcc" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      vertical={false}
                      stroke="#ffffff08"
                      strokeDasharray="2 6"
                    />
                    <XAxis
                      dataKey="label"
                      axisLine={false}
                      tickLine={false}
                      minTickGap={50}
                      tick={{ fill: "#6f7a84", fontSize: 10 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={number}
                      tick={{ fill: "#6f7a84", fontSize: 10 }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#090b0e",
                        border: "1px solid #ffffff16",
                        borderRadius: 8,
                        fontSize: 11,
                      }}
                      formatter={(value) =>
                        metric === "spend"
                          ? money(value)
                          : Number(value).toLocaleString("en")
                      }
                    />
                    <Area
                      type="monotone"
                      dataKey={metric}
                      stroke="#b5cad8"
                      strokeWidth={1.7}
                      fill="url(#ob-usage-fill)"
                      isAnimationActive={!reduced}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <details className="ob-data-details">
                <summary>View figures</summary>
                <div className="op-table-scroll">
                  <table className="op-table">
                    <thead>
                      <tr>
                        <th>Day</th>
                        <th>Entries</th>
                        <th>Tokens</th>
                        <th>CHF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {timeline.map((row) => (
                        <tr key={row.day}>
                          <td>{row.label}</td>
                          <td>{row.requests}</td>
                          <td>{row.totalTokens}</td>
                          <td>{row.spend.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </Panel>
          </div>
          <div className="ob-chart-pair">
            <Panel title="Token mix">
              <Donut
                label="Tokens"
                format={number}
                items={[
                  { label: "Input", value: uncached },
                  {
                    label: "Cached input",
                    value: Math.min(
                      totals.cachedTokens || 0,
                      totals.inputTokens || 0,
                    ),
                  },
                  { label: "Output", value: totals.outputTokens || 0 },
                ]}
              />
            </Panel>
            <Panel title="Model activity" subtitle="Ledger entries">
              <Donut
                label="Entries"
                format={number}
                items={models
                  .slice(0, 3)
                  .map((row) => ({ label: row.model, value: row.requests }))
                  .concat(
                    models.length > 3
                      ? [
                          {
                            label: "Others",
                            value: models
                              .slice(3)
                              .reduce((sum, row) => sum + row.requests, 0),
                          },
                        ]
                      : [],
                  )}
              />
            </Panel>
          </div>
          {allowProjects && (
            <Panel
              title="Projects"
              actions={
                <Link className="op-link" href="/projects">
                  Open all
                  <ArrowUpRight size={13} />
                </Link>
              }
            >
              <div className="ob-project-rows">
                {projects.map((project) => (
                  <Link key={project.id} href={"/projects/" + project.id}>
                    <FolderKanban size={16} />
                    <div>
                      <strong>{project.name}</strong>
                      <span>{project.description || "Project workspace"}</span>
                    </div>
                    <ChevronRight size={14} />
                  </Link>
                ))}
                {!projects.length && (
                  <div className="ob-quiet-empty">
                    Create a project to keep files, tasks and context together.
                  </div>
                )}
              </div>
            </Panel>
          )}
        </div>
        <aside className="ob-side-column">
          {allowTraffic && (
            <section className="ob-earth-panel">
              <header>
                <h2>Network</h2>
                {allowTraffic && (
                  <Link href="/traffic" aria-label="Open traffic map">
                    <ArrowUpRight size={15} />
                  </Link>
                )}
              </header>
              <div className="ob-earth-title">
                <span
                  className={
                    "ob-live" +
                    (!telemetry.errors.traffic &&
                    traffic?.sources?.some((row) => !row.stale)
                      ? ""
                      : " muted")
                  }
                >
                  <i />
                  {!telemetry.errors.traffic &&
                  traffic?.sources?.some((row) => !row.stale)
                    ? "Receiving"
                    : "No live source"}
                </span>
              </div>
              <GlobeGuard
                clients={
                  telemetry.errors.traffic
                    ? []
                    : traffic?.activeConnections || []
                }
                dbip={traffic?.sources?.some(
                  (row) => row.geoipProvider === "db-ip",
                )}
              >
                <Globe
                  clients={
                    telemetry.errors.traffic
                      ? []
                      : traffic?.activeConnections || []
                  }
                  dbip={traffic?.sources?.some(
                    (row) => row.geoipProvider === "db-ip",
                  )}
                  compact
                />
              </GlobeGuard>
              <div className="ob-earth-counts">
                <div>
                  <strong>
                    {telemetry.errors.traffic
                      ? "—"
                      : (traffic?.activeConnectionCount ?? "—")}
                  </strong>
                  <span>Tracked flows</span>
                </div>
                <div>
                  <strong>{traffic?.countries?.length ?? "—"}</strong>
                  <span>Countries · 1 hour</span>
                </div>
              </div>
              <p className="ob-earth-note">
                {traffic?.latestAt
                  ? "Latest activity " +
                    new Date(traffic.latestAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "Live locations appear when the collector sends data."}
              </p>
            </section>
          )}
          {allowServer && (
            <ServerVitals
              resources={telemetry.resources}
              loading={telemetry.loading}
            />
          )}
          <section className="ob-context-links">
            {(!allowedPaths || allowedPaths.includes("/brain")) && (
              <Link href="/brain">
                <span>Brain</span>
                <small>Your saved context</small>
                <ArrowUpRight size={14} />
              </Link>
            )}
            {(!allowedPaths || allowedPaths.includes("/skills")) && (
              <Link href="/skills">
                <span>Skills</span>
                <small>Instructions and workflows</small>
                <ArrowUpRight size={14} />
              </Link>
            )}
            {(!allowedPaths || allowedPaths.includes("/approvals")) && (
              <Link href="/approvals">
                <span>Approvals</span>
                <small>Actions waiting for you</small>
                <ArrowUpRight size={14} />
              </Link>
            )}
          </section>
        </aside>
      </div>
    </Page>
  );
}
