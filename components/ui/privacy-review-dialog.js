"use client";
import { useEffect, useId, useRef, useState } from "react";
import { ShieldCheck, X } from "lucide-react";
import { createPrivacySender } from "../../lib/privacy-send-controller.mjs";
import { previewSegments } from "../../lib/privacy-preview.mjs";
const LABELS = {
  PERSON: "Name",
  USERNAME: "Benutzername",
  EMAIL: "E-Mail",
  PASSWORD: "Passwort",
  API_KEY: "API-Key",
  TOKEN: "Token",
  PRIVATE_KEY: "Privater Schlüssel",
  ADDRESS: "Adresse",
  PHONE: "Telefon",
  ACCOUNT: "Konto",
  PRIVATE_IP: "IP-Adresse",
  ORGANIZATION: "Organisation",
};
export function usePrivacySend(scopeKey) {
  const [review, setReview] = useState(null),
    [selected, setSelected] = useState([]),
    [status, setStatus] = useState({ phase: "idle" });
  const titleId = useId(),
    panel = useRef(null),
    returnFocus = useRef(null),
    resolve = useRef(null),
    sender = useRef(null),
    currentScope = useRef(scopeKey),
    original = useRef("");
  currentScope.current = scopeKey;
  if (!sender.current)
    sender.current = createPrivacySender({
      onState: (value) => {
        setStatus(value);
        if (value.phase !== "review") setReview(null);
      },
      requestChoice: (value) =>
        new Promise((done) => {
          resolve.current = done;
          setSelected(
            [...value.findings, ...(value.contextFindings || [])].map(
              (f) => f.placeholder,
            ),
          );
          setReview(value);
        }),
    });
  function finish(choice) {
    const done = resolve.current;
    resolve.current = null;
    done?.(choice);
  }
  useEffect(
    () => () => {
      finish(null);
      sender.current.cancel();
    },
    [scopeKey],
  );
  useEffect(() => {
    if (!review) return;
    returnFocus.current = document.activeElement;
    panel.current?.focus({ preventScroll: true });
    return () => {
      if (returnFocus.current?.isConnected)
        returnFocus.current.focus({ preventScroll: true });
    };
  }, [review]);
  function privacySend(url, body, options = {}) {
    original.current = String(body.message || "").trim();
    const scope = scopeKey;
    return sender.current.send(url, body, {
      ...options,
      isCurrent: () => currentScope.current === scope,
    });
  }
  const findings = review
    ? [...review.findings, ...(review.contextFindings || [])]
    : [];
  const segments = review
    ? previewSegments(original.current, review.ranges, selected)
    : [];
  const privacyDialog = review ? (
    <section
      className="privacy-drawer"
      ref={panel}
      role="region"
      tabIndex={-1}
      aria-labelledby={titleId}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          finish(null);
        }
      }}
    >
      <header>
        <div>
          <ShieldCheck size={18} aria-hidden="true" />
          <h2 id={titleId}>Vor dem Versand schützen</h2>
        </div>
        <button
          type="button"
          className="privacy-close"
          aria-label="Datenschutzprüfung abbrechen"
          onClick={() => finish(null)}
        >
          <X size={18} />
        </button>
      </header>
      {review.scanStatus === "unavailable" && (
        <p className="privacy-warning" role="alert">
          Erweiterte Erkennung nicht verfügbar. Die Vorschau verwendet Regeln.
        </p>
      )}
      {review.uninspectable && (
        <p className="privacy-warning">
          Bilder können nicht maskiert werden. Entferne sie oder sende das
          Original.
        </p>
      )}
      <div className="privacy-select">
        <span>{findings.length} Fundstellen</span>
        <button
          type="button"
          onClick={() => setSelected(findings.map((f) => f.placeholder))}
        >
          Alle
        </button>
        <button type="button" onClick={() => setSelected([])}>
          Keine
        </button>
      </div>
      <ul className="privacy-list">
        {findings.map((f) => (
          <li key={f.placeholder}>
            <label>
              <input
                type="checkbox"
                checked={selected.includes(f.placeholder)}
                onChange={(e) =>
                  setSelected((old) =>
                    e.target.checked
                      ? [...old, f.placeholder]
                      : old.filter((id) => id !== f.placeholder),
                  )
                }
              />
              <span className="privacy-type">{LABELS[f.type] || "Angabe"}</span>
              <code>
                {f.type === "EMAIL"
                  ? f.displayValue.replace(/^(.{1,2})[^@]*@/, "$1…@")
                  : f.displayValue}
              </code>
              {!review.findings.includes(f) && <small>Kontext</small>}
            </label>
          </li>
        ))}
      </ul>
      <div className="privacy-preview">
        <span className="privacy-caption">
          So wird deine Nachricht gesendet
        </span>
        <pre>
          {segments.length
            ? segments.map((segment, index) =>
                segment.masked ? (
                  <mark key={index}>{segment.text}</mark>
                ) : (
                  segment.text
                ),
              )
            : review.preview}
        </pre>
      </div>
      <footer>
        <button type="button" onClick={() => finish(null)}>
          Abbrechen
        </button>
        <button type="button" onClick={() => finish("original")}>
          Original senden
        </button>
        <button
          type="button"
          className="privacy-primary"
          disabled={!review.canReplace}
          onClick={() => finish({ decision: "replace", replaceIds: selected })}
        >
          Maskieren & senden <span>({selected.length})</span>
        </button>
      </footer>
      <p className="privacy-note">
        Nicht ausgewählte Angaben bleiben im Original. Antworten werden lokal
        wieder aufgelöst. Regeln können Angaben übersehen.
      </p>
    </section>
  ) : status.phase !== "idle" ? (
    <div className="privacy-pending" role="status">
      <span className="privacy-pending-line" aria-hidden="true" />
      {status.phase === "checking" ? "Angaben prüfen…" : "Anfrage senden…"}
    </div>
  ) : null;
  return { privacySend, privacyDialog };
}
