"use client";
import {useEffect, useRef, useState} from 'react';

const LABELS = {PERSON:'Name',EMAIL:'E-Mail',PASSWORD:'Passwort',API_KEY:'API-Schlüssel',
  TOKEN:'Zugangstoken',PRIVATE_KEY:'Privater Schlüssel',ADDRESS:'Adresse',PHONE:'Telefonnummer',
  ACCOUNT:'Kontonummer',PRIVATE_IP:'Interne IP-Adresse',ORGANIZATION:'Organisation'};

export function usePrivacySend(scopeKey) {
  const [review,setReview] = useState(null);
  const resolveRef = useRef(null);
  const scopeRef = useRef(scopeKey);
  scopeRef.current=scopeKey;
  const dialogRef = useRef(null);
  const finish = choice => {
    const resolve = resolveRef.current;
    resolveRef.current = null;
    setReview(null);
    resolve?.(choice);
  };
  useEffect(() => () => {
    resolveRef.current?.(null);
    resolveRef.current = null;
    setReview(null);
  },[scopeKey]);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (review && dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  },[review]);

  async function privacySend(url,body) {
    const sendingScope=scopeKey;
    let response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    // One explicit confirmation per review. A changed/expired review is shown
    // again by a subsequent send rather than silently reusing consent.
    if (response.status !== 409) return response;
    const data = await response.clone().json();
    if (data.error !== 'PRIVACY_REVIEW_REQUIRED') return response;
    if(scopeRef.current!==sendingScope) return {ok:false,json:async()=>({privacyCancelled:true})};
    const choice = await new Promise(resolve => {resolveRef.current=resolve;setReview(data.privacyReview);});
    if (!choice) return {ok:false,json:async()=>({privacyCancelled:true})};
    response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...body,privacyDecision:choice,privacyReviewToken:data.privacyReview.token})});
    return response;
  }

  const privacyDialog = review ? <dialog ref={dialogRef} className="vector-privacy-dialog"
    aria-labelledby="privacy-review-title" aria-describedby="privacy-review-description"
    onCancel={event=>{event.preventDefault();finish(null);}}>
    <div className="vector-privacy-heading"><span aria-hidden="true">◈</span><span>Vor dem externen Versand</span></div>
    <h2 id="privacy-review-title">Vertrauliche Angaben erkannt</h2>
    <p id="privacy-review-description">Vector kann diese Angaben durch eindeutige Platzhalter ersetzen und sie in der Antwort lokal wieder einsetzen. Prüfe die erkannten Stellen.</p>
    <ul className="vector-privacy-findings">{review.findings.map(f=><li key={f.placeholder}>
      <span>{LABELS[f.type] || 'Vertrauliche Angabe'}</span><code>{f.displayValue}</code>
    </li>)}</ul>
    {review.uninspectable && <p className="vector-privacy-caution">Angehängte Bilder wurden nicht auf vertrauliche Angaben geprüft. Entferne sie für einen geschützten Textversand oder bestätige den unveränderten Versand.</p>}
    <details><summary>Vorschau mit Platzhaltern</summary><pre>{review.preview}</pre></details>
    <p className="vector-privacy-hint">Die Erkennung kann Angaben übersehen. Bei Aufgaben, die echte Identitäten benötigen, können Platzhalter das Ergebnis verändern.</p>
    <div className="vector-privacy-actions">
      <button type="button" onClick={()=>finish(null)}>Abbrechen</button>
      <button type="button" onClick={()=>finish('original')}>Unverändert senden</button>
      <button type="button" className="vector-privacy-primary" disabled={!review.canReplace}
        onClick={()=>finish('replace')}>Mit Platzhaltern senden</button>
    </div>
    <style>{`
      .vector-privacy-dialog{color:#f0f7f3;background:#131a1b;border:1px solid #33433f;border-radius:20px;padding:28px;width:min(580px,calc(100vw - 32px));max-height:85dvh;overflow:auto;box-shadow:0 24px 100px #0009}
      .vector-privacy-dialog::backdrop{background:#060b10bb;backdrop-filter:blur(5px)}
      .vector-privacy-heading{color:#8de0b7;display:flex;gap:9px;font-size:12px;letter-spacing:.04em}
      .vector-privacy-dialog h2{font-size:23px;margin:14px 0 10px;line-height:1.25}.vector-privacy-dialog p{color:#9eb5ad;font-size:14px;line-height:1.6}
      .vector-privacy-findings{list-style:none;padding:0;margin:20px 0;max-height:220px;overflow:auto}.vector-privacy-findings li{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid #ffffff10;font-size:13px}.vector-privacy-findings code{max-width:68%;overflow-wrap:anywhere;color:#f0f7f3}
      .vector-privacy-dialog details{border:1px solid #ffffff15;border-radius:10px;padding:12px;font-size:13px}.vector-privacy-dialog summary{cursor:pointer}.vector-privacy-dialog pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:220px;overflow:auto;margin-top:12px}
      .vector-privacy-dialog .vector-privacy-hint{font-size:12px}.vector-privacy-dialog .vector-privacy-caution{color:#e5c48a}
      .vector-privacy-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;margin-top:20px}.vector-privacy-actions button{background:transparent;border:1px solid #ffffff25;border-radius:9px;padding:10px 12px;color:#f0f7f3;font:inherit;font-size:12px;cursor:pointer}.vector-privacy-actions button:focus-visible{outline:2px solid #8de0b7;outline-offset:3px}.vector-privacy-actions .vector-privacy-primary{background:#8de0b7;color:#0a0d11;border-color:#8de0b7}.vector-privacy-actions button:disabled{opacity:.4;cursor:not-allowed}
      @media(max-width:480px){.vector-privacy-dialog{padding:20px}.vector-privacy-actions button{flex:1 1 100%}}
    `}</style>
  </dialog> : null;
  return {privacySend,privacyDialog};
}
