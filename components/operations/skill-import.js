"use client";
import { useState } from "react";
import { GitBranch, Download } from "lucide-react";
export default function SkillImport({ projectId, onImported }) {
  const [url, setUrl] = useState(""),
    [preview, setPreview] = useState(null),
    [accepted, setAccepted] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function run(action) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/skills/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url,
            projectId: projectId || null,
            action,
            commit: preview?.source.commit,
            contentSha256: preview?.source.sha256,
            acceptLicense: accepted,
          }),
        }),
        data = await response.json();
      if (!response.ok) throw Error(data.error);
      if (action === "preview") setPreview(data);
      else {
        setPreview(null);
        setUrl("");
        onImported?.();
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="op-skill-import">
      <summary>
        <GitBranch size={15} />
        Import from GitHub
      </summary>
      <div className="op-form">
        <label>
          Public SKILL.md URL
          <input
            type="url"
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              setPreview(null);
              setAccepted(false);
            }}
            placeholder="https://github.com/owner/repo/blob/main/skills/example/SKILL.md"
          />
        </label>
        <button
          className="op-button"
          disabled={busy || !url}
          onClick={() => run("preview")}
        >
          Preview
        </button>
        {error && (
          <p className="op-error" role="alert">
            {error}
          </p>
        )}
        {preview && (
          <div className="op-memory">
            <h3>{preview.skill.name}</h3>
            <p>{preview.skill.description}</p>
            <pre>{preview.skill.instructions}</pre>
            <p className="op-footnote">
              Commit {preview.source.commit}
              <br />
              License: {preview.source.license}. Only the Markdown instructions
              are imported. Scripts and tool grants are not installed.
            </p>
            <label className="op-toggle">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              I reviewed the source and have permission to use it.
            </label>
            <button
              className="op-button primary"
              disabled={busy || !accepted}
              onClick={() => run("import")}
            >
              <Download size={14} />
              Import as draft
            </button>
          </div>
        )}
      </div>
    </details>
  );
}
