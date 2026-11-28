"""Read-only parsing and host sampling. No packet payload capture or remote commands."""
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit


def stamp():
    return datetime.now(timezone.utc).isoformat()


def address(value):
    try:
        ip = ipaddress.ip_address(value.split('%', 1)[0])
        return str(ip.ipv4_mapped or ip) if isinstance(ip, ipaddress.IPv6Address) else str(ip)
    except ValueError:
        return None


def flow_id(source_id, transport, source, source_port, destination, destination_port, kernel_id=''):
    return hashlib.sha256('|'.join(map(str, [source_id, transport, source, source_port, destination, destination_port, kernel_id])).encode()).hexdigest()


def conntrack_line(line, services, destinations, source_id):
    """Use only the original tuple, before NAT/reply fields. Match own destinations."""
    transport = next((part for part in line.split() if part in ('tcp', 'udp')), None)
    pairs = re.findall(r'\b(src|dst|sport|dport|id)=([^\s]+)', line)
    first = {}
    for key, value in pairs:
        first.setdefault(key, value)
    source, destination = address(first.get('src', '')), address(first.get('dst', ''))
    try:
        source_port, destination_port = int(first['sport']), int(first['dport'])
    except (KeyError, ValueError):
        return None
    service = services.get(f'{transport}/{destination_port}')
    if not source or not destination or destination not in destinations or not service or not 1 <= source_port <= 65535:
        return None
    state = next((part for part in line.split() if part in ('ESTABLISHED', 'SYN_SENT', 'SYN_RECV', 'FIN_WAIT', 'TIME_WAIT', 'CLOSE', 'CLOSE_WAIT', 'LAST_ACK')), 'flow')
    kind = 'connection-close' if '[DESTROY]' in line else 'connection-open' if state == 'ESTABLISHED' or transport == 'udp' else 'network-attempt'
    return {'connectionId': flow_id(source_id, transport, source, source_port, destination, destination_port, first.get('id', '')),
            'sourceIp': source, 'sourcePort': source_port, 'destinationIp': destination, 'destinationPort': destination_port,
            'transport': transport, 'service': service, 'state': state, 'kind': kind, 'observedAt': stamp()}


def socket_line(line, services, destinations, source_id):
    fields = line.split()
    if len(fields) < 4:
        return None
    def endpoint(value):
        host, port = value.rsplit(':', 1)
        return address(host.strip('[]')), int(port)
    try:
        local, port = endpoint(fields[-2])
        peer, peer_port = endpoint(fields[-1])
    except (ValueError, IndexError):
        return None
    service = services.get(f'tcp/{port}')
    if not local or not peer or local not in destinations or not service:
        return None
    return {'connectionId': flow_id(source_id, 'tcp', peer, peer_port, local, port), 'sourceIp': peer,
            'sourcePort': peer_port, 'destinationIp': local, 'destinationPort': port, 'transport': 'tcp',
            'service': service, 'state': 'ESTABLISHED', 'kind': 'connection-snapshot', 'observedAt': stamp()}


def nginx_line(line, service_map, geoip=None, default_service=None):
    try:
        row = json.loads(line)
        service = service_map.get(row.get('server_name')) or default_service
        source = address(str(row.get('remote_addr', '')))
        at = datetime.fromisoformat(str(row['time_iso8601']).replace('Z', '+00:00'))
        if not service or not source or at.tzinfo is None or abs((datetime.now(timezone.utc)-at).total_seconds()) > 86400:
            return None
        # No query strings, body, authorization headers, cookies, referrer or user agent.
        event = {'sourceIp': source, 'service': service, 'kind': 'http-request', 'observedAt': at.isoformat()}
        method = row.get('request_method')
        if isinstance(method, str) and re.fullmatch('[A-Z]{1,12}', method):
            event['method'] = method
        if str(row.get('status', '')).isdigit() and 100 <= int(row['status']) <= 599:
            event['status'] = int(row['status'])
        for source_key, target, factor in [('request_time', 'durationMs', 1000), ('bytes_sent', 'bytesSent', 1)]:
            try:
                value = float(row[source_key]) * factor
                if 0 <= value < 1e12:
                    event[target] = value
            except (KeyError, TypeError, ValueError):
                pass
        return geoip(event) if geoip else event
    except (ValueError, KeyError, TypeError):
        return None


class HostSampler:
    def __init__(self, volumes=None, proc='/proc'):
        self.volumes = volumes or [{'name': 'System', 'path': '/'}]
        self.proc = proc
        self.previous = None

    def sample(self):
        with open(os.path.join(self.proc, 'stat'), encoding='utf-8') as handle:
            values = [int(value) for value in handle.readline().split()[1:9]]
        total, idle = sum(values), values[3] + values[4]
        percent = None
        if self.previous and total > self.previous[0]:
            percent = max(0, min(100, 100 * (1 - (idle-self.previous[1])/(total-self.previous[0]))))
        self.previous = (total, idle)
        memory = {}
        with open(os.path.join(self.proc, 'meminfo'), encoding='utf-8') as handle:
            for line in handle:
                key, value = line.split(':', 1)
                if key in ('MemTotal', 'MemAvailable'):
                    memory[key] = int(value.split()[0]) * 1024
        storage = []
        for volume in self.volumes[:16]:
            stat = os.statvfs(volume['path'])
            storage.append({'name': str(volume['name'])[:100], 'totalBytes': stat.f_blocks*stat.f_frsize,
                            'availableBytes': stat.f_bavail*stat.f_frsize})
        return {'observedAt': stamp(), 'cpuPercent': round(percent, 2) if percent is not None else None,
                'logicalCpus': os.cpu_count() or 1, 'memory': {'totalBytes': memory['MemTotal'], 'availableBytes': memory['MemAvailable']}, 'storage': storage}


def local_addresses():
    command = shutil.which('ip')
    if not command:
        return set()
    result = subprocess.run([command, '-j', 'address', 'show'], capture_output=True, text=True, timeout=5, check=True)
    return {address(info['local']) for item in json.loads(result.stdout) for info in item.get('addr_info', []) if address(info.get('local', ''))}


def geoip_lookup(path):
    if not path:
        return lambda event: event
    import maxminddb
    reader = maxminddb.open_database(path)
    def enrich(event):
        try:
            value = reader.get(event['sourceIp']) or {}
            country = value.get('country', {}).get('iso_code')
            if country and re.fullmatch('[A-Z]{2}', country):
                event['country'] = country
            location = value.get('location', {})
            if country and isinstance(location.get('latitude'), (int, float)) and isinstance(location.get('longitude'), (int, float)):
                event.update(latitude=location['latitude'], longitude=location['longitude'], locationPrecision='city')
        except (ValueError, TypeError):
            pass
        return event
    return enrich
