#!/usr/bin/env python3
"""Install isolated, pinned CPU inference and benchmark public synthetic fixtures.
No Vector settings, databases, host agent or application containers are changed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT = Path('/root/vector-workspace/local-inference')
NAME = 'vector-local-inference'
NETWORK = 'vector-local-inference'
VOLUME = 'vector-local-inference-models'
IMAGE = 'ollama/ollama@sha256:7434bb6d6a423b8c4060c4cf0bfa1b49a6540d080d6a3c98acc2cbe36a786158'
VERSION = '0.40.4'
MODELS = (
    dict(name='vector-hermes3:8b-q4km', repo='NousResearch/Hermes-3-Llama-3.1-8B-GGUF',
         revision='307a5dfb59aa38d88b6cfd32f44b8ad7c1da9fb8', file='Hermes-3-Llama-3.1-8B.Q4_K_M.gguf',
         sha256='d4403ce5a6e930f4c2509456388c20d633a15ff08dd52ef3b142ff1810ec3553', size=4920733824),
    dict(name='vector-qwen3:0.6b-q8', repo='Qwen/Qwen3-0.6B-GGUF',
         revision='23749fefcc72300e3a2ad315e1317431b06b590a', file='Qwen3-0.6B-Q8_0.gguf',
         sha256='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031', size=639446688),
)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def run(*args):
    return subprocess.check_output(args, text=True, timeout=1800).strip()


def verified(path, model):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != model['size']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == model['sha256']


def download(model):
    target = ROOT / model['file']
    if verified(target, model):
        return target
    if target.exists() or target.is_symlink():
        raise RuntimeError('Existing model file failed verification; inspect it manually.')
    partial = ROOT / (model['file'] + '.partial')
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['file']}"
    # No shell installers or model repository Python code are executed.
    run('curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
        '--connect-timeout', '20', '--max-time', '1800', '--retry', '2', '--output', str(partial), url)
    if not verified(partial, model):
        raise RuntimeError('Downloaded GGUF checksum/size mismatch.')
    partial.replace(target)
    return target


def docker_args():
    return ['docker', 'run', '-d', '--name', NAME, '--network', NETWORK,
            '--label', 'vector.component=local-inference-pilot', '--restart', 'unless-stopped',
            '--cpus', '2', '--memory', '12g', '--memory-swap', '12g', '--pids-limit', '256',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=1g', '--log-opt', 'max-size=10m',
            '--log-opt', 'max-file=2', '-v', VOLUME + ':/root/.ollama',
            '-v', str(ROOT) + ':/imports:ro',
            '-e', 'OLLAMA_HOST=0.0.0.0:11434', '-e', 'OLLAMA_NO_CLOUD=1',
            '-e', 'OLLAMA_NUM_PARALLEL=1', '-e', 'OLLAMA_MAX_LOADED_MODELS=1',
            '-e', 'OLLAMA_MAX_QUEUE=4', '-e', 'OLLAMA_KEEP_ALIVE=5m',
            '-e', 'OLLAMA_CONTEXT_LENGTH=2048', IMAGE]


def api(base, path, payload=None, timeout=180):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=body, headers={'Content-Type': 'application/json'})
    with HTTP.open(req, timeout=timeout) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise RuntimeError('Oversized inference response.')
    return json.loads(data)


def evaluate(base, model, phase):
    started = time.monotonic()
    response = api(base, '/api/chat', dict(model=model, stream=False, think=False, format='json',
        keep_alive='5m', options=dict(num_ctx=2048, num_thread=2, num_predict=128, temperature=0, seed=42),
        messages=[dict(role='system', content='Extract only supplied facts. Return JSON only. Never invent missing values.'),
                  dict(role='user', content='Return exactly {"players":3,"deaths":null} from: player count is 3; deaths are not measured. /no_think')]))
    content = response.get('message', {}).get('content', '')
    try:
        passed = json.loads(content) == dict(players=3, deaths=None)
    except (ValueError, TypeError):
        passed = False
    duration = response.get('eval_duration', 0)
    return dict(model=model, phase=phase, fixture_passed=passed,
        seconds=round(time.monotonic() - started, 3),
        input_tokens=response.get('prompt_eval_count'), output_tokens=response.get('eval_count'),
        output_tokens_per_second=round(response.get('eval_count', 0) * 1e9 / duration, 2) if duration else None,
        load_seconds=round(response.get('load_duration', 0) / 1e9, 3),
        done=response.get('done'), done_reason=response.get('done_reason'), response_text=content[:1000])


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run through the root workspace runner.')
    if ROOT.exists():
        raise RuntimeError('Pilot directory already exists; inspect previous run instead of replacing it.')
    if shutil.disk_usage('/root').free < 20 * 1024**3:
        raise RuntimeError('At least 20 GiB disk headroom required for imports and model copies.')
    for kind, name in [('container', NAME), ('network', NETWORK), ('volume', VOLUME)]:
        if subprocess.run(['docker', kind, 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError(f'Existing {kind} {name}; refusing to replace it.')
    ROOT.mkdir(mode=0o700)
    os.umask(0o077)
    (ROOT / 'rollback.sh').write_text('#!/bin/sh\nset -eu\ndocker stop ' + NAME + '\ndocker rm ' + NAME + '\ndocker network rm ' + NETWORK + '\n# Model volume and imports retained for manual inspection.\n')
    for model in MODELS:
        download(model)
        (ROOT / (model['name'].split(':')[0] + '.Modelfile')).write_text(
            f"FROM /imports/{model['file']}\nPARAMETER num_ctx 2048\nPARAMETER num_thread 2\nPARAMETER num_predict 256\nPARAMETER temperature 0\n")
    run('docker', 'pull', IMAGE)
    run('docker', 'network', 'create', '--internal', '--label', 'vector.component=local-inference-pilot', NETWORK)
    started = False
    try:
        run(*docker_args())
        started = True
        info = json.loads(run('docker', 'inspect', NAME))[0]
        address = info['NetworkSettings']['Networks'][NETWORK]['IPAddress']
        base = 'http://' + address + ':11434'
        for attempt in range(30):
            try:
                version = api(base, '/api/version', timeout=2)
                break
            except Exception:
                if attempt == 29:
                    raise RuntimeError('Inference service did not become ready.')
                time.sleep(1)
        if version.get('version') != VERSION:
            raise RuntimeError('Unexpected pinned runtime version.')
        results = []
        for model in MODELS:
            print('Import and evaluate:', model['name'], flush=True)
            run('docker', 'exec', NAME, 'ollama', 'create', model['name'], '-f',
                '/imports/' + model['name'].split(':')[0] + '.Modelfile')
            api(base, '/api/generate', dict(model=model['name'], keep_alive=0))
            for phase in ['cold', 'warm']:
                results.append(evaluate(base, model['name'], phase))
            api(base, '/api/generate', dict(model=model['name'], keep_alive=0))
        loaded = api(base, '/api/ps').get('models', [])
        report = dict(runtime_image=IMAGE, runtime_version=VERSION, models=MODELS, results=results,
            model_manifest=api(base, '/api/tags'), loaded_models_after_unload=len(loaded),
            resources=json.loads(run('docker', 'stats', '--no-stream', '--format', '{{json .}}', NAME)),
            vector_activated=False, cloud_calls=0, published_ports=info['HostConfig']['PortBindings'],
            passed=all(r['fixture_passed'] and r['done'] for r in results) and not loaded)
        (ROOT / 'pilot-result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
        if not report['passed']:
            raise RuntimeError('Pilot fixture failed; Vector routing remains unchanged.')
    except BaseException:
        if started:
            subprocess.run(['docker', 'stop', NAME], stdout=subprocess.DEVNULL)
        raise
    print('Pilot complete. Private service installed; weights unloaded. Vector integration is pending evaluation.')


if __name__ == '__main__':
    main()
