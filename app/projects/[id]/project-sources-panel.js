'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {Link2,LoaderCircle,RefreshCw,Download} from 'lucide-react';

const labels = {fetching:'Importing',indexed:'Searchable',partial:'Partial extract',failed:'Failed',interrupted:'Interrupted'};
const errors = {
  INVALID_URL:'Use a public HTTP or HTTPS URL without credentials or a custom port.',
  BLOCKED_ADDRESS:'Private, local and reserved network addresses cannot be imported.',
  BLOCKED_REDIRECT:'The redirect target is not allowed.',
  LOCAL_ONLY_PROJECT:'Web imports are disabled for local-only projects. Upload a file instead.',
  IMPORT_BUSY:'Another import is running in this project. Please wait for it to finish.',
  SOURCE_LIMIT:'This project has reached its import limit. At most 100 snapshots and five starts per minute are allowed.',
  RETRY_UNAVAILABLE:'Retry is available after 30 seconds, up to three attempts per source.',
  FETCH_TIMEOUT:'The website did not finish responding within 15 seconds.',
  UNSUPPORTED_CONTENT:'This importer supports static HTML, plain text and Markdown.',
  CONTENT_LIMIT:'The response is compressed or exceeds the 2 MB limit.',
  NO_EXTRACTABLE_TEXT:'No readable text was found. Browser rendering and OCR are not enabled.',
  ACCESS_REVOKED:'Your project editing access changed during the import.'
};
export default function ProjectSourcesPanel({projectId,canEdit,onFilesChanged}) {
  const [sources,setSources]=useState([]);
  const [url,setUrl]=useState('');
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const requestRef=useRef(null);
  const completed=useRef(new Set());
  const mounted=useRef(true);
  const endpoint=`/api/projects/${encodeURIComponent(projectId)}/sources`;
  const reload=useCallback(async signal => {
    const response=await fetch(endpoint,{cache:'no-store',signal});
    const data=await response.json();
    if (!response.ok) throw new Error('Sources could not be loaded.');
    if (mounted.current) setSources(data.sources);
  },[endpoint]);
  useEffect(() => {
    mounted.current=true;
    const controller=new AbortController();
    reload(controller.signal).catch(e => {if(e.name!=='AbortError' && mounted.current) setError(e.message);})
      .finally(() => {if(mounted.current) setLoading(false);});
    return () => {mounted.current=false;controller.abort();};
  },[reload]);
  useEffect(() => {
    const done=sources.filter(row=>['indexed','partial'].includes(row.status));
    if(done.some(row=>!completed.current.has(row.id))) {
      completed.current=new Set(done.map(row=>row.id));
      onFilesChanged().catch(()=>{});
    }
  },[sources,onFilesChanged]);
  const active=busy || sources.some(row=>row.status==='fetching');
  useEffect(() => {
    if (!active) return;
    const controller=new AbortController();
    const timer=setInterval(() => reload(controller.signal).catch(()=>{}),2000);
    return () => {clearInterval(timer);controller.abort();};
  },[active,reload]);
  async function start(sourceId) {
    if (busy || !canEdit) return;
    setBusy(true); setError('');
    let payload;
    if(sourceId) payload={sourceId};
    else {
      if(requestRef.current?.url !== url.trim()) requestRef.current={url:url.trim(),requestId:crypto.randomUUID()};
      payload=requestRef.current;
    }
    try {
      const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
      const data=await response.json();
      if(!response.ok) throw new Error(errors[data.code] || 'Import failed. The saved source status explains what happened; you can retry without re-uploading.');
      if (!sourceId && mounted.current) {setUrl('');requestRef.current=null;}
      await onFilesChanged();
    } catch(e) {if(mounted.current) setError(e.message || 'Import could not be completed.');}
    finally {await reload().catch(()=>{});if(mounted.current) setBusy(false);}
  }
  return <section className="vp-source-panel" aria-label="Project web sources">
    <header><div><h3>Sources</h3><p>Import a public page into this project. Keep its original snapshot and search its extracted text.</p></div>
      <button type="button" className="vp-icon-button" aria-label="Refresh sources" onClick={()=>reload().catch(e=>setError(e.message))}><RefreshCw size={16}/></button></header>
    {canEdit && <form onSubmit={e=>{e.preventDefault();start();}} className="vp-source-form">
      <label><span className="sr-only">Public source URL</span><input type="url" required maxLength={2048} value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.org/article" disabled={busy}/></label>
      <button className="vp-button" disabled={busy || !url.trim()}>{busy?<LoaderCircle size={16} className="vp-spin"/>:<Link2 size={16}/>} {busy?'Importing…':'Import URL'}</button>
    </form>}
    {canEdit && <p className="vp-source-hint">Vector requests this URL directly. No chat or project text is sent to the website. Static pages only, up to 2 MB. Imports are saved as read-only snapshots.</p>}
    {error && <p className="vp-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading sources…</p>}
    {!loading && sources.length===0 && <p className="vp-source-hint">No web sources imported yet.</p>}
    <ul className="vp-source-list">{sources.map(row=><li key={row.id}>
      <div className="vp-source-info"><a href={row.finalUrl || row.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{row.title || row.url}</a>
        <small>{labels[row.status] || row.status}{row.fetchedAt?` · Retrieved ${new Date(row.fetchedAt).toLocaleString()}`:''}</small>
        {row.status==='partial' && <small>Text reached the extraction limit. This is not the complete page.</small>}
        {['indexed','partial'].includes(row.status) && !row.fileId && <small>The extracted project file was removed. The original snapshot is retained.</small>}
        {row.errorCode && <small>{errors[row.errorCode] || 'The website could not be imported.'}</small>}
        {row.rawSha256 && <details><summary>Source details</summary><small>Method {row.method}</small><small>Original SHA-256 {row.rawSha256}</small><small>Text SHA-256 {row.textSha256}</small></details>}
      </div><div className="vp-actions">
        {row.rawSha256 && <a className="vp-button" href={`${endpoint}/${encodeURIComponent(row.id)}/snapshot`} download><Download size={14}/> Original</a>}
        {canEdit && row.retryable && <button type="button" className="vp-button" disabled={busy} onClick={()=>start(row.id)}>Retry</button>}
      </div>
    </li>)}</ul>
  </section>;
}
