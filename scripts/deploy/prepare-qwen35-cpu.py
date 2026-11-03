#!/usr/bin/env python3
"""Prepare a verified CPU/vision candidate; change only the authorized RAM cap."""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import uuid

MODEL='vector-qwen35:9b-q4km-candidate'
MANIFEST_SHA='56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'
WEIGHT='02d45dc1cf451ba2475ac33b301c2dd8f985abe4c182ce04a1f2f5bf0260278d'
PROJECTOR='f836f08f921193f4d6b6a6952dba0a6fb116759d26a757bcb395d570d73976ca'
TEMPLATE='b507b9c2f6ca642bffcd06665ea7c91f235fd32daeefdf875a0f938db05fb315'
BASE='https://registry.ollama.ai/v2/library/qwen3.5/'
TARGET=24*1073741824

def allowed_url(url):
    try:
        v=urllib.parse.urlsplit(url);host=v.hostname or ''
        return (v.scheme=='https' and v.username is None and v.password is None
            and v.port in (None,443) and (host=='registry.ollama.ai'
                or host in ('cdn.ollama.ai','cdn.ollama.com')
                or host.endswith('.r2.cloudflarestorage.com')))
    except ValueError:return False

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,url):
        if not allowed_url(url):raise RuntimeError('UNAPPROVED_REGISTRY_REDIRECT')
        return super().redirect_request(request,fp,code,message,headers,url)

def open_public(url):
    if not allowed_url(url):raise RuntimeError('UNAPPROVED_REGISTRY_SOURCE')
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect()).open(url,timeout=20)

def load_helper(path,name,guard):
    path=guard.checked_path(str(path))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def configuration(guard,row,ignore_memory=False):
    host=copy.deepcopy(row['HostConfig'])
    if ignore_memory:
        for key in ('Memory','MemorySwap'):host.pop(key,None)
    return guard.digest(guard.canonical({
        'identity':guard.identity(row),'config':row['Config'],'host':host,
        'running':row['State']['Running'],'oom':row['State'].get('OOMKilled'),
        'health':row['State'].get('Health',{}).get('Status'),
        'mounts':sorted(row.get('Mounts',[]),key=lambda m:guard.canonical(m)),
        'networks':row.get('NetworkSettings',{}).get('Networks',{})}))

def swap_target(host):
    memory=host['Memory'];swap=host.get('MemorySwap',0)
    if swap==-1:return -1
    if swap==0:return TARGET+memory
    if swap<memory:raise RuntimeError('UNKNOWN_SWAP_POLICY')
    return TARGET+(swap-memory)

def operator(path,guard):
    path=guard.checked_path(str(path));meta=path.stat()
    if meta.st_uid!=os.geteuid() or stat.S_IMODE(meta.st_mode)&0o077 or meta.st_size>16384:
        raise RuntimeError('PRIVATE_OPERATOR_REQUIRED')
    value=json.loads(path.read_bytes())
    if set(value)!={'assistant','inference','protected','source_hashes'}:
        raise RuntimeError('UNEXPECTED_OPERATOR_SCHEMA')
    names=[value['assistant'],value['inference'],*value['protected']]
    if any(not isinstance(n,str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}',n) for n in names):
        raise RuntimeError('INVALID_CONTAINER_NAME')
    if value['inference']!='vector-local-inference' or value['assistant'] in value['protected']:
        raise RuntimeError('UNEXPECTED_CONTAINER_BINDING')
    hashes=value['source_hashes']
    if set(hashes)!={'runtime.py','dialogue.py','knowledge.py','server.py'} or any(
        not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in hashes.values()):
        raise RuntimeError('EXPECTED_SOURCE_PINS_REQUIRED')
    return value

METADATA=r'''
import hashlib,json,re,sys,urllib.request
from pathlib import Path
model=sys.argv[1]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def read(route,body=None):
    raw=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request('http://vector-local-inference:11434/api/'+route,raw,{'Content-Type':'application/json'})
    with opener.open(req,timeout=5) as response:raw=response.read(1048577)
    if len(raw)>1048576:raise RuntimeError('METADATA_LIMIT')
    return json.loads(raw)
version=read('version').get('version','')
tags=read('tags').get('models',[])
out={'runtime_version':version,'registry':{r['name']:r['digest'] for r in tags},
     'sources':{n:hashlib.sha256((Path('/code')/n).read_bytes()).hexdigest()
        for n in ('runtime.py','dialogue.py','knowledge.py','server.py')}}
matches=[r for r in tags if r['name'].casefold()==model.casefold()]
if len(matches)>1:raise RuntimeError('AMBIGUOUS_CANDIDATE')
out['candidate_exists']=bool(matches)
if matches:
    show=read('show',{'model':model,'verbose':False});modelfile=show.get('modelfile','')
    out.update(manifest_digest=matches[0]['digest'],details=show.get('details',{}),
        capabilities=show.get('capabilities',[]),
        weight_digests=re.findall(r'^FROM\s+\S*sha256[-:]([a-f0-9]{64})\s*$',modelfile,re.M),
        template_sha256=hashlib.sha256(show.get('template','').encode()).hexdigest())
    for key in ('renderer','parser'):
        found=re.findall(r'^'+key.upper()+r'\s+(\S+)\s*$',modelfile,re.M)
        out[key]=show.get(key) or (found[0] if len(found)==1 else None)
print(json.dumps(out))
'''

def metadata(container):
    result=subprocess.run(['docker','exec',container,'python3','-c',METADATA,MODEL],
        capture_output=True,timeout=25)
    if result.returncode:raise RuntimeError('QWEN35_METADATA_FAILED')
    return json.loads(result.stdout)

def verify_model(value):
    d=value.get('details',{})
    if (value.get('candidate_exists') is not True or d.get('family')!='qwen35'
            or d.get('quantization_level')!='Q4_K_M'
            or set(value.get('weight_digests',[]))!={WEIGHT,PROJECTOR}
            or value.get('template_sha256')!=TEMPLATE
            or value.get('renderer')!='qwen3.5' or value.get('parser')!='qwen3.5'
            or not {'completion','vision','tools','thinking'}<=set(value.get('capabilities',[]))):
        raise RuntimeError('QWEN35_CANDIDATE_METADATA_MISMATCH')

def registry_retained(before,after):
    return all(after.get(k)==v for k,v in before.items()) and all(
        k in before or k.casefold()==MODEL.casefold() for k in after)

def cached(root,descriptor,guard,result):
    digest=descriptor['digest'].split(':',1)[1];size=descriptor['size']
    if not re.fullmatch('[a-f0-9]{64}',digest) or type(size) is not int or not 0<size<6000000000:
        raise RuntimeError('INVALID_PUBLIC_BLOB')
    directory=guard.checked_path(str(root/'local-inference'),directory=True)/'model-candidates'
    if directory.is_symlink():raise RuntimeError('UNSAFE_CACHE')
    directory.mkdir(mode=0o700,exist_ok=True)
    guard.checked_path(str(directory),directory=True)
    meta=directory.stat()
    if meta.st_uid!=os.geteuid() or stat.S_IMODE(meta.st_mode)!=0o700:raise RuntimeError('PRIVATE_CACHE_REQUIRED')
    target=directory/(digest+'.blob')
    if target.exists() or target.is_symlink():
        fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as source:
            m=os.fstat(source.fileno())
            if not stat.S_ISREG(m.st_mode) or m.st_uid!=os.geteuid() or m.st_mode&0o077 or m.st_size!=size:
                raise RuntimeError('CACHE_METADATA_MISMATCH')
            h=hashlib.sha256()
            for block in iter(lambda:source.read(1048576),b''):h.update(block)
        if h.hexdigest()!=digest:raise RuntimeError('CACHE_DIGEST_MISMATCH')
        return target
    part=directory/('.qwen35-part-'+uuid.uuid4().hex);created=False
    result['download_attempted']=True
    try:
        fd=os.open(part,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);created=True
        with os.fdopen(fd,'wb') as output,open_public(BASE+'blobs/'+descriptor['digest']) as response:
            header=response.headers.get('Content-Length')
            if header is not None and int(header)!=size:raise RuntimeError('BLOB_SIZE_MISMATCH')
            h=hashlib.sha256();total=0;start=last=time.monotonic()
            while True:
                if time.monotonic()-start>1200:raise RuntimeError('PUBLIC_DOWNLOAD_DEADLINE')
                block=response.read(min(1048576,size+1-total))
                if not block:break
                total+=len(block)
                if total>size:raise RuntimeError('BLOB_SIZE_MISMATCH')
                output.write(block);h.update(block)
                if time.monotonic()-last>=20:
                    print('Modelldownload: '+str(round(total/size*100))+' %',flush=True);last=time.monotonic()
            if total!=size or h.hexdigest()!=digest:raise RuntimeError('BLOB_DIGEST_MISMATCH')
            output.flush();os.fsync(output.fileno())
        os.link(part,target);guard.sync_directory(directory)
        return target
    finally:
        if created:part.unlink(missing_ok=True)

def public_plan():
    with open_public(BASE+'manifests/9b') as response:raw=response.read(65537)
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:
        raise RuntimeError('PINNED_PUBLIC_MANIFEST_CHANGED')
    value=json.loads(raw)
    if value.get('format')!='gguf' or value.get('runner')!='llamacpp':
        raise RuntimeError('CPU_GGUF_MANIFEST_REQUIRED')
    return value

def upload(path,descriptor,container,report,guard,transport,result,index):
    sha=descriptor['digest'].split(':')[1]
    head=transport.internal(container,{'operation':'head','sha256':sha},report,guard,'blob-'+str(index)+'-before')
    if head['exists']:return
    result['import_attempted']=True
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as source:
            child=subprocess.run(['docker','exec','-i',container,'python3','-c',transport.UPLOAD,sha,str(descriptor['size'])],
                stdin=source,capture_output=True,timeout=190)
        guard.write_private(report/('upload-'+str(index)+'.stdout'),child.stdout)
        guard.write_private(report/('upload-'+str(index)+'.stderr'),child.stderr)
        if child.returncode:raise RuntimeError('QWEN35_UPLOAD_FAILED')
        if not transport.internal(container,{'operation':'head','sha256':sha},report,guard,'blob-'+str(index)+'-after')['exists']:
            raise RuntimeError('QWEN35_UPLOAD_UNVERIFIED')
    except Exception as exc:
        result['import_completion_unknown']=True
        if isinstance(exc,subprocess.TimeoutExpired):
            guard.write_private(report/('upload-'+str(index)+'.stdout'),exc.stdout or b'')
            guard.write_private(report/('upload-'+str(index)+'.stderr'),exc.stderr or b'')
        raise

def main():
    parser=argparse.ArgumentParser()
    for arg in ('guard-helper','transfer-helper','operator','workspace-root','lock-file'):
        parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--memory-gib',type=int,choices=[24],required=True)
    args=parser.parse_args()
    if not args.download:parser.error('Explicit --download is required')
    sys.dont_write_bytecode=True;os.umask(0o077)
    if any(p.is_symlink() for p in (args.guard_helper,*args.guard_helper.parents)):raise RuntimeError('UNSAFE_GUARD')
    spec=importlib.util.spec_from_file_location('qwen35_guard',args.guard_helper)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    transport=load_helper(args.transfer_helper,'qwen35_transfer',guard)
    op=operator(args.operator,guard)
    lockpath=guard.checked_path(str(args.lock_file))
    fd=os.open(lockpath,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    m=os.fstat(fd)
    if not stat.S_ISREG(m.st_mode) or m.st_uid!=os.geteuid():os.close(fd);raise RuntimeError('OWNED_LOCK_REQUIRED')
    with os.fdopen(fd,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=guard.inventory();assistant=before[op['assistant']];inference=before[op['inference']]
        for name in [op['assistant'],op['inference'],*op['protected']]:
            row=before[name]
            if not row['State']['Running'] or row['State'].get('OOMKilled'):
                raise RuntimeError('REQUIRED_SERVICE_NOT_RUNNING')
            if row['State'].get('Health',{}).get('Status') not in (None,'healthy'):
                raise RuntimeError('REQUIRED_SERVICE_NOT_HEALTHY')
        old=inference['HostConfig']
        if old['Memory'] not in (12*1073741824,TARGET):raise RuntimeError('UNEXPECTED_CURRENT_RAM_LIMIT')
        if old.get('NanoCpus')!=2000000000:raise RuntimeError('OBSERVED_TWO_CPU_LIMIT_REQUIRED')
        if not any(x.get('Destination')=='/code' and x.get('RW') is False for x in assistant.get('Mounts',[])):
            raise RuntimeError('READ_ONLY_ASSISTANT_CODE_REQUIRED')
        initial=metadata(op['assistant'])
        if initial['sources']!=op['source_hashes']:raise RuntimeError('OBSERVED_ASSISTANT_SOURCE_CHANGED')
        version=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:[-+].*)?',initial['runtime_version'])
        if not version or tuple(map(int,version.groups()))<(0,30,0):raise RuntimeError('QWEN35_RUNTIME_TOO_OLD')
        if initial['candidate_exists']:verify_model(initial)
        releases=guard.checked_path(str(args.workspace_root/'releases'),directory=True)
        report=releases/('qwen35-cpu-preparation-'+uuid.uuid4().hex);report.mkdir(mode=0o700)
        result=dict(prepared=False,model=MODEL,model_calls=0,cloud_calls=0,messages_sent=0,
            production_activated=False,eligible_for_activation=False,native_execution_tested=False,
            download_attempted=False,import_attempted=False,memory_limit_updated=False,
            old_memory_bytes=old['Memory'],old_memory_swap_bytes=old.get('MemorySwap',0),
            inference_identity=guard.identity(inference),registry_manifest_sha256=MANIFEST_SHA)
        guard.write_private(report/'result.json',guard.canonical(result))
        guard.write_private(report/'preparation.py',Path(__file__).read_bytes())
        guard.write_private(report/'operator.json',guard.canonical(op))
        guard.write_private(report/'registry.before.json',guard.canonical(initial))
        print('Belege: '+str(report),flush=True)
        try:
            paths={};manifest=None
            if not initial['candidate_exists']:
                if shutil.disk_usage(args.workspace_root).free<20*1073741824:raise RuntimeError('MODEL_DISK_HEADROOM_REQUIRED')
                manifest=public_plan()
                guard.write_private(report/'public-manifest.json',guard.canonical(manifest))
                print('Lade den gepinnten CPU-Kandidaten mit Bildprojektor über den Host, rund 6,6 GB.',flush=True)
                for descriptor in [manifest['config'],*manifest['layers']]:
                    paths[descriptor['mediaType']]=cached(args.workspace_root,descriptor,guard,result)
            # Recheck service and source ownership immediately before the only configuration mutation.
            current=guard.inventory()
            if set(before)!=set(current) or any(configuration(guard,before[n])!=configuration(guard,current[n]) for n in before):
                raise RuntimeError('SERVICE_CHANGED_DURING_PREPARATION')
            rechecked=metadata(op['assistant'])
            if rechecked['sources']!=op['source_hashes']:raise RuntimeError('ASSISTANT_SOURCE_CHANGED')
            if rechecked['registry']!=initial['registry']:raise RuntimeError('MODEL_REGISTRY_CHANGED_BEFORE_IMPORT')
            new_swap=old.get('MemorySwap',0) if old['Memory']==TARGET else swap_target(old)
            result['target_memory_bytes']=TARGET;result['target_memory_swap_bytes']=new_swap
            if old['Memory']!=TARGET:
                guard.write_private(report/'resource-before.json',guard.canonical({
                    'identity':guard.identity(inference),'memory':old['Memory'],'memory_swap':old.get('MemorySwap',0),
                    'target_memory':TARGET,'target_memory_swap':new_swap}))
                result['memory_update_attempted']=True
                child=subprocess.run(['docker','update','--memory',str(TARGET),'--memory-swap',str(new_swap),inference['Id']],
                    capture_output=True,timeout=20)
                if child.returncode:raise RuntimeError('AUTHORIZED_MEMORY_UPDATE_FAILED')
                result['memory_limit_updated']=True
            if manifest:
                typed=lambda suffix:paths['application/vnd.ollama.image.'+suffix]
                config=json.loads(paths[manifest['config']['mediaType']].read_bytes())
                if (config.get('model_family')!='qwen35' or config.get('file_type')!='Q4_K_M'
                    or config.get('renderer')!='qwen3.5' or config.get('parser')!='qwen3.5'):
                    raise RuntimeError('PUBLIC_QWEN35_CONFIG_MISMATCH')
                blobs=[x for x in manifest['layers'] if x['mediaType'] in (
                    'application/vnd.ollama.image.model','application/vnd.ollama.image.projector')]
                if {x['digest'].split(':')[1] for x in blobs}!={WEIGHT,PROJECTOR}:raise RuntimeError('PUBLIC_WEIGHT_SET_MISMATCH')
                print('RAM-Grenze geprüft. Importiere nur den neuen Kandidaten über die interne Verbindung.',flush=True)
                for index,descriptor in enumerate(blobs):
                    upload(paths[descriptor['mediaType']],descriptor,op['assistant'],report,guard,transport,result,index)
                params=json.loads(typed('params').read_bytes())
                params.update(temperature=0.7,top_p=0.8,repeat_penalty=1,num_ctx=8192,num_thread=2)
                body={'model':MODEL,'stream':False,'files':{d['from']:d['digest'] for d in blobs},
                    'template':typed('template').read_text(),'license':typed('license').read_text(),
                    'renderer':config['renderer'],'parser':config['parser'],'requires':config['requires'],'parameters':params}
                rechecked=metadata(op['assistant'])
                if rechecked['registry']!=initial['registry'] or rechecked['sources']!=op['source_hashes']:
                    raise RuntimeError('MODEL_OR_SOURCE_CHANGED_BEFORE_CREATE')
                result['import_attempted']=True
                try:transport.internal(op['assistant'],{'operation':'create','body':body},report,guard,'create')
                except Exception:
                    result['import_completion_unknown']=True;raise
            final=metadata(op['assistant']);verify_model(final)
            if not registry_retained(initial['registry'],final['registry']):raise RuntimeError('OTHER_MODEL_REGISTRY_CHANGED')
            if final['sources']!=op['source_hashes']:raise RuntimeError('ASSISTANT_SOURCE_CHANGED')
            guard.write_private(report/'registry.after.json',guard.canonical(final))
            result.update(prepared=True,manifest_digest=final['manifest_digest'],template_sha256=final['template_sha256'],
                weight_sha256=WEIGHT,projector_sha256=PROJECTOR,capabilities=final['capabilities'],
                renderer=final['renderer'],parser=final['parser'])
        except Exception as exc:
            result['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
            guard.write_private(report/'failure.private.txt',traceback.format_exc().encode())
        finally:
            try:
                after=guard.inventory()
                others=(set(before)==set(after) and all(configuration(guard,before[n])==configuration(guard,after[n])
                    for n in before if n!=op['inference']))
                actual=after[op['inference']]
                inference_ok=(configuration(guard,inference,True)==configuration(guard,actual,True)
                    and (actual['HostConfig']['Memory'],actual['HostConfig'].get('MemorySwap',0)) in (
                        (old['Memory'],old.get('MemorySwap',0)),(TARGET,result.get('target_memory_swap_bytes'))))
                result['all_other_services_unchanged']=others
                result['inference_configuration_owned']=inference_ok
                result['actual_memory_limit_bytes']=actual['HostConfig']['Memory']
                result['actual_memory_swap_bytes']=actual['HostConfig'].get('MemorySwap',0)
                result['memory_limit_updated']=actual['HostConfig']['Memory']!=old['Memory']
                if not others or not inference_ok:result.setdefault('error','UNEXPECTED_SERVICE_CONFIGURATION_CHANGE')
                result['prepared']=bool(result['prepared'] and others and inference_ok and actual['HostConfig']['Memory']==TARGET)
            except Exception as exc:
                result.update(prepared=False,verification_error=type(exc).__name__)
                result.setdefault('error','SERVICE_STATE_UNVERIFIED')
            result['model_cache_may_have_changed']=result['download_attempted'] or result['import_attempted']
            guard.replace_atomic(report/'result.json',guard.canonical(result))
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if not result['prepared']:raise SystemExit(1)
        print('Kandidat und 24-GB-Grenze vorbereitet. Bisheriger Assistent bleibt aktiv; Antwortqualität und Tempo noch ungeprüft.',flush=True)

if __name__=='__main__':main()
