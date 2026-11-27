"use client";
import { useEffect, useRef, useState } from "react";
const status = (row) =>
  row.expires_at && new Date(row.expires_at) < new Date() && !row.consumed_at
    ? "expired"
    : row.consumed_at
      ? "used"
      : row.status;
export default function ApprovalQueue() {
  const [rows, setRows] = useState([]),
    [loading, setLoading] = useState(true),
    [filter, setFilter] = useState("pending"),
    [error, setError] = useState(""),
    [pending, setPending] = useState(null),
    [reviewed, setReviewed] = useState({});
  const active = useRef(true);
  async function load(signal) {
    const response = await fetch("/api/approvals", {
      cache: "no-store",
      signal,
    });
    if (!response.ok) throw Error("Approvals could not be loaded.");
    const data = await response.json();
    if (active.current && !signal?.aborted) setRows(data.approvals);
  }
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    load(controller.signal)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (active.current) setLoading(false);
      });
    const timer = setInterval(() => {
      if (!document.hidden) load(controller.signal).catch(() => {});
    }, 10000);
    return () => {
      active.current = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  async function decide(id, decision) {
    if (pending) return;
    const row = rows.find((item) => item.id === id);
    if (decision === "approved" && row?.resource_type === "security-asset" &&
        (!row.scope || reviewed[id] !== row.scope_digest)) return;
    setPending(id);
    setError("");
    try {
      const response = await fetch(`/api/approvals/${id}/decision`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision, ...(row?.resource_type === "security-asset" && decision === "approved" ? { scopeDigest: row.scope_digest } : {}) }),
      });
      if (!response.ok)
        throw Error("Decision was not saved. Refresh and try again.");
      setRows((old) =>
        old.map((row) =>
          row.id === id
            ? { ...row, status: decision, decided_at: new Date().toISOString() }
            : row,
        ),
      );
      window.dispatchEvent(new Event("vector:approvals"));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(null);
    }
  }
  const shown = rows.filter(
    (row) => filter === "all" || status(row) === filter,
  );
  return (
    <div className="ctl-page">
      <header className="ctl-page-header">
        <div>
          <h1>Approvals</h1>
          <p>Review the exact action before it can run.</p>
        </div>
        <label>
          Status
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            {["pending", "approved", "rejected", "used", "expired", "all"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
        </label>
      </header>
      {error && (
        <p role="alert" className="ctl-error">
          {error}
        </p>
      )}
      <section className="ctl-panel">
        {loading ? (
          <div aria-label="Loading approvals" role="status">
            <div className="ctl-skeleton" />
            <div className="ctl-skeleton" />
          </div>
        ) : !shown.length ? (
          <div className="ctl-empty">
            No {filter === "all" ? "" : filter} approvals.
          </div>
        ) : (
          <div className="vector-table-wrap">
            <table className="vector-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Requested</th>
                  <th>Status</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.action}</strong>
                      <details>
                        <summary>Details</summary>
                        <pre>{row.description}</pre>
                        <small>{row.permission}</small>
                        {row.resource_type === "security-asset" && (
                          row.scope ? (
                            <>
                              <p>Requested by: {row.requester || row.requested_by} ({row.requested_by})</p>
                              <p>This authorization permits repeated scans of the saved scope.</p>
                              <pre>{JSON.stringify(row.scope, null, 2)}</pre>
                              <p>Scope digest: {row.scope_digest}</p>
                              {status(row) === "pending" && (
                                <label>
                                  <input type="checkbox" checked={reviewed[row.id] === row.scope_digest}
                                    onChange={(e) => setReviewed((old) => ({ ...old, [row.id]: e.target.checked ? row.scope_digest : null }))} />
                                  I reviewed this scope and its advisory consent.
                                </label>
                              )}
                            </>
                          ) : <p role="alert">Scope unavailable or changed; approval is disabled.</p>
                        )}
                        {row.decided_at && (
                          <p>
                            {row.decided_by} ·{" "}
                            {new Date(row.decided_at).toLocaleString()}
                          </p>
                        )}
                        {row.resource_type === "tool" && (
                          <p>
                            Single-use approval. Retry the exact action after
                            approval.
                          </p>
                        )}
                      </details>
                    </td>
                    <td>{new Date(row.requested_at).toLocaleString()}</td>
                    <td>
                      <span className="ctl-status" data-state={status(row)}>
                        {status(row)}
                      </span>
                    </td>
                    <td>
                      {status(row) === "pending" && (
                        <div className="ctl-toolbar">
                          <button
                            className="ctl-primary"
                            disabled={pending !== null || (row.resource_type === "security-asset" && (!row.scope || reviewed[row.id] !== row.scope_digest))}
                            onClick={() => decide(row.id, "approved")}
                          >
                            {pending === row.id ? "Saving…" : "Approve"}
                          </button>
                          <button
                            disabled={pending !== null}
                            onClick={() => decide(row.id, "rejected")}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <a href="/permissions">Permission policies →</a>
    </div>
  );
}
