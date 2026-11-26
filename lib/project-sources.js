import crypto from 'node:crypto';
import {db} from './db';
import {canEditProject} from './identity';
import {initializeFileDatabase, writeEncryptedFile, removeEncryptedFile, encryptFileBuffer} from './project-files';
import {initializeProjectIndex, replaceProjectTextChunks} from './project-index';
import {fetchPublicSource, sourceUrl, SourceError} from './source-fetch.mjs';
import {extractSourceText} from './source-extract.mjs';

let initialization;
export function initializeProjectSources() {
  if (!initialization) initialization = (async () => {
    await initializeFileDatabase();
    await initializeProjectIndex();
    await db.query(`CREATE TABLE IF NOT EXISTS project_sources (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      created_by TEXT NOT NULL,
      request_id TEXT NOT NULL,
      url TEXT NOT NULL,
      final_url TEXT,
      title TEXT,
      status TEXT NOT NULL CHECK (status IN ('fetching','indexed','partial','failed')),
      attempt_id TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 1,
      started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      fetched_at TIMESTAMPTZ,
      file_id TEXT REFERENCES project_files(id) ON DELETE SET NULL,
      raw_snapshot BYTEA,
      raw_sha256 TEXT,
      text_sha256 TEXT,
      byte_count INTEGER,
      extraction_method TEXT,
      error_code TEXT,
      UNIQUE(project_id, created_by, request_id)
    )`);
    await db.query('CREATE INDEX IF NOT EXISTS idx_project_sources_project ON project_sources(project_id,created_at DESC)');
    await db.query(`CREATE TABLE IF NOT EXISTS project_source_attempts (
      id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL REFERENCES project_sources(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )`);
    await db.query('CREATE INDEX IF NOT EXISTS idx_source_attempts_project ON project_source_attempts(project_id,created_at)');
  })().catch(error => { initialization = undefined; throw error; });
  return initialization;
}

export function publicSource(row) {
  const interrupted = row.status === 'fetching' && Date.now() - new Date(row.started_at).getTime() > 120000;
  return {id:row.id, url:row.url, finalUrl:row.final_url, title:row.title,
    status:interrupted ? 'interrupted' : row.status,
    createdAt:row.created_at, fetchedAt:row.fetched_at, fileId:row.file_id,
    rawSha256:row.raw_sha256, textSha256:row.text_sha256,
    bytes:row.byte_count, method:row.extraction_method, errorCode:row.error_code,
    attempts:row.attempts, retryable:(row.status === 'failed' || interrupted) && row.attempts < 3};
}
const PUBLIC_COLUMNS = `id,url,final_url,title,status,created_at,started_at,fetched_at,
  file_id,raw_sha256,text_sha256,byte_count,extraction_method,error_code,attempts`;
export async function listProjectSources(projectId) {
  await initializeProjectSources();
  const result = await db.query(`SELECT ${PUBLIC_COLUMNS} FROM project_sources WHERE project_id=$1 ORDER BY created_at DESC LIMIT 100`,[projectId]);
  return result.rows.map(publicSource);
}

async function claimSource({projectId,session,url,requestId,sourceId}) {
  const client = await db.connect();
  try {
    await client.query('BEGIN');
    await client.query('SELECT pg_advisory_xact_lock(73504, 201)');
    // Serializes capacity/active-import checks for a project across app instances.
    const project = await client.query('SELECT id,privacy_level FROM projects WHERE id=$1 FOR UPDATE',[projectId]);
    if (!project.rowCount) throw new SourceError('NOT_FOUND');
    if (project.rows[0].privacy_level === 'local_only') throw new SourceError('LOCAL_ONLY_PROJECT');
    const attemptId = crypto.randomUUID();
    if (!sourceId) {
      const existing = await client.query(`SELECT ${PUBLIC_COLUMNS} FROM project_sources
        WHERE project_id=$1 AND created_by=$2 AND request_id=$3`,[projectId,session.userId,requestId]);
      if (existing.rowCount) {
        if (existing.rows[0].url !== sourceUrl(url).href) throw new SourceError('REQUEST_CONFLICT');
        await client.query('COMMIT'); return {source:existing.rows[0],claimed:false};
      }
    }
    const capacity = await client.query(`SELECT COUNT(*)::int AS total,
      COUNT(*) FILTER (WHERE status='fetching' AND started_at > NOW()-INTERVAL '2 minutes')::int AS active,
      (SELECT COUNT(*)::int FROM project_source_attempts WHERE project_id=$1 AND created_at > NOW()-INTERVAL '1 minute') AS recent
      FROM project_sources WHERE project_id=$1`,[projectId]);
    const counts = capacity.rows[0];
    const global = await client.query("SELECT COUNT(*)::int AS active FROM project_sources WHERE status='fetching' AND started_at > NOW()-INTERVAL '2 minutes'");
    if (global.rows[0].active >= 2) throw new SourceError('IMPORT_BUSY');
    if (counts.active > 0) throw new SourceError('IMPORT_BUSY');
    if (counts.recent >= 5 || (!sourceId && counts.total >= 100)) throw new SourceError('SOURCE_LIMIT');
    let result;
    if (sourceId) {
      result = await client.query(`UPDATE project_sources SET status='fetching',attempt_id=$3,
        attempts=attempts+1,started_at=NOW(),error_code=NULL
        WHERE id=$1 AND project_id=$2 AND attempts<3
        AND (status='failed' OR (status='fetching' AND started_at < NOW()-INTERVAL '2 minutes'))
        AND started_at < NOW()-INTERVAL '30 seconds'
        RETURNING *`,[sourceId,projectId,attemptId]);
      if (!result.rowCount) throw new SourceError('RETRY_UNAVAILABLE');
    } else {
      result = await client.query(`INSERT INTO project_sources
        (id,project_id,created_by,request_id,url,status,attempt_id)
        VALUES ($1,$2,$3,$4,$5,'fetching',$6) RETURNING *`,
        [crypto.randomUUID(),projectId,session.userId,requestId,sourceUrl(url).href,attemptId]);
    }
    await client.query('INSERT INTO project_source_attempts (id,source_id,project_id) VALUES ($1,$2,$3)',[attemptId,result.rows[0].id,projectId]);
    await client.query('COMMIT');
    return {source:result.rows[0],claimed:true};
  } catch (error) { await client.query('ROLLBACK'); throw error; }
  finally { client.release(); }
}

export async function importProjectSource({projectId,session,url,requestId,sourceId}) {
  await initializeProjectSources();
  const {source,claimed} = await claimSource({projectId,session,url,requestId,sourceId});
  if (!claimed) return publicSource(source);
  let stored;
  const fileId = crypto.randomUUID();
  let committed = false;
  try {
    const page = await fetchPublicSource(source.url);
    const extracted = extractSourceText(page);
    // Membership may have been revoked while the remote request was in flight.
    if (!await canEditProject(session,projectId)) throw new SourceError('ACCESS_REVOKED');
    const textBuffer = Buffer.from(extracted.text,'utf8');
    stored = await writeEncryptedFile({projectId,fileId,buffer:textBuffer});
    const client = await db.connect();
    try {
      await client.query('BEGIN');
      const current = await client.query(`SELECT id FROM project_sources WHERE id=$1 AND project_id=$2
        AND attempt_id=$3 AND status='fetching' FOR UPDATE`,[source.id,projectId,source.attempt_id]);
      if (!current.rowCount) throw new SourceError('IMPORT_SUPERSEDED');
      await client.query(`INSERT INTO project_files
        (id,project_id,original_name,stored_name,mime_type,extension,size_bytes,sha256,previewable,source_snapshot)
        VALUES ($1,$2,$3,$4,'text/plain','txt',$5,$6,TRUE,TRUE)`,
        [fileId,projectId,`${(extracted.title || new URL(page.finalUrl).hostname).replace(/[/\\\u0000-\u001f]/g,'_').slice(0,160)}.txt`,
          stored.storedName,textBuffer.length,extracted.textSha256]);
      await replaceProjectTextChunks(client,{projectId,fileId,text:extracted.text});
      await client.query(`UPDATE project_sources SET status=$3,final_url=$4,title=$5,fetched_at=$6,
        file_id=$7,raw_snapshot=$8,raw_sha256=$9,text_sha256=$10,byte_count=$11,extraction_method=$12
        WHERE id=$1 AND project_id=$2`,[source.id,projectId,extracted.partial?'partial':'indexed',page.finalUrl,
        extracted.title,page.fetchedAt,fileId,encryptFileBuffer(page.buffer),extracted.rawSha256,
        extracted.textSha256,page.buffer.length,extracted.method]);
      await client.query('COMMIT');
      committed = true;
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return (await listProjectSources(projectId)).find(row => row.id === source.id);
  } catch (error) {
    // Do not return DNS, socket, filesystem or database details to the client.
    const code = error instanceof SourceError ? error.code : 'IMPORT_FAILED';
    if (!committed) {
      if (stored) await removeEncryptedFile({project_id:projectId,stored_name:stored.storedName}).catch(() => {});
      await db.query(`UPDATE project_sources SET status='failed',error_code=$3
        WHERE id=$1 AND attempt_id=$2 AND status='fetching'`,[source.id,source.attempt_id,code]);
    }
    throw new SourceError(code);
  }
}

export async function isImportedSourceFile(fileId) {
  await initializeProjectSources();
  return (await db.query('SELECT 1 FROM project_sources WHERE file_id=$1 LIMIT 1',[fileId])).rowCount > 0;
}

export async function sourceEvidenceForFiles(projectId,fileIds) {
  if (!fileIds.length) return new Map();
  await initializeProjectSources();
  const result = await db.query(`SELECT s.id,s.url,s.final_url,s.fetched_at,s.extraction_method,
    s.raw_sha256,s.text_sha256,s.status,s.file_id FROM project_sources s
    JOIN project_files f ON f.id=s.file_id AND f.project_id=s.project_id
    WHERE s.project_id=$1 AND s.file_id=ANY($2::text[]) AND s.status IN ('indexed','partial')
      AND f.sha256=s.text_sha256`,[projectId,fileIds]);
  return new Map(result.rows.map(row => [row.file_id,{sourceId:row.id,url:row.final_url || row.url,
    fetchedAt:row.fetched_at,method:row.extraction_method,partial:row.status==='partial',
    rawSha256:row.raw_sha256,textSha256:row.text_sha256,
    snapshot:`/api/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(row.id)}/snapshot`} ]));
}
