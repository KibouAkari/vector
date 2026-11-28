"use client";
import { useId, useState } from "react";
import {
  SlidersHorizontal,
  ShieldOff,
  BrainCircuit,
  ShieldCheck,
  Leaf,
  BookOpen,
} from "lucide-react";
import { Popover, PopoverPanel } from "../ui/overlays";
import ChatSkills from "../ui/chat-skills";
function Setting({ label, hint, checked, onChange, disabled, icon: Icon }) {
  const id = useId();
  return (
    <div className="vc-setting">
      <Icon size={16} aria-hidden="true" />
      <label htmlFor={id}>
        <strong>{label}</strong>
        <small>{hint}</small>
      </label>
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
      />
    </div>
  );
}
export default function ConversationSettings({
  privacyEnabled,
  onPrivacyChange,
  brainEnabled,
  onBrainChange,
  freeOnly,
  onFreeOnlyChange,
  selectedSkills,
  onSkillsChange,
  parameters,
  onParameters,
  disabled,
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className={
            "vc-icon-button vc-settings-trigger" +
            (!privacyEnabled ? " is-warning" : "")
          }
          aria-label={
            privacyEnabled
              ? "Conversation settings"
              : "Conversation settings, privacy review is off"
          }
          title="Conversation settings"
        >
          <SlidersHorizontal size={17} />
          {!privacyEnabled && <i />}
        </button>
      </Popover.Trigger>
      <PopoverPanel label="Conversation settings" className="vc-settings-panel">
        <h2>Conversation settings</h2>
        <Setting
          icon={privacyEnabled ? ShieldCheck : ShieldOff}
          label="Privacy review"
          hint={
            privacyEnabled
              ? "Review sensitive details before sending."
              : "Messages are sent without privacy masking."
          }
          checked={privacyEnabled}
          onChange={onPrivacyChange}
          disabled={disabled}
        />
        <Setting
          icon={BrainCircuit}
          label="Brain"
          hint="Include relevant saved memories."
          checked={brainEnabled}
          onChange={onBrainChange}
          disabled={disabled}
        />
        <Setting
          icon={Leaf}
          label="Free inference only"
          hint="Use eligible local or free models. Tool services may charge separately."
          checked={freeOnly}
          onChange={onFreeOnlyChange}
          disabled={disabled}
        />
        <details className="vc-context-section">
          <summary>
            <BookOpen size={16} />
            <span>Skills</span>
            <small>
              {selectedSkills.length
                ? `${selectedSkills.length} selected`
                : "None selected"}
            </small>
          </summary>
          <ChatSkills
            inline
            selected={selectedSkills}
            onSelection={onSkillsChange}
            parameters={parameters}
            onParameters={onParameters}
            disabled={disabled}
          />
        </details>
      </PopoverPanel>
    </Popover.Root>
  );
}
