"use client";
import { useEffect, useState } from "react";
import {
  BrainCircuit,
  Plus,
  Search,
  Pin,
  Pencil,
  Trash2,
  Download,
  Check,
  X,
} from "lucide-react";
import {
  Page,
  Panel,
  Empty,
  Status,
} from "../../components/operations/primitives";
const blank = {
  title: "",
  body: "",
  tags: [],
  pinned: false,
  source: "User supplied",
  expiresAt: null,
};
export default function Brain() {
  const [data, setData] = useState(null),
    [draft, setDraft] = useState(blank),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  async function load() {
    try {
      const response = await fetch("/api/brain", { cache: "no-store" }),
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
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/brain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(draft),
        }),
        value = await response.json();
      if (!response.ok) throw Error(value.error);
      setDraft(blank);
      setNotice("Memory saved. Future tasks can retrieve it.");
      await load();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(memory) {
    if (
      !window.confirm(
        "Forget this memory? Existing conversations retain their original context.",
      )
    )
      return;
    setError("");
    const response = await fetch("/api/brain", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: memory.id, revision: memory.revision }),
    });
    if (response.ok) {
      setData((old) => ({
        ...old,
        memories: old.memories.filter((item) => item.id !== memory.id),
      }));
      if (draft.id === memory.id) setDraft(blank);
    } else setError((await response.json()).error);
  }
  const memories = (data?.memories || []).filter((item) =>
    (item.title + " " + item.body + " " + item.tags.join(" "))
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data.memories, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "vector-memories.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <Page
      title="Brain"
      eyebrow="Knowledge"
      description="Your context, across models."
      actions={
        <button
          className="op-button"
          onClick={download}
          disabled={!data?.memories?.length}
        >
          <Download size={14} />
          Export
        </button>
      }
    >
      {error && (
        <div className="op-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="op-notice" role="status">
          {notice}
        </p>
      )}
      <div className="op-split">
        <div>
          <div className="op-filter">
            <Search size={16} />
            <input
              className="op-field"
              aria-label="Search memories"
              placeholder="Search your memories…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <span className="op-chip">{data?.memories.length || 0} saved</span>
          </div>
          {!data && !error ? (
            <div className="op-panel" aria-busy="true">
              {[1, 2, 3, 4].map((n) => (
                <div className="op-skeleton" key={n} />
              ))}
            </div>
          ) : memories.length ? (
            <div className="op-memory-list">
              {memories.map((memory) => (
                <article className="op-memory" key={memory.id}>
                  <header>
                    <h3>
                      {memory.pinned && <Pin size={12} />} {memory.title}
                    </h3>
                    <span className="op-chip">v{memory.revision}</span>
                  </header>
                  <pre>{memory.body}</pre>
                  <div className="op-actions">
                    {memory.tags.map((tag) => (
                      <span className="op-chip" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <footer>
                    <small>
                      {memory.source}
                      <br />
                      {memory.expiresAt
                        ? "Expires " +
                          new Date(memory.expiresAt).toLocaleDateString()
                        : "Until you forget it"}
                    </small>
                    {data.canEdit && (
                      <div className="op-actions">
                        <button
                          className="op-icon"
                          aria-label={"Edit " + memory.title}
                          onClick={() => {
                            setDraft(memory);
                            setNotice("");
                          }}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="op-icon"
                          aria-label={"Forget " + memory.title}
                          onClick={() => remove(memory)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </footer>
                </article>
              ))}
            </div>
          ) : (
            <Panel>
              <Empty
                icon={BrainCircuit}
                title={
                  search ? "No matching memories" : "A clear starting point"
                }
                description="Save preferences, decisions or facts you want Vector to remember."
              />
            </Panel>
          )}
        </div>
        <div className="op-sticky">
          <Panel
            title={draft.id ? "Correct memory" : "Save something useful"}
            subtitle="Private to your account"
          >
            <form className="op-form" onSubmit={save}>
              <label>
                Title
                <input
                  required
                  maxLength={100}
                  value={draft.title}
                  onChange={(event) =>
                    setDraft({ ...draft, title: event.target.value })
                  }
                />
              </label>
              <label>
                Context
                <textarea
                  required
                  maxLength={12000}
                  value={draft.body}
                  onChange={(event) =>
                    setDraft({ ...draft, body: event.target.value })
                  }
                  placeholder="A preference, decision or fact. Keep credentials in Connections."
                />
              </label>
              <label>
                Tags
                <input
                  value={draft.tags.join(", ")}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      tags: event.target.value
                        .split(",")
                        .map((tag) => tag.trim())
                        .slice(0, 8),
                    })
                  }
                  placeholder="project, preference"
                />
              </label>
              <label>
                Source
                <input
                  value={draft.source}
                  maxLength={300}
                  onChange={(event) =>
                    setDraft({ ...draft, source: event.target.value })
                  }
                />
              </label>
              <label>
                Expires
                <input
                  type="date"
                  value={draft.expiresAt?.slice(0, 10) || ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      expiresAt: event.target.value
                        ? event.target.value + "T23:59:59Z"
                        : null,
                    })
                  }
                />
              </label>
              <label className="op-toggle">
                <input
                  type="checkbox"
                  checked={draft.pinned}
                  onChange={(event) =>
                    setDraft({ ...draft, pinned: event.target.checked })
                  }
                />
                Always consider this memory
              </label>
              <div className="op-actions">
                <button
                  className="op-button primary"
                  disabled={busy || data?.canEdit === false}
                >
                  <Check size={14} />
                  {busy ? "Saving…" : "Save memory"}
                </button>
                {draft.id && (
                  <button
                    type="button"
                    className="op-button"
                    onClick={() => setDraft(blank)}
                  >
                    <X size={14} />
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </Panel>
          <p className="op-footnote">
            Encrypted at rest. Up to six relevant memories, capped at 2,400
            UTF-8 bytes, are included before the privacy review. Retrieval uses
            no model call. Forgetting stops future retrieval; it does not
            rewrite previous conversations.
          </p>
        </div>
      </div>
    </Page>
  );
}
