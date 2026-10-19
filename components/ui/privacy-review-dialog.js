"use client";
import {useEffect, useId, useRef, useState} from 'react';
import {createPrivacySender} from '../../lib/privacy-send-controller.mjs';

const LABELS = {PERSON:'Name',USERNAME:'Benutzername',EMAIL:'E-Mail',PASSWORD:'Passwort',API_KEY:'API-Schlüssel',
  TOKEN:'Zugangstoken',PRIVATE_KEY:'Privater Schlüssel',ADDRESS:'Adresse',PHONE:'Telefonnummer',
  ACCOUNT:'Konto',PRIVATE_IP:'Interne IP-Adresse',ORGANIZATION:'Organisation'};

function readablePreview(review) {
  const names=new Map();const counts={};
  for(const f of [...review.findings,...(review.contextFindings || [])]) {
    counts[f.type]=(counts[f.type] || 0)+1;
    names.set(f.placeholder,`[${LABELS[f.type] || 'Angabe'} ${counts[f.type]}]`);
  }
  return review.preview.replace(/<VEC_[A-Z_]+_[a-f0-9]{32}>|<[A-Z0-9_]+_[A-F0-9]{6}>/g,
    token=>names.get(token) || '[Geschützte Angabe]');
}

export function usePrivacySend(scopeKey) {
  const [review,setReview]=useState(null);
  const [status,setStatus]=useState({phase:'idle'});
  const [elapsed,setElapsed]=useState(0);
  const titleId=useId();const panelRef=useRef(null);const inputRef=useRef(null);
  const resolveRef=useRef(null);const senderRef=useRef(null);
  const scopeRef=useRef(scopeKey);scopeRef.current=scopeKey;
  if(!senderRef.current)senderRef.current=createPrivacySender({
    onState:value=>{setStatus(value);if(value.phase!=='review')setReview(null);},
    requestChoice:value=>new Promise(resolve=>{resolveRef.current=resolve;setReview(value);})
  });
  const finish=choice=>{const resolve=resolveRef.current;resolveRef.current=null;resolve?.(choice);};
  useEffect(()=>()=>{finish(null);senderRef.current.cancel();},[scopeKey]);
  useEffect(()=>{
    if(review){
      inputRef.current=panelRef.current?.closest('form')?.querySelector('textarea');
      panelRef.current?.focus({preventScroll:true});
    }else if(inputRef.current?.isConnected){
      inputRef.current.focus({preventScroll:true});inputRef.current=null;
    }
  },[review]);
  useEffect(()=>{
    if(!['checking','sending'].includes(status.phase))return;
    const update=()=>setElapsed(Math.max(0,Math.floor((Date.now()-status.startedAt)/1000)));
    update();const timer=setInterval(update,250);return()=>clearInterval(timer);
  },[status]);

  function privacySend(url,body,options={}){
    const scope=scopeKey;
    return senderRef.current.send(url,body,{...options,isCurrent:()=>scopeRef.current===scope});
  }
  const list=findings=><ul className="vector-privacy-findings">{findings.map(f=><li key={f.placeholder}>
    <span>{LABELS[f.type] || 'Angabe'}</span><code>{f.displayValue}</code>
  </li>)}</ul>;
  const privacyDialog=status.phase==='idle'?null:<div className="vector-privacy-anchor">
    {review ? <section ref={panelRef} className="vector-privacy-panel" role="region" tabIndex={-1}
      aria-labelledby={titleId} onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();finish(null);}}}>
      <h2 id={titleId}>Vertrauliche Angaben erkannt</h2>
      {review.findings.length>0?list(review.findings):<p>Weitere Angaben befinden sich im mitgesendeten Kontext.</p>}
      {review.contextFindings?.length>0 && <details><summary>Weitere Angaben im Kontext ({review.contextFindings.length})</summary>
        {list(review.contextFindings)}</details>}
      {review.uninspectable && <p className="vector-privacy-caution">Bilder können hier nicht anonymisiert werden. Entferne sie oder bestätige den unveränderten Versand.</p>}
      <details><summary>Vorschau dieser Nachricht</summary><pre>{readablePreview(review)}</pre></details>
      <div className="vector-privacy-actions">
        <button type="button" onClick={()=>finish(null)}>Abbrechen</button>
        <button type="button" onClick={()=>finish('original')}>Nachricht original senden</button>
        <button type="button" className="vector-privacy-primary" disabled={!review.canReplace}
          onClick={()=>finish('replace')}>Platzhalter verwenden</button>
      </div>
      <p className="vector-privacy-hint">Die Originalfreigabe gilt für diese Nachricht und den geprüften Kontext. Neue Tool-Daten werden mit Platzhaltern geschützt und in der Antwort lokal wieder eingesetzt. Die Erkennung kann Angaben übersehen.</p>
    </section>:<div className="vector-privacy-status" role="status" aria-live="polite">
      <span className="vector-privacy-spinner" aria-hidden="true" />
      <span>{status.phase==='checking'?'Vector überprüft die Anfrage':'Vector sendet deine Anfrage'}</span>
      <span className="vector-privacy-time" aria-hidden="true">{elapsed} s</span>
    </div>}
    <style>{`
      .vector-privacy-anchor{position:relative;flex:1 1 100%;min-width:0;width:100%;max-width:900px;margin:0 auto 8px;color:#f0f7f3}
      .project-chat-composer > .vector-privacy-anchor{display:block;border:0;background:none;padding:0;min-height:0;border-radius:0}
      .vector-privacy-panel{box-sizing:border-box;background:#131a1b;border:1px solid #8de0b75c;border-radius:12px;padding:14px 16px;max-height:min(340px,44dvh);overflow:auto;box-shadow:0 8px 24px #0003;outline:none}
      .vector-privacy-panel:focus-visible{outline:2px solid #8de0b7;outline-offset:2px}
      .vector-privacy-panel h2{font-size:15px;font-weight:600;line-height:1.4;margin:0 0 8px}.vector-privacy-panel p{font-size:12px;color:#9eb5ad;margin:8px 0;line-height:1.45}
      .vector-privacy-findings{display:flex;flex-wrap:wrap;gap:6px;list-style:none;padding:0;margin:8px 0 10px;max-height:110px;overflow:auto}
      .vector-privacy-findings li{display:flex;gap:7px;align-items:baseline;border:1px solid #ffffff18;border-radius:7px;padding:5px 8px;min-width:0;font-size:12px}.vector-privacy-findings span{font-size:12px;color:#9eb5ad;white-space:nowrap}.vector-privacy-findings code{overflow-wrap:anywhere;color:#f0f7f3;max-width:260px;white-space:pre-wrap}
      .vector-privacy-panel details{font-size:12px;border-top:1px solid #ffffff12;padding:7px 0}.vector-privacy-panel summary{cursor:pointer;color:#b9cbc2}.vector-privacy-panel pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:12px;line-height:1.5;max-height:140px;overflow:auto;margin:8px 0 0}
      .vector-privacy-panel .vector-privacy-hint{font-size:11px;margin:8px 0 0;color:#9eb5ad}.vector-privacy-panel .vector-privacy-caution{color:#e5c48a}
      .vector-privacy-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.vector-privacy-anchor .vector-privacy-actions button{width:auto;height:auto;font-weight:500;background:transparent;border:1px solid #ffffff25;border-radius:7px;padding:8px 10px;color:#f0f7f3;font:inherit;font-size:12px;cursor:pointer}.vector-privacy-actions button:focus-visible{outline:2px solid #8de0b7;outline-offset:2px}.vector-privacy-actions .vector-privacy-primary{background:#8de0b7;color:#0a0d11;border-color:#8de0b7}.vector-privacy-actions button:disabled{opacity:.4;cursor:not-allowed}
      .vector-privacy-status{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid #8de0b733;border-radius:10px;background:#131a1b;font-size:12px;color:#c5d9cd}
      .vector-privacy-spinner{width:12px;height:12px;border:2px solid #8de0b72b;border-top-color:#8de0b7;border-radius:50%;animation:vector-privacy-spin .9s linear infinite}.vector-privacy-anchor .vector-privacy-status>span{font-size:12px;color:#c5d9cd}.vector-privacy-anchor .vector-privacy-time{margin-left:auto;font-variant-numeric:tabular-nums;color:#9eb5ad;white-space:nowrap}
      @keyframes vector-privacy-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.vector-privacy-spinner{animation:none;border-color:#8de0b7}}
      @media(max-width:480px){.vector-privacy-panel{padding:12px}.vector-privacy-actions button{flex:1 1 auto}.vector-privacy-findings code{max-width:190px}}
    `}</style>
  </div>;
  return {privacySend,privacyDialog};
}
