"use client";

import {
  Download, File, FileArchive, FileSpreadsheet, FileText,
  Image as ImageIcon, Maximize2, ExternalLink
} from "lucide-react";

function describe(name, mime) {
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  const image = /^(png|jpe?g|webp|gif|avif)$/.test(ext) || mime.startsWith("image/");
  if (image) return { kind: "Image", ext, Icon: ImageIcon, image };
  if (/^(docx?|odt)$/.test(ext)) return { kind: "Word document", ext, Icon: FileText };
  if (ext === "pdf") return { kind: "PDF document", ext, Icon: FileText };
  if (/^(xlsx?|csv)$/.test(ext)) return { kind: "Spreadsheet", ext, Icon: FileSpreadsheet };
  if (/^(pptx?)$/.test(ext)) return { kind: "Presentation", ext, Icon: FileText };
  if (/^(zip|rar|7z|tar|gz)$/.test(ext)) return { kind: "Archive", ext, Icon: FileArchive };
  if (/^(js|jsx|ts|tsx|py|json|md|txt|html|css|sh|yaml|yml|sql)$/.test(ext)) {
    return { kind: "Source file", ext, Icon: FileText };
  }
  return { kind: "File", ext: ext || "file", Icon: File };
}

export default function VectorChatArtifact({ attachment, onPreview }) {
  const item = typeof attachment === "string" ? { name: attachment } : attachment || {};
  const name = String(item.name || item.originalName || "Generated file");
  const mime = String(item.mimeType || item.mime_type || "");
  const { kind, ext, Icon, image } = describe(name, mime);
  const rawUrl = item.downloadUrl ||
    (item.id ? `/api/chat/attachments/${encodeURIComponent(item.id)}/raw` : null);
  const url = typeof rawUrl === "string" &&
    ((rawUrl.startsWith("/") && !rawUrl.startsWith("//")) || /^https:\/\//i.test(rawUrl))
      ? rawUrl : null;
  const bytes = Number(item.sizeBytes || item.size_bytes || 0);
  const size = bytes > 0
    ? bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB`
      : `${Math.max(1, Math.ceil(bytes / 1024))} KB` : null;

  if (image && url) {
    return (
      <article className="vux-file-card vux-file-image">
        <button type="button" className="vux-file-thumbnail"
          onClick={() => onPreview?.({ name, url })}
          aria-label={`Preview ${name}`}>
          <img src={url} alt="" loading="lazy" />
          <Maximize2 size={17} aria-hidden="true" />
        </button>
        <div className="vux-file-info">
          <span className="vux-file-kind">IMAGE FILE</span>
          <strong title={name}>{name}</strong>
          <small>{size || ext.toUpperCase()}</small>
        </div>
        <a className="vux-file-download vux-file-download-compact" href={url}
          download={name} aria-label={`Download ${name}`}>
          <Download size={16} aria-hidden="true" />
        </a>
      </article>
    );
  }

  return (
    <article className="vux-file-card">
      <span className="vux-file-symbol" aria-hidden="true">
        <Icon size={24} strokeWidth={1.5} />
      </span>
      <div className="vux-file-info">
        <span className="vux-file-kind">VECTOR FILE · {ext.toUpperCase() || "FILE"}</span>
        <strong title={name}>{name}</strong>
        <small>{kind}{size ? ` · ${size}` : ""}</small>
      </div>
      {url ? (
        <a className="vux-file-download" href={url} download={name}
          aria-label={`Download ${name}`}>
          <Download size={16} aria-hidden="true" />
          <span>Download</span>
        </a>
      ) : (
        <span className="vux-file-unavailable" title="No download link available">
          <ExternalLink size={14} aria-hidden="true" /> Unavailable
        </span>
      )}
    </article>
  );
}
