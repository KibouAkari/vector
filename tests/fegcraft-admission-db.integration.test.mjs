import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import test from 'node:test';
import pg from 'pg';

test('read-only admission audit counts PUBLIC grants without exposing application rows or changing ACLs',async()=>{
  assert.equal(process.env.CI,'true','run only against the disposable CI database');
  assert.match(process.env.DATABASE_URL??'',/@127\.0\.0\.1:5432\/vector_ci$/);
  const db=new pg.Client({connectionString:process.env.DATABASE_URL});
  await db.connect();
  const schema='vector_admission_'+randomBytes(8).toString('hex');
  const audit=execFileSync('python3',['-c',
    "import ast;from pathlib import Path;t=ast.parse(Path('scripts/diagnostics/fegcraft-admission-readiness.py').read_text());print(next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DB_AUDIT' for x in n.targets)))"],{encoding:'utf8'});
  const invoke=()=>JSON.parse(execFileSync(process.execPath,['--input-type=module','-e',audit],
    {encoding:'utf8',timeout:20000,env:process.env}));
  const count=(r,scope,privilege)=>r.public_grants.find(g=>g.scope===scope&&g.privilege_type===privilege)?.count??0;
  const before=invoke();
  try {
    await db.query(`CREATE SCHEMA ${schema}`);
    await db.query(`GRANT USAGE, CREATE ON SCHEMA ${schema} TO PUBLIC`);
    await db.query(`CREATE TABLE ${schema}.private_fixture (a text,b text)`);
    await db.query(`INSERT INTO ${schema}.private_fixture VALUES ('synthetic-secret-not-for-report','synthetic-other')`);
    await db.query(`GRANT SELECT (a) ON ${schema}.private_fixture TO PUBLIC`);
    await db.query(`CREATE TABLE ${schema}.whole_fixture (a int)`);
    await db.query(`GRANT SELECT ON ${schema}.whole_fixture TO PUBLIC`);
    await db.query(`CREATE SEQUENCE ${schema}.sequence_fixture`);
    await db.query(`GRANT USAGE ON SEQUENCE ${schema}.sequence_fixture TO PUBLIC`);
    await db.query(`CREATE FUNCTION ${schema}.fixture() RETURNS integer LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'`);
    await db.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema} GRANT SELECT ON TABLES TO PUBLIC`);
    const result=invoke();
    assert.equal(result.read_only_catalog_audit,true);
    assert.equal(count(result,'schema','CREATE'),count(before,'schema','CREATE')+1);
    assert.equal(count(result,'column','SELECT'),count(before,'column','SELECT')+1);
    assert.equal(count(result,'relation','SELECT'),count(before,'relation','SELECT')+1);
    assert.equal(count(result,'sequence','USAGE'),count(before,'sequence','USAGE')+1);
    assert.equal(count(result,'routine','EXECUTE'),count(before,'routine','EXECUTE')+1);
    assert.equal(count(result,'future_default','SELECT'),count(before,'future_default','SELECT')+1);
    assert.equal(result.public_security_definer_count,before.public_security_definer_count+1);
    assert.ok(!JSON.stringify(result).includes(schema));
    assert.ok(!JSON.stringify(result).includes('synthetic-secret'));
    assert.deepEqual(invoke(),result,'the audit must not change ACLs or create its proposed role');
  } finally {
    await db.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema} REVOKE SELECT ON TABLES FROM PUBLIC`).catch(()=>{});
    await db.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);
    await db.end();
  }
});
