"use client";
import { useEffect, useState } from "react";
export default function PoliciesClient() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [role, setRole] = useState("member"),
    [models, setModels] = useState(""),
    [tools, setTools] = useState(""),
    [restrictedModels, setRestrictedModels] = useState(false),
    [restrictedTools, setRestrictedTools] = useState(false);
  async function load() {
    const response = await fetch("/api/permissions/policies", {
      cache: "no-store",
    });
    if (!response.ok) throw Error("Policies could not be loaded.");
    setData(await response.json());
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    const policy = data?.roles.find((r) => r.role === role)?.policy || {};
    setRestrictedModels(Array.isArray(policy.models));
    setRestrictedTools(Array.isArray(policy.tools));
    setModels(policy.models?.join("\n") || "");
    setTools(policy.tools?.join("\n") || "");
  }, [data, role]);
  async function save(input) {
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/permissions/policies", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!response.ok) throw Error("Policy was not saved.");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="ctl-page">
      <header className="ctl-page-header">
        <div>
          <h1>Permission policies</h1>
          <p>Control models, tools and action approvals.</p>
        </div>
        <a className="ctl-button" href="/users">
          Users
        </a>
      </header>
      {error && (
        <p className="ctl-error" role="alert">
          {error}
        </p>
      )}
      {!data ? (
        <div className="ctl-skeleton" />
      ) : (
        <div className="ctl-split">
          <section className="ctl-panel">
            <h2>Role access</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                save({
                  role,
                  policy: {
                    models: restrictedModels
                      ? models
                          .split("\n")
                          .map((s) => s.trim())
                          .filter(Boolean)
                      : null,
                    tools: restrictedTools
                      ? tools
                          .split("\n")
                          .map((s) => s.trim())
                          .filter(Boolean)
                      : null,
                  },
                });
              }}
            >
              <label>
                Role
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {["admin", "member", "readonly"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label className="ctl-check">
                <input
                  type="checkbox"
                  checked={restrictedModels}
                  onChange={(e) => setRestrictedModels(e.target.checked)}
                />
                Restrict model IDs
              </label>
              {restrictedModels && (
                <label>
                  Allowed provider/model IDs
                  <textarea
                    value={models}
                    onChange={(e) => setModels(e.target.value)}
                    placeholder="openai/gpt-6-luna"
                  />
                  <small>
                    One exact provider/model per line. Empty means none.
                  </small>
                </label>
              )}
              <label className="ctl-check">
                <input
                  type="checkbox"
                  checked={restrictedTools}
                  onChange={(e) => setRestrictedTools(e.target.checked)}
                />
                Restrict tool names
              </label>
              {restrictedTools && (
                <label>
                  Allowed tools
                  <textarea
                    value={tools}
                    onChange={(e) => setTools(e.target.value)}
                    placeholder={"project_search\nproject_read_file"}
                  />
                </label>
              )}
              <button className="ctl-primary" disabled={saving}>
                {saving ? "Saving…" : "Save role policy"}
              </button>
              <p>
                Read-only accounts cannot run tasks or mutate resources. Owner
                access is retained.
              </p>
            </form>
          </section>
          <section className="ctl-panel">
            <h2>Critical actions</h2>
            {["network.scan", "sandbox.execute", "sandbox.write"].map(
              (permission) => (
                <div className="ctl-asset" key={permission}>
                  <strong>{permission}</strong>
                  <label>
                    Decision
                    <select
                      disabled={saving}
                      value={
                        data.permissions.find(
                          (p) => p.permission === permission,
                        )?.decision || "ASK"
                      }
                      onChange={(e) =>
                        save({ permission, decision: e.target.value })
                      }
                    >
                      <option value="ASK">Ask</option>
                      <option value="DENY">Deny</option>
                      <option value="ALLOW">Allow</option>
                    </select>
                  </label>
                </div>
              ),
            )}
            <p>
              Saved scanner assets have separate scope-bound authorization.
              Policies cannot authorize another target or override project
              access.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
