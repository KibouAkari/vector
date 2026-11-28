"use client";
import { useEffect, useMemo, useState } from "react";
const position = ([lon, lat]) => [
  ((lon + 180) * 1000) / 360,
  ((90 - lat) * 500) / 180,
];
function shape(polygons) {
  return polygons
    .map((polygon) =>
      polygon
        .map(
          (ring) =>
            ring
              .map((point, index) => {
                const [x, y] = position(point);
                return (index ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
              })
              .join("") + "Z",
        )
        .join(""),
    )
    .join("");
}
export function useWorld() {
  const [data, setData] = useState(null);
  useEffect(() => {
    const c = new AbortController();
    fetch("/vector-assets/maps/world-110m.json", { signal: c.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => {});
    return () => c.abort();
  }, []);
  return data;
}
export default function WorldMap({
  rows = [],
  selectedCountry,
  onCountry,
  mode = "connections",
  dbip = false,
}) {
  const world = useWorld(),
    [hover, setHover] = useState(null);
  const countries = useMemo(() => {
    const grouped = new Map();
    for (const row of rows) {
      if (!row.country) continue;
      const current = grouped.get(row.country) || {
        country: row.country,
        count: 0,
        ips: new Set(),
        latitude: row.latitude,
        longitude: row.longitude,
        services: new Set(),
      };
      current.count += row.observations || 1;
      current.ips.add(row.sourceIp);
      current.services.add(row.service);
      grouped.set(row.country, current);
    }
    return grouped;
  }, [rows]);
  return (
    <div className="ob-world-map">
      <svg
        viewBox="0 35 1000 425"
        role="group"
        aria-label="World map of observed client countries. Country-level locations are approximate."
      >
        <defs>
          <radialGradient id="map-atmosphere">
            <stop stopColor="#16252c" stopOpacity=".45" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse
          cx="500"
          cy="250"
          rx="480"
          ry="220"
          fill="url(#map-atmosphere)"
        />
        {[90, 180, 270, 360].map((y) => (
          <line key={y} x1="0" y1={y} x2="1000" y2={y} stroke="#ffffff03" />
        ))}
        {world?.features.map((country) => {
          const sample = countries.get(country.id);
          return (
            <g key={country.id}>
              <path
                fillRule="evenodd"
                d={shape(country.polygons)}
                className={
                  "ob-country" +
                  (sample ? " has-traffic" : "") +
                  (selectedCountry === country.id ? " is-selected" : "")
                }
                onMouseEnter={() => setHover({ name: country.name, sample })}
                onMouseLeave={() => setHover(null)}
                onClick={() =>
                  onCountry?.(
                    selectedCountry === country.id ? null : country.id,
                  )
                }
                role={sample && onCountry ? "button" : undefined}
                tabIndex={sample && onCountry ? 0 : undefined}
                aria-label={
                  sample
                    ? `${country.name}: ${sample.ips.size} observed clients`
                    : undefined
                }
                onKeyDown={(event) => {
                  if (
                    sample &&
                    onCountry &&
                    ["Enter", " "].includes(event.key)
                  ) {
                    event.preventDefault();
                    onCountry(
                      selectedCountry === country.id ? null : country.id,
                    );
                  }
                }}
              />
            </g>
          );
        })}
        {[...countries.values()].map((row) => {
          const country = world?.features.find(
            (feature) => feature.id === row.country,
          );
          const point =
            Number.isFinite(row.latitude) && Number.isFinite(row.longitude)
              ? [row.longitude, row.latitude]
              : country?.center;
          if (!point) return null;
          const [x, y] = position(point);
          return (
            <g
              key={row.country}
              className="ob-map-dot"
              transform={`translate(${x} ${y})`}
            >
              <circle
                r={Math.min(12, 3 + Math.sqrt(row.ips.size))}
                fill="#c6e5e7"
                fillOpacity=".12"
              />
              <circle r="2.5" fill="#d6ecee" />
            </g>
          );
        })}
      </svg>
      <div className="ob-map-caption">
        {hover ? (
          <>
            <strong>{hover.name}</strong>
            <span>
              {hover.sample
                ? `${hover.sample.ips.size} clients · ${hover.sample.services.size} services`
                : "No located observations"}
            </span>
          </>
        ) : (
          <>
            <span>Country-level view</span>
            <span>
              {rows.filter((row) => !row.country).length} unlocated{" "}
              {mode === "connections" ? "connections" : "client groups"}
            </span>
          </>
        )}
      </div>
      {dbip && (
        <a
          className="ob-map-attribution"
          href="https://db-ip.com"
          target="_blank"
          rel="noreferrer"
        >
          IP Geolocation by DB-IP
        </a>
      )}
      {!world && <span className="ob-map-loading">Loading geography…</span>}
    </div>
  );
}
