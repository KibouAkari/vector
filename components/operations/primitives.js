"use client";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight, Inbox, RefreshCw } from "lucide-react";
export function Page({
  title,
  eyebrow,
  description,
  actions,
  children,
  className = "",
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={"op-page vx:min-w-0 " + className}
      initial={{ opacity: 0, y: reduced ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.25 }}
    >
      <header className="op-page-heading">
        <div>
          {eyebrow && <span className="op-eyebrow">{eyebrow}</span>}
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        <div className="op-actions">{actions}</div>
      </header>
      {children}
    </motion.div>
  );
}
export function Panel({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={"op-panel vx:min-w-0 " + className}>
      <div className="op-panel-heading">
        <div>
          {title && <h2>{title}</h2>}
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div className="op-actions">{actions}</div>}
      </div>
      {children}
    </section>
  );
}
export function Empty({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="op-empty vx:text-center">
      <Icon size={27} strokeWidth={1.25} />
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function Metric({ label, value, detail, icon: Icon, children, tone }) {
  return (
    <div className="op-metric" data-tone={tone}>
      <div>
        {Icon && <Icon size={16} />}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      {children}
      {detail && <small>{detail}</small>}
    </div>
  );
}
export function Status({ value, children }) {
  return (
    <span className="op-status" data-status={value}>
      <i />
      {children || value}
    </span>
  );
}
export function Refresh({ onClick, loading }) {
  return (
    <button className="op-button" onClick={onClick} disabled={loading}>
      <RefreshCw size={14} className={loading ? "op-spin" : ""} />
      {loading ? "Refreshing…" : "Refresh"}
    </button>
  );
}
export function Sparkline({
  values = [],
  color = "var(--op-accent)",
  height = 45,
  label = "Activity",
}) {
  if (values.length < 2)
    return <div className="op-spark-empty" style={{ height }} />;
  const max = Math.max(1, ...values),
    min = Math.min(0, ...values),
    points = values
      .map(
        (value, index) =>
          `${(index / (values.length - 1)) * 180},${height - 4 - ((value - min) / (max - min || 1)) * (height - 8)}`,
      )
      .join(" ");
  return (
    <svg
      viewBox={`0 0 180 ${height}`}
      role="img"
      aria-label={label}
      className="op-sparkline"
      preserveAspectRatio="none"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
export function Ring({ value, label, size = 130 }) {
  const safe = Math.min(100, Math.max(0, Number(value) || 0)),
    radius = 46,
    circumference = 2 * Math.PI * radius;
  return (
    <div className="op-ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 110 110" aria-hidden="true">
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="var(--op-line)"
          strokeWidth="5"
        />
        <circle
          className="op-ring-progress"
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="var(--op-accent)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - safe / 100)}
          transform="rotate(-90 55 55)"
        />
      </svg>
      <div>
        <strong>{Math.round(safe)}%</strong>
        <small>{label}</small>
      </div>
    </div>
  );
}
