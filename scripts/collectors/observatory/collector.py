#!/usr/bin/env python3
"""Local observability collector: nginx JSON, read-only conntrack, host samples.
Credentials are read from a file. No shell commands, packet bodies or cloud GeoIP.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import signal
import selectors
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from urllib.parse import urlsplit
from core import HostSampler, address, conntrack_line, socket_line, nginx_line, geoip_lookup, local_addresses, stamp

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def bounded_command(command, limit=4_000_000, timeout=5):
    """Bound snapshot output while reading, with no shell and a fixed deadline."""
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    selector=selectors.DefaultSelector()
    selector.register(process.stdout,selectors.EVENT_READ)
    output=bytearray()
    deadline=time.monotonic()+timeout
    try:
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise RuntimeError('Snapshot reader timeout')
            if not selector.select(min(remaining,.2)): continue
            chunk=os.read(process.stdout.fileno(),65536)
            if not chunk: break
            output.extend(chunk)
            if len(output)>limit: raise RuntimeError('Snapshot output limit')
        code=process.wait(timeout=max(.1,deadline-time.monotonic()))
        return subprocess.CompletedProcess(command,code,output.decode(errors='replace'))
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()

class Collector:
    def __init__(self, config, secret):
        self.config = config
        self.secret = secret
        self.queue = queue.Queue(maxsize=4000)
        self.status = {'metrics': {'kind':'metrics','status':'ok'}, 'geoip':{'kind':'geoip','status':'ok' if config.get('geoipDatabase') else 'unavailable' if config.get('geoipExpected') else 'disabled'}}
        self.dropped = 0
        self.stop = threading.Event()
        self.destinations = {address(value) for value in config.get('destinations', [])}
        if not self.destinations:
            self.destinations = local_addresses()
        self.services = config.get('ports', {})
        if len(self.services) > 100 or any(not __import__('re').fullmatch(r'(tcp|udp)/[0-9]{1,5}', key) or not isinstance(name,str) or not 1 <= int(key.split('/')[1]) <= 65535 for key,name in self.services.items()):
            raise ValueError('Invalid service/port map')
        try:
            self.enrich = geoip_lookup(config.get('geoipDatabase'))
        except (OSError, ImportError, ValueError):
            self.enrich = lambda event: event
            self.status['geoip'] = {'kind':'geoip','status':'unavailable','message':'Local database cannot be opened. Locations remain unknown.'}
        self.log_status = {}
        self.processes = set()
        self.sampler = HostSampler(config.get('volumes'))
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def emit(self, value):
        if value:
            try:
                self.queue.put_nowait(self.enrich(value))
            except queue.Full:
                self.dropped += 1

    def logs(self, entry):
        path = Path(entry['path'])
        handle = None
        initial = True
        self.log_status[str(path)] = False
        while not self.stop.is_set():
            try:
                stat = path.stat()
                if handle is None or os.fstat(handle.fileno()).st_ino != stat.st_ino or handle.tell() > stat.st_size:
                    if handle:
                        handle.close()
                    handle = path.open(encoding='utf-8', errors='replace')
                    if initial:
                        handle.seek(0, 2)
                    initial = False
                line = handle.readline(65537)
                if not line:
                    self.stop.wait(.2)
                    continue
                if len(line)>65536:
                    self.dropped += 1
                    while line and not line.endswith('\n'):
                        line = handle.readline(65537)
                    continue
                event=nginx_line(line,self.config.get('websites',{}),default_service=entry.get('service'))
                self.log_status[str(path)] = event is not None
                self.emit(event)
                self.status['nginx'] = {'kind':'nginx','status':'ok' if all(self.log_status.values()) else 'degraded','message':'Some configured logs are unreadable, have no recent data or use an unsupported format.' if not all(self.log_status.values()) else ''}
            except (OSError,ValueError):
                self.log_status[str(path)] = False
                self.status['nginx'] = {'kind':'nginx','status':'degraded','message':'A configured log cannot be read.'}
                self.stop.wait(2)
        if handle:
            handle.close()

    def network_events(self):
        command = shutil.which('conntrack')
        if not command:
            self.status['conntrack'] = {'kind':'conntrack','status':'unavailable','message':'Install conntrack for Docker/NAT connection events.'}
            return
        while not self.stop.is_set():
            process = subprocess.Popen([command,'-E','-o','timestamp,id','-b','2097152'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
            self.processes.add(process)
            self.status['conntrack'] = {'kind':'conntrack','status':'ok'}
            def errors(reader):
                for line in reader:
                    self.status['conntrack'] = {'kind':'conntrack','status':'degraded','message':'Connection reader reports a gap or permission error; inspect the local journal.'}
            threading.Thread(target=errors,args=(process.stderr,),daemon=True).start()
            previous = {}
            try:
                for line in process.stdout:
                    if self.stop.is_set():
                        break
                    event = conntrack_line(line,self.services,self.destinations,self.config['sourceId'])
                    if event:
                        key = event['connectionId']
                        marker = (event['kind'],event['state'])
                        if previous.get(key) != marker:
                            self.emit(event)
                        if event['kind']=='connection-close':
                            previous.pop(key,None)
                        else:
                            previous[key] = marker
                        if len(previous)>10000:
                            previous.clear()
                            self.status['conntrack']={'kind':'conntrack','status':'degraded','message':'Event deduplication window reset at capacity.'}
            finally:
                self.processes.discard(process)
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            self.status['conntrack'] = {'kind':'conntrack','status':'unavailable','message':'Connection event reader stopped. Check CAP_NET_ADMIN and conntrack support.'}
            self.stop.wait(5)

    def snapshot(self):
        command = shutil.which('conntrack')
        if command:
            result = bounded_command([command,'-L','-o','id'])
            if result.returncode==0:
                self.status.pop('sockets',None)
                records = [conntrack_line(line,self.services,self.destinations,self.config['sourceId']) for line in result.stdout.splitlines()[:20000]]
                active = [self.enrich(row) for row in records if row and (row['state']=='ESTABLISHED' or row['transport']=='udp')]
                return active[:250], len(active)>250 or len(result.stdout.splitlines())>20000
        command = shutil.which('ss')
        if not command:
            raise RuntimeError('No connection snapshot reader')
        result = bounded_command([command,'-Hnt','state','established'])
        if result.returncode: raise RuntimeError('Socket reader failed')
        self.status['sockets'] = {'kind':'sockets','status':'degraded','message':'Host sockets only; forwarded Docker/NAT connections are not covered.'}
        active = [self.enrich(row) for row in (socket_line(line,self.services,self.destinations,self.config['sourceId']) for line in result.stdout.splitlines()) if row]
        return active[:250],len(active)>250

    def send(self, body):
        raw = json.dumps(body,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>256000:
            raise RuntimeError('Telemetry batch exceeds the server limit')
        timestamp, nonce = str(int(time.time()*1000)), str(uuid.uuid4())
        signature = hmac.new(self.secret,(timestamp+'\n'+nonce+'\n').encode()+raw,hashlib.sha256).hexdigest()
        request = urllib.request.Request(self.config['endpoint'],data=raw,headers={'Content-Type':'application/json','X-Vector-Timestamp':timestamp,'X-Vector-Nonce':nonce,'X-Vector-Signature':signature})
        with self.opener.open(request,timeout=8) as response:
            if response.status!=200:
                raise RuntimeError('Telemetry submission failed')

    def run(self):
        for entry in self.config.get('logs',[])[:16]:
            threading.Thread(target=self.logs,args=(entry,),daemon=True).start()
        threading.Thread(target=self.network_events,daemon=True).start()
        if not self.config.get('logs'):
            self.status['nginx']={'kind':'nginx','status':'disabled','message':'No metadata log is configured.'}
        snapshot, sample_at, truncated, next_sample = [],None,False,0
        while not self.stop.is_set():
            started = time.monotonic()
            if started>=next_sample:
                try:
                    snapshot,truncated = self.snapshot()
                    sample_at = stamp()
                except (OSError,subprocess.SubprocessError,RuntimeError):
                    self.status['sockets']={'kind':'sockets','status':'unavailable','message':'Cannot obtain a current connection sample.'}
                next_sample = started+15
            events=[]
            while len(events)<200:
                try:
                    events.append(self.queue.get_nowait())
                except queue.Empty:
                    break
            source={'id':self.config['sourceId'],'name':self.config.get('name','Local host'),'observedAt':stamp(),'readers':[],'dropped':self.dropped,'geoipProvider':self.config.get('geoipProvider'),'connectionSampleAt':sample_at,'connectionsTruncated':truncated}
            body={'events':events,'source':source,'connections':snapshot}
            try:
                body['vitals']=self.sampler.sample()
                self.status['metrics']={'kind':'metrics','status':'ok'}
            except (OSError,ValueError,KeyError):
                self.status['metrics']={'kind':'metrics','status':'unavailable','message':'Host resource sample unavailable.'}
            source['readers'] = list(self.status.values())
            try:
                self.send(body)
            except Exception:
                # Do not replay uncertain batches. Count lost observations and retain only fresh state.
                self.dropped += len(events)
                print('Telemetry submission failed; observations were not replayed. Check endpoint/key and the local journal.',file=sys.stderr,flush=True)
            self.stop.wait(max(.2,5-(time.monotonic()-started)))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--key-file',required=True)
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    url=urlsplit(config['endpoint'])
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path!='/api/traffic':
        raise SystemExit('Configure the HTTPS /api/traffic endpoint without credentials in its URL.')
    uuid.UUID(config['sourceId'])
    secret=Path(args.key_file).read_bytes().strip()
    if len(secret)<32:
        raise SystemExit('Collector key must have at least 32 bytes.')
    collector=Collector(config,secret)
    def shutdown(*_):
        collector.stop.set()
        for process in tuple(collector.processes):
            process.terminate()
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try:
        collector.run()
    except KeyboardInterrupt:
        collector.stop.set()

if __name__=='__main__':main()
