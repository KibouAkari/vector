#!/usr/bin/env python3
"""Read-only evidence for the next local assistant rollout. Never activates it."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import zipfile

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
INSTALL = ROOT / 'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf'
EVIDENCE = ROOT / 'releases/vector-fegcraft-general-20261018T070145Z-b27866/result.json'
TESTED = '07dcb2e3d16df6796b5db2a236cd88b7d3bc6f8e'
CATALOG = '214261e4c9184837e4f532dcb6482cc1be8e0b8db0089a130a3e20e7a18df7b8'
MODEL = 'vector-qwen3-instruct2507:4b-q4km'
PYTHON = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
SERVICE = 'vector-fegcraft-assistant'
ADDON = Path('/opt/fegcraft-updated/data/DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar')
ADDON_SHA = '0be86352e50597fc5e8e82742d87bba3ef924b8d1a8c2230c03bc89d261bc671'
ADDON_SOURCE = '5f5eb4185480ea9ea095d37ff1cdb273498f2031'
CLASS = 'com/kibouakari/vector/VectorAddon.class'
NAMES = ('vector-app', 'vector-worker', 'vector-runner', 'vector-postgres', 'vector-redis',
         'vector-privacy-ner', 'vector-local-inference', 'fegcraft-updated', SERVICE)
CASES = frozenset(('piston', 'comparator', 'claims', 'parties', 'party-followup', 'off-topic',
 'other-topic', 'animal-breeding', 'backpack', 'unknown-other-topic', 'unknown-game-topic',
 'glass', 'commands', 'unknown-command', 'seed', 'game-mode', 'cheating', 'live-ownership',
 'carry-on', 'missing-recipe', 'voice-menu', 'voice-group', 'bee-honey', 'parrot',
 'uncovered-specific', 'missing-document', 'claim-chest-paraphrase', 'claim-area-paraphrase',
 'claim-container-paraphrase', 'claim-live-limit', 'backpack-missing-procedure'))
SOURCE_FILES = ('runtime.py', 'server.py', 'stats.py', 'policy.py', 'recipes.py',
                'knowledge.py', 'documentation.py', 'public-knowledge.json')

# Catalog metadata only, never SELECT application rows, password catalogs or DSNs.
# Explicit READ ONLY and bounded execution; no role/ACL changes or advisory lock.
DB_AUDIT = r"""
import pg from 'pg';
const db=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:3000,query_timeout:8000});
try {
 await db.connect();
 await db.query('BEGIN READ ONLY');
 await db.query("SET LOCAL statement_timeout = '5s'");
 await db.query("SET LOCAL lock_timeout = '1s'");
 const {rows}=await db.query(`
 WITH grants AS (
  SELECT 'database' AS scope,a.* FROM pg_database d,
   LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a WHERE d.datname=current_database()
  UNION ALL
  SELECT 'schema',a.* FROM pg_namespace n,
   LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a
   WHERE n.nspname !~ '^pg_(?:temp|toast_temp)_'
  UNION ALL
  SELECT CASE WHEN c.relkind='S' THEN 'sequence' ELSE 'relation' END,a.*
   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
   LATERAL aclexplode(COALESCE(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 's'::"char" ELSE 'r'::"char" END,c.relowner))) a
   WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
  UNION ALL
  SELECT 'column',a.* FROM pg_attribute att JOIN pg_class c ON c.oid=att.attrelid
   JOIN pg_namespace n ON n.oid=c.relnamespace,
   LATERAL aclexplode(att.attacl) a WHERE att.attnum>0 AND NOT att.attisdropped
   AND n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
  UNION ALL
  SELECT 'routine',a.* FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
   LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
   WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
  UNION ALL
  SELECT 'future_default',a.* FROM pg_default_acl d,LATERAL aclexplode(d.defaclacl) a
 )
 SELECT scope,privilege_type,count(*)::int AS count,bool_or(is_grantable) AS grant_option
 FROM grants WHERE grantee=0 GROUP BY scope,privilege_type ORDER BY scope,privilege_type`);
 const role=await db.query(`SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolinherit,rolreplication,rolbypassrls,
  (SELECT count(*)::int FROM pg_auth_members m WHERE m.member=r.oid) AS memberships
  FROM pg_roles r WHERE rolname=$1`,['vector_fegcraft_slot']);
 const definer=await db.query(`SELECT count(*)::int AS count FROM pg_proc p,
  LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
  WHERE p.prosecdef AND a.grantee=0 AND a.privilege_type='EXECUTE'`);
 const authority=await db.query(`SELECT rolsuper,rolcreaterole FROM pg_roles WHERE rolname=current_user`);
 const version=await db.query("SELECT current_setting('server_version_num')::int AS number");
 await db.query('ROLLBACK');
 console.log(JSON.stringify({read_only_catalog_audit:true,server_version_num:version.rows[0].number,
  public_grants:rows,public_security_definer_count:definer.rows[0].count,
  proposed_role_exists:role.rows.length===1,proposed_role_attributes:role.rows[0]??null,
  auditor_can_create_role:authority.rows[0]?.rolsuper===true||authority.rows[0]?.rolcreaterole===true}));
} catch (_) { console.error('READ_ONLY_DATABASE_AUDIT_FAILED');process.exitCode=1; }
finally { await db.end(); }
"""

DRIVER_PROBE = """
import importlib.metadata,json
try:
 import psycopg
 version=importlib.metadata.version('psycopg')
 print(json.dumps({'available':True,'version':version,'binary':psycopg.pq.__impl__=='binary'}))
except ImportError:
 print(json.dumps({'available':False,'version':None,'binary':False}))
"""


def read(path, limit=2_000_000):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('READINESS_SYMLINK')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
        os.close(fd)
        raise RuntimeError('READINESS_FILE_LIMIT')
    with os.fdopen(fd, 'rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise RuntimeError('READINESS_FILE_LIMIT')
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(*args, input=None, timeout=25):
    result = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
    if result.returncode:
        # Child output may contain private configuration; never relay it.
        raise RuntimeError('READINESS_COMMAND_FAILED:' + args[0])
    return result.stdout


def evidence(value):
    fields = ('passed', 'quality_passed', 'latency_passed', 'production_unchanged',
              'cleanup_verified', 'weights_unloaded')
    if (any(value.get(k) is not True for k in fields) or value.get('revision') != TESTED
        or value.get('catalog_sha256') != CATALOG or value.get('model') != MODEL
        or value.get('evaluation_scope') != 'offline-reviewed-passage-selection'
        or value.get('answer_mode') != 'reviewed-extractive'
        or any(value.get(k) is not False for k in ('production_activated', 'eligible_for_activation', 'ledger_writes', 'diagnostic_only',
          'full_knowledge_qualified', 'universal_mod_accuracy_claimed', 'exact_installed_mod_versions_qualified'))
        or any(type(value.get(k)) is not int or value[k] != 0 for k in ('cloud_calls', 'api_cost_chf', 'messages_sent', 'unknown_usage_calls'))):
        raise RuntimeError('READINESS_MODEL_EVIDENCE_MISMATCH')
    cases = value.get('cases')
    if (not isinstance(cases, list) or len(cases) != 31
        or {c.get('id') for c in cases} != CASES or any(c.get('passed') is not True for c in cases)):
        raise RuntimeError('READINESS_MODEL_CASES_MISMATCH')
    actual = [n for c in cases for n in c['native']]
    if (value.get('model_calls') != 17 or len(actual) != 17
        or sum(c['model_calls'] for c in cases) != 17
        or any(n.get('done') is not True or n.get('done_reason') != 'stop' or n.get('model') != MODEL for n in actual)):
        raise RuntimeError('READINESS_NATIVE_CALLS_MISMATCH')
    for key, native in (('input_tokens', 'prompt_eval_count'), ('output_tokens', 'eval_count')):
        if (any(type(n.get(native)) is not int or n[native] < 0 for n in actual)
            or value.get(key) != sum(n[native] for n in actual)
            or value.get('known_' + key) != value.get(key)):
            raise RuntimeError('READINESS_USAGE_MISMATCH')
    times = [c['seconds'] for c in cases if c['model_calls']]
    warm = sorted(times[1:])
    median = (warm[7] + warm[8]) / 2
    if (times[0] > 25 or max(warm) > 12 or median > 8
        or abs(value.get('warm_median_seconds', -100) - median) > .001):
        raise RuntimeError('READINESS_LATENCY_MISMATCH')
    return {'cases': 31, 'native_calls': 17, 'cold_seconds': times[0],
            'warm_median_seconds': value['warm_median_seconds'],
            'input_tokens': value['input_tokens'], 'output_tokens': value['output_tokens']}


def canonical_mounts(mounts):
    # Docker's Mounts array has no precedence semantics. Retain every complete
    # record and duplicate; normalize ONLY this array's enumeration order.
    return sorted(mounts, key=lambda value: json.dumps(value, sort_keys=True))


def snapshot_differences(before, after):
    # Never serialize snapshot values: Config can contain credentials.
    containers = []
    for name in NAMES:
        key = '/' + name
        fields = sorted(field for field in before[key] if before[key][field] != after[key].get(field))
        if fields:
            containers.append({'container': name, 'changed_fields': fields})
    return {'containers': containers, 'changed_file_count': sum(
        before[key] != after.get(key) for key in before if not isinstance(before[key], dict))}


def snapshot():
    values = json.loads(run('docker', 'inspect', *NAMES))
    if len(values) != len(NAMES) or {v['Name'].lstrip('/') for v in values} != set(NAMES):
        raise RuntimeError('READINESS_CONTAINER_SET_MISMATCH')
    result = {}
    for v in values:
        state = v['State']
        if not state['Running'] or state.get('Restarting') or state.get('OOMKilled'):
            raise RuntimeError('READINESS_PRODUCTION_NOT_RUNNING')
        if v['Name'] in ('/fegcraft-updated', '/' + SERVICE) and state.get('Health', {}).get('Status') != 'healthy':
            raise RuntimeError('READINESS_GAME_OR_ASSISTANT_UNHEALTHY')
        result[v['Name']] = {k: v[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')}
        result[v['Name']]['Mounts'] = canonical_mounts(v['Mounts'])
        result[v['Name']]['StartedAt'] = state['StartedAt']
        result[v['Name']]['networks'] = sorted(v['NetworkSettings']['Networks'])
    for path in (Path('/opt/vector/docker-compose.yml'), Path('/opt/fegcraft-updated/docker-compose.yml'),
                 INSTALL/'compose.json', INSTALL/'manifest.json', ADDON):
        result[str(path)] = sha(read(path))
    # This snapshot stays in memory: Config may contain secrets, never serialize it.
    return result


def baseline(before):
    manifest = json.loads(read(INSTALL/'manifest.json'))
    profile_raw = read(INSTALL/'compose.json')
    profile = json.loads(profile_raw)['services']['assistant']
    value = before['/' + SERVICE]
    labels = value['Config'].get('Labels') or {}
    mounts = {(m['Destination'], m.get('Source'), not m.get('RW', False))
              for m in value['Mounts'] if m['Type'] == 'bind'}
    declared = {(m['target'], m['source'], m.get('read_only', False)) for m in profile['volumes']}
    env = dict(item.split('=', 1) for item in value['Config']['Env'] if '=' in item)
    targets = {m['target']: m for m in profile['volumes']}
    input_sources = {'/inputs/stats': '/opt/fegcraft-updated/data/world/players/stats',
      '/inputs/usercache.json': '/opt/fegcraft-updated/data/usercache.json',
      '/inputs/mods.json': str(INSTALL/'mods.json'), '/inputs/recipes.json': str(INSTALL/'recipes.json'),
      '/run/secrets/vector_fegcraft_token': '/opt/fegcraft-updated/data/DiscordIntegration-Data/vector/token'}
    if (set(targets) != set(input_sources) | {'/code', '/state'}
        or any(targets[k]['source'] != source or targets[k].get('read_only') is not True
               for k, source in input_sources.items())
        or targets['/state']['source'] != str(INSTALL/'state') or targets['/state'].get('read_only', False)
        or not re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*', profile.get('user', ''))
        or value['HostConfig'].get('PortBindings')):
        raise RuntimeError('READINESS_ASSISTANT_SCOPE_CHANGED')
    if (value['Image'] != PYTHON or manifest.get('compose_sha256') != sha(profile_raw)
        or labels.get('com.vector.installation') != manifest.get('owner') or not manifest.get('owner')
        or labels.get('com.docker.compose.project') != SERVICE
        or labels.get('com.docker.compose.service') != 'assistant'
        or env.get('VECTOR_FEGCRAFT_KNOWLEDGE') != '0'
        or profile.get('environment', {}).get('VECTOR_FEGCRAFT_KNOWLEDGE') != '0'
        or value['networks'] != ['mc-net'] or mounts != declared
        or value['HostConfig'].get('ReadonlyRootfs') is not True
        or value['Config'].get('User') != profile['user']
        or value['Config'].get('Entrypoint') != profile['entrypoint']):
        raise RuntimeError('READINESS_ASSISTANT_BASELINE_CHANGED')
    code = [m['source'] for m in profile['volumes'] if m['target'] == '/code' and m.get('read_only') is True]
    if len(code) != 1 or manifest.get('backend_revision') != '70f3adc9e6516c4fb4531cf5289a6cd99c29c7b1':
        raise RuntimeError('READINESS_ASSISTANT_CODE_CHANGED')
    for name in ('runtime.py', 'server.py', 'stats.py', 'policy.py', 'recipes.py'):
        expected = run('git', '-C', str(REPO), 'show', manifest['backend_revision'] + ':services/fegcraft-assistant/' + name)
        if read(Path(code[0])/name) != expected:
            raise RuntimeError('READINESS_ASSISTANT_SOURCE_MISMATCH')
    return {'owned_mode_zero_baseline': True, 'read_only_input_mounts_retained': True}


def addon():
    raw = read(ADDON)
    if sha(raw) != ADDON_SHA:
        raise RuntimeError('READINESS_INSTALLED_ADDON_CHANGED')
    # Match the actual installed class to the captured build, not today's Java.
    capture = ROOT/'releases/vector-fegcraft-bridge-evaluation-20261016T224316Z-280627'
    captured = read(capture/'vector-minecraft-0.1.0.jar')
    if sha(captured) != ADDON_SHA:
        raise RuntimeError('READINESS_CAPTURE_ADDON_MISMATCH')
    value = json.loads(read(capture/'result.json'))
    if value.get('passed') is not True or value.get('revision') != ADDON_SOURCE or value.get('cleanup_verified') is not True:
        raise RuntimeError('READINESS_CAPTURE_EVIDENCE_MISMATCH')
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as jar:
        if jar.getinfo(CLASS).file_size > 262144:
            raise RuntimeError('READINESS_ADDON_CLASS_LIMIT')
        jar.read(CLASS)  # CRC verifies the class in the exact captured artifact.
    source = run('git', '-C', str(REPO), 'show', ADDON_SOURCE + ':integrations/fegcraft-addon/src/main/java/com/kibouakari/vector/VectorAddon.java').decode()
    if ('.timeout(Duration.ofSeconds(27))' not in source or 'future.get(27, TimeUnit.SECONDS)' not in source
        or 'subscriber.abort();' not in source or 'future.cancel(true);' not in source):
        raise RuntimeError('READINESS_ADDON_DEADLINE_SOURCE_MISMATCH')
    return {'installed_captured_artifact_matches': True, 'http_wall_deadline_seconds': 27,
            'candidate_computation_deadline_seconds': 24, 'real_chat_qualified': False}


def driver_probe(name, owner):
    try:
        output = run('docker', 'run', '--rm', '--name', name, '--label', 'com.vector.admission-audit=' + owner,
          '--pull', 'never', '--network', 'none', '--user', '65534:65534', '--read-only', '--cap-drop', 'ALL',
          '--security-opt', 'no-new-privileges:true', '--cpus', '1', '--memory', '128m', '--pids-limit', '32',
          '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python3', PYTHON, '-c', DRIVER_PROBE)
        value = json.loads(output)
        if set(value) != {'available', 'version', 'binary'}:
            raise RuntimeError('READINESS_DRIVER_RESULT_INVALID')
        return value
    finally:
        # --rm normally removes it; inspect/remove only our uniquely labelled probe.
        ids = run('docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$').decode().split()
        for identity in ids:
            item = json.loads(run('docker', 'inspect', identity))[0]
            if (item['Config'].get('Labels') or {}).get('com.vector.admission-audit') != owner:
                raise RuntimeError('READINESS_PROBE_OWNERSHIP_CHANGED')
            run('docker', 'rm', '-f', identity)
        if run('docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$').strip():
            raise RuntimeError('READINESS_PROBE_CLEANUP_FAILED')


def audit():
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[a-f0-9]{40}', revision):
        raise RuntimeError('ROOT_AND_IMMUTABLE_PIN_REQUIRED')
    run('git', '-C', str(REPO), 'merge-base', '--is-ancestor', revision, 'origin/main')
    for name in SOURCE_FILES:
        run('git', '-C', str(REPO), 'diff', '--exit-code', TESTED, revision, '--', 'services/fegcraft-assistant/' + name)
    summary = evidence(json.loads(read(EVIDENCE)))
    before = snapshot()
    owned = baseline(before)
    deadline = addon()
    directory = ROOT/'releases'/('vector-fegcraft-admission-readiness-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise RuntimeError('READINESS_REPORT_SYMLINK')
    directory.mkdir(mode=0o700)
    print('Nur Laufzeit-/Berechtigungsprüfung. Keine Installation, Rechteänderung, Modellanfrage oder Spielnachricht.', flush=True)
    result = {'audit_completed': False, 'revision': revision, 'model_evidence': summary,
      'baseline': owned, 'installed_addon': deadline, 'dedicated_role_qualified': False,
      'eligible_for_activation': False, 'production_activated': False,
      'cloud_calls': 0, 'model_calls': 0, 'messages_sent': 0, 'database_writes': False}
    try:
        database = json.loads(run('docker', 'exec', '-i', 'vector-app', 'node', '--input-type=module', '-', input=DB_AUDIT.encode(), timeout=25))
        result['database_catalog'] = database
        driver = driver_probe('vector-admission-probe-' + secrets.token_hex(10), secrets.token_hex(16))
        after = snapshot()
        result.update(driver_in_current_python_image=driver, cleanup_verified=True,
          production_unchanged=after == before, production_differences=snapshot_differences(before, after))
        if not result['production_unchanged']:
            raise RuntimeError('READINESS_PRODUCTION_CHANGED')
        result['audit_completed'] = True
    except Exception:
        result['audit_completed'] = False
        if 'production_unchanged' not in result:
            try:
                after = snapshot()
                result.update(production_unchanged=after == before,
                  production_differences=snapshot_differences(before, after))
            except Exception:
                result.update(production_unchanged=None, production_comparison_unavailable=True)
        (directory/'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print('Report:', directory/'result.json')
        if result.get('production_differences'):
            print(json.dumps({'production_differences': result['production_differences']}))
        raise
    (directory/'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    print('Report:', directory/'result.json')
    print('Prüfung abgeschlossen. Rollen-/Treiber-Qualifikation und geschützter Dienst-Rollout bleiben separat; Minecraft unverändert.')
    return result


def main():
    os.umask(0o077)
    if ROOT.is_symlink() or (ROOT/'.chat-release.lock').is_symlink():
        raise RuntimeError('READINESS_LOCK_SYMLINK')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return audit()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
