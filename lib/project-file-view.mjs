const INLINE_IMAGES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);

export function filePreviewKind(file) {
  const mime = String(file?.mime_type || '').toLowerCase();
  if (INLINE_IMAGES.has(mime)) return 'image';
  if (mime === 'application/pdf') return 'pdf';
  if (file?.previewable === true) return 'text';
  return 'download';
}

export function visibleProjectFiles(files, query = '', sort = 'recent') {
  const needle = query.trim().toLocaleLowerCase();
  return [...(files || [])].filter(file =>
    String(file.original_name || '').toLocaleLowerCase().includes(needle)
  ).sort((a, b) => {
    if (sort === 'name') return String(a.original_name).localeCompare(String(b.original_name), 'en', {numeric: true});
    if (sort === 'size') return Number(b.size_bytes || 0) - Number(a.size_bytes || 0);
    const timestamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
    return timestamp(b.created_at) - timestamp(a.created_at);
  });
}

export function projectFileBytes(value) {
  const size = Math.max(0, Number(value) || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}

export function projectDownloadDisposition(name) {
  const clean = String(name || 'download').replace(/[\x00-\x1f\x7f]/g, '_');
  const ascii = clean.replace(/[^\x20-\x7e]|["\\/]/g, '_');
  const encoded = encodeURIComponent(clean).replace(/[!'()*]/g, char =>
    '%' + char.charCodeAt(0).toString(16).toUpperCase());
  return `attachment; filename="${ascii}"; filename*=UTF-8''${encoded}`;
}
