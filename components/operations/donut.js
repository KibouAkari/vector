"use client";
import { useState } from "react";
const palette = ["#c3d5e0", "#647c8d", "#b4a07e", "#466861", "#67627b"];
export default function Donut({
  items = [],
  label = "Total",
  format = (value) => Number(value).toLocaleString("en"),
}) {
  const [active, setActive] = useState(null),
    total = items.reduce(
      (sum, row) => sum + Math.max(0, Number(row.value) || 0),
      0,
    ),
    c = 2 * Math.PI * 56;
  let before = 0;
  return (
    <div className="ob-donut">
      <div className="ob-donut-visual">
        <svg
          viewBox="0 0 140 140"
          role="img"
          aria-label={label + ": " + format(total)}
        >
          <circle
            cx="70"
            cy="70"
            r="56"
            fill="none"
            stroke="#ffffff0a"
            strokeWidth="9"
          />
          {items.map((row, index) => {
            const share = total
                ? Math.max(0, Number(row.value) || 0) / total
                : 0,
              offset = -before * c;
            before += share;
            return (
              <circle
                key={row.label}
                cx="70"
                cy="70"
                r="56"
                fill="none"
                stroke={palette[index % palette.length]}
                opacity={active === null || active === index ? 1 : 0.2}
                strokeWidth={active === index ? 12 : 9}
                strokeDasharray={`${Math.max(0, c * share - 4)} ${c}`}
                strokeDashoffset={offset}
                transform="rotate(-90 70 70)"
                onMouseEnter={() => setActive(index)}
                onMouseLeave={() => setActive(null)}
              />
            );
          })}
        </svg>
        <div>
          <strong>
            {format(active === null ? total : items[active].value)}
          </strong>
          <span>{active === null ? label : items[active].label}</span>
        </div>
      </div>
      <div className="ob-donut-legend">
        {items.map((row, index) => (
          <button
            key={row.label}
            type="button"
            onFocus={() => setActive(index)}
            onBlur={() => setActive(null)}
            onMouseEnter={() => setActive(index)}
            onMouseLeave={() => setActive(null)}
          >
            <i style={{ background: palette[index % palette.length] }} />
            <span>{row.label}</span>
            <strong>{format(row.value)}</strong>
          </button>
        ))}
        {!total && <small>No records in this period</small>}
      </div>
    </div>
  );
}
