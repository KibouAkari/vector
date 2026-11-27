"use client";
import { useState } from "react";
import { useReducedMotion } from "motion/react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  Coins,
  FolderKanban,
  MessageSquare,
  Workflow,
  ArrowDownToLine,
  ChevronRight,
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
import { Page, Panel, Metric, Empty, Sparkline } from "./operations/primitives";
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
  const reduced = useReducedMotion();
  const [metric, setMetric] = useState("requests");
  const trend = timeline.map((row) => row[metric] || 0);
  const totalCalls = totals.providerCalls || 0;
  function download() {
    const blob = new Blob(
      [
        JSON.stringify(
          { period: "30 days UTC", totals, models, timeline },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "vector-usage.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <Page
      title="Overview"
      eyebrow="Workspace"
      description={`Welcome back, ${displayName}.`}
      actions={
        <>
          <span className="op-period">Last 30 days · UTC</span>
          <button className="op-button" onClick={download}>
            <ArrowDownToLine size={14} />
            Export
          </button>
        </>
      }
    >
      <div className="op-dashboard">
        <div className="op-dashboard-primary">
          <section className="op-welcome">
            <div>
              <span className="op-eyebrow">Your next move</span>
              <h2>What are we working on?</h2>
              <p>Pick up a project, ask a question or check your services.</p>
              <div className="op-actions">
                <Link href="/chat" className="op-button primary">
                  <MessageSquare size={15} />
                  New conversation
                  <ArrowUpRight size={14} />
                </Link>
                <Link href="/projects" className="op-button">
                  Open projects
                </Link>
              </div>
            </div>
            <div className="op-orbit" aria-hidden="true">
              <span />
              <span />
              <span />
              <img src="/vector-assets/brand/vector-mark.svg" alt="" />
            </div>
          </section>
          <div className="op-metrics">
            <Metric
              label="Provider calls"
              value={number(totalCalls)}
              icon={Activity}
              detail={`${number(totals.requests)} ledger entries`}
            >
              <Sparkline values={timeline.map((row) => row.requests)} />
            </Metric>
            <Metric
              label="Tokens"
              value={number(totals.totalTokens)}
              icon={Workflow}
              detail={`${number(totals.cachedTokens)} cached input`}
            >
              <Sparkline values={timeline.map((row) => row.totalTokens)} />
            </Metric>
            <Metric
              label="Recorded spend"
              value={money(totals.spend)}
              icon={Coins}
              detail={
                totals.incompleteCalls
                  ? `${totals.incompleteCalls} calls with incomplete cost`
                  : "Reported and configured price records"
              }
            >
              <Sparkline values={timeline.map((row) => row.spend)} />
            </Metric>
            <Metric
              label="Recent projects"
              value={projects.length}
              icon={FolderKanban}
              detail="Up to 5 recently updated"
            />
          </div>
          <Panel
            title="Activity"
            subtitle="Your usage ledger"
            actions={
              <div className="op-segment" aria-label="Chart metric">
                {[
                  ["requests", "Requests"],
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
              className="op-chart"
              role="img"
              aria-label={`${metric} over the last 30 days`}
            >
              <ResponsiveContainer width="100%" height={245}>
                <AreaChart
                  data={timeline}
                  margin={{ top: 16, right: 10, bottom: 0, left: -20 }}
                >
                  <defs>
                    <linearGradient
                      id="op-chart-fill"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="var(--op-accent)"
                        stopOpacity={0.18}
                      />
                      <stop
                        offset="100%"
                        stopColor="var(--op-accent)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    stroke="var(--op-line)"
                    vertical={false}
                    strokeDasharray="3 5"
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={55}
                    tick={{ fill: "#87959f", fontSize: 10 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={number}
                    tick={{ fill: "#87959f", fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#121920",
                      border: "1px solid #29343e",
                      borderRadius: 8,
                      fontSize: 12,
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
                    stroke="var(--op-accent)"
                    strokeWidth={2}
                    fill="url(#op-chart-fill)"
                    isAnimationActive={!reduced}
                    animationDuration={650}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <details className="op-details">
              <summary>View data table</summary>
              <div className="op-table-scroll">
                <table className="op-table">
                  <thead>
                    <tr>
                      <th>Day</th>
                      <th>Requests</th>
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
          <Panel
            title="Recent projects"
            actions={
              <Link className="op-link" href="/projects">
                All projects
                <ArrowUpRight size={13} />
              </Link>
            }
          >
            {projects.length ? (
              <div className="op-project-list">
                {projects.map((project) => (
                  <Link key={project.id} href={"/projects/" + project.id}>
                    <span className="op-square">
                      <FolderKanban size={17} />
                    </span>
                    <div>
                      <strong>{project.name}</strong>
                      <small>{project.description || "Open workspace"}</small>
                    </div>
                    <ChevronRight size={15} />
                  </Link>
                ))}
              </div>
            ) : (
              <Empty
                title="Start with a project"
                description="Keep tasks, files and conversations together."
                action={
                  <Link className="op-button" href="/projects">
                    Create project
                  </Link>
                }
              />
            )}
          </Panel>
        </div>
        <div className="op-dashboard-secondary">
          <Panel
            title="Model mix"
            subtitle="Calls recorded in the last 30 days"
          >
            {models.length ? (
              <div className="op-model-list">
                {models.slice(0, 6).map((model) => (
                  <div key={model.provider + model.model}>
                    <div>
                      <strong title={model.model}>{model.model}</strong>
                      <span>{model.requests}</span>
                    </div>
                    <div className="op-meter">
                      <i
                        style={{
                          width:
                            Math.max(
                              2,
                              (model.requests / Math.max(1, totals.requests)) *
                                100,
                            ) + "%",
                        }}
                      />
                    </div>
                    <small>
                      {model.provider} · {money(model.spend)}
                    </small>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                title="No model usage yet"
                description="Your first request will appear here."
              />
            )}
          </Panel>
          <Panel title="Brain" subtitle="Knowledge that follows your work">
            <div className="op-brain-signal" aria-hidden="true">
              <BrainCircuit size={48} strokeWidth={1} />
            </div>
            <p className="op-muted">
              Keep useful facts and preferences in one place. Review what is
              shared with each task.
            </p>
            <Link href="/brain" className="op-button">
              Open Brain
              <ArrowUpRight size={14} />
            </Link>
          </Panel>
          <Panel title="Operations">
            <div className="op-shortcuts">
              {[
                ["/server", "Infrastructure", "Services and resource use"],
                [
                  "/connections",
                  "Connections",
                  "Monitoring and workspace tools",
                ],
                ["/security", "Security", "Assets, checks and findings"],
                ["/approvals", "Approvals", "Review actions before execution"],
              ]
                .filter(
                  ([href]) => !allowedPaths || allowedPaths.includes(href),
                )
                .map(([href, title, sub]) => (
                  <Link key={href} href={href}>
                    <div>
                      <strong>{title}</strong>
                      <small>{sub}</small>
                    </div>
                    <ArrowUpRight size={14} />
                  </Link>
                ))}
            </div>
          </Panel>
          <p className="op-footnote">
            Cost totals follow ledger attribution. Incomplete provider records
            remain marked in Usage.
          </p>
        </div>
      </div>
    </Page>
  );
}
