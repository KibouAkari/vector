#!/usr/bin/env python3
"""Update the web app and install the user-authorized local metadata collector.
Run from a pinned, complete source checkout. No paid tests or game restarts.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--public-url',required=True)
    parser.add_argument('--app',default='vector-app')
    args=parser.parse_args()
    url=urlsplit(args.public_url)
    if os.geteuid()!=0 or url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise RuntimeError('Run as root with the HTTPS Vector origin')
    source=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(source/'scripts/collectors/observatory'))
    from install import prepare_key,install
    args.traffic_key_file=str(prepare_key(args.app))
    spec=importlib.util.spec_from_file_location('vector_web_update',source/'scripts/deploy/update-operations-web.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    update=module.Update(args)
    print('Private update evidence: '+str(update.release),flush=True)
    update.apply()
    try:
        install(args.public_url,args.app)
    except Exception:
        print(json.dumps({'webUpdated':True,'collectorInstalled':False,'message':'The app update succeeded. Collector setup did not finish. Inspect the local log; the app does not need to be rebuilt to retry collector installation.'}),flush=True)
        raise


if __name__=='__main__':main()
