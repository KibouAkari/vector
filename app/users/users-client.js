"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft, ArrowRight, Check, ChevronRight, KeyRound,
  Shield, UserRoundPlus, X
} from "lucide-react";

const CAPABILITIES = [
  ["chat", "Chat", "Messages, attachments and AI conversations"],
  ["projects", "Projects", "Project workspaces and explicitly shared files"],
  ["server", "Server", "Read-only infrastructure monitoring"],
  ["models", "Models & APIs", "Manage their own model connections"],
  ["activity", "Audit log", "View activity belonging to their account"]
];

const initialUser = () => ({
  username: "", displayName: "", password: "",
  role: "member", enabled: true,
  monthlyBudgetChf: "2.00", totalBudgetChf: "",
  expiresAt: "",
  features: {
    chat: true, projects: false, server: false,
    models: false, activity: false, showLockedNavigation: false
  }
});

const presetFeatures = (name, existing = {}) => ({
  chat: true,
  projects: name === "collaborator",
  server: false,
  models: name === "collaborator",
  activity: false,
  showLockedNavigation: Boolean(existing.showLockedNavigation)
});

export default function UsersClient({ currentUserId }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [step, setStep] = useState(0);
  const [shares, setShares] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadUsers() {
    const response = await fetch("/api/users", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not load user accounts.");
    const data = await response.json();
    setUsers(data.users || []);
  }

  useEffect(() => {
    loadUsers().catch(error => setError(error.message))
      .finally(() => setLoading(false));
  }, []);

  async function open(user) {
    setStep(0);
    setError("");
    setShares([]);
    setEditing(user ? {
      id: user.userId,
      username: user.username,
      displayName: user.displayName || user.username,
      password: "",
      role: user.role,
      enabled: user.enabled,
      monthlyBudgetChf: user.monthlyBudgetChf ?? "",
      totalBudgetChf: user.totalBudgetChf ?? "",
      expiresAt: user.expiresAt
        ? new Date(user.expiresAt).toISOString().slice(0, 16) : "",
      features: { ...user.features }
    } : initialUser());
    try {
      const endpoint = user
        ? "/api/users/" + encodeURIComponent(user.userId) + "/projects"
        : "/api/projects";
      const response = await fetch(endpoint, { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load project permissions.");
      const data = await response.json();
      setShares((data.projects || []).map(project => ({
        ...project,
        shared: Boolean(project.shared)
      })));
    } catch (err) {
      setError(err.message);
    }
  }

  function patch(changes) {
    setEditing(current => ({ ...current, ...changes }));
    setError("");
  }

  function toggleFeature(key, checked) {
    patch({
      features: { ...editing.features, [key]: checked }
    });
    if (key === "projects" && !checked) {
      setShares(current => current.map(project => ({ ...project, shared: false })));
    }
  }

  function validateIdentity() {
    if (!editing.id && !/^[A-Za-z0-9._-]{2,64}$/.test(editing.username.trim())) {
      return "Use 2–64 letters, numbers, dots, underscores or dashes for the username.";
    }
    if (!editing.id && editing.password.length < 8) {
      return "Choose a password with at least eight characters.";
    }
    if (editing.password && editing.password.length < 8) {
      return "A new password must have at least eight characters.";
    }
    if (!editing.displayName.trim()) return "Enter a display name.";
    return "";
  }

  function validateAccess() {
    for (const value of [editing.monthlyBudgetChf, editing.totalBudgetChf]) {
      if (value !== "" && (!Number.isFinite(Number(value)) || Number(value) < 0)) {
        return "Budgets must be non-negative amounts in CHF.";
      }
    }
    if (editing.expiresAt && Number.isNaN(Date.parse(editing.expiresAt))) {
      return "Choose a valid account expiry date.";
    }
    return "";
  }

  async function submit(event) {
    event.preventDefault();
    if (saving || !editing) return;

    if (step === 0) {
      const issue = validateIdentity();
      if (issue) { setError(issue); return; }
      setError("");
      setStep(1);
      return;
    }

    const issue = validateAccess();
    if (issue) { setError(issue); return; }
    setError("");
    setSaving(true);

    try {
      const previousId = editing.id;
      const endpoint = previousId
        ? "/api/users/" + encodeURIComponent(previousId)
        : "/api/users";
      const response = await fetch(endpoint, {
        method: previousId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...editing,
          expiresAt: editing.expiresAt
            ? new Date(editing.expiresAt).toISOString() : null
        })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save the account.");
      const userId = previousId || result.id;
      if (!userId) throw new Error("Account saved but no user ID was returned.");

      if (editing.role !== "owner" && editing.features?.projects) {
        const shareResponse = await fetch(
          "/api/users/" + encodeURIComponent(userId) + "/projects",
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              projectIds: shares.filter(project => project.shared).map(project => project.id),
              accessRole: "viewer"
            })
          }
        );
        if (!shareResponse.ok) {
          setEditing(current => ({ ...current, id: userId }));
          throw new Error("Account saved, but project access could not be updated. Please retry.");
        }
      } else if (previousId && editing.role !== "owner") {
        const clearResponse = await fetch(
          "/api/users/" + encodeURIComponent(userId) + "/projects",
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ projectIds: [], accessRole: "viewer" })
          }
        );
        if (!clearResponse.ok) throw new Error("Account updated, but old project shares could not be cleared.");
      }

      setEditing(null);
      setShares([]);
      await loadUsers();
    } catch (err) {
      setError(err.message || "Could not save account.");
    } finally {
      setSaving(false);
    }
  }

  const allowedFeatures = user =>
    user.role === "owner" ? "Full access" :
      CAPABILITIES.filter(([key]) => user.features?.[key])
        .map(([, label]) => label).join(", ") || "No active features";

  return (
    <section className="vux-users">
      <header className="vux-users-head">
        <div>
          <span className="vux-eyebrow">OWNER / ACCESS MANAGEMENT</span>
          <h1>Users</h1>
          <p>Give everyone exactly the access they need. Nothing more.</p>
        </div>
        <button className="vux-main-action" type="button" onClick={() => open(null)}>
          <UserRoundPlus size={16} aria-hidden="true" /> New account
        </button>
      </header>

      {loading && <p className="vux-empty">Loading accounts…</p>}
      {!loading && users.length === 0 && (
        <p className="vux-empty">No accounts yet. Create your first member account.</p>
      )}

      <div className="vux-users-list" aria-label="User accounts">
        {users.map(user => (
          <button key={user.userId} type="button" className="vux-user-row"
            onClick={() => open(user)}>
            <span className="vux-user-avatar">{(user.displayName || user.username)[0]?.toUpperCase()}</span>
            <span className="vux-user-name">
              <strong>{user.displayName || user.username}</strong>
              <small>@{user.username} · {user.role}</small>
            </span>
            <span className="vux-user-permissions">
              <small>ACCESS</small>
              <strong>{allowedFeatures(user)}</strong>
            </span>
            <span className="vux-user-budget">
              <small>MONTHLY BUDGET</small>
              <strong>{user.role === "owner" ? "Owner" :
                user.monthlyBudgetChf == null ? "Unlimited" :
                "CHF " + Number(user.monthlyBudgetChf).toFixed(2)}</strong>
            </span>
            <span className={"vux-user-status " + (user.enabled ? "" : "inactive")}>
              {user.enabled ? "Active" : "Disabled"}
            </span>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        ))}
      </div>

      {editing && (
        <div className="v5-modal-layer vux-layer">
          <button type="button" className="v5-modal-shade" aria-label="Close editor"
            onClick={() => !saving && setEditing(null)} />
          <div className="vux-user-dialog" role="dialog" aria-modal="true"
            aria-labelledby="vux-dialog-title">
            <header className="vux-dialog-head">
              <div>
                <span className="vux-eyebrow">{editing.id ? "EDIT ACCOUNT" : "NEW ACCOUNT"}</span>
                <h2 id="vux-dialog-title">{editing.id
                  ? (editing.displayName || editing.username) : "Create an account"}</h2>
                <p>{step === 0
                  ? "Start with the account details."
                  : "Set permissions, spending limits and shared projects."}</p>
              </div>
              <button type="button" className="vux-icon-button"
                onClick={() => !saving && setEditing(null)} aria-label="Close editor">
                <X size={18} aria-hidden="true" />
              </button>
            </header>
            <div className="vux-steps" aria-label="Account creation progress">
              <span className={step === 0 ? "active" : "done"}>
                {step > 0 ? <Check size={14} aria-hidden="true" /> : <KeyRound size={14} aria-hidden="true" />}
                Account
              </span>
              <span className={step === 1 ? "active" : ""}>
                <Shield size={14} aria-hidden="true" /> Access & limits
              </span>
            </div>

            {error && <p className="vux-form-error" role="alert">{error}</p>}

            <form onSubmit={submit} className="vux-user-form">
              {step === 0 ? (
                <div className="vux-form-body">
                  <div className="vux-field-grid">
                    <label>Username
                      <input value={editing.username} disabled={Boolean(editing.id)}
                        autoComplete="off" minLength={2} maxLength={64}
                        onChange={event => patch({ username: event.target.value })}
                        placeholder="e.g. alex" required />
                      <small>Used to sign in. Cannot be changed later.</small>
                    </label>
                    <label>Display name
                      <input value={editing.displayName} maxLength={80}
                        onChange={event => patch({ displayName: event.target.value })}
                        placeholder="How should Vector address them?" required />
                    </label>
                  </div>
                  <label>Password {editing.id && <small>Leave blank to keep the current password</small>}
                    <input type="password" autoComplete="new-password"
                      minLength={editing.id ? undefined : 8}
                      value={editing.password}
                      onChange={event => patch({ password: event.target.value })}
                      placeholder={editing.id ? "Optional new password" : "At least 8 characters"}
                      required={!editing.id} />
                  </label>

                  <div className="vux-form-split">
                    <div>
                      <strong>Role</strong>
                      <p>Owners can administer every user, project and service.</p>
                    </div>
                    <select value={editing.role} disabled={editing.id === currentUserId}
                      onChange={event => patch({ role: event.target.value })}>
                      <option value="member">Member</option>
                      <option value="owner">Owner</option>
                    </select>
                  </div>
                  {editing.id !== currentUserId && (
                    <label className="vux-toggle-line">
                      <input type="checkbox" checked={Boolean(editing.enabled)}
                        onChange={event => patch({ enabled: event.target.checked })} />
                      <span><strong>Account enabled</strong><small>Turn off to immediately revoke logins.</small></span>
                    </label>
                  )}
                </div>
              ) : (
                <div className="vux-form-body">
                  {editing.role !== "owner" && (
                    <>
                      <div className="vux-form-section">
                        <h3>What can they use?</h3>
                        <p>Choose a starting point, then fine-tune individual features.</p>
                        <div className="vux-presets">
                          <button type="button" onClick={() => patch({
                            features: presetFeatures("chat", editing.features)
                          })}>Chat only</button>
                          <button type="button" onClick={() => patch({
                            features: presetFeatures("collaborator", editing.features)
                          })}>Collaborator</button>
                        </div>
                        <div className="vux-feature-list">
                          {CAPABILITIES.map(([key, label, description]) => (
                            <label key={key} className="vux-feature-row">
                              <input type="checkbox" checked={Boolean(editing.features?.[key])}
                                onChange={event => toggleFeature(key, event.target.checked)} />
                              <span><strong>{label}</strong><small>{description}</small></span>
                            </label>
                          ))}
                        </div>
                        <label className="vux-toggle-line vux-discovery">
                          <input type="checkbox"
                            checked={Boolean(editing.features?.showLockedNavigation)}
                            onChange={event => toggleFeature("showLockedNavigation", event.target.checked)} />
                          <span><strong>Show locked features in navigation</strong>
                            <small>Other pages appear muted with a friendly access message. They stay blocked.</small></span>
                        </label>
                      </div>
                    </>
                  )}

                  <div className="vux-form-section">
                    <h3>Budget & expiry</h3>
                    <p>Empty budgets mean no additional per-user limit.</p>
                    <div className="vux-field-grid">
                      <label>Monthly budget (CHF)
                        <input type="number" min="0" step="0.01"
                          value={editing.monthlyBudgetChf}
                          disabled={editing.role === "owner"}
                          onChange={event => patch({ monthlyBudgetChf: event.target.value })}
                          placeholder="No limit" />
                      </label>
                      <label>Total budget (CHF)
                        <input type="number" min="0" step="0.01"
                          value={editing.totalBudgetChf}
                          disabled={editing.role === "owner"}
                          onChange={event => patch({ totalBudgetChf: event.target.value })}
                          placeholder="No limit" />
                      </label>
                      <label className="vux-wide">Expires at
                        <input type="datetime-local" value={editing.expiresAt}
                          disabled={editing.id === currentUserId}
                          onChange={event => patch({ expiresAt: event.target.value })} />
                      </label>
                    </div>
                  </div>

                  {editing.role !== "owner" && editing.features?.projects && (
                    <div className="vux-form-section">
                      <h3>Project sharing</h3>
                      <p>Only explicitly selected workspaces are visible to this member.</p>
                      <div className="vux-feature-list">
                        {shares.length ? shares.map(project => (
                          <label key={project.id} className="vux-feature-row">
                            <input type="checkbox" checked={Boolean(project.shared)}
                              onChange={event => setShares(current => current.map(item =>
                                item.id === project.id ? { ...item, shared: event.target.checked } : item
                              ))} />
                            <span><strong>{project.name}</strong>
                              <small>{project.description || "Project workspace"}</small></span>
                          </label>
                        )) : <p className="vux-empty">No projects available to share.</p>}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <footer className="vux-dialog-footer">
                <button type="button" className="vux-secondary" disabled={saving}
                  onClick={() => step === 0 ? setEditing(null) : (setStep(0), setError(""))}>
                  {step === 0 ? "Cancel" : <><ArrowLeft size={15} /> Back</>}
                </button>
                <button className="vux-main-action" type="submit" disabled={saving}>
                  {step === 0
                    ? <>Next: permissions <ArrowRight size={15} /></>
                    : saving ? "Saving…" : editing.id ? "Save changes" : "Create account"}
                </button>
              </footer>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
