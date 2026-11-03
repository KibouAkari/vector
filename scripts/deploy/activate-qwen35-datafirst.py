#!/usr/bin/env python3
"""Owned coherent assistant activation with a bounded 2-to-4 CPU migration."""
import argparse
import ast
import base64
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import uuid


def load(path, name):
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('UNSAFE_HELPER')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private(path, guard):
    path = guard.checked_path(str(path))
    meta = path.stat()
    if meta.st_uid != os.getuid() or not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077 or meta.st_size > 2000000:
        raise RuntimeError('OWNED_PRIVATE_EVIDENCE_REQUIRED')
    return json.loads(path.read_bytes())


def switch_factory(text):
    """Change exactly the dialogue import in main; preserve all installed bindings."""
    tree = ast.parse(text)
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main']
    if len(mains) != 1:
        raise RuntimeError('UNIQUE_MAIN_REQUIRED')
    nodes = [n for n in ast.walk(mains[0]) if isinstance(n, ast.ImportFrom)
             and n.module == 'dialogue' and len(n.names) == 1
             and n.names[0].name == 'GroundedDialogue' and n.names[0].asname is None]
    if len(nodes) != 1:
        raise RuntimeError('UNIQUE_INSTALLED_DIALOGUE_IMPORT_REQUIRED')
    node = nodes[0]
    lines = text.encode().splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno-1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno-1])) + node.end_col_offset
    result = (text.encode()[:start] + b'from datafirst import DataFirstDialogue as GroundedDialogue' + text.encode()[end:])
    ast.parse(result)
    return result


def restore_cpu(guard, prep, resources, inference):
    row = guard.inventory()[inference]
    if (list(guard.identity(row)) != resources['identity']
            or fingerprint(guard, prep, row) != resources['non_cpu_fingerprint']
            or row['HostConfig'].get('NanoCpus') not in (2000000000, 4000000000)):
        raise RuntimeError('CPU_RESTORE_OWNERSHIP_DRIFT')
    if row['HostConfig']['NanoCpus'] == 4000000000:
        guard.run(['docker', 'update', '--cpus', '2', row['Id']])
    final = guard.inventory()[inference]
    if final['HostConfig']['NanoCpus'] != 2000000000:
        raise RuntimeError('CPU_RESTORE_FAILED')


def fingerprint(guard, prep, row):
    value = copy.deepcopy(row)
    value['HostConfig'].pop('NanoCpus', None)
    return prep.configuration(guard, value)


BOOTSTRAP = r'''
import base64,io,json,sys,tempfile
from pathlib import Path
payload=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='vector-coherent-code-',dir=payload.get('temporary_parent')) as directory:
    root=Path(directory)
    for name,value in payload.pop('files').items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('UNSAFE_CODE_PATH')
        path=root/relative
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(value,validate=True))
    payload['candidate_code']=str(root)
    program=payload.pop('integration')
    sys.dont_write_bytecode=True;sys.stdin=io.StringIO(json.dumps(payload))
    exec(compile(program,'<coherent-candidate>','exec'))
'''


def candidate_run(guard, evaluation, process, container, payload, directory, stem):
    evaluation_id=uuid.uuid4().hex
    child=None
    try:
        try:
            child=subprocess.run(['docker','exec','-i',container,'python3','-c',evaluation.WATCHDOG],
                input=json.dumps(dict(payload,program=BOOTSTRAP,evaluation_id=evaluation_id)).encode(),
                capture_output=True,timeout=240,start_new_session=True)
        except subprocess.TimeoutExpired as exc:
            from types import SimpleNamespace
            child=SimpleNamespace(stdout=exc.stdout or b'',stderr=exc.stderr or b'',returncode=124)
        finally:
            if child is not None:
                guard.write_private(directory/(stem+'.stdout'),child.stdout)
                guard.write_private(directory/(stem+'.stderr'),child.stderr)
    finally:process.ensure_native_terminated(container,evaluation_id)
    return child


def main():
    parser = argparse.ArgumentParser()
    for key in ('guard-helper', 'prepare-helper', 'process-helper', 'evaluation-helper',
                'release-helper', 'preparation', 'source-root', 'workspace-root', 'lock-file'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    sys.dont_write_bytecode = True
    guard = load(args.guard_helper, 'qwen35_guard')
    prep = load(args.prepare_helper, 'qwen35_preparation')
    process = load(args.process_helper, 'qwen35_process')
    evaluation = load(args.evaluation_helper, 'qwen35_evaluation')
    release_helper = load(args.release_helper, 'qwen35_release')
    lock_path = guard.checked_path(str(args.lock_file))
    fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
        os.close(fd);raise RuntimeError('OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(fd, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            directory = guard.checked_path(str(args.rollback), directory=True)
            resources = private(directory/'resources.json', guard)
            guard.rollback(directory)
            restore_cpu(guard, prep, resources, resources['inference'])
            return
        if not args.activate:
            raise RuntimeError('EXPLICIT_ACTIVATION_REQUIRED')
        evidence = private(args.preparation/'result.json', guard)
        op = prep.operator(args.preparation/'operator.json', guard)
        before = guard.inventory()
        row, inference = before[op['assistant']], before[op['inference']]
        initial = prep.metadata(op['assistant']);prep.verify_model(initial)
        if (evidence.get('prepared') is not True or initial['sources'] != op['source_hashes']
                or initial['manifest_digest'] != evidence.get('manifest_digest')
                or list(guard.identity(inference)) != evidence.get('inference_identity')):
            raise RuntimeError('PREPARATION_OR_SOURCE_DRIFT')
        if (inference['HostConfig'].get('NanoCpus') != 2000000000 or inference['HostConfig']['Memory'] != prep.TARGET
                or inference['HostConfig'].get('MemorySwap')!=evidence.get('actual_memory_swap_bytes')):
            raise RuntimeError('OWNED_TWO_CPU_24_GIB_BASELINE_REQUIRED')
        labels = row['Config']['Labels']
        active = guard.checked_path(labels['com.docker.compose.project.config_files'])
        original = active.read_bytes()
        config = dict(schema=1, container=op['assistant'], service=labels['com.docker.compose.service'],
            compose=str(active), project_directory=labels['com.docker.compose.project.working_dir'],
            expected_project_name=labels['com.docker.compose.project'], expected_image=row['Image'],
            expected_runtime_sha256=op['source_hashes']['runtime.py'], expected_compose_sha256=guard.digest(original))
        profile = guard.compose(config, active)
        config['expected_profile_sha256'] = guard.digest(guard.canonical(profile))
        installed = guard.validate_live(config, before, profile)
        modes=[n.args[0].value for n in ast.walk(ast.parse((installed/'server.py').read_text()))
            if isinstance(n,ast.Call) and ast.unparse(n.func)=='os.environ.get'
            and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str)
            and n.args[0].value.endswith('_KNOWLEDGE')]
        if len(modes)!=1 or profile['services'][config['service']].get('environment',{}).get(modes[0])!='6':
            raise RuntimeError('EXISTING_MODE6_REQUIRED')
        for name in (op['assistant'], op['inference'], *op['protected']):
            state = before[name]['State']
            if not state['Running'] or state.get('OOMKilled') or state.get('Health', {}).get('Status') not in (None, 'healthy'):
                raise RuntimeError('HEALTHY_REQUIRED_SERVICES_NEEDED')
        if row['Config'].get('User', '').split(':')[0] in ('', '0', 'root'):
            raise RuntimeError('UNPRIVILEGED_ASSISTANT_REQUIRED')
        directory = guard.checked_path(str(args.workspace_root/'releases'), directory=True)/('qwen35-activation-'+uuid.uuid4().hex)
        directory.mkdir(mode=0o700);guard.COMMAND_EVIDENCE=directory
        print('Aktivierung und Rückrollbelege: '+str(directory), flush=True)
        code = directory/'code'
        shutil.copytree(installed, code, ignore=shutil.ignore_patterns('__pycache__'))
        original_files = guard.tree_files(installed)
        source = args.source_root/'services/minecraft-assistant'
        for name in ('runtime.py', 'dialogue.py', 'portraits.py', 'stats.py', 'recipes.py', 'modrecipes.py',
                     'datafirst.py', 'documentation.py', 'knowledge.py', 'companion.py', 'policy.py'):
            raw = guard.checked_path(str(source/name)).read_bytes();ast.parse(raw)
            if name == 'runtime.py':
                raw = guard.preserve_joke((installed/name).read_text(),
                    guard.preserve_server_literals((installed/name).read_text(), raw.decode()))
            (code/name).write_bytes(raw)
        (code/'server.py').write_bytes(switch_factory((installed/'server.py').read_text()))
        for path in [code, *code.rglob('*')]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        files = guard.tree_files(code)
        candidate = guard.changed_profile(profile, config['service'], code)
        candidate_raw = json.dumps(candidate, indent=2).replace('$', '$$').encode()+b'\n'
        record = dict(original_identity=guard.identity(row), original_code=str(installed), original_files=original_files,
            candidate_code=str(code), candidate_files=files, other_containers=guard.others(before, op['assistant']),
            candidate_compose_sha256=guard.digest(candidate_raw), candidate_profile_sha256=guard.digest(guard.canonical(candidate)))
        resources = dict(inference=op['inference'], identity=list(guard.identity(inference)),
            original_cpu=2000000000, target_cpu=4000000000, non_cpu_fingerprint=fingerprint(guard, prep, inference))
        for name, value in (('operator.json', config), ('record.json', record), ('resources.json', resources)):
            guard.write_private(directory/name, guard.canonical(value))
        guard.write_private(directory/'compose.original', original)
        guard.write_private(directory/'compose.candidate.json', candidate_raw)
        if guard.compose(config, directory/'compose.candidate.json') != candidate:
            raise RuntimeError('CANDIDATE_PROFILE_RENDER_CHANGED')
        helpers = {'guard.py':args.guard_helper,'prepare.py':args.prepare_helper,'process.py':args.process_helper,
            'evaluation.py':args.evaluation_helper,'release.py':args.release_helper,'deploy.py':Path(__file__)}
        for name, path in helpers.items():guard.write_private(directory/name, path.read_bytes())
        rollback_args=[str(directory/'deploy.py'),'--guard-helper',str(directory/'guard.py'),
            '--prepare-helper',str(directory/'prepare.py'),'--process-helper',str(directory/'process.py'),
            '--evaluation-helper',str(directory/'evaluation.py'),'--release-helper',str(directory/'release.py'),
            '--preparation',str(args.preparation),'--source-root',str(args.source_root),
            '--workspace-root',str(args.workspace_root),'--lock-file',str(args.lock_file),'--rollback',str(directory)]
        launcher='#!/usr/bin/env python3\nimport runpy,sys\nsys.dont_write_bytecode=True\nsys.argv='+repr(rollback_args)+'\nrunpy.run_path(sys.argv[0],run_name="__main__")\n'
        guard.write_private(directory/'rollback.py', launcher.encode())
        print('Rollback: python3 '+str(directory/'rollback.py'), flush=True)
        cpu_attempted=False;activated=False;phase='preflight'
        try:
            payload=dict(module_source=(code/'datafirst.py').read_text(),
                pins={'manifest_digest':initial['manifest_digest'],'candidate_files':files},
                files={name:base64.b64encode((code/name).read_bytes()).decode() for name in files})
            imports="import sys;sys.path.insert(0,payload['candidate_code']);import runtime,dialogue,server,datafirst;assert callable(dialogue.personal_reference);assert callable(datafirst.DataFirstDialogue);print('COHERENT_IMPORTS_OK')"
            print('Prüfe zuerst das vollständige Modulpaket ohne Modellaufruf.',flush=True)
            imported=candidate_run(guard,evaluation,process,op['assistant'],dict(payload,integration=imports),directory,'imports')
            if imported.returncode or b'COHERENT_IMPORTS_OK' not in imported.stdout:
                raise RuntimeError('COHERENT_IMPORT_CHECK_FAILED')
            current=guard.inventory()
            if set(before)!=set(current) or any(prep.configuration(guard,before[n])!=prep.configuration(guard,current[n]) for n in before):
                raise RuntimeError('SERVICE_DRIFT_BEFORE_CPU_UPDATE')
            phase='cpu_update';cpu_attempted=True
            guard.run(['docker','update','--cpus','4',inference['Id']])
            actual=guard.inventory()[op['inference']]
            if actual['HostConfig']['NanoCpus']!=4000000000 or fingerprint(guard,prep,actual)!=resources['non_cpu_fingerprint']:
                raise RuntimeError('CPU_UPDATE_SCOPE_MISMATCH')
            phase='coherent_signed_candidate'
            print('Prüfe vollständiges Modulpaket und signierten Chat; höchstens zwei Modellantworten.',flush=True)
            program=evaluation.INTEGRATION
            if program.count("sys.path.insert(0,'/code')")!=1:raise RuntimeError('UNEXPECTED_EVALUATION_CONTRACT')
            program=program.replace("sys.path.insert(0,'/code')","sys.path.insert(0,payload['candidate_code'])")
            child=candidate_run(guard,evaluation,process,op['assistant'],dict(payload,integration=program),directory,'check')
            native=None
            for line in child.stdout.decode(errors='replace').splitlines():
                if line.startswith('VECTOR_QWEN35_RESULT='):native=json.loads(line.split('=',1)[1])
                elif line.startswith('{'):print(line,flush=True)
            guard.write_private(directory/'native.json',guard.canonical(native or {'error':'CANDIDATE_START_FAILED'}))
            if child.returncode or not native or not native.get('passed'):
                if native is None:
                    import re
                    errors=re.findall(r'^[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception):[^\n]*',child.stderr.decode(errors='replace'),re.M)
                    if errors:
                        text=re.sub(r'\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+','[URL entfernt]',errors[-1])
                        text=re.sub(r'(?i)\b(token|password|secret)\s*[=:]\s*[^\s;,]+',r'\1=[entfernt]',text)
                        print(json.dumps({'candidate_start_error':text[:600]},ensure_ascii=False),flush=True)
                raise RuntimeError('SIGNED_CANDIDATE_NOT_QUALIFIED')
            phase='activation_preflight'
            observed=guard.inventory();meta=prep.metadata(op['assistant']);prep.verify_model(meta)
            if (active.read_bytes()!=original or guard.tree_files(installed)!=original_files
                    or guard.tree_files(code)!=files or meta['registry']!=initial['registry']
                    or set(observed)!=set(before) or any(
                        (fingerprint(guard,prep,observed[n])!=resources['non_cpu_fingerprint'] if n==op['inference']
                         else prep.configuration(guard,before[n])!=prep.configuration(guard,observed[n])) for n in before)):
                raise RuntimeError('ACTIVATION_BASELINE_DRIFT')
            phase='assistant_activation'
            print('Aktiviere Qwen3.5 nur im Minecraft-Assistenten. Minecraft bleibt online.',flush=True)
            release_helper.activate(guard,config,directory,record,candidate_raw,original)
            after=guard.inventory()
            if (set(after)!=set(before) or any(
                    (fingerprint(guard,prep,after[n])!=resources['non_cpu_fingerprint']
                        or after[n]['HostConfig']['NanoCpus']!=4000000000) if n==op['inference'] else
                    prep.configuration(guard,before[n])!=prep.configuration(guard,after[n])
                    for n in before if n!=op['assistant'])):
                raise RuntimeError('POST_ACTIVATION_RESOURCE_OR_SERVICE_DRIFT')
            result=dict(deployed=True,model=prep.MODEL,knowledge_mode='qwen35-data-first',inference_cpus=4,generation_threads=4,memory_gib=24,
                game_restart=False,only_assistant_recreated=True,other_services_unchanged=True,
                model_calls=native['model_calls'],cloud_calls=0,messages_sent=0,
                release=str(directory),rollback=str(directory/'rollback.py'),native_cases=native['cases'])
            guard.write_private(directory/'result.json',guard.canonical(result))
            activated=True
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        except BaseException as exc:
            import traceback
            guard.write_private(directory/'failure.private.txt',traceback.format_exc().encode())
            if not activated and active.read_bytes()==candidate_raw:
                guard.rollback(directory,allow_missing=True)
            if cpu_attempted and not activated:
                restore_cpu(guard,prep,resources,op['inference'])
            raise RuntimeError('QWEN35_ACTIVATION_FAILED '+phase+'; Belege: '+str(directory)) from exc


if __name__=='__main__':
    main()
