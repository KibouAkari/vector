"use client";
import { useEffect, useState } from "react";
import SkillParameters from "../../../components/ui/skill-parameters";
export default function ProjectSkillsPanel({
  projectId,
  canEdit,
  selected,
  onSelection,
  parameters = {},
  onParameters = () => {},
}) {
  const [skills, setSkills] = useState([]),
    [reviewer, setReviewer] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const endpoint = `/api/projects/${encodeURIComponent(projectId)}/skills`;
  async function load() {
    const response = await fetch(endpoint, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw Error("Skills could not be loaded.");
    setSkills(data.skills);
    setReviewer(data.canReview);
  }
  useEffect(() => {
    setSkills([]);
    setReviewer(false);
    setLoading(true);
    setError("");
    let active = true;
    fetch(endpoint, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw Error("Skills could not be loaded.");
        return response.json();
      })
      .then((data) => {
        if (active) {
          setSkills(data.skills);
          setReviewer(data.canReview);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [endpoint]);
  async function update(skill) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: skill.status === "draft" ? "activate" : "retire",
          id: skill.id,
          contentSha256: skill.content_sha256,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Skill update failed.");
      if (skill.status === "active")
        onSelection(selected.filter((id) => id !== skill.id));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="vp-source-panel" aria-label="Project skills">
      <summary>Project skills · {selected.length} selected</summary>
      <div className="ctl-toolbar">
        <a href={`/skills?project=${projectId}`}>
          {canEdit ? "Manage versions & parameters" : "View skills"}
        </a>
        <small>Select up to three active skills.</small>
      </div>
      {error && <p role="alert">{error}</p>}
      {loading && <div className="ctl-skeleton" aria-label="Loading skills" />}
      <ul className="vp-source-list">
        {skills.map((skill) => (
          <li key={skill.id}>
            <div>
              <label>
                {skill.status === "active" && (
                  <input
                    type="checkbox"
                    checked={selected.includes(skill.id)}
                    disabled={
                      !canEdit ||
                      busy ||
                      (!selected.includes(skill.id) && selected.length >= 3)
                    }
                    onChange={(event) =>
                      onSelection(
                        event.target.checked
                          ? [...selected, skill.id]
                          : selected.filter((id) => id !== skill.id),
                      )
                    }
                  />
                )}{" "}
                {skill.name} · v{skill.version || 1} · {skill.status}
              </label>
              {selected.includes(skill.id) && (
                <SkillParameters
                  skill={skill}
                  values={parameters[skill.id]}
                  onChange={(values) =>
                    onParameters({ ...parameters, [skill.id]: values })
                  }
                  disabled={!canEdit || busy}
                />
              )}
              <details>
                <summary>Review instructions</summary>
                <pre style={{ whiteSpace: "pre-wrap" }}>
                  {skill.instructions}
                </pre>
              </details>
            </div>
            {reviewer && skill.status !== "retired" && (
              <button
                type="button"
                className="vp-button"
                disabled={busy}
                onClick={() => update(skill)}
              >
                {skill.status === "draft" ? "Activate reviewed text" : "Retire"}
              </button>
            )}
          </li>
        ))}
      </ul>
      {!loading && !skills.length && <p>No project skills yet.</p>}
    </details>
  );
}
