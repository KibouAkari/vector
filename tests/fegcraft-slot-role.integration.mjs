// Actual PG17 CI only; no production destination, cloud or model credentials.
import assert from 'node:assert/strict';
import pg from 'pg';
import {spawn} from 'node:child_process';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import {once} from 'node:events';
import {ROLE,prepareRole,rollbackRole,destination} from '../scripts/lib/fegcraft-slot-role.mjs';

assert.equal(process.env.CI,'true','disposable CI required');
const dsn=process.env.VECTOR_ADMISSION_FIXTURE_DSN;
destination(dsn,true);
const connect=url=>new pg.Client({connectionString:url,connectionTimeoutMillis:3000,query_timeout:6000});
const admin=connect(dsn);await admin.connect();
const owner='1'.repeat(32),password='2'.repeat(64);
const args={dsn,owner,password,fixture:true,connect};
const slot='6194261933202610';
const dir=await mkdtemp(path.join(os.tmpdir(),'vector-slot-role-'));
let role,held,child;
async function absent(){assert.equal((await admin.query('SELECT count(*)::int AS n FROM pg_roles WHERE rolname=$1',[ROLE])).rows[0].n,0);}
async function denied(sql){await assert.rejects(role.query(sql),e=>e.code==='42501');}
function launch(mode,file){
  const process=spawn('/tmp/vector-admission-driver-ci/bin/python',['tests/fegcraft-slot-role-probe.py',mode,file],{stdio:['pipe','pipe','pipe']});
  let errors='';process.stderr.on('data',d=>{errors+=d;});
  const lines=readline.createInterface({input:process.stdout})[Symbol.asyncIterator]();
  const ended=once(process,'exit');
  return {process,ended,async line(){const result=await Promise.race([lines.next(),new Promise((_,reject)=>{
    const timer=setTimeout(()=>reject(Error('role probe deadline')),16000);timer.unref();
  })]);assert.equal(result.done,false,errors);return JSON.parse(result.value);}};
}
try{
  await absent();
  const version=(await admin.query('SHOW server_version_num')).rows[0].server_version_num;
  assert.ok(version.startsWith('17'));
  const publicQuery=`SELECT d.oid,a.privilege_type,a.is_grantable FROM pg_database d,
    LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a WHERE a.grantee=0 ORDER BY d.oid,a.privilege_type`;
  const publicBefore=(await admin.query(publicQuery)).rows;
  await admin.query('CREATE SCHEMA vector_role_test');
  await admin.query('GRANT USAGE ON SCHEMA vector_role_test TO PUBLIC');
  await admin.query('CREATE TABLE vector_role_test.private_data (secret text)');
  await admin.query('INSERT INTO vector_role_test.private_data VALUES (\'synthetic\')');
  await admin.query('GRANT SELECT ON vector_role_test.private_data TO PUBLIC');
  await assert.rejects(prepareRole(args),/UNSAFE_PUBLIC/);await absent();
  await admin.query('REVOKE SELECT ON vector_role_test.private_data FROM PUBLIC');

  const prepared=await prepareRole(args);
  assert.equal(prepared.created,true);assert.equal(prepared.privileges.inherited_public_temp,true);
  assert.ok(prepared.privileges.checked_databases>=3,'include connectable template1 and postgres');
  assert.equal((await prepareRole(args)).created,false,'idempotent owned resume');
  await assert.rejects(prepareRole({...args,owner:'3'.repeat(32)}),/FOREIGN/);
  await assert.rejects(rollbackRole({...args,owner:'3'.repeat(32)}),/FOREIGN/);
  role=connect(prepared.dsn);await role.connect();
  await role.query('SET default_transaction_read_only=off');
  await denied('SELECT secret FROM vector_role_test.private_data');
  await denied('CREATE SCHEMA vector_unwanted');
  await denied('CREATE TABLE public.vector_unwanted (x int)');
  await denied('CREATE ROLE vector_unwanted');
  await role.query('CREATE TEMP TABLE vector_allowed_temp (x int)');
  await role.query('DROP TABLE vector_allowed_temp');
  await assert.rejects(rollbackRole(args),/ACTIVE_CONNECTIONS/);
  await role.end();role=null;

  // An explicit column grant in another accessible DB must block resumption.
  const otherURL=new URL(dsn);otherURL.pathname='/postgres';
  const other=connect(otherURL.href);await other.connect();
  try{
    await other.query('CREATE TABLE public.vector_role_other_test (private_value text)');
    await other.query('GRANT SELECT(private_value) ON public.vector_role_other_test TO '+ROLE);
    await assert.rejects(prepareRole(args),/UNSAFE_PUBLIC/);
    await other.query('REVOKE SELECT(private_value) ON public.vector_role_other_test FROM '+ROLE);
    await other.query('CREATE FUNCTION public.vector_role_definer_test() RETURNS int LANGUAGE sql SECURITY DEFINER AS $$ SELECT 1 $$');
    await assert.rejects(prepareRole(args),/UNSAFE_PUBLIC/);
  }finally{
    await other.query('DROP FUNCTION IF EXISTS public.vector_role_definer_test()');
    await other.query('DROP TABLE IF EXISTS public.vector_role_other_test');await other.end();
  }

  // Unexpected dependencies are not silently revoked or cascaded by rollback.
  await admin.query('GRANT SELECT(secret) ON vector_role_test.private_data TO '+ROLE);
  await assert.rejects(rollbackRole(args),e=>e.code==='2BP01');
  assert.equal((await admin.query('SELECT has_database_privilege($1,current_database(),\'CONNECT\') AS ok',[ROLE])).rows[0].ok,true);
  await admin.query('REVOKE SELECT(secret) ON vector_role_test.private_data FROM '+ROLE);

  const file=path.join(dir,'dsn');await writeFile(file,prepared.dsn,{mode:0o400});
  child=launch('ping',file);assert.equal((await child.line()).passed,true);assert.equal((await child.ended)[0],0);child=null;
  await admin.query('SELECT pg_advisory_lock($1::bigint)',[slot]);held=true;
  child=launch('busy',file);assert.deepEqual(await child.line(),{passed:true,shared_slot_busy_verified:true});assert.equal((await child.ended)[0],0);child=null;
  await admin.query('SELECT pg_advisory_unlock($1::bigint)',[slot]);held=false;
  child=launch('hold',file);assert.deepEqual(await child.line(),{ready:true});
  assert.equal((await admin.query('SELECT pg_try_advisory_lock($1::bigint) AS ok',[slot])).rows[0].ok,false);
  child.process.stdin.end('release\n');assert.deepEqual(await child.line(),{passed:true,shared_slot_released:true});
  assert.equal((await child.ended)[0],0);child=null;
  assert.equal((await admin.query('SELECT pg_try_advisory_lock($1::bigint) AS ok',[slot])).rows[0].ok,true);held=true;
  await admin.query('SELECT pg_advisory_unlock($1::bigint)',[slot]);held=false;
  assert.deepEqual(await rollbackRole(args),{removed:true,already_absent:false});await absent();
  assert.deepEqual(await rollbackRole(args),{removed:false,already_absent:true});
  assert.deepEqual((await admin.query(publicQuery)).rows,publicBefore,'global PUBLIC database ACLs unchanged');
  await admin.query('CREATE ROLE '+ROLE+' NOLOGIN');
  await assert.rejects(prepareRole(args),/FOREIGN/);await assert.rejects(rollbackRole(args),/FOREIGN/);
  await admin.query('DROP ROLE '+ROLE);
  console.log(JSON.stringify({passed:true,actual_postgresql_17:true,role_create_resume_rollback:true,
    app_data_and_permanent_create_denied:true,other_database_column_and_definer_grants_rejected:true,
    inherited_public_temp:true,shared_python_slot_both_directions:true,global_public_acl_changed:false}));
}finally{
  if(child){child.process.kill();await child.ended.catch(()=>{});}
  if(role)await role.end();
  if(held)await admin.query('SELECT pg_advisory_unlock($1::bigint)',[slot]);
  await admin.query('DROP SCHEMA IF EXISTS vector_role_test CASCADE');
  const exists=(await admin.query('SELECT 1 FROM pg_roles WHERE rolname=$1',[ROLE])).rowCount;
  if(exists)await rollbackRole(args).catch(()=>{});
  await admin.end();await rm(dir,{recursive:true,force:true});
}
