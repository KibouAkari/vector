#!/usr/bin/env python3
"""Read nginx JSON lines from stdin and post bounded signed batches. No model calls.
Required fields: remote_addr, server_name, time_iso8601.
Optional country_code, latitude, longitude must come from your trusted local GeoIP.
Unknown hosts are ignored. X-Forwarded-For is never trusted by this collector.
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit


def events(lines, services):
    for line in lines:
        try:
            row = json.loads(line)
            if row.get('server_name') not in services:
                continue
            ipaddress.ip_address(row['remote_addr'])
            at = datetime.fromisoformat(row['time_iso8601'].replace('Z', '+00:00'))
            if at.tzinfo is None or abs((datetime.now(timezone.utc)-at).total_seconds()) > 86400:
                continue
            item = {'sourceIp': row['remote_addr'], 'service': services[row['server_name']],
                    'kind': 'http-request', 'observedAt': at.isoformat()}
            if isinstance(row.get('country_code'), str) and len(row['country_code']) == 2:
                item['country'] = row['country_code'].upper()
                for key in ('latitude', 'longitude'):
                    if key in row:
                        item[key] = float(row[key])
            yield item
        except (KeyError, ValueError, TypeError):
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--services', required=True, help='JSON file mapping exact nginx server_name to service label')
    args = parser.parse_args()
    url = urlsplit(args.endpoint)
    if url.scheme != 'https' or url.username or url.password or url.query or url.fragment or url.path != '/api/traffic':
        raise SystemExit('Use the HTTPS /api/traffic endpoint without credentials or query parameters.')
    key = os.environ.get('VECTOR_TRAFFIC_INGEST_TOKEN', '')
    if len(key) < 32:
        raise SystemExit('Set a random VECTOR_TRAFFIC_INGEST_TOKEN of at least 32 characters.')
    with open(args.services, encoding='utf-8') as handle:
        services = json.load(handle)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # Refuse redirects before transmitting an authenticated follow-up request.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener.add_handler(NoRedirect())
    def send(batch):
        body = json.dumps({'events': batch}, separators=(',', ':')).encode()
        stamp, nonce = str(int(time.time()*1000)), str(uuid.uuid4())
        signature = hmac.new(key.encode(), (stamp+'\n'+nonce+'\n').encode()+body, hashlib.sha256).hexdigest()
        request = urllib.request.Request(args.endpoint, data=body, headers={
            'Content-Type': 'application/json', 'X-Vector-Timestamp': stamp,
            'X-Vector-Nonce': nonce, 'X-Vector-Signature': signature})
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError('Traffic ingest failed')
        print(json.dumps({'accepted': len(batch)}))
    batch = []
    for event in events(sys.stdin, services):
        batch.append(event)
        if len(batch) == 100:
            send(batch)
            batch = []
    if batch:
        send(batch)


if __name__ == '__main__':
    main()
