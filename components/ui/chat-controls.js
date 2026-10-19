"use client";
import {createPortal} from 'react-dom';
import {chatMenuPosition} from '../../lib/chat-menu-position.mjs';
import {useEffect,useId,useRef,useState} from 'react';
import {ChevronDown,Check,ShieldCheck,ShieldOff} from 'lucide-react';
import {CHAT_MODES} from '../../lib/chat-controls.mjs';

export default function ChatControls({mode,onModeChange,privacyEnabled,onPrivacyChange,disabled=false}) {
  const [open,setOpen]=useState(false);
  const [position,setPosition]=useState(null);
  const root=useRef(null);const trigger=useRef(null);const menu=useRef(null);const id=useId();
  const selected=CHAT_MODES.find(option=>option.value===mode) || CHAT_MODES[0];
  const place=()=>{if(trigger.current)setPosition(chatMenuPosition(trigger.current.getBoundingClientRect(),{width:window.innerWidth,height:window.innerHeight},menu.current?.scrollHeight || 250));};
  useEffect(()=>{
    if(!open)return;
    const outside=event=>{if(!root.current?.contains(event.target)&&!menu.current?.contains(event.target))setOpen(false);};
    document.addEventListener('pointerdown',outside);place();
    menu.current?.querySelector('[aria-checked="true"]')?.focus();
    window.addEventListener('resize',place);document.addEventListener('scroll',place,true);
    return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',place);document.removeEventListener('scroll',place,true);};
  },[open]);
  const close=()=>{setOpen(false);trigger.current?.focus();};
  const Shield=privacyEnabled?ShieldCheck:ShieldOff;
  return <div className="vector-chat-controls" ref={root}>
    <button type="button" className="vector-privacy-switch" role="switch" aria-checked={privacyEnabled}
      aria-label="Datenschutzprüfung" disabled={disabled} onClick={()=>onPrivacyChange(!privacyEnabled)}
      title={privacyEnabled?'Nachricht und Kontext prüfen; neue Tool-Daten mit Platzhaltern schützen':'Datenschutzprüfung aus: Angaben werden unverändert gesendet'}>
      <Shield size={15} aria-hidden="true"/><span>Datenschutz {privacyEnabled?'an':'aus'}</span>
    </button>
    {privacyEnabled && <span className="vector-tool-privacy-note">Neue Tool-Daten werden geschützt.</span>}
    <div className="vector-mode-picker">
      <button type="button" ref={trigger} disabled={disabled} aria-haspopup="menu" aria-expanded={open}
        aria-controls={open?id:undefined} onClick={()=>{place();setOpen(!open);}} aria-label={`Chatmodus: ${selected.label}`}>
        {selected.label}<ChevronDown size={13} aria-hidden="true"/>
      </button>
      {open && position && createPortal(<div style={position} ref={menu} id={id} className="vector-mode-menu" role="menu" aria-label="Chatmodus"
        onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget)&&event.relatedTarget!==trigger.current)setOpen(false);}}
        onKeyDown={event=>{
          if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();}
          if(event.key==='Tab'){setOpen(false);trigger.current?.focus();}
          const buttons=[...menu.current.querySelectorAll('button')];
          const index=buttons.indexOf(document.activeElement);
          if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
            event.preventDefault();
            const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:
              (index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;
            buttons[next].focus();
          }
        }}>
        {CHAT_MODES.map(option=><button type="button" key={option.value} role="menuitemradio"
          aria-checked={mode===option.value} tabIndex={mode===option.value?0:-1}
          onClick={()=>{onModeChange(option.value);close();}}>
          <span>{option.label}</span>{mode===option.value&&<Check size={14} aria-hidden="true"/>}
        </button>)}
      </div>,document.body)}
    </div>
    <style>{`
      .vector-chat-controls{display:flex;align-items:center;gap:8px;position:relative;flex-wrap:wrap}
      .vector-chat-controls button,.vector-mode-menu button{display:flex;align-items:center;justify-content:center;gap:6px;width:auto;min-height:30px;padding:5px 9px;border:1px solid #ffffff20;border-radius:8px;background:#131a1b;color:#c5d9cd;font:inherit;font-size:12px;cursor:pointer}
      .vector-chat-controls button:focus-visible,.vector-mode-menu button:focus-visible{outline:2px solid #8de0b7;outline-offset:2px}.vector-chat-controls button:disabled{opacity:.5;cursor:default}
      .vector-privacy-switch[aria-checked=true]{color:#8de0b7}.vector-privacy-switch[aria-checked=false]{color:#e5c48a;border-color:#e5c48a55}
      .vector-tool-privacy-note{font-size:11px;color:#9eb5ad}.vector-mode-picker{position:relative}.vector-mode-menu{position:fixed;box-sizing:border-box;overflow:auto;z-index:1000;padding:5px;border:1px solid #8de0b740;border-radius:10px;background:#131a1b;box-shadow:0 8px 24px #0005}
      .vector-mode-menu button{width:100%;justify-content:space-between;border:0;background:transparent;padding:8px 9px}
      .vector-mode-menu button:hover,.vector-mode-menu button[aria-checked=true]{background:#8de0b714;color:#f0f7f3}
      @media(max-width:480px){.vector-chat-controls{gap:4px}.vector-chat-controls button,.vector-mode-menu button{padding:5px 7px;font-size:11px}}
    `}</style>
  </div>;
}
