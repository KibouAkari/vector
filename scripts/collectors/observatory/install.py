#!/usr/bin/env python3
"""Install the explicitly authorized local metadata collector on Debian/Ubuntu.
No scans, model calls, packet payloads or Docker socket access by the collector.
"""
import argparse
from datetime import datetime, timezone
import grp
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from urllib.parse import urlsplit
from nginx_config import FORMAT, instrument, listed_files
from core import listening_services

ETC=Path('/etc/vector-observatory')
CODE=Path('/opt/vector-observatory')
LOG=Path('/var/log/vector-observatory')


def safe(path):
    path=Path(path)
    if not path.is_absolute() or any(value.is_symlink() for value in (path,*path.parents)):
        raise RuntimeError('Unsafe collector path')
    return path


def atomic(path,data,mode=0o600,gid=0):
    path=safe(path)
    temporary=path.with_name('.vector-'+uuid.uuid4().hex)
    try:
        with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as handle:
            os.fchmod(handle.fileno(),mode)
            os.fchown(handle.fileno(),0,gid)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def run(command,timeout=30,check=True):
    result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Collector setup command failed: '+command[0]+'. Inspect local service logs.')
    return result


def prepare_key(app):
    safe(ETC).mkdir(mode=0o700,exist_ok=True)
    row=json.loads(run(['docker','inspect',app]).stdout)[0]
    value=next((value.split('=',1)[1] for value in row['Config'].get('Env',[]) if value.startswith('VECTOR_TRAFFIC_INGEST_TOKEN=')),None)
    key=ETC/'ingest.key'
    if value:
        if len(value.encode())<32 or '\n' in value: raise RuntimeError('Existing ingest credential is invalid')
        atomic(key,value.encode())
    elif not key.exists():
        atomic(key,secrets.token_hex(32).encode())
    safe(key)
    return key


def geoip_database():
    destination=ETC/'country.mmdb'
    if destination.exists(): return str(destination),'db-ip'
    # Public monthly country database. No client IPs or service information are sent to the download host.
    month=datetime.now(timezone.utc).strftime('%Y-%m')
    url='https://download.db-ip.com/free/dbip-country-lite-'+month+'.mmdb.gz'
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(url,timeout=30) as response:
            compressed=response.read(20_000_001)
        if len(compressed)>20_000_000: raise ValueError('Download limit')
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as handle:
            raw=handle.read(40_000_001)
        if len(raw)>40_000_000: raise ValueError('Database limit')
        temporary=ETC/('.country-'+uuid.uuid4().hex+'.mmdb')
        try:
            atomic(temporary,raw,0o640,grp.getgrnam('vector-observatory').gr_gid)
            import maxminddb
            with maxminddb.open_database(str(temporary)) as reader:
                if 'Country' not in reader.metadata().database_type: raise ValueError('Unexpected database type')
            os.replace(temporary,destination)
        finally:
            temporary.unlink(missing_ok=True)
        atomic(ETC/'geoip-source.json',json.dumps({'source':url,'sha256':hashlib.sha256(raw).hexdigest(),'license':'CC-BY-4.0','attribution':'https://db-ip.com','downloadedAt':datetime.now(timezone.utc).isoformat()}).encode())
        return str(destination),'db-ip'
    except (OSError,ValueError):
        return None,None


def metadata_file(path,gid):
    path=safe(path)
    if not path.exists(): atomic(path,b'',0o640,gid)
    # Only the dedicated metadata file is changed, never the existing access logs.
    os.chmod(path,0o640)
    os.chown(path,0,gid)


def nginx_setup(rows):
    logs,websites,coverage=[],{},[]
    adm=grp.getgrnam('adm').gr_gid
    targets=[]
    if shutil.which('nginx') and Path('/etc/nginx/nginx.conf').is_file():
        targets.append(([],Path('/etc/nginx/nginx.conf'),None))
    for row in rows:
        image=row['Config'].get('Image','').lower()
        if 'nginx-proxy-manager' not in image: continue
        mount=next((value for value in row.get('Mounts',[]) if value['Destination']=='/data' and value.get('RW')),None)
        if mount: targets.append((['docker','exec',row['Name'].lstrip('/')],None,Path(mount['Source'])))
    for prefix,main,npm in targets:
        dump=run(prefix+['nginx','-T'],check=False)
        if dump.returncode:
            coverage.append('An nginx instance could not be inspected; its HTTP logs are not configured.')
            continue
        for names in re.findall(r'^\s*server_name\s+([^;]+);',dump.stdout,re.M):
            for name in names.split():
                if re.fullmatch(r'[A-Za-z0-9.-]{1,100}',name) and name!='_': websites[name]=name
        changes={}
        try:
            if npm:
                custom=safe(npm/'nginx/custom')
                custom.mkdir(parents=True,exist_ok=True)
                metadata=safe(npm/'logs/vector-metadata.log')
                metadata.parent.mkdir(parents=True,exist_ok=True)
                metadata_file(metadata,adm)
                for name,value in [('http_top.conf',FORMAT),('server_proxy.conf','access_log /data/logs/vector-metadata.log vector_metadata buffer=16k flush=1s;')]:
                    path=safe(custom/name)
                    old=path.read_bytes() if path.exists() else None
                    if old is not None and b'vector_metadata' in old: continue
                    changes[path]=(old,path.stat().st_mode&0o777 if path.exists() else 0o644,path.stat().st_gid if path.exists() else 0)
                    atomic(path,(old or b'')+('\n# Vector connection metadata\n'+value+'\n').encode(),0o644)
                logs.append({'path':str(metadata)})
                coverage.append('Nginx Proxy Manager proxy hosts: metadata logger added. Explicit access_log off or location overrides can exclude requests.')
            else:
                metadata=LOG/'nginx-metadata.log'
                metadata_file(metadata,adm)
                for value in listed_files(dump.stdout):
                    # Resolve the normal sites-enabled links, then limit edits to the nginx configuration tree.
                    path=Path(value).resolve()
                    if not path.is_relative_to('/etc/nginx') or not path.is_file(): continue
                    safe(path)
                    old=path.read_bytes()
                    updated,changed=instrument(old.decode(),str(metadata),main=path==main.resolve())
                    if changed:
                        meta=path.stat()
                        changes[path]=(old,meta.st_mode&0o777,meta.st_gid)
                        atomic(path,updated.encode(),meta.st_mode&0o777,meta.st_gid)
                logs.append({'path':str(metadata)})
                coverage.append('Host nginx: metadata logger added to inspectable HTTP contexts. Disabled logs and unsupported fragments remain excluded.')
            run(prefix+['nginx','-t'])
            if changes: run(prefix+['nginx','-s','reload'])
        except Exception:
            for path,(old,mode,gid) in changes.items():
                if old is None: path.unlink(missing_ok=True)
                else: atomic(path,old,mode,gid)
            run(prefix+['nginx','-t'],check=False)
            logs=[entry for entry in logs if entry['path']!=str(metadata)]
            coverage.append('Metadata hook failed validation and was restored. Existing nginx configuration stays active.')
    if not targets: coverage.append('No supported host nginx or Nginx Proxy Manager installation found. Connections are still collected; configure a trusted JSON metadata log for HTTP requests.')
    return logs,websites,coverage


def install(endpoint,app):
    if os.geteuid()!=0: raise RuntimeError('Run collector installation as root')
    url=urlsplit(endpoint)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        raise RuntimeError('Use the HTTPS Vector origin')
    key=prepare_key(app)
    if not shutil.which('apt-get') or not Path('/run/systemd/system').exists(): raise RuntimeError('Automatic installation supports Debian/Ubuntu with systemd')
    print('Installing distribution packages for read-only connection tracking and local GeoIP.',flush=True)
    run(['apt-get','update'],timeout=120)
    run(['apt-get','install','-y','--no-install-recommends','conntrack','iproute2','python3-maxminddb','ca-certificates'],timeout=180)
    try: pwd.getpwnam('vector-observatory')
    except KeyError: run(['useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','vector-observatory'])
    gid=grp.getgrnam('vector-observatory').gr_gid
    os.chown(ETC,0,gid)
    os.chmod(ETC,0o750)
    safe(CODE).mkdir(mode=0o755,exist_ok=True)
    safe(LOG).mkdir(mode=0o750,exist_ok=True)
    os.chown(LOG,0,grp.getgrnam('adm').gr_gid)
    for name in ('core.py','collector.py'):
        atomic(CODE/name,(Path(__file__).parent/name).read_bytes(),0o644)
    ids=run(['docker','ps','-q']).stdout.split()
    rows=json.loads(run(['docker','inspect',*ids]).stdout) if ids else []
    old=json.loads((ETC/'config.json').read_text()) if (ETC/'config.json').exists() else {}
    ports=listening_services(run(['ss','-H','-lntup']).stdout)
    ports.update({'tcp/22':'SSH','tcp/80':'HTTP gateway','tcp/443':'HTTPS gateway','tcp/25565':'Minecraft'})
    for row in rows:
        for container_port,bindings in (row.get('NetworkSettings',{}).get('Ports') or {}).items():
            protocol=container_port.split('/')[-1]
            for binding in bindings or []:
                ports[protocol+'/'+binding['HostPort']]=row['Name'].lstrip('/')
    logs,websites,coverage=nginx_setup(rows)
    database,provider=geoip_database()
    config={**old,'endpoint':endpoint.rstrip('/')+'/api/traffic','sourceId':old.get('sourceId') or str(uuid.uuid4()),'name':old.get('name','Server'),'destinations':old.get('destinations',[]),'ports':{**ports,**old.get('ports',{})},'logs':old.get('logs') or logs,'websites':{**websites,**old.get('websites',{})},'volumes':old.get('volumes',[{'name':'System','path':'/'}]),'geoipDatabase':old.get('geoipDatabase') or database,'geoipProvider':old.get('geoipProvider') or provider,'geoipExpected':True}
    atomic(ETC/'config.json',(json.dumps(config,indent=2)+'\n').encode(),0o640,gid)
    atomic(Path('/etc/systemd/system/vector-observatory.service'),(Path(__file__).parent/'vector-observatory.service').read_bytes(),0o644)
    if shutil.which('logrotate') and config['logs']:
        rotation=' '.join(chr(34)+entry['path'].replace(chr(34),'')+chr(34) for entry in config['logs'])+' {\n daily\n maxsize 20M\n rotate 1\n missingok\n notifempty\n copytruncate\n create 0640 root adm\n}\n'
        atomic(Path('/etc/logrotate.d/vector-observatory'),rotation.encode(),0o644)
    run(['systemctl','daemon-reload'])
    run(['systemctl','enable','--now','vector-observatory.service'])
    run(['systemctl','restart','vector-observatory.service'])
    active=run(['systemctl','is-active','vector-observatory.service']).stdout.strip()=='active'
    ingest_seen=False
    probe="const{Pool}=require('pg');const p=new Pool({connectionString:process.env.DATABASE_URL});p.query('SELECT received_at FROM traffic_sources WHERE id=$1 AND received_at>NOW()-INTERVAL \'30 seconds\'',[process.argv[1]]).then(r=>console.log(r.rowCount)).catch(()=>console.log(0)).finally(()=>p.end());"
    for _ in range(8):
        result=run(['docker','exec',app,'node','-e',probe,config['sourceId']],check=False)
        if result.returncode==0 and result.stdout.strip()=='1':
            ingest_seen=True
            break
        time.sleep(2)
    report={'installed':active,'signedIngestionVerified':ingest_seen,'geoipConfigured':bool(config['geoipDatabase']),'coverage':coverage,'configuredPorts':len(config['ports']),'configuredMetadataLogs':len(config['logs']),'payloadCapture':False,'modelCalls':0,'externalScans':0,'configuration':str(ETC/'config.json'),'note':'A running process does not prove end-to-end ingestion. Check the Collection heartbeat and source health in Traffic.'}
    atomic(ETC/'installation.json',(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url',required=True)
    parser.add_argument('--app',default='vector-app')
    args=parser.parse_args()
    install(args.public_url,args.app)


if __name__=='__main__': main()
