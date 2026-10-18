"""Read only public recipe JSON exported from the exact installed backpack JAR."""
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import zipfile
from runtime import safe_answer
from recipes import label

NAMESPACE = 'travelersbackpack'
VERSION = '11.3.2'
ID = re.compile(r'#?[a-z0-9_.-]{1,64}:[a-z0-9_./-]{1,96}')
LABELS = {'#c:strings': 'Faden', '#c:leathers': 'Leder', '#c:chests/wooden': 'Holztruhe',
          '#travelersbackpack:sleeping_bags': 'Schlafsack', 'travelersbackpack:backpack_tank': 'Rucksacktank',
          'travelersbackpack:standard': 'Standardrucksack'}


def export_installed(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128*1024*1024:
        raise ValueError('BACKPACK_ARCHIVE_LIMIT')
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''): digest.update(block)
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if len(entries)>30000 or len({i.filename for i in entries})!=len(entries): raise ValueError('BACKPACK_ENTRY_LIMIT')
        meta=archive.getinfo('fabric.mod.json')
        if meta.file_size>32768: raise ValueError('BACKPACK_METADATA_LIMIT')
        mod=json.loads(archive.read(meta))
        if mod.get('id')!=NAMESPACE or mod.get('version')!=VERSION: raise ValueError('BACKPACK_VERSION_CHANGED')
        recipes={}; size=0
        for info in entries:
            match=re.fullmatch(r'data/travelersbackpack/recipes?/([a-z0-9_/-]+)\.json',info.filename)
            if not match: continue
            size+=info.file_size
            if info.file_size>32768 or size>2_000_000 or len(recipes)>=1000: raise ValueError('BACKPACK_RECIPE_LIMIT')
            recipes[NAMESPACE+':'+match[1]]=json.loads(archive.read(info))
    value={'schema':1,'mod':NAMESPACE,'version':VERSION,'jar_sha256':digest.hexdigest(),'recipes':recipes}
    if not recipes: raise ValueError('BACKPACK_RECIPES_MISSING')
    return value


class ModRecipes:
    def __init__(self,path,expected):
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as handle:
            meta=os.fstat(handle.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_size>2_000_000: raise ValueError('BACKPACK_CATALOG_LIMIT')
            raw=handle.read(2_000_001)
        value=json.loads(raw)
        if len(raw)>2_000_000 or not re.fullmatch('[a-f0-9]{64}',expected) or hashlib.sha256(raw).hexdigest()!=expected:
            raise ValueError('BACKPACK_CATALOG_CHANGED')
        if (set(value)!={'schema','mod','version','jar_sha256','recipes'} or value['schema']!=1
            or value['mod']!=NAMESPACE or value['version']!=VERSION or not re.fullmatch('[a-f0-9]{64}',value['jar_sha256'])
            or not isinstance(value['recipes'],dict) or not 1<=len(value['recipes'])<=1000): raise ValueError('BACKPACK_CATALOG_SCHEMA')
        self.value=value

    def render(self,identifier):
        recipe=self.value['recipes'].get(identifier,{})
        if recipe.get('type') not in ('minecraft:crafting_shaped','travelersbackpack:backpack_shaped'):
            return None
        pattern=recipe.get('pattern'); keys=recipe.get('key'); result=recipe.get('result')
        if (not isinstance(pattern,list) or not 1<=len(pattern)<=3 or not isinstance(keys,dict)
            or any(not isinstance(row,str) or not 1<=len(row)<=3 for row in pattern)
            or len(set(map(len,pattern)))!=1 or not isinstance(result,dict)
            or result.get('id',result.get('item'))!=identifier or type(result.get('count',1)) is not int or not 1<=result.get('count',1)<=64): return None
        def item(value):
            if isinstance(value,dict) and set(value) in ({'item'},{'tag'}):
                value=('#' if 'tag' in value else '')+next(iter(value.values()))
            if not isinstance(value,str) or not ID.fullmatch(value): raise ValueError('BACKPACK_INGREDIENT_SCHEMA')
            return value
        try:
            mapping={k:item(v) for k,v in keys.items() if isinstance(k,str) and len(k)==1 and k!=' '}
            if len(mapping)!=len(keys): return None
            rows=[]
            for row in pattern:
                rows.append(', '.join('frei' if c==' ' else LABELS.get(mapping[c],label(mapping[c].lstrip('#'))) for c in row))
            name=LABELS.get(identifier,label(identifier))
            count=result.get('count',1)
            text=('für den '+name if count==1 else 'für '+str(count)+'x '+name)+': '+ ' | '.join(rows) + '. Von oben nach unten; Grundrezept der installierten Mod.'
            if len(text)>340:return None
            return safe_answer(text)
        except (KeyError,ValueError,TypeError): return None

    def answer(self,question):
        q=question.casefold()
        if not re.search(r'backpack|rucksack|rucksäcke|rucksaecke|rucksacktank',q): return None
        if not re.search(r'craft|rezept|recipe|herstell|bekomm|kriege|erhalte|tank',q): return None
        if re.search(r'eisen|iron|gold|diamant|diamond|netherit|creeper|drache|dragon|roten?|blauen?|grünen?|gruenen?',q):
            return 'welche genaue Rucksack-Variante meinst du? Ihr Rezept kann vom Standardrucksack abweichen; ich möchte dir keine falschen Zutaten nennen.'
        identifier='travelersbackpack:backpack_tank' if re.search(r'tank',q) else 'travelersbackpack:standard'
        return self.render(identifier) or 'das genaue Mod-Grundrezept ist gerade nicht verfügbar. Welchen Rucksack meinst du genau?'
