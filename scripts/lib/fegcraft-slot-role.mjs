// Deployment-side catalog/role management only. Never imported by the model.
import {isIP} from 'node:net';
export const ROLE='vector_fegcraft_slot';
export const SETTINGS={statement_timeout:'3s',lock_timeout:'1s',idle_in_transaction_session_timeout:'5s',
  idle_session_timeout:'45s',default_transaction_read_only:'on',search_path:'pg_catalog'};
const marker=owner=>'vector-fegcraft-slot:'+owner;
const ident=value=>'"'+value.replaceAll('"','""')+'"';
const literal=value=>"'"+value.replaceAll("'","''")+"'";
function fail(code){const e=new Error(code);e.name='RoleGuardError';e.code=code;throw e;}

export function destination(dsn,fixture=false,privateHost='vector-postgres'){
  const url=new URL(dsn);
  if(!['postgres:','postgresql:'].includes(url.protocol)||!url.username||!url.password||!url.pathname||url.pathname==='/'||url.hash)
    fail('ROLE_DESTINATION_INVALID');
  if(fixture){
    if(url.hostname!=='127.0.0.1'||url.port!=='5433'||url.pathname!=='/vector_admission_fixture'||url.search)fail('ROLE_FIXTURE_REQUIRED');
  }else if(url.hostname!==privateHost||!['','5432'].includes(url.port)||url.search)fail('ROLE_PRIVATE_DATABASE_REQUIRED');
  return url;
}

function privateAddress(value){
  if(typeof value!=='string')return false;
  if(isIP(value)===6)return /^f[cd]/i.test(value);
  if(isIP(value)!==4)return false;
  const [a,b]=value.split('.').map(Number);
  return a===10||a===172&&b>=16&&b<=31||a===192&&b===168;
}

export async function verifyPrivateEndpoint(dsn,endpoint,lookup){
  const url=new URL(dsn),host=url.hostname.replace(/^\[|\]$/g,'');
  // Metadata comes only from host-side inspect of the fixed running container.
  if(!endpoint||endpoint.container!=='vector-postgres'||endpoint.network!=='vector-internal'
    ||!(/^[a-f0-9]{64}$/.test(endpoint.container_id??''))||typeof lookup!=='function'
    ||!Array.isArray(endpoint.aliases)||endpoint.aliases.length>32
    ||endpoint.aliases.some(v=>typeof v!=='string'||!(/^[a-zA-Z0-9_.-]{1,253}$/.test(v)))
    ||!Array.isArray(endpoint.addresses)||!endpoint.addresses.length||endpoint.addresses.length>4
    ||!endpoint.addresses.every(privateAddress))fail('ROLE_PRIVATE_ENDPOINT_PROOF_REQUIRED');
  if(!endpoint.aliases.includes(host)&&!endpoint.addresses.includes(host))fail('ROLE_PRIVATE_ALIAS_REQUIRED');
  destination(dsn,false,url.hostname);
  let rows;
  try{rows=await lookup(host,{all:true});}catch{fail('ROLE_PRIVATE_DNS_UNAVAILABLE');}
  if(!Array.isArray(rows)||!rows.length||rows.length>8||rows.some(row=>!endpoint.addresses.includes(row.address)))
    fail('ROLE_PRIVATE_DNS_MISMATCH');
  return url;
}

async function checkedDestination({dsn,fixture,endpoint,lookup}){
  if(fixture)return destination(dsn,true);
  return verifyPrivateEndpoint(dsn,endpoint,lookup);
}

function inputCheck(owner,password){
  if(!/^[a-f0-9]{32}$/.test(owner)||!(/^[a-f0-9]{64}$/.test(password)))fail('ROLE_PRIVATE_INPUT_INVALID');
}

async function session(dsn,connect,readonly,body){
  const db=connect(dsn);
  try{
    await db.connect();await db.query(readonly?'BEGIN READ ONLY':'BEGIN');
    await db.query("SET LOCAL statement_timeout='5s'");await db.query("SET LOCAL lock_timeout='1s'");
    const result=await body(db);await db.query(readonly?'ROLLBACK':'COMMIT');return result;
  }catch(e){await db.query('ROLLBACK').catch(()=>{});throw e;}
  finally{await db.end();}
}

async function roleRecord(db){
  return (await db.query(`SELECT r.oid,r.rolcanlogin,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolinherit,
    r.rolreplication,r.rolbypassrls,r.rolconnlimit,r.rolvaliduntil,r.rolconfig,
    shobj_description(r.oid,'pg_authid') AS marker,
    (SELECT count(*)::int FROM pg_auth_members m WHERE m.member=r.oid) AS memberships,
    (SELECT count(*)::int FROM pg_shdepend d WHERE d.refclassid='pg_authid'::regclass AND d.refobjid=r.oid AND d.deptype='o') AS owned
    FROM pg_roles r WHERE r.rolname=$1`,[ROLE])).rows[0]??null;
}

function assertOwned(row,owner){
  if(!row||row.marker!==marker(owner))fail('ROLE_FOREIGN_OR_ABSENT');
  if(row.rolcanlogin!==true||['rolsuper','rolcreatedb','rolcreaterole','rolinherit','rolreplication','rolbypassrls'].some(k=>row[k]!==false)
    ||row.rolconnlimit!==2||row.memberships!==0||row.owned!==0||row.rolvaliduntil!==null)fail('ROLE_ATTRIBUTES_CHANGED');
  const expected=Object.entries(SETTINGS).map(([k,v])=>k+'='+v).sort();
  if(JSON.stringify((row.rolconfig??[]).slice().sort())!==JSON.stringify(expected))fail('ROLE_SETTINGS_CHANGED');
}

const GRANTS=`WITH grants AS (
 SELECT 'database' AS scope,a.* FROM pg_database d,LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a WHERE d.datname=current_database()
 UNION ALL SELECT 'schema',a.* FROM pg_namespace n,LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a
 UNION ALL SELECT 'relation',a.* FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
 LATERAL aclexplode(COALESCE(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 's'::"char" ELSE 'r'::"char" END,c.relowner))) a
 WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_(toast|temp)(_|$)'
 UNION ALL SELECT 'column',a.* FROM pg_attribute att JOIN pg_class c ON c.oid=att.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace,
 LATERAL aclexplode(att.attacl) a WHERE att.attnum>0 AND NOT att.attisdropped AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_(toast|temp)(_|$)'
 UNION ALL SELECT 'routine',a.* FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
 LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE n.nspname NOT IN ('pg_catalog','information_schema')
 UNION ALL SELECT 'security_definer',a.* FROM pg_proc p,LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE p.prosecdef
 UNION ALL SELECT 'large_object',a.* FROM pg_largeobject_metadata o,LATERAL aclexplode(COALESCE(o.lomacl,acldefault('L',o.lomowner))) a
 UNION ALL SELECT 'foreign_server',a.* FROM pg_foreign_server s,LATERAL aclexplode(COALESCE(s.srvacl,acldefault('S',s.srvowner))) a
 UNION ALL SELECT 'foreign_wrapper',a.* FROM pg_foreign_data_wrapper w,LATERAL aclexplode(COALESCE(w.fdwacl,acldefault('F',w.fdwowner))) a
 UNION ALL SELECT 'tablespace',a.* FROM pg_tablespace t,LATERAL aclexplode(COALESCE(t.spcacl,acldefault('t',t.spcowner))) a
 UNION ALL SELECT 'parameter',a.* FROM pg_parameter_acl p,LATERAL aclexplode(p.paracl) a
 UNION ALL SELECT 'future_data',a.* FROM pg_default_acl d,LATERAL aclexplode(d.defaclacl) a WHERE d.defaclobjtype IN ('r','S')
 ) SELECT scope,privilege_type,count(*)::int AS count,bool_or(is_grantable) AS grant_option FROM grants
 WHERE grantee=ANY($1::oid[]) GROUP BY scope,privilege_type ORDER BY scope,privilege_type`;

export function assertGrants(rows){
  for(const row of rows){
    const allowed=row.scope==='database'&&['CONNECT','TEMPORARY'].includes(row.privilege_type)
      ||row.scope==='schema'&&row.privilege_type==='USAGE';
    if(!allowed||row.grant_option)fail('ROLE_UNSAFE_PUBLIC_OR_DIRECT_GRANTS');
  }
}

async function auditCluster(dsn,connect,oid){
  const list=await session(dsn,connect,true,async db=>(await db.query(
    'SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname')).rows);
  if(!list.length||list.length>8)fail('ROLE_DATABASE_INVENTORY_REVIEW_REQUIRED');
  let checked=0,currentTemp=false;
  const current=new URL(dsn);const ids=oid===null?[0]:[0,oid];
  for(const {datname} of list){
    const url=new URL(dsn);url.pathname='/'+encodeURIComponent(datname);
    await session(url.href,connect,true,async db=>{
      assertGrants((await db.query(GRANTS,[ids])).rows);
      if(oid!==null){
        const row=(await db.query('SELECT has_database_privilege($1::oid,oid,\'CONNECT\') AS connect,has_database_privilege($1::oid,oid,\'TEMP\') AS temp FROM pg_database WHERE datname=current_database()',[oid])).rows[0];
        if(datname===decodeURIComponent(current.pathname.slice(1))){if(!row.connect)fail('ROLE_CONNECT_MISSING');currentTemp=row.temp;}
      }
      checked++;
    });
  }
  return {checked_databases:checked,no_application_object_privileges:true,no_permanent_create_privileges:true,
    no_security_definer_or_foreign_access:true,inherited_public_temp:oid===null?null:currentTemp,
    system_catalog_access_retained:true,global_public_acl_changed:false};
}

export async function prepareRole({dsn,owner,password,fixture=false,connect,endpoint,lookup}){
  inputCheck(owner,password);await checkedDestination({dsn,fixture,endpoint,lookup});
  const old=await session(dsn,connect,true,async db=>{
    if((await db.query("SELECT current_setting('server_version_num')::int AS version")).rows[0].version!==170011)
      fail('ROLE_DATABASE_VERSION_CHANGED');
    return roleRecord(db);
  });
  if(old)assertOwned(old,owner);
  await auditCluster(dsn,connect,old?.oid??null);
  let created=false;
  if(!old){
    await session(dsn,connect,false,async db=>{
      if(await roleRecord(db))fail('ROLE_CREATED_CONCURRENTLY');
      await db.query("SET LOCAL password_encryption='scram-sha-256'");
      // Both values have fixed hex alphabets; SQL identifiers remain fixed.
      await db.query('CREATE ROLE '+ident(ROLE)+' LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD '+literal(password));
      await db.query('COMMENT ON ROLE '+ident(ROLE)+' IS '+literal(marker(owner)));
      for(const [key,value] of Object.entries(SETTINGS))await db.query('ALTER ROLE '+ident(ROLE)+' SET '+ident(key)+' TO '+literal(value));
      const name=(await db.query('SELECT current_database() AS name')).rows[0].name;
      await db.query('GRANT CONNECT ON DATABASE '+ident(name)+' TO '+ident(ROLE));
    });created=true;
  }
  const row=await session(dsn,connect,true,db=>roleRecord(db));assertOwned(row,owner);
  const privileges=await auditCluster(dsn,connect,row.oid);
  const url=new URL(dsn);url.username=ROLE;url.password=password;url.search='';
  return {created,owned:true,privileges,dsn:url.href};
}

export async function rollbackRole({dsn,owner,password,fixture=false,connect,endpoint,lookup}){
  inputCheck(owner,password);await checkedDestination({dsn,fixture,endpoint,lookup});
  return session(dsn,connect,false,async db=>{
    const row=await roleRecord(db);
    if(!row)return {removed:false,already_absent:true};
    assertOwned(row,owner);
    if((await db.query('SELECT count(*)::int AS count FROM pg_stat_activity WHERE usename=$1',[ROLE])).rows[0].count!==0)fail('ROLE_ACTIVE_CONNECTIONS_REFUSE_ROLLBACK');
    const name=(await db.query('SELECT current_database() AS name')).rows[0].name;
    await db.query('REVOKE CONNECT ON DATABASE '+ident(name)+' FROM '+ident(ROLE));
    // No DROP OWNED/CASCADE: unexpected grants/dependencies must block deletion.
    await db.query('DROP ROLE '+ident(ROLE));
    return {removed:true,already_absent:false};
  });
}
