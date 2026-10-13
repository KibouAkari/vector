"use client";

export default function EventHorizon({
  mode = "login",
  reduced = false
}) {
  return (
    <div
      className={`vector-event-horizon vector-event-horizon--${mode}`}
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        background: "#000",
        pointerEvents: "none"
      }}
    >
      {!reduced && (
        <iframe
          title="Vector Event Horizon"
          src="/vector-gargantua/index.html"
          loading="eager"
          tabIndex={-1}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          style={{
            display: "block",
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            border: 0,
            pointerEvents: "none"
          }}
        />
      )}
    </div>
  );
}
