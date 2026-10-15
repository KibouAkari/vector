"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity, Boxes, ChevronDown, Clock3, Cpu, HardDrive,
  MemoryStick, Network, RefreshCw, Terminal, WifiOff
} from "lucide-react";

import {
  resourceBytes, resourcePercent, sortedContainers, topContainers
} from "../../lib/server-resources.mjs";

function lines(text) {
  return String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
}

function memorySummary(raw) {
  const line = lines(raw).find(row => /^Mem:\s*/i.test(row));
  if (!line) return null;
  const fields = line.split(/\s+/);
  return fields.length >= 4 ? { total: fields[1], used: fields[2], free: fields[3], available: fields[6] || null } : null;
}

function storageRows(raw) {
  return lines(raw)
    .filter(row => !/^Filesystem\s/i.test(row))
    .map(row => row.split(/\s+/))
    .filter(parts => parts.length >= 6 && /%$/.test(parts[4]) && !/^(overlay|tmpfs|devtmpfs)$/i.test(parts[0]))
    .map(parts => ({ name: parts[0], size: parts[1], used: parts[2], usage: parts[4], mount: parts.slice(5).join(" ") }))
    .slice(0, 10);
}

function dockerRows(raw) {
  return lines(raw).filter(row => !/^(CONTAINER ID|NAME\s+IMAGE|No data|NAMES\s+IMAGE)/i.test(row)).slice(0, 50);
}

function DetailPanel({ icon: Icon, title, description, children, raw, initiallyOpen = false }) {
  return (
    <section className="vx586-server-panel">
      <div className="vx586-panel-heading">
        <span className="vx586-panel-icon"><Icon size={17} strokeWidth={1.8} aria-hidden="true" /></span>
        <div><h2>{title}</h2>{description && <p>{description}</p>}</div>
      </div>
      {children}
      {raw && <details className="vx586-raw" open={initiallyOpen}>
        <summary><Terminal size={14} aria-hidden="true" /> Raw output <ChevronDown size={14} aria-hidden="true" /></summary>
        <pre>{String(raw)}</pre>
      </details>}
    </section>
  );
}

function Metric({ icon: Icon, label, value, detail }) {
  return <article className="vx586-server-metric">
    <div className="vx586-metric-head"><Icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span></div>
    <strong title={value}>{value || "Unavailable"}</strong>
    {detail && <small>{detail}</small>}
  </article>;
}

function ResourceRanking({containers, metric}) {
  const cpu = metric === 'cpu';
  const ranked = topContainers(containers, metric);
  const field = cpu ? 'cpuPercent' : 'memoryBytes';
  const maximum = ranked[0]?.[field] || 0;
  const Icon = cpu ? Cpu : MemoryStick;
  return <section className="vsc-ranking" aria-label={`Top five containers by ${cpu ? 'CPU' : 'memory'}`}>
    <h2><Icon size={17} aria-hidden="true"/> Top 5 by {cpu ? 'CPU' : 'memory'}</h2>
    <p>{cpu ? 'Current CPU use. Values can exceed 100% across multiple cores.' : 'Current memory use in bytes, independent of container memory limits.'}</p>
    {ranked.length ? <ol className="vsc-rank-list">{ranked.map(row => <li key={row.id}>
      <div><strong title={row.name}>{row.name}</strong><span>{cpu ? resourcePercent(row.cpuPercent) : resourceBytes(row.memoryBytes)}</span></div>
      <div className="vsc-rank-track" aria-hidden="true"><span style={{width:`${maximum > 0 ? row[field] / maximum * 100 : 0}%`}}/></div>
    </li>)}</ol> : <p className="vsc-unavailable">No measurements available for this ranking.</p>}
  </section>;
}

function ContainerResources({resources, stale}) {
  const [sort, setSort] = useState('memory');
  const [query, setQuery] = useState('');
  const containers = resources?.available ? resources.containers : [];
  const rows = sortedContainers(containers, sort, query);
  return <>
    <div className="vsc-rankings">
      <ResourceRanking containers={containers} metric="cpu"/>
      <ResourceRanking containers={containers} metric="memory"/>
    </div>
    <section className="vsc-containers" aria-label="Container resource overview">
      <div className="vsc-containers-header"><div><h2><Boxes size={17} aria-hidden="true"/> Container resources</h2>
        <p>{stale ? 'Last successful snapshot' : 'One-shot sample'} · Docker containers only. Host services are listed separately below.</p>
      </div><span className="vsc-refresh-mode">Refreshes every 30 seconds while visible</span></div>
      {!resources?.available ? <p className="vsc-unavailable">Container resource sampling is unavailable. Host information remains available below. Try refreshing.</p> : <>
        <div className="vsc-filters">
          <input type="search" aria-label="Find container" placeholder="Find a container…" value={query} onChange={event => setQuery(event.target.value)}/>
          <label>Sort by<select value={sort} onChange={event => setSort(event.target.value)}><option value="memory">Memory usage</option><option value="cpu">CPU usage</option><option value="name">Name</option></select></label>
        </div>
        <div className="vsc-table-scroll"><table className="vsc-table">
          <caption className="sr-only">Current Docker container resource measurements</caption>
          <thead><tr><th scope="col">Container</th><th scope="col">CPU</th><th scope="col">Memory</th><th scope="col">Reported memory limit</th><th scope="col">PIDs</th><th scope="col">Network I/O</th><th scope="col">Block I/O</th></tr></thead>
          <tbody>{rows.map(row => <tr key={row.id}>
            <td>{row.name}</td><td>{resourcePercent(row.cpuPercent)}</td><td>{resourceBytes(row.memoryBytes)}</td><td>{resourceBytes(row.memoryLimitBytes)}</td><td>{row.pids ?? 'Unavailable'}</td><td>{row.networkIO ?? 'Unavailable'}</td><td>{row.blockIO ?? 'Unavailable'}</td>
          </tr>)}</tbody>
        </table></div>
        {!rows.length && <p className="vsc-unavailable">{query ? 'No matching containers.' : 'No running containers in this sample.'}</p>}
        <p className="vsc-note">Bars compare containers with the largest measured value in each ranking. Network and block I/O are cumulative counters reported by Docker, not transfer rates. A reported memory limit may reflect host capacity when no dedicated container limit is set.</p>
      </>}
    </section>
  </>;
}

export default function ServerClient() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);
  const inFlight = useRef(false);
  const active = useRef(true);

  async function load(isManual = false) {
    if (inFlight.current) return;
    inFlight.current = true;
    if (isManual && active.current) setRefreshing(true);
    try {
      const response = await fetch("/api/server/snapshot", {
        cache: "no-store", signal: AbortSignal.timeout(20000)
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Server context unavailable");
      if (active.current) {
        setData(body);
        setError(null);
        setUpdatedAt(new Date());
      }
    } catch (err) {
      if (active.current) setError(err.message || "Unable to load server context");
    } finally {
      inFlight.current = false;
      if (active.current) { setLoading(false); setRefreshing(false); }
    }
  }

  useEffect(() => {
    active.current = true;
    void load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 30000);
    return () => { active.current = false; window.clearInterval(timer); };
  }, []);

  const memory = memorySummary(data?.memory);
  const disks = storageRows(data?.disk);
  const containers = dockerRows(data?.docker);
  const ports = lines(data?.listeningPorts ?? data?.ports);
  const services = lines(data?.services);
  const hasSnapshot = Boolean(data);

  return <div className="vx586-server">
    <header className="simple-page-head vx586-server-head">
      <div><h1>Server Control Center</h1><p>Host status, resource usage and the services running on your server.</p></div>
      <button type="button" className="vx586-refresh" onClick={() => void load(true)} disabled={refreshing}>
        <RefreshCw size={16} className={refreshing ? "vx586-spin" : ""} aria-hidden="true" /> Refresh
      </button>
    </header>

    {error && <div className="vx586-server-alert" role="alert"><WifiOff size={17} aria-hidden="true" />
      <span>{error}{hasSnapshot ? " · Displaying the last successful snapshot." : ""}</span>
    </div>}

    {loading && !hasSnapshot ? <div className="vx586-server-loading" role="status"><RefreshCw size={19} className="vx586-spin" /> Loading server information…</div>
    : !hasSnapshot ? <div className="vx586-server-empty"><WifiOff size={23} /><strong>No server snapshot available</strong><p>Check the host agent or try refreshing.</p></div>
    : <>
      <div className="vx586-server-status" data-stale={Boolean(error)}><span className="vx586-server-status-dot" />
        <strong>{error ? "Last snapshot" : "Connected"}</strong>
        <span>Read only · Host changes require approval</span>
        {updatedAt && <time dateTime={updatedAt.toISOString()}>Updated {updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>}
      </div>

      <div className="vx586-server-metrics">
        <Metric icon={Clock3} label="Uptime" value={String(data.uptime || "").replace(/^up\s*/i, "") || "Unknown"} detail="Host availability" />
        <Metric icon={MemoryStick} label="Memory" value={memory?.used || "See details"} detail={memory ? `of ${memory.total} total` : "Resource usage"} />
        <Metric icon={HardDrive} label="Volumes" value={String(disks.length || "—")} detail="Mounted disks reported" />
        <Metric icon={Boxes} label="Containers" value={data.containerResources?.available ? String(data.containerResources.runningCount) : containers.length ? String(containers.length) : "—"} detail={data.containerResources?.available ? "Running in resource sample" : "Rows in Docker snapshot"} />
      </div>

      <div className="vsc-context">
        <p><strong>Last reboot</strong> · Exact timestamp is not reported by the host agent.</p>
        <p><strong>Recent activity</strong> · This snapshot does not include event logs.</p>
      </div>

      <ContainerResources resources={data.containerResources} stale={Boolean(error)}/>

      <div className="vx586-server-panels">
        <DetailPanel icon={MemoryStick} title="Memory" description="Host memory allocation" raw={data.memory}>
          {memory ? <div className="vx586-memory-stats"><div><span>Used</span><strong>{memory.used}</strong></div><div><span>Total</span><strong>{memory.total}</strong></div><div><span>Available</span><strong>{memory.available || memory.free}</strong></div></div>
          : <p className="vx586-empty-inline">Memory details are available in raw output.</p>}
        </DetailPanel>
        <DetailPanel icon={HardDrive} title="Storage" description="Mounted filesystems" raw={data.disk}>
          {disks.length ? <div className="vx586-disk-list">{disks.map((disk, i) => {
            const pct = Math.min(100, Math.max(0, parseInt(disk.usage, 10) || 0));
            return <div className="vx586-disk-row" key={`${disk.mount}-${i}`}>
              <div><strong title={disk.name}>{disk.mount}</strong><span>{disk.used} of {disk.size}</span><small>{disk.usage}</small></div>
              <div className="vx586-track" role="meter" aria-label={`Disk usage ${disk.mount}`} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${pct}%`}} /></div>
            </div>;
          })}</div> : <p className="vx586-empty-inline">Storage details are available in raw output.</p>}
        </DetailPanel>
        <DetailPanel icon={Boxes} title="Docker" description="Containers reported by the host" raw={data.docker}>
          {containers.length ? <div className="vx586-terminal-list">{containers.slice(0, 8).map((row, i) => <div key={i}><span className="vx586-line-dot" /> <code title={row}>{row}</code></div>)}</div>
            : <p className="vx586-empty-inline">No container records in the snapshot.</p>}
          {containers.length > 8 && <small className="vx586-more">+{containers.length-8} more in raw output</small>}
        </DetailPanel>
        <DetailPanel icon={Activity} title="Services" description="Running system services" raw={data.services}>
          {services.length ? <div className="vx586-terminal-list">{services.slice(0, 7).map((line, i) => <div key={i}><span className="vx586-line-dot" /><code title={line}>{line}</code></div>)}</div>
            : <p className="vx586-empty-inline">No service details reported.</p>}
          {services.length > 7 && <small className="vx586-more">+{services.length - 7} more in raw output</small>}
        </DetailPanel>
        <DetailPanel icon={Network} title="Listening ports" description="Open listeners in the snapshot" raw={data.listeningPorts ?? data.ports}>
          {ports.length && !/^No data$/i.test(ports[0]) ? <div className="vx586-terminal-list">{ports.slice(0, 8).map((line, i) => <div key={i}><span className="vx586-line-dot" /><code title={line}>{line}</code></div>)}</div>
            : <p className="vx586-empty-inline">No port information was returned.</p>}
        </DetailPanel>
      </div>
    </>}
  </div>;
}

