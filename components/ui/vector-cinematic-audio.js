"use client";

let audio = null;
let master = null;

function muted() {
  try {
    return window.sessionStorage.getItem(
      "vector:cinematic:mute"
    ) === "1";
  } catch {
    return true;
  }
}

export function isCinematicMuted() {
  return typeof window !== "undefined"
    ? muted()
    : true;
}

export function setCinematicMuted(flag) {
  if (typeof window === "undefined") return;

  try {
    sessionStorage.setItem(
      "vector:cinematic:mute",
      flag ? "1" : "0"
    );
  } catch {}

  if (audio && master) {
    master.gain.setTargetAtTime(
      flag ? 0 : 0.55,
      audio.currentTime,
      0.05
    );
  }
}

export async function primeCinematicAudio() {
  if (typeof window === "undefined") return;

  const Type =
    window.AudioContext || window.webkitAudioContext;

  if (!Type) return;

  try {
    if (!audio) {
      audio = new Type();

      master = audio.createGain();
      master.gain.value = muted() ? 0 : 0.55;

      master.connect(audio.destination);
    }

    if (audio.state === "suspended") {
      await audio.resume();
    }
  } catch {}
}

function tone(
  freq,
  end,
  duration,
  gainValue,
  when = 0,
  kind = "sine"
) {
  if (!audio || !master || muted()) return;

  const t = audio.currentTime + when;

  const osc = audio.createOscillator();
  const gain = audio.createGain();

  osc.type = kind;

  osc.frequency.setValueAtTime(freq, t);

  osc.frequency.exponentialRampToValueAtTime(
    Math.max(20, end),
    t + duration
  );

  gain.gain.setValueAtTime(0.0001, t);

  gain.gain.exponentialRampToValueAtTime(
    gainValue,
    t + 0.17
  );

  gain.gain.exponentialRampToValueAtTime(
    0.0001,
    t + duration
  );

  osc.connect(gain).connect(master);

  osc.start(t);
  osc.stop(t + duration + 0.02);
}

export function playCinematicWarp() {
  tone(64, 26, 2.75, 0.15);
  tone(180, 35, 2.5, 0.045, 0.15, "triangle");
  tone(95, 32, 2.3, 0.035, 0.3, "sawtooth");
}

export function playCinematicWelcome() {
  tone(220, 220, 2.7, 0.036, 0);
  tone(330, 330, 2.8, 0.022, 0.18);
  tone(440, 440, 2.6, 0.018, 0.48);
}
