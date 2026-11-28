"use client";
import { useEffect, useRef, useState } from "react";
import SkillImport from "../../components/operations/skill-import";
import Markdown from "react-markdown";
import {
  BookOpen,
  Plus,
  Search,
  Code2,
  LoaderCircle,
  ChevronDown,
} from "lucide-react";
import { Dialog, DialogPanel } from "../../components/ui/overlays";
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
    [preview, setPreview] = useState(false),
    [search, setSearch] = useState("");
  const editorOrigin = useRef(null),
    scopeRef = useRef("");
  const epoch = useRef(0);
  const endpoint = project ? `/api/projects/${project}/skills` : "/api/skills";
  scopeRef.current = endpoint;
  async function load() {
    const activeScope = endpoint;
    const response = await fetch(endpoint, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw Error("Skills could not be loaded.");
    if (scopeRef.current !== activeScope) return;
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
    setCanEdit(false);
    setReviewer(false);
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
  function edit(skill, event) {
    editorOrigin.current = event.currentTarget;
    setEditing(skill);
    setDocument(skill.id ? documentFor(skill) : template);
    setPreview(false);
  }
  const visible = [...families].filter(([, versions]) =>
    versions.some((skill) =>
      (skill.name + " " + skill.description)
        .toLowerCase()
        .includes(search.toLowerCase()),
    ),
  );
  return (
    <div className="vs-skills">
      <header className="vs-page-header">
        <div>
          <h1>Skills</h1>
          <p>Reusable instructions for your work.</p>
        </div>
        <div className="vs-page-actions">
          {canEdit && (
            <SkillImport
              key={project || "chat"}
              projectId={project}
              onImported={load}
            />
          )}
          <button
            type="button"
            className="vc-primary"
            disabled={busy || !canEdit}
            onClick={(event) => edit({}, event)}
          >
            <Plus size={15} />
            Create skill
          </button>
        </div>
      </header>
      {error && (
        <p className="vs-error" role="alert">
          {error}
        </p>
      )}
      <div className="vs-toolbar">
        <label className="vs-search">
          <Search size={15} />
          <input
            type="search"
            placeholder="Search skills"
            aria-label="Search skills"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="vs-scope">
          Workspace
          <select
            disabled={busy}
            value={project}
            onChange={(event) => {
              setProject(event.target.value);
              window.history.replaceState(
                null,
                "",
                event.target.value
                  ? "/skills?project=" + event.target.value
                  : "/skills",
              );
            }}
          >
            <option value="">My chat skills</option>
            {projects.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading ? (
        <div className="vs-loading" role="status" aria-label="Loading skills">
          <div />
          <div />
        </div>
      ) : !visible.length ? (
        <div className="vs-empty" role="status">
          <BookOpen size={34} strokeWidth={1} />
          <h2>{search ? "No matching skills" : "Your skill library"}</h2>
          <p>
            {search
              ? "Try another name or choose a different workspace."
              : "Save instructions you use often, or import a skill from GitHub. Drafts stay inactive until reviewed."}
          </p>
        </div>
      ) : (
        visible.map(([family, versions]) => {
          const latest = versions[0];
          return (
            <article className="vs-skill" key={family}>
              <header>
                <BookOpen size={18} strokeWidth={1.5} />
                <div className="vs-skill-heading">
                  <h2>{latest.name}</h2>
                  <p>{latest.description}</p>
                  <small>Version {latest.version || 1}</small>
                </div>
                <span className="vs-state" data-state={latest.status}>
                  {latest.status}
                </span>
                {canEdit && (
                  <button
                    className="vc-secondary"
                    disabled={busy}
                    onClick={(event) => edit(latest, event)}
                  >
                    Edit
                  </button>
                )}
              </header>
              <details className="vs-versions">
                <summary>Instructions and versions</summary>
                {versions.map((skill) => (
                  <section className="vs-version" key={skill.id}>
                    <header>
                      <span>Version {skill.version || 1}</span>
                      <span className="vs-state" data-state={skill.status}>
                        {skill.status}
                      </span>
                    </header>
                    <pre>{skill.instructions}</pre>
                    {Object.keys(skill.parameters || {}).length > 0 && (
                      <details>
                        <summary>Parameters</summary>
                        <pre>{JSON.stringify(skill.parameters, null, 2)}</pre>
                      </details>
                    )}
                    <footer>
                      {reviewer && (
                        <button
                          className="vc-secondary"
                          disabled={busy}
                          onClick={() =>
                            update({
                              action:
                                skill.status === "active"
                                  ? "retire"
                                  : "activate",
                              id: skill.id,
                              contentSha256: skill.content_sha256,
                            })
                          }
                        >
                          {skill.status === "active"
                            ? "Deactivate"
                            : "Activate reviewed version"}
                        </button>
                      )}
                      <details>
                        <summary>Content fingerprint</summary>
                        <code>{skill.content_sha256}</code>
                      </details>
                    </footer>
                  </section>
                ))}
              </details>
            </article>
          );
        })
      )}
      <Dialog.Root
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setEditing(null);
        }}
      >
        <DialogPanel
          className="vc-skill-editor"
          title={editing?.id ? "New skill version" : "Create a skill"}
          description="Save a draft. Review its exact content before activation."
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            editorOrigin.current?.focus();
          }}
        >
          <div className="vc-editor-tabs" role="group" aria-label="Editor view">
            <button
              type="button"
              aria-pressed={!preview}
              onClick={() => setPreview(false)}
            >
              Markdown
            </button>
            <button
              type="button"
              aria-pressed={preview}
              onClick={() => setPreview(true)}
            >
              Preview
            </button>
          </div>
          {error && (
            <p className="vector-dialog-error" role="alert">
              {error}
            </p>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              update({
                action: editing?.id ? "revise" : "create",
                parentId: editing?.id,
                baseContentSha256: editing?.content_sha256,
                document,
              });
            }}
          >
            {preview ? (
              <div className="vc-preview">
                <Markdown>
                  {document.replace(/^---\n[\s\S]*?\n---\n/, "")}
                </Markdown>
              </div>
            ) : (
              <label>
                Markdown instructions
                <textarea
                  rows={15}
                  required
                  maxLength={12000}
                  spellCheck={false}
                  value={document}
                  onChange={(event) => setDocument(event.target.value)}
                  style={{ fontFamily: "ui-monospace,monospace" }}
                  disabled={busy}
                />
                <small>
                  Frontmatter: name, description and parameters. Use{" "}
                  {"{{parameter}}"} in instructions.
                </small>
              </label>
            )}
            <footer className="vector-dialog-footer">
              <small>{document.length.toLocaleString()} / 12,000</small>
              <button
                type="button"
                className="vc-secondary"
                onClick={() => setEditing(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button className="vc-primary" disabled={busy || !canEdit}>
                {busy && <LoaderCircle size={14} className="vc-spin" />}Save
                draft
              </button>
            </footer>
          </form>
        </DialogPanel>
      </Dialog.Root>
    </div>
  );
}
