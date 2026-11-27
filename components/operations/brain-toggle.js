"use client";
import { BrainCircuit } from "lucide-react";
export default function BrainToggle({ enabled, onChange, disabled }) {
  return (
    <button
      type="button"
      className="op-brain-toggle"
      aria-pressed={enabled}
      title={
        enabled
          ? "Relevant saved memories are included before privacy review"
          : "Saved memory is off for this conversation"
      }
      disabled={disabled}
      onClick={() => onChange(!enabled)}
    >
      <BrainCircuit size={15} />
      <span>Brain</span>
      <i />
    </button>
  );
}
