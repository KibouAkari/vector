import crypto from 'node:crypto';
import {db,initializeDatabase} from '../db';
import {encryptFileBuffer,decryptFileBuffer} from '../project-files';
import {assessmentScope,scopeDigest,parseNmapEvidence,SecurityInputError,evidenceHash} from './evidence.mjs';
let initialization;
export function initializeSecurityWorkspace(){
  if(!initialization)initialization=(async()=>{
    await initializeDatabase();
    await db.query(`CREATE TABLE IF NOT EXISTS security_assessments (
      id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      created_by TEXT NOT NULL,request_id TEXT NOT NULL,scope JSONB NOT NULL,scope_digest TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('pending','approved','completed')),
      approved_by TEXT,approved_at TIMESTAMPTZ,result JSONB,raw_evidence BYTEA,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(project_id,created_by,request_id)
    )`);
    await db.query('CREATE INDEX IF NOT EXISTS idx_security_assessment_page ON security_assessments(created_at DESC,id DESC)');
    await db.query(`CREATE TABLE IF NOT EXISTS security_assessment_events (
      id TEXT PRIMARY KEY,assessment_id TEXT NOT NULL REFERENCES security_assessments(id) ON DELETE CASCADE,
      actor TEXT NOT NULL,action TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )`);
  })().catch(error=>{initialization=undefined;throw error;});return initialization;
}
const columns='id,project_id,created_by,scope,scope_digest,status,approved_by,approved_at,result,created_at';
export async function listAssessments({after=null}={}){
  if(after!==null && !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(after))throw new SecurityInputError('INVALID_CURSOR');
  await initializeSecurityWorkspace();
  if(after && !(await db.query('SELECT id FROM security_assessments WHERE id=$1',[after])).rowCount)throw new SecurityInputError('INVALID_CURSOR');
  const rows=(await db.query(`SELECT ${columns} FROM security_assessments
    WHERE ($1::text IS NULL OR (created_at,id)<(SELECT created_at,id FROM security_assessments WHERE id=$1))
    ORDER BY created_at DESC,id DESC LIMIT 26`,[after])).rows;
  return {assessments:rows.slice(0,25),nextCursor:rows.length>25?rows[24].id:null};
}
export async function getAssessment(id){await initializeSecurityWorkspace();return (await db.query(`SELECT ${columns} FROM security_assessments WHERE id=$1`,[id])).rows[0] || null;}
export async function assessmentOriginal(id){await initializeSecurityWorkspace();const row=(await db.query('SELECT raw_evidence FROM security_assessments WHERE id=$1',[id])).rows[0];return row?.raw_evidence?decryptFileBuffer(row.raw_evidence):null;}
export async function changeAssessment(session,input){
  if(session?.role!=='owner')throw new SecurityInputError('OWNER_REQUIRED');
  await initializeSecurityWorkspace();
  let scope;
  if(input.action==='create'){
    if(input.authorizationConfirmed!==true || !/^[a-f0-9-]{36}$/i.test(input.requestId || ''))throw new SecurityInputError('INVALID_REQUEST');
    scope=assessmentScope(input);
  } else if(!['approve','import'].includes(input.action) || typeof input.id!=='string' || input.id.length>80)throw new SecurityInputError('INVALID_REQUEST');
  const client=await db.connect();
  try {
    await client.query('BEGIN');let row;
    if(input.action==='create'){
      const project=await client.query('SELECT id FROM projects WHERE id=$1 FOR UPDATE',[input.projectId]);
      if(!project.rowCount)throw new SecurityInputError('PROJECT_NOT_FOUND');
      const existing=await client.query(`SELECT ${columns} FROM security_assessments WHERE project_id=$1 AND created_by=$2 AND request_id=$3`,[input.projectId,session.userId,input.requestId]);
      if(existing.rowCount){if(existing.rows[0].scope_digest!==scopeDigest(scope))throw new SecurityInputError('REQUEST_CONFLICT');await client.query('COMMIT');return existing.rows[0];}
      const count=await client.query('SELECT COUNT(*)::int AS n FROM security_assessments WHERE project_id=$1',[input.projectId]);
      if(count.rows[0].n>=100)throw new SecurityInputError('ASSESSMENT_LIMIT');
      row=(await client.query(`INSERT INTO security_assessments (id,project_id,created_by,request_id,scope,scope_digest,status)
        VALUES ($1,$2,$3,$4,$5,$6,'pending') RETURNING ${columns}`,[crypto.randomUUID(),input.projectId,session.userId,input.requestId,JSON.stringify(scope),scopeDigest(scope)])).rows[0];
    } else {
      row=(await client.query(`SELECT ${columns} FROM security_assessments WHERE id=$1 FOR UPDATE`,[input.id])).rows[0];
      if(!row)throw new SecurityInputError('NOT_FOUND');
      if(new Date(row.scope.expiresAt).getTime()<=Date.now())throw new SecurityInputError('SCOPE_EXPIRED');
      if(input.action==='approve'){
        if(row.status!=='pending' || input.scopeDigest!==row.scope_digest)throw new SecurityInputError('SCOPE_CONFLICT');
        row=(await client.query(`UPDATE security_assessments SET status='approved',approved_by=$2,approved_at=NOW() WHERE id=$1 RETURNING ${columns}`,[row.id,session.username || session.userId])).rows[0];
      } else {
        if(typeof input.xml!=='string')throw new SecurityInputError('INVALID_REQUEST');
        if(row.status==='completed'){
          if(row.result.evidenceSha256!==evidenceHash(input.xml))throw new SecurityInputError('EVIDENCE_CONFLICT');
          await client.query('COMMIT');return row;
        }
        if(row.status!=='approved')throw new SecurityInputError('APPROVAL_REQUIRED');
        const result=parseNmapEvidence(input.xml,row.scope);
        row=(await client.query(`UPDATE security_assessments SET status='completed',result=$2,raw_evidence=$3 WHERE id=$1 RETURNING ${columns}`,[row.id,JSON.stringify(result),encryptFileBuffer(Buffer.from(input.xml,'utf8'))])).rows[0];
      }
    }
    await client.query('INSERT INTO security_assessment_events (id,assessment_id,actor,action) VALUES ($1,$2,$3,$4)',[crypto.randomUUID(),row.id,session.userId,input.action]);
    await client.query('COMMIT');return row;
  } catch(error){await client.query('ROLLBACK');throw error;}finally{client.release();}
}
