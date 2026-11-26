import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';
import pg from 'pg';
import {sourceUrl,SourceError} from '../lib/source-fetch.mjs';
import {extractSourceText} from '../lib/source-extract.mjs';
const url=new URL(process.env.DATABASE_URL || 'postgres://missing');
if(process.env.CI!=='true' || !['127.0.0.1','localhost'].includes(url.hostname) || url.pathname!=='/vector_ci') throw Error('Refusing source integration tests outside isolated CI.');
const load=(path,deps,names)=>new Function(...Object.keys(deps),readFileSync(new URL(path,import.meta.url),'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'')+`\nreturn {${names.join(',')}};`)(...Object.values(deps));

test('retained source import, index and recovery on real PostgreSQL',async t=>{
  const schema='sources_fixture_'+crypto.randomBytes(8).toString('hex');
  const admin=new pg.Pool({connectionString:url.toString(),max:1});
  const pool=new pg.Pool({connectionString:url.toString(),max:4,options:`-c search_path=${schema}`});
  let failIndex=false, uncertainCommit=false, allowed=true, calls=0, waitFetch;
  const stored=new Map();
  const db={query:(...args)=>pool.query(...args),connect:async()=>{
    const client=await pool.connect();
    let materializing=false;
    return {release:()=>client.release(),query:async(sql,params)=>{
      if(/INSERT INTO project_files/.test(sql)) materializing=true;
      if(sql==='COMMIT' && materializing && uncertainCommit) {await client.query(sql,params);throw Error('lost commit acknowledgement');}
      if(failIndex && /INSERT INTO project_file_chunks/.test(sql))throw Error('injected index failure');
      return client.query(sql,params);
    }};
  }};
  try {
    await admin.query(`CREATE SCHEMA ${schema}`);
    await pool.query(`CREATE TABLE projects(id TEXT PRIMARY KEY,privacy_level TEXT);
      CREATE TABLE conversations(id TEXT PRIMARY KEY); CREATE TABLE tasks(id TEXT PRIMARY KEY);
      CREATE TABLE project_files(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),original_name TEXT,
        stored_name TEXT,mime_type TEXT,extension TEXT,size_bytes BIGINT,sha256 TEXT,previewable BOOLEAN,source_snapshot BOOLEAN);
      INSERT INTO projects VALUES ('p','internal'),('other','internal'),('local','local_only');`);
    const index=load('../lib/project-index.js',{crypto,db,initializeDatabase:async()=>{}},['initializeProjectIndex','replaceProjectTextChunks','searchProjectChunks']);
    const deps={crypto,db,canEditProject:async()=>allowed,initializeFileDatabase:async()=>{},...index,
      writeEncryptedFile:async({fileId,buffer})=>{stored.set(fileId,buffer);return {storedName:fileId};},
      removeEncryptedFile:async({stored_name})=>stored.delete(stored_name),encryptFileBuffer:buffer=>Buffer.concat([Buffer.from('encrypted fixture:'),buffer]),
      sourceUrl,SourceError,extractSourceText,fetchPublicSource:async value=>{
        calls++;if(waitFetch)await waitFetch;
        return {buffer:Buffer.from('<title>Fixture</title><p>Research evidence with a unique phrase.</p>'),mimeType:'text/html',finalUrl:value,fetchedAt:new Date().toISOString()};
      }};
    const api=load('../lib/project-sources.js',deps,['importProjectSource','listProjectSources','sourceEvidenceForFiles','isImportedSourceFile']);
    const session={userId:'owner'};
    const run=(options={})=>api.importProjectSource({projectId:'p',session,url:'https://docs.example.org/article',requestId:crypto.randomUUID(),...options});
    let first;
    await t.test('success retains snapshot provenance and an immutable searchable text file',async()=>{
      first=await run();assert.equal(first.status,'indexed');assert.equal(first.method,'static-html-text-v1');
      assert.ok(first.rawSha256);assert.ok(await api.isImportedSourceFile(first.fileId));
      const chunks=await index.searchProjectChunks({projectId:'p',query:'evidence'});
      assert.equal(chunks[0].file_id,first.fileId);
      const evidence=await api.sourceEvidenceForFiles('p',[first.fileId]);assert.equal(evidence.get(first.fileId).rawSha256,first.rawSha256);
      assert.equal((await api.sourceEvidenceForFiles('other',[first.fileId])).size,0);
      const raw=await pool.query('SELECT raw_snapshot FROM project_sources WHERE id=$1',[first.id]);assert.ok(raw.rows[0].raw_snapshot.length>20);
    });
    await t.test('replaying an idempotency key never refetches or adds another file',async()=>{
      const row=(await pool.query('SELECT request_id FROM project_sources WHERE id=$1',[first.id])).rows[0];
      const count=calls;assert.equal((await run({requestId:row.request_id})).id,first.id);assert.equal(calls,count);
    });
    let failed;
    await t.test('failed index writes retain only a failed source record and clean the new staged file',async()=>{
      const before=(await pool.query('SELECT COUNT(*)::int AS n FROM project_files')).rows[0].n;
      failIndex=true;await assert.rejects(run(),{code:'IMPORT_FAILED'});failIndex=false;
      failed=(await pool.query("SELECT * FROM project_sources WHERE status='failed'")).rows[0];
      assert.equal(failed.file_id,null);assert.equal(stored.size,before);
      assert.equal((await pool.query('SELECT COUNT(*)::int AS n FROM project_files')).rows[0].n,before);
    });
    await t.test('retry claims the saved URL and cannot move a source between projects',async()=>{
      await pool.query("UPDATE project_sources SET started_at=NOW()-INTERVAL '40 seconds' WHERE id=$1",[failed.id]);
      const recovered=await run({sourceId:failed.id,requestId:undefined,url:undefined});
      assert.equal(recovered.status,'indexed');assert.equal(recovered.attempts,2);
      await assert.rejects(run({projectId:'other',sourceId:failed.id,requestId:undefined,url:undefined}),{code:'RETRY_UNAVAILABLE'});
    });
    await t.test('local-only policy blocks fetches before any network operation',async()=>{
      const before=calls;await assert.rejects(run({projectId:'local'}),{code:'LOCAL_ONLY_PROJECT'});assert.equal(calls,before);
    });
    await t.test('concurrent import gets an explicit busy result, then revocation blocks materialization',async()=>{
      let release;waitFetch=new Promise(r=>{release=r;});
      const pending=run();
      while(calls<4)await new Promise(r=>setTimeout(r,5));
      try {await assert.rejects(run(),{code:'IMPORT_BUSY'});allowed=false;}
      finally{release();waitFetch=null;}
      await assert.rejects(pending,{code:'ACCESS_REVOKED'});allowed=true;
    });
    await t.test('a lost commit acknowledgement never deletes a committed evidence file',async()=>{
      uncertainCommit=true;
      await assert.rejects(run(),{code:'IMPORT_FAILED'});
      uncertainCommit=false;
      const rows=(await pool.query("SELECT file_id FROM project_sources WHERE status='indexed'")).rows;
      assert.ok(rows.length>=3);
      for(const row of rows)assert.ok(stored.has(row.file_id));
    });
  } finally {await pool.end();await admin.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);await admin.end();}
});
