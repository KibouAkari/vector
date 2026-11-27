"use client";
import { useEffect, useRef, useState } from "react";
const value = (n) =>
  n === null
    ? "Unknown"
    : n.toLocaleString(undefined, { maximumFractionDigits: 10 });
export default function UsageCalls() {
  const [rows, setRows] = useState([]),
    [cursor, setCursor] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [projects, setProjects] = useState([]),
    [project, setProject] = useState(""),
    [model, setModel] = useState(""),
    [filters, setFilters] = useState({});
  const sequence = useRef(0);
  async function load(after = null, signal) {
    const version = ++sequence.current;
    setBusy(true);
    setError("");
    try {
      const query = new URLSearchParams(filters);
      if (after) query.set("after", after);
      const response = await fetch("/api/usage/calls?" + query, {
        cache: "no-store",
        signal,
      });
      const data = await response.json();
      if (!response.ok)
        throw Error("Usage records are temporarily unavailable.");
      if (version !== sequence.current) return;
      setRows((previous) =>
        after
          ? [
              ...previous,
              ...data.calls.filter(
                (row) => !previous.some((old) => old.id === row.id),
              ),
            ]
          : data.calls,
      );
      setCursor(data.nextCursor);
    } catch (e) {
      if (e.name !== "AbortError" && version === sequence.current)
        setError(e.message);
    } finally {
      if (version === sequence.current) setBusy(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    load(null, controller.signal);
    return () => {
      controller.abort();
    };
  }, [filters]);
  useEffect(() => {
    fetch("/api/projects", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => setProjects(data.projects || []))
      .catch(() => {});
  }, []);
  return (
    <section className="control-card">
      <div className="control-card-body">
        <h2>My calls</h2>
        <p>
          Reported charges and estimates are labelled separately. Unknown
          counters stay unknown.
        </p>
        {error && <p role="alert">{error}</p>}
        <form
          className="ctl-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            setFilters({
              ...(project ? { project } : {}),
              ...(model.trim() ? { model: model.trim() } : {}),
            });
          }}
        >
          <label>
            Project
            <select
              value={project}
              onChange={(event) => setProject(event.target.value)}
            >
              <option value="">All my projects</option>
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Exact model
            <input
              value={model}
              maxLength={200}
              placeholder="All models"
              onChange={(event) => setModel(event.target.value)}
            />
          </label>
          <button disabled={busy}>Apply filters</button>
        </form>
        <button type="button" disabled={busy} onClick={() => load()}>
          Refresh
        </button>
      </div>
      <div className="vector-table-wrap">
        <table className="vector-table">
          <thead>
            <tr>
              <th>Time / task</th>
              <th>Provider / model</th>
              <th>Project / latency</th>
              <th>Input / output</th>
              <th>Cache / reasoning</th>
              <th>Cost basis</th>
              <th>USD</th>
              <th>Converted CHF</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {new Date(row.createdAt).toLocaleString()}
                  <br />
                  {row.jobId || "No task reference"}
                </td>
                <td>
                  {row.provider}
                  <br />
                  {row.model}
                </td>
                <td>
                  {projects.find((item) => item.id === row.projectId)?.name ||
                    (row.projectId
                      ? "Project " + row.projectId.slice(0, 8)
                      : "Chat")}
                  <br />
                  {row.elapsedMs === null
                    ? "Unknown latency"
                    : (row.elapsedMs / 1000).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      }) + " s"}
                </td>
                <td>
                  {value(row.inputTokens)} / {value(row.outputTokens)}
                </td>
                <td>
                  {value(row.cachedTokens)} / {value(row.reasoningTokens)}
                </td>
                <td>{row.costStatus}</td>
                <td>
                  {row.costStatus === "local-no-api"
                    ? "0 API fee"
                    : value(row.reportedCostUsd ?? row.estimatedCostUsd)}
                </td>
                <td>{value(row.convertedCostChf)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!busy && !rows.length && (
          <p>No provider calls recorded for your account.</p>
        )}
      </div>
      {cursor && (
        <button disabled={busy} onClick={() => load(cursor)}>
          Load older calls
        </button>
      )}
    </section>
  );
}
