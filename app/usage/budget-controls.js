"use client";
import { useEffect, useState } from "react";
export default function BudgetControls() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [scope, setScope] = useState("workspace"),
    [currency, setCurrency] = useState("CHF"),
    [hard, setHard] = useState("25"),
    [warning, setWarning] = useState("20"),
    [entities, setEntities] = useState([]);
  async function load() {
    const response = await fetch("/api/budgets", { cache: "no-store" });
    if (!response.ok) throw Error("Budgets could not be loaded.");
    const result = await response.json();
    setData(result);
    return result;
  }
  useEffect(() => {
    let mounted = true;
    load()
      .then(async (result) => {
        if (result.canManage) {
          const [users, projects] = await Promise.all([
            fetch("/api/users").then((r) => r.json()),
            fetch("/api/projects").then((r) => r.json()),
          ]);
          if (mounted)
            setEntities([
              ...(users.users || []).map((u) => ({
                scope: "user:" + u.userId,
                name: "User · " + u.displayName,
              })),
              ...(projects.projects || []).map((p) => ({
                scope: "project:" + p.id,
                name: "Project · " + p.name,
              })),
            ]);
        }
      })
      .catch((e) => setError(e.message));
    const timer = setInterval(() => {
      if (!document.hidden) load().catch(() => {});
    }, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);
  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/budgets", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          scope,
          currency,
          monthlyHard: hard,
          monthlyWarning: warning,
        }),
      });
      if (!response.ok) throw Error("Budget was not saved.");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="ctl-panel">
      <h2>Budgets</h2>
      {error && (
        <p className="ctl-error" role="alert">
          {error}
        </p>
      )}
      {!data ? (
        <div className="ctl-skeleton" />
      ) : (
        <>
          <div className="vector-table-wrap">
            <table className="vector-table">
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>Spent</th>
                  <th>Reserved</th>
                  <th>Warning</th>
                  <th>Monthly limit</th>
                </tr>
              </thead>
              <tbody>
                {data.limits.map((row) => (
                  <tr key={row.scope}>
                    <td>
                      {row.scope === "workspace"
                        ? "Workspace"
                        : entities.find((e) => e.scope === row.scope)?.name ||
                          row.scope}
                    </td>
                    <td>
                      {row.spent === undefined
                        ? "Private"
                        : Number(row.spent).toFixed(4)}{" "}
                      {row.currency}
                    </td>
                    <td>
                      {row.held === undefined
                        ? "—"
                        : Number(row.held).toFixed(4)}
                    </td>
                    <td>
                      {row.warningReached
                        ? "Threshold reached"
                        : Number(row.monthly_warning).toFixed(2)}
                    </td>
                    <td>
                      {Number(row.monthly_hard).toFixed(2)} {row.currency}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.limits.length && (
            <p>
              Environment and account limits apply. Add a monthly policy below.
            </p>
          )}
          {data.canManage && (
            <details>
              <summary>Edit monthly budget</summary>
              <form onSubmit={save}>
                <div className="ctl-split">
                  <label>
                    Scope
                    <select
                      value={scope}
                      onChange={(e) => {
                        setScope(e.target.value);
                        const row = data.limits.find(
                          (r) => r.scope === e.target.value,
                        );
                        if (row) {
                          setCurrency(row.currency);
                          setHard(String(row.monthly_hard));
                          setWarning(String(row.monthly_warning));
                        }
                      }}
                    >
                      <option value="workspace">Workspace</option>
                      {entities.map((e) => (
                        <option key={e.scope} value={e.scope}>
                          {e.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Currency
                    <select
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      <option>CHF</option>
                      <option>USD</option>
                    </select>
                  </label>
                </div>
                <div className="ctl-split">
                  <label>
                    Warning threshold
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      value={warning}
                      onChange={(e) => setWarning(e.target.value)}
                    />
                  </label>
                  <label>
                    Hard limit
                    <input
                      type="number"
                      min="0"
                      max="100000"
                      step="0.01"
                      required
                      value={hard}
                      onChange={(e) => setHard(e.target.value)}
                    />
                  </label>
                </div>
                <button className="ctl-primary" disabled={saving}>
                  {saving ? "Saving…" : "Save budget"}
                </button>
              </form>
            </details>
          )}
          {data.reservations.length > 0 && (
            <details>
              <summary>
                {data.reservations.length} held call reservations
              </summary>
              <p>
                Reservations are conservative allowances, not billed cost.
                Unknown or failed calls remain held until accounting can be
                reconciled.
              </p>
              <div className="vector-table-wrap">
                <table className="vector-table">
                  <thead>
                    <tr>
                      <th>Created</th>
                      <th>Status</th>
                      <th>Reserved CHF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.reservations.map((row) => (
                      <tr key={row.id}>
                        <td>{new Date(row.created_at).toLocaleString()}</td>
                        <td>{row.status}</td>
                        <td>{Number(row.reserved_chf).toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          <p>
            Environment ceilings: CHF {data.environmentCeilings.dailyChf} daily
            / CHF {data.environmentCeilings.monthlyChf} monthly. Stricter limits
            apply first.
          </p>
          <p>
            Model calls reserve capacity before execution. Actual reported
            charges and rate-based estimates remain separate in the call ledger.
            External tool fees and provider invoices require separate
            reconciliation.
          </p>
        </>
      )}
    </section>
  );
}
