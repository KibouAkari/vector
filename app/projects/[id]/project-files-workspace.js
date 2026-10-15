"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, File, FileCode2, FileImage, FileText, FolderOpen, LoaderCircle, Plus, Save, Search, Upload, X } from 'lucide-react';
import { filePreviewKind, projectFileBytes, visibleProjectFiles } from '../../../lib/project-file-view.mjs';

function fileIcon(file) {
  const kind = filePreviewKind(file);
  return kind === 'image' ? FileImage : kind === 'text' ? FileCode2 : kind === 'pdf' ? FileText : File;
}

export default function ProjectFilesWorkspace({
  projectId, files, canEdit = false, uploading, onUpload,
  onFilesChanged, openCreate, onCreateOpenChange
}) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('recent');
  const [selectedId, setSelectedId] = useState(null);
  const [preview, setPreview] = useState({status: 'empty'});
  const [draft, setDraft] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [filename, setFilename] = useState('');
  const [content, setContent] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const detailRef = useRef(null);
  const selected = files.find(file => file.id === selectedId) || null;
  const kind = selected ? filePreviewKind(selected) : null;
  const previewMatches = preview.fileId === selectedId;
  const visible = useMemo(() => visibleProjectFiles(files, query, sort), [files, query, sort]);
  const totalBytes = files.reduce((total, file) => total + Number(file.size_bytes || 0), 0);
  const fileBase = selected ? `/api/files/${encodeURIComponent(selected.id)}` : null;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setEditing(false);
    setNotice('');
    setDraft('');
    if (!selectedId || !kind) {
      setPreview({status: 'empty'});
      return () => controller.abort();
    }
    if (kind !== 'text') {
      setPreview({status: 'ready', fileId: selectedId});
      return () => controller.abort();
    }
    setPreview({status: 'loading', fileId: selectedId});
    (async () => {
      try {
        const response = await fetch(`/api/files/${encodeURIComponent(selectedId)}/preview`, {
          cache: 'no-store', signal: controller.signal
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Preview could not be loaded.');
        if (typeof data.content !== 'string') throw new Error('Preview content is unavailable.');
        if (active) {
          setPreview({status: 'ready', fileId: selectedId, text: data.content, truncated: data.truncated === true});
          setDraft(data.content);
        }
      } catch (error) {
        if (active && error.name !== 'AbortError') setPreview({status: 'error', fileId: selectedId, error: error.message});
      }
    })();
    return () => { active = false; controller.abort(); };
  }, [selectedId, kind]);

  function choose(file) {
    if (editing || saving) return;
    setSelectedId(file.id);
    setEditing(false);
    detailRef.current?.focus({preventScroll: true});
  }

  async function save() {
    if (!selected || !canEdit || preview.truncated || saving) return;
    setSaving(true);
    setNotice('');
    try {
      const response = await fetch(`${fileBase}/content`, {
        method: 'PATCH', headers: {'content-type': 'application/json'},
        body: JSON.stringify({content: draft})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'File could not be saved.');
      setPreview({status: 'ready', fileId: selectedId, text: draft, truncated: false});
      setEditing(false);
      setNotice('Changes saved.');
      await onFilesChanged();
    } catch (error) {
      setNotice(error.message || 'File could not be saved. Your changes are still in the editor.');
    } finally { setSaving(false); }
  }

  async function create(event) {
    event.preventDefault();
    if (!canEdit || creating || !filename.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/files/create`, {
        method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify({name: filename.trim(), content})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'File could not be created.');
      setFilename(''); setContent(''); onCreateOpenChange(false);
      await onFilesChanged();
    } catch (error) { setCreateError(error.message); }
    finally { setCreating(false); }
  }

  return <section className="vp-files" aria-label="Project files">
    <header className="vp-files-toolbar">
      <div><h2>Files</h2><p>{files.length} {files.length === 1 ? 'file' : 'files'} · {projectFileBytes(totalBytes)}</p></div>
      <div className="vp-actions">
        {!canEdit && <span className="vp-read-only">View access</span>}
        {canEdit && <>
          <button type="button" className="vp-button" onClick={() => onCreateOpenChange(!openCreate)}><Plus size={16}/> New file</button>
          <button type="button" className="vp-button vp-button-primary" disabled={uploading} onClick={onUpload}>
            {uploading ? <LoaderCircle size={16} className="vp-spin"/> : <Upload size={16}/>} {uploading ? 'Uploading…' : 'Upload files'}
          </button>
        </>}
      </div>
    </header>
    {openCreate && canEdit && <form className="vp-create-file" onSubmit={create}>
      <div className="vp-create-heading"><h3>Create a text file</h3><button type="button" className="vp-icon-button" aria-label="Close file form" disabled={creating} onClick={() => onCreateOpenChange(false)}><X size={17}/></button></div>
      <label>Filename<input autoFocus required value={filename} onChange={event => setFilename(event.target.value)} placeholder="notes.md" disabled={creating}/></label>
      <label>Content<textarea rows={6} value={content} onChange={event => setContent(event.target.value)} placeholder="Start writing…" disabled={creating}/></label>
      {createError && <p role="alert" className="vp-error">{createError}</p>}
      <div className="vp-actions"><button className="vp-button vp-button-primary" disabled={creating || !filename.trim()}>{creating ? 'Creating…' : 'Create file'}</button></div>
    </form>}
    <div className="vp-file-layout">
      <aside className="vp-file-list" aria-label="File browser">
        <div className="vp-file-filters">
          <label className="vp-search"><Search size={16}/><input type="search" aria-label="Search project files" placeholder="Find a file…" value={query} onChange={event => setQuery(event.target.value)}/></label>
          <label className="vp-sort">Sort by<select value={sort} onChange={event => setSort(event.target.value)}><option value="recent">Most recent</option><option value="name">Name</option><option value="size">Largest first</option></select></label>
        </div>
        <div className="vp-file-rows">
          {visible.map(file => {
            const Icon = fileIcon(file);
            return <button type="button" key={file.id} className={`vp-file-row${selectedId === file.id ? ' is-selected' : ''}`} aria-pressed={selectedId === file.id} disabled={editing || saving} onClick={() => choose(file)}>
              <span className="vp-file-symbol"><Icon size={19}/></span>
              <span className="vp-file-name"><strong title={file.original_name}>{file.original_name}</strong><small>{projectFileBytes(file.size_bytes)}</small></span>
              <span className="vp-file-extension">{String(file.extension || '').slice(0, 6)}</span>
            </button>;
          })}
          {visible.length === 0 && <div className="vp-empty vp-list-empty"><FolderOpen size={25}/><strong>{query ? 'No matching files' : 'A place for your work'}</strong><p>{query ? 'Try another filename.' : canEdit ? 'Upload files to keep them with this project.' : 'This project has no files yet.'}</p></div>}
        </div>
      </aside>
      <section className="vp-file-detail" aria-label="File preview" tabIndex={-1} ref={detailRef}>
        {!selected && <div className="vp-empty"><FileText size={34} strokeWidth={1.3}/><h3>Your files, in focus</h3><p>Select a file to preview it here.<br/>Every file can be downloaded in its original format.</p></div>}
        {selected && <>
          <header className="vp-detail-header">
            <div><strong title={selected.original_name}>{selected.original_name}</strong><small>{projectFileBytes(selected.size_bytes)} · {selected.extension || 'File'}</small></div>
            <a className="vp-button" href={`${fileBase}/download`} download={selected.original_name}><Download size={16}/> Download</a>
          </header>
          {(!previewMatches || preview.status === 'loading') && <div className="vp-empty" role="status"><LoaderCircle className="vp-spin" size={24}/><p>Loading preview…</p></div>}
          {previewMatches && preview.status === 'error' && <div className="vp-empty" role="alert"><File size={28}/><h3>Preview unavailable</h3><p>{preview.error}</p><p>You can still download the original file.</p></div>}
          {previewMatches && preview.status === 'ready' && kind === 'image' && <div className="vp-image-preview"><img src={`${fileBase}/raw`} alt={selected.original_name} onError={() => setPreview(current => current.fileId === selected.id ? {status:'error', fileId:selected.id, error:'The image could not be loaded.'} : current)}/></div>}
          {previewMatches && preview.status === 'ready' && kind === 'pdf' && <iframe className="vp-pdf-preview" src={`${fileBase}/raw`} title={`PDF preview: ${selected.original_name}`}/>}
          {previewMatches && preview.status === 'ready' && kind === 'download' && <div className="vp-empty"><File size={34} strokeWidth={1.3}/><h3>Open it in your own app</h3><p>A browser preview is not available for this format.<br/>Download the original file to view or edit it.</p></div>}
          {previewMatches && preview.status === 'ready' && kind === 'text' && <div className="vp-text-preview">
            <div className="vp-editor-toolbar"><span>{editing ? 'Editing · save or cancel before switching files' : preview.truncated ? 'Partial preview · editing disabled' : 'Text preview'}</span>
              {canEdit && !preview.truncated && <div className="vp-actions">{editing ? <>
                <button type="button" className="vp-button" disabled={saving} onClick={() => {setDraft(preview.text); setEditing(false); setNotice('');}}>Cancel</button>
                <button type="button" className="vp-button vp-button-primary" disabled={saving} onClick={save}><Save size={15}/>{saving ? 'Saving…' : 'Save changes'}</button>
              </> : <button type="button" className="vp-button" onClick={() => setEditing(true)}>Edit text</button>}</div>}
            </div>
            {editing ? <textarea aria-label={`Edit ${selected.original_name}`} className="vp-code-editor" spellCheck={false} value={draft} disabled={saving} onChange={event => setDraft(event.target.value)}/> : <pre className="vp-code-preview">{preview.text}</pre>}
          </div>}
          {notice && <p className="vp-file-notice" role="status">{notice}</p>}
        </>}
      </section>
    </div>
  </section>;
}
