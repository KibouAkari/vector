"use client";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
const template =
  '---\nname: Evidence report\ndescription: A concise report grounded in supplied sources.\nparameters: {"tone":{"type":"string","default":"concise"}}\n---\nSummarize the provided evidence in a {{tone}} style. Distinguish observations from assumptions and include source references.';
const documentFor = (skill) =>
  `---\nname: ${skill.name}\ndescription: ${skill.description || ""}\nparameters: ${JSON.stringify(skill.parameters || {})}\n---\n${skill.instructions}`;
export default function SkillsWorkspace() {
  const [projects, setProjects] = useState([]),
    [project, setProject] = useState(""),
    [skills, setSkills] = useState([]),
    [reviewer, setReviewer] = useState(false),
    [canEdit, setCanEdit] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [editing, setEditing] = useState(null),
    [document, setDocument] = useState(""),
    [preview, setPreview] = useState(false);
  const epoch = useRef(0);
  const endpoint = project ? `/api/projects/${project}/skills` : "/api/skills";
  async function load() {
    const response = await fetch(endpoint, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw Error("Skills could not be loaded.");
    setSkills(data.skills);
    setReviewer(data.canReview);
    setCanEdit(data.canEdit ?? data.canReview);
  }
  useEffect(() => {
    fetch("/api/projects", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { projects: [] }))
      .then((data) => setProjects(data.projects || []))
      .catch(() => {});
    const id = new URL(window.location.href).searchParams.get("project");
    if (id && /^[a-f0-9-]{36}$/i.test(id)) setProject(id);
  }, []);
  useEffect(() => {
    const id = ++epoch.current;
    setLoading(true);
    setEditing(null);
    setSkills([]);
    setError("");
    fetch(endpoint, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw Error("Skills could not be loaded.");
        return response.json();
      })
      .then((data) => {
        if (id === epoch.current) {
          setSkills(data.skills);
          setReviewer(data.canReview);
          setCanEdit(data.canEdit ?? data.canReview);
        }
      })
      .catch((e) => {
        if (id === epoch.current) setError(e.message);
      })
      .finally(() => {
        if (id === epoch.current) setLoading(false);
      });
  }, [endpoint]);
  async function update(body) {
    if (busy) return;
    const id = epoch.current;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Skill was not saved.");
      if (id === epoch.current) {
        setEditing(null);
        await load();
      }
    } catch (e) {
      if (id === epoch.current) setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const families = new Map();
  for (const skill of skills) {
    const key = skill.family_id || skill.id;
    if (!families.has(key)) families.set(key, []);
    families.get(key).push(skill);
  }
  for (const versions of families.values())
    versions.sort((a, b) => b.version - a.version);
  return (
    <div className="ctl-page">
      <header className="ctl-page-header">
        <div>
          <h1>Skills</h1>
          <p>Versioned instructions for chat and project work.</p>
        </div>
        <div className="ctl-toolbar">
          <label>
            Workspace
            <select
              disabled={busy}
              value={project}
              onChange={(e) => {
                setProject(e.target.value);
                window.history.replaceState(
                  null,
                  "",
                  e.target.value
                    ? "/skills?project=" + e.target.value
                    : "/skills",
                );
              }}
            >
              <option value="">My chat skills</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="ctl-primary"
            disabled={busy || !canEdit}
            onClick={() => {
              setEditing({});
              setDocument(template);
              setPreview(false);
            }}
          >
            Create skill
          </button>
        </div>
      </header>
      {error && (
        <p className="ctl-error" role="alert">
          {error}
        </p>
      )}
      {editing !== null && (
        <section className="ctl-panel">
          <div className="ctl-page-header">
            <h2>{editing.id ? "New version" : "New skill"}</h2>
            <button onClick={() => setPreview(!preview)}>
              {preview ? "Edit" : "Preview"}
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              update({
                action: editing.id ? "revise" : "create",
                parentId: editing.id,
                baseContentSha256: editing.content_sha256,
                document,
              });
            }}
          >
            {preview ? (
              <div>
                <Markdown>
                  {document.replace(/^---\n[\s\S]*?\n---\n/, "")}
                </Markdown>
              </div>
            ) : (
              <label>
                Markdown instructions
                <textarea
                  rows={16}
                  required
                  maxLength={12000}
                  spellCheck={false}
                  value={document}
                  onChange={(e) => setDocument(e.target.value)}
                  style={{ fontFamily: "ui-monospace,monospace" }}
                />
                <small>
                  Frontmatter supports name, description and a JSON parameters
                  object. Values use {"{{parameter}}"} in the instructions.
                </small>
              </label>
            )}
            <div className="ctl-toolbar">
              <button className="ctl-primary" disabled={busy || !canEdit}>
                {busy ? "Saving…" : "Save draft"}
              </button>
              <button type="button" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}
      {loading ? (
        <div role="status" aria-label="Loading skills">
          <div className="ctl-skeleton" />
          <div className="ctl-skeleton" />
        </div>
      ) : !skills.length ? (
        <div className="ctl-panel ctl-empty">
          Create a skill, review it and select it in chat.
        </div>
      ) : (
        [...families].map(([family, versions]) => {
          const latest = versions[0];
          return (
            <section className="ctl-panel" key={family}>
              <div className="ctl-page-header">
                <div>
                  <h2>{latest.name}</h2>
                  <p>{latest.description}</p>
                </div>
                <button
                  disabled={busy || !canEdit}
                  onClick={() => {
                    setEditing(latest);
                    setDocument(documentFor(latest));
                    setPreview(false);
                  }}
                >
                  Edit as new version
                </button>
              </div>
              {versions.map((skill) => (
                <details key={skill.id}>
                  <summary>
                    Version {skill.version || 1}{" "}
                    <span className="ctl-status" data-state={skill.status}>
                      {skill.status}
                    </span>
                  </summary>
                  <pre>{skill.instructions}</pre>
                  <small>Content SHA-256 {skill.content_sha256}</small>
                  {Object.keys(skill.parameters || {}).length > 0 && (
                    <pre>{JSON.stringify(skill.parameters, null, 2)}</pre>
                  )}
                  {reviewer && (
                    <div className="ctl-toolbar">
                      <button
                        disabled={busy}
                        onClick={() =>
                          update({
                            action:
                              skill.status === "active" ? "retire" : "activate",
                            id: skill.id,
                            contentSha256: skill.content_sha256,
                          })
                        }
                      >
                        {skill.status === "active"
                          ? "Deactivate"
                          : "Activate reviewed version"}
                      </button>
                    </div>
                  )}
                </details>
              ))}
            </section>
          );
        })
      )}
    </div>
  );
}
