"use client";


const STORAGE_KEY =
  "vector:sound:enabled";


let sharedContext =
  null;


function soundEnabled() {
  if (
    typeof window ===
    "undefined"
  ) {
    return false;
  }


  return (
    window.localStorage.getItem(
      STORAGE_KEY
    ) !==
    "0"
  );
}


function context() {
  if (
    typeof window ===
    "undefined"
  ) {
    return null;
  }


  if (
    sharedContext
  ) {
    return sharedContext;
  }


  const AudioContextClass =
    window.AudioContext ||
    window.webkitAudioContext;


  if (
    !AudioContextClass
  ) {
    return null;
  }


  sharedContext =
    new AudioContextClass();


  return sharedContext;
}


export function vectorSoundEnabled() {
  return soundEnabled();
}


export function setVectorSoundEnabled(
  enabled
) {
  if (
    typeof window ===
    "undefined"
  ) {
    return;
  }


  window.localStorage.setItem(
    STORAGE_KEY,
    enabled
      ? "1"
      : "0"
  );


  window.dispatchEvent(
    new CustomEvent(
      "vector-sound-change",
      {
        detail: {
          enabled
        }
      }
    )
  );
}


export async function primeVectorAudio() {
  try {
    const audio =
      context();


    if (
      !audio
    ) {
      return false;
    }


    if (
      audio.state ===
      "suspended"
    ) {
      await audio.resume();
    }


    const oscillator =
      audio.createOscillator();


    const gain =
      audio.createGain();


    gain.gain.value =
      0;


    oscillator.connect(
      gain
    );


    gain.connect(
      audio.destination
    );


    oscillator.start();


    oscillator.stop(
      audio.currentTime +
      .008
    );


    return true;

  } catch {
    return false;
  }
}


function tone({
  frequency,
  start,
  duration,
  volume,
  type = "sine"
}) {
  const audio =
    context();


  if (
    !audio
  ) {
    return;
  }


  const oscillator =
    audio.createOscillator();


  const gain =
    audio.createGain();


  oscillator.type =
    type;


  oscillator.frequency.setValueAtTime(
    frequency,
    start
  );


  gain.gain.setValueAtTime(
    .0001,
    start
  );


  gain.gain.exponentialRampToValueAtTime(
    volume,
    start +
    .018
  );


  gain.gain.exponentialRampToValueAtTime(
    .0001,
    start +
    duration
  );


  oscillator.connect(
    gain
  );


  gain.connect(
    audio.destination
  );


  oscillator.start(
    start
  );


  oscillator.stop(
    start +
    duration +
    .02
  );
}


export async function playVectorSound(
  kind = "soft"
) {
  if (
    !soundEnabled()
  ) {
    return false;
  }


  try {
    const audio =
      context();


    if (
      !audio
    ) {
      return false;
    }


    if (
      audio.state ===
      "suspended"
    ) {
      await audio.resume();
    }


    const now =
      audio.currentTime +
      .015;


    if (
      kind ===
      "intro"
    ) {
      tone({
        frequency:
          392,

        start:
          now,

        duration:
          .34,

        volume:
          .014
      });


      tone({
        frequency:
          523.25,

        start:
          now +
          .11,

        duration:
          .42,

        volume:
          .012
      });


      tone({
        frequency:
          659.25,

        start:
          now +
          .24,

        duration:
          .48,

        volume:
          .009
      });


      return true;
    }


    if (
      kind ===
      "enable"
    ) {
      tone({
        frequency:
          523.25,

        start:
          now,

        duration:
          .13,

        volume:
          .012
      });


      tone({
        frequency:
          659.25,

        start:
          now +
          .055,

        duration:
          .16,

        volume:
          .009
      });


      return true;
    }


    tone({
      frequency:
        470,

      start:
        now,

      duration:
        .09,

      volume:
        .007
    });


    return true;

  } catch {
    return false;
  }
}
