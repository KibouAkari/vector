"use client";
import Link from "next/link";
import { Cpu, MemoryStick, HardDrive, ArrowUpRight } from "lucide-react";
import { resourceBytes } from "../../lib/server-resources.mjs";
import { utilization } from "../../lib/host-vitals.mjs";
import { Sparkline } from "./primitives";
function Dial({ value, label, detail, icon: Icon, values }) {
  const safe = Number.isFinite(value)
    ? Math.min(100, Math.max(0, value))
    : null;
  const c = 2 * Math.PI * 39;
  return (
    <div className="ob-vital">
      <div className="ob-vital-title">
        <Icon size={14} />
        <span>{label}</span>
      </div>
      <div className="ob-dial">
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <circle
            cx="50"
            cy="50"
            r="39"
            fill="none"
            stroke="#ffffff09"
            strokeWidth="3"
          />
          <circle
            cx="50"
            cy="50"
            r="39"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - (safe || 0) / 100)}
            transform="rotate(-90 50 50)"
          />
        </svg>
        <strong>
          {safe === null ? "—" : Math.round(safe)}
          {safe !== null && <small>%</small>}
        </strong>
      </div>
      <p>{detail}</p>
      {values?.length > 1 && <Sparkline values={values} height={25} />}
    </div>
  );
}
export default function ServerVitals({ resources, loading = false }) {
  const memory = resources?.memory,
    disk = resources?.storage?.[0],
    stale =
      resources?.stale ||
      (resources?.observedAt &&
        Date.now() - Date.parse(resources.observedAt) > 45000);
  return (
    <section
      className="ob-vitals"
      aria-label="Server resources"
      aria-busy={loading}
    >
      <header>
        <h2>Host resources</h2>
        <span
          className={
            "ob-live" + (resources?.available && !stale ? "" : " muted")
          }
        >
          <i />
          {stale
            ? "Last sample"
            : resources?.available
              ? resources.approximate
                ? "Host agent"
                : "Live sample"
              : "Awaiting collector"}
        </span>
        <Link href="/server" aria-label="Open infrastructure">
          <ArrowUpRight size={15} />
        </Link>
      </header>
      <div className="ob-vital-grid">
        <Dial
          label="CPU"
          icon={Cpu}
          value={resources?.cpuPercent}
          detail={
            resources?.cpuPercent === null || !resources?.available
              ? "Sampler required"
              : `${resources.logicalCpus} logical CPUs`
          }
          values={resources?.history
            ?.map((row) => row.cpuPercent)
            .filter(Number.isFinite)}
        />
        <Dial
          label="Memory"
          icon={MemoryStick}
          value={
            memory ? utilization(memory.usedBytes, memory.totalBytes) : null
          }
          detail={
            memory
              ? `${resourceBytes(memory.usedBytes)} / ${resourceBytes(memory.totalBytes)}`
              : "No host sample"
          }
        />
        <Dial
          label="Storage"
          icon={HardDrive}
          value={disk ? utilization(disk.usedBytes, disk.totalBytes) : null}
          detail={
            disk
              ? `${resourceBytes(disk.usedBytes)} / ${resourceBytes(disk.totalBytes)}`
              : "No volume sample"
          }
        />
      </div>
      <footer>
        {resources?.sourceName || "No sample source"}
        {resources?.observedAt && (
          <time dateTime={resources.observedAt}>
            {new Date(resources.observedAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </time>
        )}
      </footer>
    </section>
  );
}
