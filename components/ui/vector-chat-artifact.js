"use client";

import {
  Download, File, FileArchive, FileSpreadsheet, FileText,
  Image as ImageIcon, Maximize2
} from "lucide-react";

function describe(name, mime) {
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  const image = /^(png|jpe?g|webp|gif|avif)$/.test(ext) || mime.startsWith("image/");
  if (image) return { kind: "Image", ext: ext || "image", Icon: ImageIcon, image };
  if (/^(docx?|odt)$/.test(ext)) return { kind: "Word document", ext, Icon: FileText };
  if (ext === "pdf") return { kind: "PDF document", ext, Icon: FileText };
  if (/^(xlsx?|csv)$/.test(ext)) return { kind: "Spreadsheet", ext, Icon: FileSpreadsheet };
  if (/^(pptx?)$/.test(ext)) return { kind: "Presentation", ext, Icon: FileText };
  if (/^(zip|rar|7z|tar|gz)$/.test(ext)) return { kind: "Archive", ext, Icon: FileArchive };
  if (/^(js|jsx|ts|tsx|py|json|md|txt|html|css|sh|yaml|yml|sql)$/.test(ext)) return { kind: "Source file", ext, Icon: FileText };
  return { kind: "File", ext: ext || "file", Icon: File };
}

export default function VectorChatArtifact({ attachment, onPreview }) {
  const item = typeof attachment === "string" ? { name: attachment } : attachment || {};
  const name = String(item.name || item.originalName || "Generated file");
  const mime = String(item.mimeType || item.mime_type || "");
  const { kind, ext, Icon, image } = describe(name, mime);
  const originalUrl = item.downloadUrl || (item.id ? `/api/chat/attachments/${encodeURIComponent(item.id)}/raw` : null);
  const url = typeof originalUrl === "string" &&
    ((originalUrl.startsWith("/") && !originalUrl.startsWith("//")) || /^https:\/\//i.test(originalUrl))
    ? originalUrl : null;
  const bytes = Number(item.sizeBytes || item.size_bytes || 0);
  const size = bytes > 0 ?
    (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.ceil(bytes / 1024))} KB`)
    : null;

  if (image && url) return (
    <article className="vx585-image-card vx586-image">
      <button type="button" className="vx585-image-open" aria-label={`Preview ${name}`}
        onClick={() => onPreview?.({ name, url })}>
        <img src={url} alt={name} loading="lazy" />
        <span><Maximize2 size={15} aria-hidden="true" /> View</span>
      </button>
      <div className="vx585-image-info"><strong title={name}>{name}</strong>
        <a href={url} download={name} target="_blank" rel="noreferrer" title="Download image" aria-label={`Download ${name}`}>
          <Download size={16} aria-hidden="true" />
        </a>
      </div>
    </article>
  );

  return (
    <article className={url ? "vx600-document" : "vx600-document vx600-document-unavailable"}>
      <div className="vx600-document-icon" aria-hidden="true">
        <Icon size={22} strokeWidth={1.6} />
      </div>
      <div className="vx600-document-info">
        <strong title={name}>{name}</strong>
        <span>{kind}{size ? ` · ${size}` : ""}</span>
      </div>
      <span className="vx600-document-extension" aria-label={`File type: ${ext}`}>
        {ext.toUpperCase().slice(0, 6)}
      </span>
      {url ? (
        <a className="vx600-document-download"
          href={url} download={name} rel="noreferrer"
          aria-label={`Download ${name}`} title={`Download ${name}`}>
          <Download size={15} strokeWidth={1.9} aria-hidden="true" />
          <span>Download</span>
        </a>
      ) : (
        <span className="vx600-document-missing">Unavailable</span>
      )}
    </article>
  );
}
