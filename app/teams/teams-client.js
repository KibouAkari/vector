"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Workflow, Check, ArrowUpRight } from "lucide-react";
import { SPECIALISTS } from "../../lib/teams/policy.mjs";
import { usePrivacySend } from "../../components/ui/privacy-review-dialog";
import {
  Page,
  Panel,
  Empty,
  Status,
} from "../../components/operations/primitives";
export default function Teams({ canRun }) {
  const router = useRouter(),
    [projects, setProjects] = useState([]),
    [project, setProject] = useState(""),
    [roles, setRoles] = useState(["research", "data"]),
    [calls, setCalls] = useState(6),
    [task, setTask] = useState(""),
    [steps, setSteps] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [freeOnly, setFreeOnly] = useState(false);
  const { privacySend, privacyDialog } = usePrivacySend("team:" + project);
  useEffect(() => {
    fetch("/api/projects")
      .then((response) => response.json())
      .then((data) => {
        setProjects(data.projects || []);
        setProject(data.projects?.[0]?.id || "");
      })
      .catch(() => setError("Projects could not be loaded."));
    const load = () =>
      fetch("/api/teams", { cache: "no-store" })
        .then((response) => response.json())
        .then((data) => setSteps(data.steps || []))
        .catch(() => {});
    load();
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, 10000);
    return () => clearInterval(timer);
  }, []);
  async function start(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await privacySend(`/api/projects/${project}/chat`, {
        message: task,
        mode: "normal",
        billingPolicy: freeOnly ? "free-only" : "standard",
        team: { roles, maxCalls: calls },
        requestId: crypto.randomUUID(),
      });
      if (!response) return;
      const data = await response.json();
      if (data.privacyCancelled) return;
      if (!response.ok) throw Error(data.error || "Team could not be started.");
      router.push("/projects/" + project);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Page
      title="Agent teams"
      eyebrow="Workspace"
      description="Bring in specialists when the task needs them."
    >
      {privacyDialog}
      {error && (
        <p role="alert" className="op-error">
          {error}
        </p>
      )}
      <div className="op-split">
        <Panel
          title="Build a team"
          subtitle="Up to three specialists, one worker and a quality review"
        >
          <form className="op-form" onSubmit={start}>
            <label>
              Project
              <select
                required
                value={project}
                onChange={(event) => setProject(event.target.value)}
              >
                <option value="">Choose project</option>
                {projects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Task
              <textarea
                required
                maxLength={12000}
                value={task}
                onChange={(event) => setTask(event.target.value)}
                placeholder="Describe the outcome, evidence and constraints…"
              />
            </label>
            <fieldset className="op-role-grid">
              <legend>Specialists</legend>
              {Object.entries(SPECIALISTS).map(([role, description]) => (
                <label
                  key={role}
                  title={description}
                  className={roles.includes(role) ? "selected" : ""}
                >
                  <input
                    type="checkbox"
                    checked={roles.includes(role)}
                    disabled={!roles.includes(role) && roles.length >= 3}
                    onChange={(event) => {
                      const next = event.target.checked
                        ? [...roles, role]
                        : roles.filter((value) => value !== role);
                      setRoles(next);
                      setCalls(Math.max(next.length + 3, calls));
                    }}
                  />
                  <span>{role}</span>
                  <Check size={12} />
                </label>
              ))}
            </fieldset>
            <label>
              Shared request limit <strong>{calls} provider calls</strong>
              <input
                type="range"
                min={Math.max(4, roles.length + 3)}
                max={8}
                value={calls}
                onChange={(event) => setCalls(Number(event.target.value))}
              />
            </label>
            <label className="op-toggle">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(event) => setFreeOnly(event.target.checked)}
              />
              Free inference only, with no paid fallback
            </label>
            <p className="op-muted">
              At most two specialists run at once. All roles share the job's
              call limit and existing workspace, user and project budgets.
              Single-agent chat remains the default.
            </p>
            <button
              className="op-button primary"
              disabled={!canRun || busy || !project || !roles.length}
            >
              <Workflow size={15} />
              {busy ? "Preparing…" : "Start team"}
            </button>
          </form>
        </Panel>
        <Panel title="Recent work">
          {steps.length ? (
            <div className="op-team-steps">
              {steps.slice(0, 15).map((step) => (
                <div key={step.job_id + step.role}>
                  <span className="op-square">
                    <Workflow size={15} />
                  </span>
                  <div>
                    <strong>{step.role}</strong>
                    <small>
                      {step.model || "Automatic routing"} · {step.used_calls}/
                      {step.max_calls} shared calls
                    </small>
                  </div>
                  <Status value={step.status} />
                </div>
              ))}
            </div>
          ) : (
            <Empty
              icon={Workflow}
              title="No teams running"
              description="Start a team for a task that benefits from different perspectives."
            />
          )}
        </Panel>
      </div>
    </Page>
  );
}
