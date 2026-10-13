"use client";


import {
  useEffect,
  useState
} from "react";


import {
  Volume2,
  VolumeX
} from "lucide-react";


import VectorIconButton
  from "./vector-icon-button";


import {
  playVectorSound,
  setVectorSoundEnabled,
  vectorSoundEnabled
} from "./vector-sound";


export default function VectorSoundButton() {
  const [
    enabled,
    setEnabled
  ] =
    useState(
      true
    );


  useEffect(
    () => {
      setEnabled(
        vectorSoundEnabled()
      );


      function changed(
        event
      ) {
        setEnabled(
          Boolean(
            event.detail
              ?.enabled
          )
        );
      }


      window.addEventListener(
        "vector-sound-change",
        changed
      );


      return () =>
        window.removeEventListener(
          "vector-sound-change",
          changed
        );
    },
    []
  );


  async function toggle() {
    const next =
      !enabled;


    setVectorSoundEnabled(
      next
    );


    setEnabled(
      next
    );


    if (
      next
    ) {
      await playVectorSound(
        "enable"
      );
    }
  }


  const Icon =
    enabled
      ? Volume2
      : VolumeX;


  return (
    <VectorIconButton
      className="vx-sound-toggle"
      label={
        enabled
          ? "Mute sounds"
          : "Enable sounds"
      }
      onClick={
        toggle
      }
    >
      <Icon
        aria-hidden="true"
      />
    </VectorIconButton>
  );
}
