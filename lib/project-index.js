import crypto from "node:crypto";

import {
  db,
  initializeDatabase
} from "./db";

const MAX_CHUNK_CHARS = 5000;
const OVERLAP_LINES = 5;

export async function initializeProjectIndex() {
  await initializeDatabase();

  await db.query(`
    ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS project_id TEXT;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS project_id TEXT;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS title TEXT;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS description TEXT;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS status TEXT
    NOT NULL DEFAULT 'pending';
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS task_type TEXT
    NOT NULL DEFAULT 'normal';
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS privacy_level TEXT
    NOT NULL DEFAULT 'internal';
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS budget_chf NUMERIC
    NOT NULL DEFAULT 0.10;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS spent_chf NUMERIC
    NOT NULL DEFAULT 0;
  `);

  await db.query(`
    ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
    NOT NULL DEFAULT NOW();
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_conversations_project_id
    ON conversations(project_id);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_tasks_project_id
    ON tasks(project_id);
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS project_file_chunks (
      id TEXT PRIMARY KEY,

      project_id TEXT NOT NULL
        REFERENCES projects(id)
        ON DELETE CASCADE,

      file_id TEXT NOT NULL
        REFERENCES project_files(id)
        ON DELETE CASCADE,

      chunk_index INTEGER NOT NULL,

      start_line INTEGER,
      end_line INTEGER,

      content TEXT NOT NULL,

      search_vector TSVECTOR
        GENERATED ALWAYS AS (
          to_tsvector(
            'simple',
            content
          )
        ) STORED,

      created_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

      UNIQUE (
        file_id,
        chunk_index
      )
    );
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_project_chunks_project
    ON project_file_chunks(project_id);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS
      idx_project_chunks_search
    ON project_file_chunks
    USING GIN(search_vector);
  `);
}

function chunkText(text) {
  const lines =
    String(text || "")
      .replace(/\r\n/g, "\n")
      .split("\n");

  const chunks = [];

  let start = 0;

  while (start < lines.length) {
    let end = start;
    let size = 0;

    while (
      end < lines.length &&
      size + lines[end].length + 1
        <= MAX_CHUNK_CHARS
    ) {
      size +=
        lines[end].length + 1;

      end += 1;
    }

    if (end === start) {
      end += 1;
    }

    chunks.push({
      startLine:
        start + 1,

      endLine:
        end,

      content:
        lines
          .slice(
            start,
            end
          )
          .join("\n")
    });

    if (end >= lines.length) {
      break;
    }

    start =
      Math.max(
        end - OVERLAP_LINES,
        start + 1
      );
  }

  return chunks;
}

export async function indexProjectTextFile({
  projectId,
  fileId,
  text
}) {
  await initializeProjectIndex();

  await db.query(
    `
      DELETE FROM project_file_chunks
      WHERE file_id = $1
    `,
    [
      fileId
    ]
  );

  const chunks =
    chunkText(
      text
    );

  for (
    let index = 0;
    index < chunks.length;
    index += 1
  ) {
    const chunk =
      chunks[index];

    await db.query(
      `
        INSERT INTO project_file_chunks (
          id,
          project_id,
          file_id,
          chunk_index,
          start_line,
          end_line,
          content
        )
        VALUES (
          $1,
          $2,
          $3,
          $4,
          $5,
          $6,
          $7
        )
      `,
      [
        crypto.randomUUID(),
        projectId,
        fileId,
        index,
        chunk.startLine,
        chunk.endLine,
        chunk.content
      ]
    );
  }

  return chunks.length;
}

export async function searchProjectChunks({
  projectId,
  query,
  limit = 10
}) {
  await initializeProjectIndex();

  const clean =
    String(query || "")
      .trim()
      .slice(
        0,
        2000
      );

  if (!clean) {
    return [];
  }

  /*
   * PostgreSQL full-text search first.
   */
  const result =
    await db.query(
      `
        SELECT
          c.file_id,
          c.start_line,
          c.end_line,
          c.content,
          f.original_name,

          ts_rank_cd(
            c.search_vector,
            websearch_to_tsquery(
              'simple',
              $2
            )
          ) AS rank

        FROM project_file_chunks c

        JOIN project_files f
          ON f.id =
             c.file_id

        WHERE
          c.project_id = $1
          AND
          c.search_vector @@
          websearch_to_tsquery(
            'simple',
            $2
          )

        ORDER BY
          rank DESC

        LIMIT $3
      `,
      [
        projectId,
        clean,
        limit
      ]
    );

  if (
    result.rows.length > 0
  ) {
    return result.rows;
  }

  /*
   * Fallback for stack traces,
   * filenames, IDs and unusual tokens.
   */
  const terms =
    clean
      .split(/\s+/)
      .filter(
        (term) =>
          term.length >= 4
      )
      .slice(
        0,
        6
      );

  if (
    terms.length === 0
  ) {
    return [];
  }

  const fallback =
    await db.query(
      `
        SELECT
          c.file_id,
          c.start_line,
          c.end_line,
          c.content,
          f.original_name,
          0 AS rank

        FROM project_file_chunks c

        JOIN project_files f
          ON f.id =
             c.file_id

        WHERE
          c.project_id = $1

          AND (
            ${terms
              .map(
                (_, index) =>
                  `c.content ILIKE $${index + 2}`
              )
              .join(" OR ")}
          )

        LIMIT $${terms.length + 2}
      `,
      [
        projectId,
        ...terms.map(
          (term) =>
            `%${term}%`
        ),
        limit
      ]
    );

  return fallback.rows;
}

export async function projectIndexStats(
  projectId
) {
  await initializeProjectIndex();

  const result =
    await db.query(
      `
        SELECT
          COUNT(*)::int
            AS chunks,

          COUNT(
            DISTINCT file_id
          )::int
            AS indexed_files

        FROM project_file_chunks

        WHERE
          project_id = $1
      `,
      [
        projectId
      ]
    );

  return result.rows[0];
}
