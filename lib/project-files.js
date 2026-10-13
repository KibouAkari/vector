import crypto
  from "node:crypto";

import fs
  from "node:fs/promises";

import path
  from "node:path";

import {
  db,
  initializeDatabase
} from "./db";

const PREVIEW_EXTENSIONS =
  new Set([
    "txt",
    "log",
    "md",
    "markdown",
    "json",
    "jsonl",
    "csv",
    "tsv",
    "xml",
    "yaml",
    "yml",
    "toml",
    "ini",
    "conf",
    "config",
    "properties",
    "env",
    "js",
    "jsx",
    "ts",
    "tsx",
    "mjs",
    "cjs",
    "py",
    "java",
    "c",
    "h",
    "cpp",
    "hpp",
    "cs",
    "go",
    "rs",
    "php",
    "rb",
    "sh",
    "bash",
    "zsh",
    "ps1",
    "sql",
    "html",
    "htm",
    "css",
    "scss",
    "less",
    "vue",
    "svelte",
    "dockerfile",
    "gitignore",
    "editorconfig",
    "gradle",
    "kts",
    "tf",
    "tfvars",
    "ldif"
  ]);

const TEXT_MIME_PREFIXES = [
  "text/",
  "application/json",
  "application/xml",
  "application/javascript",
  "application/x-javascript",
  "application/sql",
  "application/yaml",
  "application/x-yaml"
];

function storageRoot() {
  return (
    process.env
      .FILE_STORAGE_PATH ||
    "/data/vector-files"
  );
}

function encryptionKey() {
  const raw =
    process.env
      .FILE_ENCRYPTION_KEY;

  if (!raw) {
    throw new Error(
      "FILE_ENCRYPTION_KEY is missing."
    );
  }

  const key =
    Buffer.from(
      raw,
      "hex"
    );

  if (
    key.length !==
    32
  ) {
    throw new Error(
      "FILE_ENCRYPTION_KEY must be exactly 32 bytes."
    );
  }

  return key;
}

export async function initializeFileDatabase() {
  await initializeDatabase();

  await db.query(`
    ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS privacy_level
      TEXT NOT NULL DEFAULT 'personal';
  `);

  await db.query(`
    ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS updated_at
      TIMESTAMPTZ NOT NULL DEFAULT NOW();
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS project_files (
      id TEXT PRIMARY KEY,

      project_id TEXT NOT NULL
        REFERENCES projects(id)
        ON DELETE CASCADE,

      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL,
      mime_type TEXT,
      extension TEXT,

      size_bytes BIGINT NOT NULL,
      sha256 TEXT NOT NULL,

      previewable BOOLEAN NOT NULL DEFAULT FALSE,

      encryption_version INTEGER NOT NULL DEFAULT 1,

      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_project_files_project
    ON project_files(project_id);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_project_files_created
    ON project_files(created_at DESC);
  `);
}

export function cleanFilename(
  filename
) {
  return String(
    filename ||
    "file"
  )
    .replace(
      /[\u0000-\u001F\u007F]/g,
      ""
    )
    .replace(
      /[/\\]/g,
      "_"
    )
    .trim()
    .slice(
      0,
      240
    ) ||
    "file";
}

export function extensionFor(
  filename
) {
  const clean =
    cleanFilename(
      filename
    );

  const ext =
    path.extname(
      clean
    )
      .replace(
        /^\./,
        ""
      )
      .toLowerCase();

  if (ext) {
    return ext;
  }

  const base =
    clean.toLowerCase();

  if (
    base === "dockerfile" ||
    base === "makefile" ||
    base === ".gitignore" ||
    base === ".editorconfig"
  ) {
    return base.replace(
      /^\./,
      ""
    );
  }

  return "";
}

export function isPreviewable({
  filename,
  mimeType
}) {
  const extension =
    extensionFor(
      filename
    );

  if (
    PREVIEW_EXTENSIONS.has(
      extension
    )
  ) {
    return true;
  }

  const mime =
    String(
      mimeType ||
      ""
    ).toLowerCase();

  return TEXT_MIME_PREFIXES.some(
    (prefix) =>
      mime.startsWith(
        prefix
      )
  );
}

export function sha256(
  buffer
) {
  return crypto
    .createHash(
      "sha256"
    )
    .update(
      buffer
    )
    .digest(
      "hex"
    );
}

/*
 * Storage format:
 *
 * Bytes 0..3    = ASCII "VEC1"
 * Bytes 4..15   = 12 byte random GCM IV
 * Bytes 16..31  = 16 byte authentication tag
 * Remaining     = ciphertext
 */
export function encryptFileBuffer(
  plain
) {
  const iv =
    crypto.randomBytes(
      12
    );

  const cipher =
    crypto.createCipheriv(
      "aes-256-gcm",
      encryptionKey(),
      iv
    );

  const ciphertext =
    Buffer.concat([
      cipher.update(
        plain
      ),
      cipher.final()
    ]);

  const tag =
    cipher.getAuthTag();

  return Buffer.concat([
    Buffer.from(
      "VEC1",
      "ascii"
    ),
    iv,
    tag,
    ciphertext
  ]);
}

export function decryptFileBuffer(
  encrypted
) {
  if (
    encrypted.length <
    32
  ) {
    throw new Error(
      "Invalid encrypted Vector file."
    );
  }

  const magic =
    encrypted
      .subarray(
        0,
        4
      )
      .toString(
        "ascii"
      );

  if (
    magic !==
    "VEC1"
  ) {
    throw new Error(
      "Unknown Vector file format."
    );
  }

  const iv =
    encrypted.subarray(
      4,
      16
    );

  const tag =
    encrypted.subarray(
      16,
      32
    );

  const ciphertext =
    encrypted.subarray(
      32
    );

  const decipher =
    crypto.createDecipheriv(
      "aes-256-gcm",
      encryptionKey(),
      iv
    );

  decipher.setAuthTag(
    tag
  );

  return Buffer.concat([
    decipher.update(
      ciphertext
    ),
    decipher.final()
  ]);
}

export async function writeEncryptedFile({
  projectId,
  fileId,
  buffer
}) {
  const projectFolder =
    path.join(
      storageRoot(),
      projectId
    );

  await fs.mkdir(
    projectFolder,
    {
      recursive:
        true,

      mode:
        0o700
    }
  );

  const storedName =
    `${fileId}.vfile`;

  const finalPath =
    path.join(
      projectFolder,
      storedName
    );

  const temporaryPath =
    `${finalPath}.tmp`;

  const encrypted =
    encryptFileBuffer(
      buffer
    );

  await fs.writeFile(
    temporaryPath,
    encrypted,
    {
      mode:
        0o600
    }
  );

  await fs.rename(
    temporaryPath,
    finalPath
  );

  return {
    storedName,
    finalPath
  };
}

export async function readEncryptedFile(
  file
) {
  const filePath =
    path.join(
      storageRoot(),
      file.project_id,
      file.stored_name
    );

  const encrypted =
    await fs.readFile(
      filePath
    );

  return decryptFileBuffer(
    encrypted
  );
}

export async function removeEncryptedFile(
  file
) {
  const filePath =
    path.join(
      storageRoot(),
      file.project_id,
      file.stored_name
    );

  try {
    await fs.unlink(
      filePath
    );
  } catch (
    error
  ) {
    if (
      error.code !==
      "ENOENT"
    ) {
      throw error;
    }
  }
}

export async function removeProjectFiles(
  projectId
) {
  const projectFolder =
    path.join(
      storageRoot(),
      projectId
    );

  await fs.rm(
    projectFolder,
    {
      recursive:
        true,

      force:
        true
    }
  );
}

export function maxUploadBytes() {
  const megabytes =
    Number(
      process.env
        .VECTOR_MAX_UPLOAD_MB ||
      100
    );

  return (
    Math.max(
      1,
      megabytes
    ) *
    1024 *
    1024
  );
}

export function previewMaxBytes() {
  return Number(
    process.env
      .VECTOR_PREVIEW_MAX_BYTES ||
    5242880
  );
}

export function humanBytes(
  bytes
) {
  const size =
    Number(
      bytes ||
      0
    );

  if (
    size <
    1024
  ) {
    return `${size} B`;
  }

  if (
    size <
    1024 * 1024
  ) {
    return (
      `${(
        size /
        1024
      ).toFixed(1)} KB`
    );
  }

  if (
    size <
    1024 *
    1024 *
    1024
  ) {
    return (
      `${(
        size /
        1024 /
        1024
      ).toFixed(1)} MB`
    );
  }

  return (
    `${(
      size /
      1024 /
      1024 /
      1024
    ).toFixed(2)} GB`
  );
}
