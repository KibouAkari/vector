"use client";
import { useState } from "react";
import { GitBranch, Download, LoaderCircle } from "lucide-react";
import { Dialog, DialogPanel } from "../ui/overlays";
export default function SkillImport({ projectId, onImported }) {
  const [open, setOpen] = useState(false),
    [url, setUrl] = useState(""),
    [preview, setPreview] = useState(null),
    [accepted, setAccepted] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function run(action) {
    if (busy) return;
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
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error);
      if (action === "preview") setPreview(data);
      else {
        setPreview(null);
        setUrl("");
        setAccepted(false);
        setOpen(false);
        await onImported?.();
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (!busy) setOpen(value);
      }}
    >
      <Dialog.Trigger asChild>
        <button type="button" className="vc-secondary">
          <GitBranch size={14} />
          Import from GitHub
        </button>
      </Dialog.Trigger>
      <DialogPanel
        title="Import a skill"
        description="Review the source before adding it to your library."
      >
        {error && (
          <p role="alert" className="vector-dialog-error">
            {error}
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            run("preview");
          }}
        >
          <label>
            Public SKILL.md URL
            <input
              type="url"
              required
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setPreview(null);
                setAccepted(false);
              }}
              placeholder="https://github.com/owner/repo/blob/main/SKILL.md"
              disabled={busy}
            />
          </label>
          <div className="vector-dialog-footer">
            <button
              type="submit"
              className="vc-secondary"
              disabled={busy || !url}
            >
              {busy && <LoaderCircle size={14} className="vc-spin" />}Preview
              source
            </button>
          </div>
        </form>
        {preview && (
          <section className="vc-import-content">
            <h3>{preview.skill.name}</h3>
            <p>{preview.skill.description}</p>
            <pre>{preview.skill.instructions}</pre>
            <div className="vc-import-source">
              Commit <code>{preview.source.commit}</code>
              <br />
              License: {preview.source.license}. Only Markdown instructions are
              imported.
            </div>
            <label className="vector-dialog-check">
              <input
                type="checkbox"
                checked={accepted}
                disabled={busy}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span>I reviewed the source and have permission to use it.</span>
            </label>
            <div className="vector-dialog-footer">
              <button
                type="button"
                className="vc-primary"
                disabled={busy || !accepted}
                onClick={() => run("import")}
              >
                <Download size={14} />
                Import draft
              </button>
            </div>
          </section>
        )}
      </DialogPanel>
    </Dialog.Root>
  );
}
