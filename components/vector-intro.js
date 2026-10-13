"use client";

import {
  useEffect,
  useRef,
  useState
} from "react";

import {
  isCinematicMuted,
  setCinematicMuted,
  playCinematicWelcome
} from "./ui/vector-cinematic-audio";

import VectorCelestialField from "./ui/vector-celestial-field";

function greetingForNow() {
  const hour = new Date().getHours();

  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function VectorIntro({
  displayName
}) {
  const [phase, setPhase] = useState("idle");
  const [greeting, setGreeting] = useState("Welcome");
  const [muted, setMuted] = useState(true);

  const activeTimers = useRef([]);
  const name = displayName || "there";

  useEffect(() => {
    const pending =
      sessionStorage.getItem("vector:intro:pending") === "1";

    const sessionKey =
      `vector:intro:v584h3:${name}`;

    if (
      !pending &&
      sessionStorage.getItem(sessionKey) === "1"
    ) {
      return;
    }

    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    sessionStorage.removeItem("vector:intro:pending");

    document.documentElement.classList.remove(
      "vector-warp-active"
    );

    document.documentElement.classList.remove(
      "vector-gravity-black",
      "vector-gravity-active"
    );


    setMuted(isCinematicMuted());
    setGreeting(greetingForNow());
    setPhase("black");

    const timers = [];
    activeTimers.current = timers;

    const at = (fn, ms) => {
      timers.push(window.setTimeout(fn, ms));
    };

    if (reduced) {
      at(() => setPhase("welcome"), 80);

      at(() => {
        setPhase("idle");
        sessionStorage.setItem(sessionKey, "1");
      }, 1600);
    } else {
      at(() => {
        setPhase("welcome");
        playCinematicWelcome();
      }, 850);

      at(() => setPhase("leaving"), 4400);

      at(() => {
        setPhase("idle");
        sessionStorage.setItem(sessionKey, "1");
      }, 5050);
    }

    return () => {
      timers.forEach(window.clearTimeout);
    };
  }, [name]);

  if (phase === "idle") {
    return null;
  }

  function skip() {
    activeTimers.current.forEach(window.clearTimeout);

    sessionStorage.setItem(
      `vector:intro:v584h3:${name}`,
      "1"
    );

    setPhase("idle");
  }

  function toggleSound() {
    const next = !muted;

    setMuted(next);
    setCinematicMuted(next);
  }

  return (
    <div
      className={`vector-h3-intro vector-h3-${phase}`}
      role="dialog"
      aria-label="Vector welcome"
    >
      <VectorCelestialField intro />
      <div
        className="vector-h3-singularity"
        aria-hidden="true"
      />

      <div className="vector-h3-identity">
        <div className="vector-logo vector-h4-intro-brand" aria-label="Vector">
  <div className="vector-mark canonical-vector-mark" aria-hidden="true">&lt;</div>
  <div className="vector-wordmark">Vector</div>
</div>

        <h1>
          {greeting},{" "}
          <strong>{name}.</strong>
        </h1>
      </div>

      <div className="vector-h3-controls">
        <button
          type="button"
          onClick={toggleSound}
          aria-label={muted ? "Enable sound" : "Mute sound"}
        >
          {muted ? "Sound off" : "Sound on"}
        </button>

        <button
          type="button"
          onClick={skip}
          aria-label="Skip intro"
        >
          Skip
        </button>
      </div>
    </div>
  );
}
