"use client";
import { useEffect, useState } from "react";
import SkillParameters from "./skill-parameters";
export default function ChatSkills({
  selected,
  onSelection,
  parameters = {},
  onParameters = () => {},
  disabled,
  inline = false,
}) {
  const [skills, setSkills] = useState([]),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    fetch("/api/skills", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw Error("Skills unavailable");
        return response.json();
      })
      .then((data) => {
        if (active) setSkills(data.skills.filter((s) => s.status === "active"));
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  const list = (
    <div className={inline ? "vc-skills-list" : "chat-skill-menu"}>
      {error && <p role="alert">{error}</p>}
      {skills.length ? (
        skills.map((skill) => (
          <div key={skill.id}>
            <label>
              <input
                type="checkbox"
                disabled={
                  disabled ||
                  (!selected.includes(skill.id) && selected.length >= 3)
                }
                checked={selected.includes(skill.id)}
                onChange={(e) =>
                  onSelection(
                    e.target.checked
                      ? [...selected, skill.id]
                      : selected.filter((id) => id !== skill.id),
                  )
                }
              />
              {skill.name}
              <small>v{skill.version || 1}</small>
            </label>
            {selected.includes(skill.id) && (
              <SkillParameters
                skill={skill}
                values={parameters[skill.id]}
                onChange={(values) =>
                  onParameters({ ...parameters, [skill.id]: values })
                }
                disabled={disabled}
              />
            )}
          </div>
        ))
      ) : (
        <p>No active chat skills.</p>
      )}
      <a href="/skills">Manage skills →</a>
    </div>
  );
  return inline ? (
    list
  ) : (
    <details className="chat-skill-picker">
      <summary>Skills{selected.length ? ` (${selected.length})` : ""}</summary>
      {list}
    </details>
  );
}
