#!/usr/bin/env python3
"""Host-only verified public GGUF download and internal owner-operated import.

No native generation, external container egress, service restart or network edit.
This helper is loaded only by the explicit model preparer, never by the assistant.
"""
import hashlib
import json
import os
import socket
import ssl
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

MODEL = 'vector-lfm25:1.2b-q4km-candidate'
SHA256 = 'b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5'
SIZE = 730895168
FILENAME = 'LFM2.5-1.2B-Instruct-Q4_K_M.gguf'
URL = 'https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/'+FILENAME
LICENSE_URL = 'https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct/raw/main/LICENSE'


def allowed_url(url):
    try:
        value=urllib.parse.urlsplit(url)
        if value.port not in (None,443):return False
        host=value.hostname or ''
    except ValueError:return False
    return (value.scheme=='https' and value.username is None and value.password is None
        and (host=='huggingface.co' or host.endswith('.huggingface.co') or host.endswith('.hf.co')))


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,url):
        if not allowed_url(url):raise RuntimeError('UNAPPROVED_MODEL_REDIRECT')
        return super().redirect_request(request,fp,code,message,headers,url)


def public_open(url):
    if not allowed_url(url):raise RuntimeError('UNAPPROVED_MODEL_SOURCE')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicRedirects(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:return opener.open(url,timeout=20)
    except urllib.error.HTTPError as exc:raise RuntimeError('HOST_DOWNLOAD_HTTP_'+str(exc.code)) from None
    except urllib.error.URLError as exc:
        reason=exc.reason
        code='DNS' if isinstance(reason,socket.gaierror) else 'TLS' if isinstance(reason,ssl.SSLError) else 'NETWORK'
        raise RuntimeError('HOST_DOWNLOAD_'+code+'_FAILED') from None


def verify_file(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as handle:
        meta=os.fstat(handle.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid()
                or stat.S_IMODE(meta.st_mode)&0o077 or meta.st_size!=SIZE):
            raise RuntimeError('MODEL_CACHE_FILE_INVALID')
        digest=hashlib.sha256()
        for block in iter(lambda:handle.read(1048576),b''):digest.update(block)
    if digest.hexdigest()!=SHA256:raise RuntimeError('MODEL_CACHE_DIGEST_MISMATCH')


def ensure_cached(root,guard,status):
    parent=guard.checked_path(str(root/'local-inference'),directory=True)
    directory=parent/'model-candidates'
    if directory.is_symlink():raise RuntimeError('UNSAFE_MODEL_CACHE')
    directory.mkdir(mode=0o700,exist_ok=True)
    guard.checked_path(str(directory),directory=True)
    meta=directory.stat()
    if meta.st_uid!=os.geteuid() or stat.S_IMODE(meta.st_mode)!=0o700:
        raise RuntimeError('PRIVATE_MODEL_CACHE_REQUIRED')
    target=directory/(SHA256+'.gguf')
    if target.exists() or target.is_symlink():
        verify_file(target);status['host_cache_reused']=True;status['host_weight_digest_verified']=True
        return target
    temporary=directory/('.part-'+uuid.uuid4().hex)
    status['download_attempted']=True
    print('Lade die öffentliche GGUF-Datei auf dem Host; etwa 731 MB.',flush=True)
    try:
        descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as output,public_open(URL) as response:
            expected=response.headers.get('Content-Length')
            if expected is not None and int(expected)!=SIZE:raise RuntimeError('MODEL_DOWNLOAD_SIZE_MISMATCH')
            started=time.monotonic();last=started;total=0;digest=hashlib.sha256()
            while True:
                if time.monotonic()-started>300:raise RuntimeError('HOST_MODEL_DOWNLOAD_TIMEOUT')
                block=response.read(min(1048576,SIZE+1-total))
                if not block:break
                total+=len(block)
                if total>SIZE:raise RuntimeError('MODEL_DOWNLOAD_SIZE_MISMATCH')
                digest.update(block);output.write(block)
                if time.monotonic()-last>=20:
                    print('Modelldownload: '+str(round(total/SIZE*100))+' %',flush=True);last=time.monotonic()
            if total!=SIZE or digest.hexdigest()!=SHA256:raise RuntimeError('MODEL_DOWNLOAD_DIGEST_MISMATCH')
            output.flush();os.fsync(output.fileno())
        # Never replace an existing cache entry, even on a race.
        os.link(temporary,target);guard.sync_directory(directory)
        status['host_weight_digest_verified']=True
        return target
    finally:temporary.unlink(missing_ok=True)


INTERNAL = r'''
import http.client,json,sys,time
payload=json.load(sys.stdin)
connection=http.client.HTTPConnection('vector-local-inference',11434,timeout=60)
try:
    if payload['operation']=='head':
        connection.request('HEAD','/api/blobs/sha256:'+payload['sha256'])
        response=connection.getresponse()
        if response.status not in (200,404):raise RuntimeError('BLOB_HEAD_HTTP_'+str(response.status))
        print(json.dumps({'exists':response.status==200}))
    elif payload['operation']=='create':
        body=json.dumps(payload['body']).encode()
        connection.request('POST','/api/create',body,{'Content-Type':'application/json'})
        response=connection.getresponse();raw=response.read(65537)
        if len(raw)>65536:raise RuntimeError('MODEL_IMPORT_RESPONSE_LIMIT')
        value=json.loads(raw)
        if response.status!=200 or value.get('status')!='success':
            print(json.dumps({'import_error':str(value.get('error','MODEL_IMPORT_HTTP_'+str(response.status)))[:400]}))
            raise SystemExit(1)
        print(json.dumps({'created':True}))
    else:raise RuntimeError('UNAPPROVED_IMPORT_OPERATION')
finally:connection.close()
'''


UPLOAD = r'''
import hashlib,http.client,json,sys,time
digest=sys.argv[1];size=int(sys.argv[2]);end=time.monotonic()+180
connection=http.client.HTTPConnection('vector-local-inference',11434,timeout=10)
try:
    connection.putrequest('POST','/api/blobs/sha256:'+digest)
    connection.putheader('Content-Type','application/octet-stream')
    connection.putheader('Content-Length',str(size));connection.endheaders()
    received=0;actual=hashlib.sha256()
    while received<size:
        remaining=end-time.monotonic()
        if remaining<=0:raise TimeoutError('BLOB_UPLOAD_DEADLINE')
        connection.sock.settimeout(min(10,remaining))
        block=sys.stdin.buffer.read(min(1048576,size-received))
        if not block:raise RuntimeError('BLOB_UPLOAD_INPUT_INCOMPLETE')
        actual.update(block);received+=len(block);connection.send(block)
    if actual.hexdigest()!=digest:raise RuntimeError('BLOB_UPLOAD_INPUT_DIGEST_MISMATCH')
    connection.sock.settimeout(max(.001,min(10,end-time.monotonic())))
    response=connection.getresponse();response.read(65537)
    if response.status not in (200,201):raise RuntimeError('BLOB_UPLOAD_HTTP_'+str(response.status))
    print(json.dumps({'uploaded_bytes':received,'uploaded_digest':actual.hexdigest()}))
finally:connection.close()
'''


def internal(container,payload,report,guard,phase):
    try:
        result=subprocess.run(['docker','exec','-i',container,'python3','-c',INTERNAL],
            input=json.dumps(payload).encode(),capture_output=True,timeout=70)
    except subprocess.TimeoutExpired as exc:
        guard.write_private(report/(phase+'.stdout'),exc.stdout or b'')
        guard.write_private(report/(phase+'.stderr'),exc.stderr or b'')
        raise
    guard.write_private(report/(phase+'.stdout'),result.stdout)
    guard.write_private(report/(phase+'.stderr'),result.stderr)
    if result.returncode:raise RuntimeError('CANDIDATE_INTERNAL_IMPORT_FAILED_'+phase.upper())
    return json.loads(result.stdout)


def prepare(root,container,report,guard,status):
    exists=internal(container,{'operation':'head','sha256':SHA256},report,guard,'blob-before')['exists']
    if not exists:
        path=ensure_cached(root,guard,status)
        status['import_attempted']=True
        print('Übertrage die geprüfte Datei über die bestehende interne Verbindung.',flush=True)
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            with os.fdopen(descriptor,'rb') as source:
                upload=subprocess.run(['docker','exec','-i',container,'python3','-c',UPLOAD,SHA256,str(SIZE)],
                    stdin=source,capture_output=True,timeout=190)
        except subprocess.TimeoutExpired:
            status['import_completion_unknown']=True
            raise RuntimeError('CANDIDATE_BLOB_UPLOAD_TIMEOUT') from None
        guard.write_private(report/'upload.stdout',upload.stdout)
        guard.write_private(report/'upload.stderr',upload.stderr)
        if upload.returncode:raise RuntimeError('CANDIDATE_BLOB_UPLOAD_FAILED')
        if not internal(container,{'operation':'head','sha256':SHA256},report,guard,'blob-after')['exists']:
            raise RuntimeError('CANDIDATE_BLOB_UPLOAD_UNVERIFIED')
    else:status['existing_verified_blob_reused']=True
    with public_open(LICENSE_URL) as response:license_raw=response.read(65537)
    if len(license_raw)>65536 or not license_raw.startswith(b'LFM Open License v1.0'):
        raise RuntimeError('CANDIDATE_LICENSE_INVALID')
    guard.write_private(report/'MODEL_LICENSE.txt',license_raw)
    status['license_sha256']=hashlib.sha256(license_raw).hexdigest()
    status['import_attempted']=True
    # Let the existing runtime import the original GGUF metadata/template. This
    # remains unqualified until its actual template and native behavior are tested.
    body={'model':MODEL,'stream':False,'files':{FILENAME:'sha256:'+SHA256},
          'license':license_raw.decode(),
          'parameters':{'temperature':0.1,'top_k':50,'repeat_penalty':1.05}}
    try:internal(container,{'operation':'create','body':body},report,guard,'create')
    except subprocess.TimeoutExpired:
        status['import_completion_unknown']=True
        raise RuntimeError('CANDIDATE_CREATE_TIMEOUT') from None
    status['host_download_internal_import']=True
