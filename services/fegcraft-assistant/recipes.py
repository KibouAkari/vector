"""Deterministic installed vanilla recipes. Never claims effective mod recipes."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile

ID = re.compile(r'minecraft:[a-z0-9_./-]{1,96}\Z')
INTENT = re.compile(r'craft|rezept|recipe|herstell|wie (?:baue|baut|mache|macht|stelle|stellt)', re.I)
NAMES = {
    'minecraft:crafting_table': ('Werkbank', 'werkbank', 'crafting table'),
    'minecraft:furnace': ('Ofen', 'ofen', 'furnace'),
    'minecraft:hopper': ('Trichter', 'trichter', 'hopper'),
    'minecraft:chest': ('Truhe', 'truhe', 'chest'),
    'minecraft:iron_ingot': ('Eisenbarren', 'eisenbarren', 'iron ingot'),
    'minecraft:stick': ('Stock', 'stock', 'sticks'),
    'minecraft:torch': ('Fackel', 'fackel', 'torch'),
    'minecraft:piston': ('Kolben', 'kolben', 'piston'),
    'minecraft:repeater': ('Redstone-Verstärker', 'repeater', 'redstone verstärker'),
    'minecraft:comparator': ('Redstone-Komparator', 'komparator', 'comparator'),
    '#minecraft:planks': ('Holzbretter',),
    '#minecraft:stone_crafting_materials': ('Steinmaterial',),
}
UNAVAILABLE = 'dafür habe ich kein eindeutig zugeordnetes Grundrezept. Nenne bitte den genauen Itemnamen oder die Minecraft-ID.'


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value.removeprefix('#')):
        raise ValueError('INVALID_RECIPE_ITEM')
    return value


def ingredient(value):
    if isinstance(value, dict) and set(value) in ({'item'}, {'tag'}):
        key = next(iter(value))
        value = ('#' if key == 'tag' else '') + value[key]
    if isinstance(value, str):
        return [identifier(value)]
    if isinstance(value, list) and 1 <= len(value) <= 8:
        # Flat alternatives only. Unknown custom ingredient predicates are not
        # equivalent to plain items and must not be guessed.
        if any(not isinstance(x, str) for x in value):
            raise ValueError('UNSUPPORTED_RECIPE_INGREDIENT')
        return sorted(set(identifier(x) for x in value))
    raise ValueError('UNSUPPORTED_RECIPE_INGREDIENT')


def normalise(recipe_id, value):
    identifier(recipe_id)
    if not isinstance(value, dict):
        raise ValueError('INVALID_RECIPE')
    kind = value.get('type')
    allowed = {'type', 'group', 'category', 'result', 'show_notification'}
    if kind == 'minecraft:crafting_shaped':
        allowed |= {'pattern', 'key'}
        pattern, keys = value.get('pattern'), value.get('key')
        if (not isinstance(pattern, list) or not 1 <= len(pattern) <= 3
                or any(not isinstance(row, str) or not 1 <= len(row) <= 3 for row in pattern)
                or len({len(row) for row in pattern}) != 1 or not isinstance(keys, dict)
                or any(not isinstance(k, str) or len(k) != 1 or k == ' ' for k in keys)):
            raise ValueError('INVALID_RECIPE_PATTERN')
        used = set(''.join(pattern)) - {' '}
        if not used or used != set(keys):
            raise ValueError('INVALID_RECIPE_KEYS')
        rows = [[None if cell == ' ' else ingredient(keys[cell]) for cell in row] for row in pattern]
    elif kind == 'minecraft:crafting_shapeless':
        allowed |= {'ingredients'}
        items = value.get('ingredients')
        if not isinstance(items, list) or not 1 <= len(items) <= 9:
            raise ValueError('INVALID_RECIPE_INGREDIENTS')
        rows = [[ingredient(item) for item in items]]
    else:
        raise ValueError('UNSUPPORTED_RECIPE_TYPE')
    if set(value) - allowed:
        raise ValueError('UNSUPPORTED_RECIPE_CONDITION')
    result = value.get('result')
    if not isinstance(result, dict) or set(result) - {'id', 'count'} or 'id' not in result:
        raise ValueError('INVALID_RECIPE_RESULT')
    output = identifier(result['id'])
    count = result.get('count', 1)
    if output.startswith('#') or type(count) is not int or not 1 <= count <= 64:
        raise ValueError('INVALID_RECIPE_COUNT')
    return {'id': recipe_id, 'output': output, 'count': count,
            'kind': kind.rsplit(':', 1)[-1], 'rows': rows}


def build_catalog(path, expected_sha256, version='26.2'):
    """Only the explicitly selected game JAR; no cache/mod/datapack merging."""
    if version != '26.2' or not re.fullmatch(r'[a-f0-9]{64}', expected_sha256):
        raise ValueError('UNQUALIFIED_RECIPE_SOURCE')
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('RECIPE_SOURCE_SYMLINK')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 512 * 1024 * 1024:
        raise ValueError('RECIPE_SOURCE_LIMIT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    recipes, unsupported, total = [], 0, 0
    with os.fdopen(fd, 'rb') as stream:
        digest = hashlib.sha256()
        while block := stream.read(1024 * 1024):
            digest.update(block)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('RECIPE_SOURCE_CHANGED')
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > 200_000:
                raise ValueError('RECIPE_ARCHIVE_LIMIT')
            seen = set()
            def read(entry, limit):
                nonlocal total
                if entry.flag_bits & 1 or entry.file_size > limit or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError('RECIPE_MEMBER_LIMIT')
                total += entry.file_size
                if total > 32 * 1024 * 1024:
                    raise ValueError('RECIPE_TOTAL_LIMIT')
                with archive.open(entry) as member:
                    raw = member.read(limit + 1)
                if len(raw) != entry.file_size:
                    raise ValueError('RECIPE_MEMBER_LIMIT')
                return json.loads(raw)
            version_entries = [e for e in entries if e.filename == 'version.json']
            if len(version_entries) != 1 or read(version_entries[0], 65536).get('id') != version:
                raise ValueError('RECIPE_VERSION_MISMATCH')
            for entry in entries:
                match = re.fullmatch(r'data/minecraft/recipe/([a-z0-9_./-]+)\.json', entry.filename)
                if not match:
                    continue
                if '..' in match[1].split('/') or entry.filename in seen or len(seen) >= 8000:
                    raise ValueError('RECIPE_PATH_OR_COUNT_LIMIT')
                seen.add(entry.filename)
                value = read(entry, 128 * 1024)
                try:
                    recipes.append(normalise('minecraft:' + match[1], value))
                except (ValueError, TypeError, KeyError):
                    unsupported += 1
        after = os.fstat(stream.fileno())
    if any(getattr(before, k) != getattr(after, k) or getattr(before, k) != getattr(path.stat(), k)
           for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')):
        raise ValueError('RECIPE_SOURCE_CHANGED')
    result = {'schema': 1, 'scope': 'vanilla-base', 'minecraft_version': version,
              'source_sha256': expected_sha256, 'recipes': sorted(recipes, key=lambda x: x['id']),
              'unsupported_count': unsupported}
    RecipeBook(result)
    return result


def label(token):
    if token in NAMES:
        return NAMES[token][0]
    text = token.removeprefix('#minecraft:').removeprefix('minecraft:').replace('_', ' ').replace('/', ' ')
    return ('Gruppe ' if token.startswith('#') else '') + text


class RecipeBook:
    def __init__(self, data=None):
        self.recipes = []
        if data is None:
            return
        if (not isinstance(data, dict) or set(data) != {'schema', 'scope', 'minecraft_version', 'source_sha256', 'recipes', 'unsupported_count'}
                or type(data['schema']) is not int or data['schema'] != 1 or data['scope'] != 'vanilla-base' or data['minecraft_version'] != '26.2'
                or not isinstance(data['source_sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', data['source_sha256'])
                or type(data['unsupported_count']) is not int or not 0 <= data['unsupported_count'] <= 8000
                or not isinstance(data['recipes'], list) or not 1 <= len(data['recipes']) <= 8000):
            raise ValueError('INVALID_RECIPE_CATALOG')
        seen = set()
        for recipe in data['recipes']:
            if not isinstance(recipe, dict) or set(recipe) != {'id', 'output', 'count', 'kind', 'rows'}:
                raise ValueError('INVALID_RECIPE_CATALOG')
            if identifier(recipe['id']).startswith('#') or identifier(recipe['output']).startswith('#') or recipe['id'] in seen:
                raise ValueError('INVALID_RECIPE_CATALOG')
            seen.add(recipe['id'])
            if type(recipe['count']) is not int or not 1 <= recipe['count'] <= 64:
                raise ValueError('INVALID_RECIPE_CATALOG')
            rows = recipe['rows']
            shaped = recipe['kind'] == 'crafting_shaped'
            if recipe['kind'] not in ('crafting_shaped', 'crafting_shapeless') or not isinstance(rows, list) or not 1 <= len(rows) <= (3 if shaped else 1):
                raise ValueError('INVALID_RECIPE_CATALOG')
            if any(not isinstance(row, list) or not 1 <= len(row) <= (3 if shaped else 9) for row in rows):
                raise ValueError('INVALID_RECIPE_CATALOG')
            if shaped and len({len(row) for row in rows}) != 1:
                raise ValueError('INVALID_RECIPE_CATALOG')
            cells = [cell for row in rows for cell in row if cell is not None]
            if not shaped and any(cell is None for row in rows for cell in row):
                raise ValueError('INVALID_RECIPE_CATALOG')
            if not cells or any(not isinstance(cell, list) or not 1 <= len(cell) <= 8 for cell in cells):
                raise ValueError('INVALID_RECIPE_CATALOG')
            for cell in cells:
                for token in cell:
                    identifier(token)
            self.recipes.append(recipe)

    @classmethod
    def load(cls, path):
        path = Path(path)
        meta = path.stat()
        if path.is_symlink() or not stat.S_ISREG(meta.st_mode) or meta.st_size > 4 * 1024 * 1024:
            raise ValueError('RECIPE_CATALOG_LIMIT')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            raw = handle.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('RECIPE_CATALOG_LIMIT')
        return cls(json.loads(raw))

    def answer(self, question):
        if not INTENT.search(question):
            return None
        q = question.casefold().replace('_', ' ')
        candidates = []
        for recipe in self.recipes:
            output = recipe['output']
            aliases = NAMES.get(output, (output.removeprefix('minecraft:').replace('_', ' '),))
            if any(re.search(r'(?<!\w)' + re.escape(alias.casefold()) + r'(?!\w)', q) for alias in aliases):
                candidates.append(recipe)
        outputs = {r['output'] for r in candidates}
        if len(outputs) != 1:
            return UNAVAILABLE
        recipe = sorted(candidates, key=lambda r: (r['id'] != r['output'], r['id']))[0]
        counts = Counter(tuple(cell) for row in recipe['rows'] for cell in row if cell is not None)
        def choices(cell):
            return ' oder '.join(label(token) for token in cell)
        text = 'Grundrezept für Minecraft 26.2: ' + str(recipe['count']) + 'x ' + label(recipe['output']) + ' aus '
        text += ', '.join(str(count) + 'x ' + choices(cell) for cell, count in counts.items()) + '.'
        if recipe['kind'] == 'crafting_shaped':
            text += ' Reihen: ' + ' | '.join(', '.join(choices(cell) if cell else 'frei' for cell in row) for row in recipe['rows']) + '.'
        else:
            text += ' Anordnung beliebig.'
        text += ' Mod-Anpassungen sind nicht geprüft.'
        return text if len(text) <= 350 else 'das Grundrezept ist für eine kurze Chatantwort zu umfangreich. Bitte grenze die Frage ein.'
