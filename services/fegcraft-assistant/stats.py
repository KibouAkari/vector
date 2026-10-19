"""Bounded read-only statistics. Never read world metadata, ops or configuration."""
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone

METRICS = {
    'play_time': ('Spielzeit', 'h', 72000, ('play_time',)),
    'distance': ('Strecke', 'km', 100000, (
        'walk_one_cm', 'sprint_one_cm', 'swim_one_cm', 'aviate_one_cm',
        'boat_one_cm', 'horse_one_cm', 'minecart_one_cm')),
    'mob_kills': ('Mobkills', 'Kills', 1, ('mob_kills',)),
    'player_kills': ('Spielerkills', 'Kills', 1, ('player_kills',)),
    'deaths': ('Tode', 'Tode', 1, ('deaths',)),
}
UUID = re.compile(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}')
PLAYER = re.compile(r'[A-Za-z0-9_]{1,16}')


def read_json(path, limit=2_000_000):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ValueError('Unsupported statistics file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Statistics file exceeds limit')
        return json.loads(data), meta.st_mtime
    finally:
        os.close(fd)


def snapshot(stats_dir, usercache, max_players=1000, include_items=False):
    """Paths are configured by the operator, never taken from a chat message.

    Distance deliberately matches the existing seven-category FEGCraft report.
    Absent counters in a valid custom-statistics map count as zero, as in that
    report; unreadable files or absent category maps never become zero players.
    """
    root = Path(stats_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Statistics directory unavailable')
    identities, _ = read_json(usercache)
    if not isinstance(identities, list) or len(identities) > 10000:
        raise ValueError('Invalid identity map')
    names = {}
    for item in identities:
        if not isinstance(item, dict):
            continue
        uid, name = item.get('uuid', ''), item.get('name', '')
        if isinstance(uid, str) and isinstance(name, str) and UUID.fullmatch(uid) and PLAYER.fullmatch(name):
            names[uid.lower()] = name
    files = []
    for path in root.iterdir():
        if path.suffix == '.json' and UUID.fullmatch(path.stem):
            files.append(path)
            if len(files) > max_players:
                raise ValueError('Player limit exceeded; no partial ranking')
    players, skipped, unknown = [], 0, 0
    for path in sorted(files):
        try:
            value, modified = read_json(path)
            custom = value['stats']['minecraft:custom']
            if not isinstance(custom, dict):
                raise ValueError('Missing statistics category')
            metrics = {}
            for metric, (_, _, divisor, fields) in METRICS.items():
                values = [custom.get('minecraft:' + field, 0) for field in fields]
                if any(type(v) is not int or v < 0 or v > 2**53-1 for v in values):
                    raise ValueError('Invalid counter')
                metrics[metric] = sum(values) / divisor if divisor != 1 else sum(values)
            uid = path.stem.lower()
            if uid not in names:
                unknown += 1
            person = {'uuid': uid, 'name': names.get(uid), 'values': metrics,
                      'saved_at': datetime.fromtimestamp(modified, timezone.utc).isoformat()}
            if include_items:
                for category in ('used', 'mined'):
                    counters = value['stats'].get('minecraft:' + category, {})
                    if (not isinstance(counters, dict) or len(counters) > 20000
                            or any(not isinstance(k, str) or not re.fullmatch(r'[a-z0-9_.-]{1,64}:[a-z0-9_./-]{1,96}', k)
                                   or type(v) is not int or not 0 <= v <= 2**53 - 1 for k, v in counters.items())):
                        raise ValueError('Invalid item counters')
                    person[category] = counters
            players.append(person)
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            skipped += 1
    return {'read_at': datetime.now(timezone.utc).isoformat(), 'players': players,
            'coverage': {'files': len(files), 'read': len(players),
                         'skipped': skipped, 'unnamed': unknown},
            'source': 'saved_player_statistics',
            'distance_scope': 'walk,sprint,swim,elytra,boat,horse,minecart'}


def require_complete(data):
    coverage = data['coverage']
    if not data['players'] or coverage['skipped'] or coverage['unnamed']:
        raise ValueError('Incomplete statistics; no definitive record available')


def leaders(data, metric, limit=1):
    require_complete(data)
    if metric not in METRICS or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('Unsupported ranking')
    ordered = sorted(data['players'], key=lambda p: (-p['values'][metric], p['name'].casefold()))
    cutoff = ordered[min(limit, len(ordered))-1]['values'][metric]
    # Include ties; do not pretend an arbitrary name is the sole record holder.
    return [{'name': p['name'], 'value': p['values'][metric]} for p in ordered
            if p['values'][metric] >= cutoff]


def records(data, player):
    require_complete(data)
    matches = [p for p in data['players'] if p['name'].casefold() == player.casefold()]
    if len(matches) != 1:
        raise ValueError('Unknown or ambiguous player')
    person = matches[0]
    result = []
    for metric, (label, unit, _, _) in METRICS.items():
        top = leaders(data, metric)
        if person['values'][metric] > 0 and any(p['name'] == person['name'] for p in top):
            result.append({'metric': metric, 'label': label, 'unit': unit,
                           'value': person['values'][metric], 'shared': len(top) > 1})
    return {'name': person['name'], 'records': result, 'read_at': data['read_at'],
            'saved_at': person['saved_at']}


def rank(data, person, metric):
    require_complete(data)
    return 1 + sum(p['values'][metric] > person['values'][metric] for p in data['players'])


def block_leaders(data, category, block_items=()):
    require_complete(data)
    if category not in ('used', 'mined') or category == 'used' and not block_items:
        raise ValueError('Live block registry required')
    allowed = set(block_items)
    totals = {}
    for player in data['players']:
        for identifier, count in player[category].items():
            if category == 'mined' or identifier in allowed:
                totals[identifier] = totals.get(identifier, 0) + count
    highest = max(totals.values(), default=0)
    return [(identifier, count) for identifier, count in sorted(totals.items()) if count == highest and count > 0]





def mined_leaders(data, identifiers):
    """Saved block counters, not item drops or current inventory. Include ties."""
    require_complete(data)
    if not isinstance(identifiers, tuple) or not 1 <= len(identifiers) <= 3:
        raise ValueError('Unsupported block group')
    counts = [(p['name'], sum(p['mined'].get(k, 0) for k in identifiers)) for p in data['players']]
    highest = max(v for _, v in counts)
    return [{'name': n, 'value': v} for n, v in sorted(counts, key=lambda row: row[0].casefold()) if v == highest and v > 0]
