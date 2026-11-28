"use client";
import { useEffect, useState } from "react";
import {
  Cable,
  Plus,
  RefreshCw,
  Trash2,
  ArrowUpRight,
  KeyRound,
} from "lucide-react";
import { CONNECTORS } from "../../lib/connectors/catalog.mjs";
import {
  Page,
  Panel,
  Empty,
  Status,
} from "../../components/operations/primitives";
const initial = {
  kind: "checkmk",
  name: "",
  base: CONNECTORS[0].base,
  username: "",
  secret: "",
  readPath: "status",
};
export default function Connections() {
  const [data, setData] = useState(null),
    [form, setForm] = useState(initial),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [show, setShow] = useState(false),
    [action, setAction] = useState({
      id: "",
      action: "create-issue",
      repository: "",
      title: "",
      body: "",
      channel: "",
      text: "",
    });
  async function load() {
    try {
      const response = await fetch("/api/connections", { cache: "no-store" }),
        value = await response.json();
      if (!response.ok) throw Error(value.error);
      setData(value);
    } catch (error) {
      setError(error.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function send(input) {
    setBusy(input.id || "create");
    setError("");
    try {
      const response = await fetch("/api/connections", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        }),
        value = await response.json();
      if (!response.ok) throw Error(value.error);
      await load();
      window.dispatchEvent(new Event("vector:approvals"));
      return true;
    } catch (error) {
      setError(error.message);
      return false;
    } finally {
      setBusy("");
    }
  }
  const selected = CONNECTORS.find((row) => row.id === form.kind);
  return (
    <Page
      title="Connections"
      eyebrow="Operations"
      description="Your tools, in reach."
      actions={
        <button className="op-button primary" onClick={() => setShow(!show)}>
          <Plus size={15} />
          Connect a tool
        </button>
      }
    >
      {error && (
        <div role="alert" className="op-error">
          {error}
        </div>
      )}
      <div className={show ? "op-split" : ""}>
        <div>
          {!data && !error ? (
            <Panel>
              {[1, 2, 3].map((n) => (
                <div key={n} className="op-skeleton" />
              ))}
            </Panel>
          ) : !data?.connections?.length ? (
            <Panel>
              <Empty
                icon={Cable}
                title="Connect your first service"
                description="Add a scoped credential, then fetch a snapshot when you need it."
                action={
                  <button className="op-button" onClick={() => setShow(true)}>
                    Add connection
                  </button>
                }
              />
            </Panel>
          ) : (
            <div className="op-grid two">
              {data.connections.map((connection) => (
                <Panel
                  key={connection.id}
                  title={connection.name}
                  subtitle={
                    CONNECTORS.find((row) => row.id === connection.kind)?.name
                  }
                  actions={
                    <Status
                      value={
                        connection.lastError
                          ? "failed"
                          : connection.lastSyncedAt
                            ? "completed"
                            : "pending"
                      }
                    >
                      {connection.lastError
                        ? "Needs attention"
                        : connection.lastSyncedAt
                          ? "Snapshot saved"
                          : "Not synced"}
                    </Status>
                  }
                >
                  <p className="op-connection-url">{connection.base}</p>
                  {connection.lastError && (
                    <p className="op-error">{connection.lastError}</p>
                  )}
                  {connection.snapshot && (
                    <>
                      <dl className="op-facts">
                        {Object.entries(connection.snapshot.summary).map(
                          ([key, value]) => (
                            <div key={key}>
                              <dt>{key.replace(/([A-Z])/g, " $1")}</dt>
                              <dd>
                                {value === null ? "Unavailable" : String(value)}
                              </dd>
                            </div>
                          ),
                        )}
                      </dl>
                      {connection.snapshot.resources?.length > 0 && (
                        <details className="op-details">
                          <summary>
                            {connection.snapshot.resources.length} resources
                          </summary>
                          <div className="op-table-scroll">
                            <table className="op-table">
                              <thead>
                                <tr>
                                  <th>Name</th>
                                  <th>State</th>
                                  <th>Version</th>
                                </tr>
                              </thead>
                              <tbody>
                                {connection.snapshot.resources.map(
                                  (row, index) => (
                                    <tr key={row.id || index}>
                                      <td>{row.name}</td>
                                      <td>{row.state}</td>
                                      <td>{row.version || "—"}</td>
                                    </tr>
                                  ),
                                )}
                              </tbody>
                            </table>
                          </div>
                        </details>
                      )}
                    </>
                  )}
                  <div className="op-connection-footer">
                    <small>
                      {connection.lastSyncedAt
                        ? "Fetched " +
                          new Date(connection.lastSyncedAt).toLocaleString()
                        : "No requests made yet"}
                    </small>
                    <div className="op-actions">
                      <button
                        className="op-button"
                        disabled={!!busy}
                        onClick={() =>
                          send({ action: "sync", id: connection.id })
                        }
                      >
                        <RefreshCw
                          size={13}
                          className={busy === connection.id ? "op-spin" : ""}
                        />
                        Sync
                      </button>
                      {["github", "slack"].includes(connection.kind) && (
                        <button
                          className="op-button"
                          onClick={() =>
                            setAction({
                              ...action,
                              id: connection.id,
                              action:
                                connection.kind === "github"
                                  ? "create-issue"
                                  : "send-message",
                            })
                          }
                        >
                          New action
                        </button>
                      )}
                      <button
                        className="op-icon"
                        aria-label={"Remove " + connection.name}
                        disabled={!!busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Remove connection and its credentials?",
                            )
                          )
                            send({ action: "remove", id: connection.id });
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </Panel>
              ))}
            </div>
          )}
          {action.id && (
            <Panel
              title="Prepare action"
              subtitle="Exact content goes to the approval queue"
            >
              <form
                className="op-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (
                    await send({
                      action: "request-action",
                      id: action.id,
                      spec: action,
                    })
                  )
                    setAction({ ...action, id: "" });
                }}
              >
                {action.action === "create-issue" ? (
                  <>
                    <label>
                      Repository
                      <input
                        required
                        value={action.repository}
                        placeholder="owner/repo"
                        onChange={(event) =>
                          setAction({
                            ...action,
                            repository: event.target.value,
                          })
                        }
                      />
                    </label>
                    <label>
                      Issue title
                      <input
                        required
                        value={action.title}
                        onChange={(event) =>
                          setAction({ ...action, title: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Body
                      <textarea
                        value={action.body}
                        onChange={(event) =>
                          setAction({ ...action, body: event.target.value })
                        }
                      />
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      Slack channel ID
                      <input
                        required
                        value={action.channel}
                        onChange={(event) =>
                          setAction({ ...action, channel: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Message
                      <textarea
                        required
                        value={action.text}
                        onChange={(event) =>
                          setAction({ ...action, text: event.target.value })
                        }
                      />
                    </label>
                  </>
                )}
                <div className="op-actions">
                  <button className="op-button primary" disabled={!!busy}>
                    Request approval
                  </button>
                  <button
                    className="op-button"
                    type="button"
                    onClick={() => setAction({ ...action, id: "" })}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </Panel>
          )}
          {!!data?.actions.length && (
            <Panel
              title="Action history"
              subtitle="Approval is followed by a separate, single execution"
            >
              <div className="op-table-scroll">
                <table className="op-table">
                  <thead>
                    <tr>
                      <th>Action</th>
                      <th>Approval</th>
                      <th>Execution</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.actions.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <details>
                            <summary>
                              {item.spec.method} {item.spec.path}
                            </summary>
                            <pre className="op-code">
                              {JSON.stringify(item.spec.body, null, 2)}
                            </pre>
                            <small>SHA-256 {item.scope_digest}</small>
                          </details>
                        </td>
                        <td>{item.approval_status}</td>
                        <td>{item.status}</td>
                        <td>
                          {item.status === "pending" &&
                            item.approval_status === "approved" && (
                              <button
                                className="op-button"
                                disabled={!!busy}
                                onClick={() =>
                                  send({ action: "execute", id: item.id })
                                }
                              >
                                Execute once
                              </button>
                            )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </div>
        {show && (
          <div className="op-sticky">
            <Panel title="Add connection" actions={<KeyRound size={16} />}>
              <form
                className="op-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (await send({ ...form, action: "create" })) {
                    setForm(initial);
                    setShow(false);
                  }
                }}
              >
                <label>
                  Service
                  <select
                    value={form.kind}
                    onChange={(event) => {
                      const kind = CONNECTORS.find(
                        (row) => row.id === event.target.value,
                      );
                      setForm({
                        ...initial,
                        kind: kind.id,
                        base: kind.base,
                        name: kind.name,
                      });
                    }}
                  >
                    {CONNECTORS.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Name
                  <input
                    required
                    value={form.name}
                    onChange={(event) =>
                      setForm({ ...form, name: event.target.value })
                    }
                  />
                </label>
                <label>
                  API base URL
                  <input
                    required
                    type="url"
                    disabled={selected.fixed}
                    value={form.base}
                    onChange={(event) =>
                      setForm({ ...form, base: event.target.value })
                    }
                  />
                </label>
                {["basic", "automation"].includes(selected.auth) && (
                  <label>
                    {form.kind === "patchmon" ? "Token key" : "Username"}
                    <input
                      required
                      autoComplete="off"
                      value={form.username}
                      onChange={(event) =>
                        setForm({ ...form, username: event.target.value })
                      }
                    />
                  </label>
                )}
                <label>
                  {form.kind === "patchmon"
                    ? "Token secret"
                    : "Secret / access token"}
                  <input
                    type="password"
                    required
                    autoComplete="new-password"
                    value={form.secret}
                    onChange={(event) =>
                      setForm({ ...form, secret: event.target.value })
                    }
                  />
                </label>
                {form.kind === "api" && (
                  <label>
                    Read path
                    <input
                      value={form.readPath}
                      onChange={(event) =>
                        setForm({ ...form, readPath: event.target.value })
                      }
                    />
                  </label>
                )}
                <p className="op-muted">{selected.hint}</p>
                <button className="op-button primary" disabled={!!busy}>
                  {busy ? "Connecting…" : "Save connection"}
                </button>
              </form>
            </Panel>
            <p className="op-footnote">
              Credentials are encrypted and never returned to the browser.
              Internal addresses require an operator CIDR allowlist. TLS
              verification stays enabled. Saving does not call the remote API.
            </p>
          </div>
        )}
      </div>
    </Page>
  );
}
