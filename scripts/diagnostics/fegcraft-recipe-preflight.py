#!/usr/bin/env python3
"""Read installed public recipe assets. Candidate evidence, never activation."""
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path('/root/vector-workspace')
BASE = Path('/opt/fegcraft-updated/data')
TARGETS = {'minecraft:crafting_table', 'minecraft:furnace', 'minecraft:hopper'}
RESOURCE = re.compile(r'data/([a-z0-9_.-]+)/recipes?/([a-z0-9_./-]+)\.json\Z')
NESTED = re.compile(r'META-INF/(?:versions/[^/]+|jars)/[^/]+\.jar\Z')
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_JSON = 128 * 1024
MAX_ENTRIES = 200_000
MAX_FILES = 512
MAX_VISITED = 20_000
MAX_READ = 1024 * 1024 * 1024
MAX_HASH = 4 * 1024 * 1024 * 1024


class Refused(RuntimeError):
    """A bounded diagnostic failed. Do not print private paths or raw exceptions."""


def no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise Refused('SYMLINK_REFUSED')


def files(base):
    """Only installed archive trees, never logs, configuration or player files."""
    no_links(base)
    seen = set()
    visited = 0
    roots = [base, base / 'versions', base / 'libraries/net/minecraft',
             base / '.fabric', base / 'mods']
    for root in roots:
        no_links(root)
        if not root.is_dir():
            continue
        for directory, dirs, names in os.walk(root, followlinks=False):
            depth = len(Path(directory).relative_to(root).parts)
            visited += len(dirs) + len(names)
            if visited > MAX_VISITED:
                raise Refused('FILE_WALK_LIMIT')
            # Root-level server JARs only; do not enter world/config/logs.
            dirs[:] = sorted(d for d in dirs if root != base and depth < 8
                             and not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                if path.suffix != '.jar' or path in seen or path.is_symlink():
                    continue
                no_links(path)
                meta = path.stat()
                if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_ARCHIVE:
                    raise Refused('ARCHIVE_SIZE_OR_TYPE')
                seen.add(path)
                if len(seen) > MAX_FILES:
                    raise Refused('ARCHIVE_COUNT_LIMIT')
                yield path


def signature(meta):
    return meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns


class Inventory:
    def __init__(self):
        self.deadline = time.monotonic() + 120
        self.bytes_read = 0
        self.bytes_hashed = 0
        self.entries = 0
        self.recipe_count = 0
        self.types = Counter()
        self.schemas = {}
        self.targets = {}
        self.versions = []
        self.sources = []

    def check(self):
        if time.monotonic() > self.deadline:
            raise Refused('TIME_LIMIT')

    def read(self, archive, entry, limit):
        self.check()
        if (entry.flag_bits & 1 or not 0 <= entry.file_size <= limit
                or stat.S_ISLNK(entry.external_attr >> 16)):
            raise Refused('MEMBER_SIZE_OR_TYPE')
        self.bytes_read += entry.file_size
        if self.bytes_read > MAX_READ:
            raise Refused('READ_LIMIT')
        with archive.open(entry) as stream:
            value = stream.read(limit + 1)
        if len(value) != entry.file_size or len(value) > limit:
            raise Refused('MEMBER_READ_LIMIT')
        return value

    def scan(self, archive, source, depth=0):
        entries = archive.infolist()
        self.entries += len(entries)
        if self.entries > MAX_ENTRIES:
            raise Refused('ENTRY_COUNT_LIMIT')
        selected = set()
        found = False
        for entry in entries:
            self.check()
            name = entry.filename
            match = RESOURCE.fullmatch(name)
            nested = NESTED.fullmatch(name)
            if not (match or nested or name == 'version.json'):
                continue
            if name in selected or '..' in name.split('/'):
                raise Refused('AMBIGUOUS_RESOURCE_PATH')
            selected.add(name)
            if nested:
                if depth >= 2:
                    raise Refused('NESTING_LIMIT')
                content = self.read(archive, entry, MAX_ARCHIVE)
                with zipfile.ZipFile(io.BytesIO(content)) as child:
                    found = self.scan(child, source + '!' + name, depth + 1) or found
                continue
            raw = self.read(archive, entry, MAX_JSON)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise Refused('RESOURCE_NOT_OBJECT')
            if name == 'version.json':
                version = value.get('id')
                if isinstance(version, str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,64}', version):
                    self.versions.append({'source': source, 'id': version})
                continue
            found = True
            self.recipe_count += 1
            recipe_type = value.get('type', 'missing')
            if not isinstance(recipe_type, str) or not re.fullmatch(r'[a-z0-9_.:-]{1,128}', recipe_type):
                raise Refused('RECIPE_TYPE_INVALID')
            self.types[recipe_type] += 1
            if len(self.types) > 128:
                raise Refused('RECIPE_TYPE_LIMIT')
            if recipe_type not in self.schemas:
                if len(value) > 64 or any(not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', key) for key in value):
                    raise Refused('SCHEMA_FIELD_LIMIT')
                self.schemas[recipe_type] = {key: type(item).__name__ for key, item in value.items()}
            recipe_id = match[1] + ':' + match[2]
            if recipe_id in TARGETS:
                if len(raw) > 8192:
                    raise Refused('TARGET_DOCUMENT_LIMIT')
                digest = hashlib.sha256(raw).hexdigest()
                record = self.targets.setdefault((recipe_id, digest), {
                    'id': recipe_id, 'sha256': digest, 'document': value, 'sources': []})
                record['sources'].append(source + '!' + name)
                if len(self.targets) > 32:
                    raise Refused('TARGET_VARIANT_LIMIT')
        return found

    def run(self, base):
        count = 0
        for path in files(base):
            count += 1
            self.check()
            before = path.stat()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                if signature(os.fstat(stream.fileno())) != signature(before):
                    raise Refused('ARCHIVE_CHANGED')
                with zipfile.ZipFile(stream) as archive:
                    found = self.scan(archive, path.relative_to(base).as_posix())
                if found:
                    self.bytes_hashed += before.st_size
                    if self.bytes_hashed > MAX_HASH:
                        raise Refused('HASH_LIMIT')
                    stream.seek(0)
                    digest = hashlib.sha256()
                    while block := stream.read(1024 * 1024):
                        self.check()
                        digest.update(block)
                    self.sources.append({'archive': path.relative_to(base).as_posix(),
                                         'sha256': digest.hexdigest(), 'bytes': before.st_size})
                if signature(os.fstat(stream.fileno())) != signature(before):
                    raise Refused('ARCHIVE_CHANGED')
            if signature(path.stat()) != signature(before):
                raise Refused('ARCHIVE_CHANGED')
        packs = base / 'world/datapacks'
        no_links(packs)
        # Count only. Do not read level.dat or infer enabled pack order.
        pack_count = 0
        if packs.is_dir():
            with os.scandir(packs) as entries:
                for _ in entries:
                    pack_count += 1
                    if pack_count > MAX_VISITED:
                        raise Refused('DATAPACK_COUNT_LIMIT')
        targets = sorted(self.targets.values(), key=lambda x: (x['id'], x['sha256']))
        missing = sorted(TARGETS - {item['id'] for item in targets})
        return {'candidate_inventory_complete': not missing, 'missing_targets': missing,
                'archives_examined': count, 'recipe_documents': self.recipe_count,
                'source_archives': self.sources, 'versions': self.versions,
                'recipe_types': dict(sorted(self.types.items())), 'schemas': self.schemas,
                'target_variants': targets, 'datapack_entries': pack_count,
                'active_pack_order_verified': False, 'effective_recipes_qualified': False,
                'production_activated': False, 'model_calls': 0, 'cloud_calls': 0,
                'messages_sent': 0, 'api_cost_chf': 0}


def command(*args):
    result = subprocess.run(args, capture_output=True, timeout=25)
    if result.returncode:
        raise Refused('STATE_COMMAND_FAILED')
    return result.stdout


def production_state():
    paths = (Path('/opt/vector/docker-compose.yml'), BASE.parent / 'docker-compose.yml')
    profiles = []
    for path in paths:
        no_links(path)
        profiles.append(hashlib.sha256(path.read_bytes()).hexdigest())
    values = json.loads(command('docker', 'inspect', 'vector-app', 'fegcraft-updated',
                                'vector-local-inference', 'vector-privacy-ner'))
    return profiles, sorted((item['Id'], item['Image']) for item in values)


def main():
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise Refused('PIN_REQUIRED')
    no_links(ROOT)
    with (ROOT / '.chat-release.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        directory = ROOT / 'releases' / ('vector-fegcraft-recipes-' + stamp + '-' + secrets.token_hex(3))
        no_links(directory.parent)
        directory.mkdir(mode=0o700)
        print('Read installed public recipe assets only. No model calls, restart or chat messages.', flush=True)
        before = production_state()
        report = {'revision': revision, 'candidate_inventory_complete': False,
                  'effective_recipes_qualified': False, 'production_activated': False}
        error = None
        try:
            report.update(Inventory().run(BASE))
        except Exception as exc:
            error = str(exc) if isinstance(exc, Refused) else type(exc).__name__
        finally:
            report['production_unchanged'] = production_state() == before
            report['error'] = error
            report['passed'] = bool(report['candidate_inventory_complete'] and
                                    report['production_unchanged'] and error is None)
            output = directory / 'result.json'
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print('Report: ' + str(output), flush=True)
        if not report['passed']:
            raise Refused('CANDIDATE_INVENTORY_INCOMPLETE')
        print('Candidate assets captured. Active recipe precedence and runtime delivery remain unqualified.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, Refused) else type(exc).__name__
        print('ERROR: ' + reason + '. No activation performed.', file=sys.stderr)
        sys.exit(1)
