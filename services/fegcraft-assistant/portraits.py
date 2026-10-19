"""Fresh public game portraits; no stored labels, private logs or channel transcript."""
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import re
import threading
import time
import unicodedata
import stats

INTENT=re.compile(r'einschätz|einschaetz|beurteil|bewert|\b(?:bin ich|ist \w+) (?:ein |eine |wirklich |eigentlich )?gut\w* spieler|was (?:hältst|haltest|denkst|meinst|findest) du (?:eigentlich |so )?(?:von|über|ueber)|wie findest du|beschreib\w* (?:mich|den spieler)|spielerportr|spielertyp|was bin ich für ein spieler',re.I)
SELF=re.compile(r'\b(?:bin ich|mich|von mir|über mich|ueber mich|mein(?:e[rmns]?)? (?:spielstil|profil|spieler))\b',re.I)
KNOWN_ADVANCEMENTS={'minecraft:adventure/sniper_duel':'Sniper-Duell','minecraft:adventure/kill_all_mobs':'Monsterjäger',
 'minecraft:adventure/adventuring_time':'Abenteurer','minecraft:nether/explore_nether':'Nether-Erkundung',
 'minecraft:end/kill_dragon':'Drachensieg','minecraft:husbandry/bred_all_animals':'Tierzüchter'}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if c.isalnum() and not unicodedata.combining(c))


def distance_one(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))<=1
    if len(a)>len(b):a,b=b,a
    return any(a==b[:i]+b[i+1:] for i in range(len(b)))


def targets(question,players):
    tokens={normalized(x) for x in re.findall(r'\w+',question)}
    exact=[p for p in players if normalized(p['name']) in tokens]
    if exact:return exact
    result=[]
    for p in players:
        name=normalized(p['name']);compact=re.sub(r'\d','',name)
        if any(len(t)>=4 and (t==compact or name.startswith(t) or (len(t)>=6 and (distance_one(t,name) or distance_one(t,compact)))) for t in tokens):result.append(p)
    return result


def advancement_summary(directory,uid):
    if directory is None:return None
    root=Path(directory)
    if root.is_symlink() or not root.is_dir():return None
    try:
        value,_=stats.read_json(root/(uid+'.json'))
        if not isinstance(value,dict) or len(value)>20000:raise ValueError('ADVANCEMENT_LIMIT')
        count=0;known=[]
        for identifier,row in value.items():
            if identifier=='DataVersion':continue
            if not isinstance(identifier,str) or not re.fullmatch(r'[a-z0-9_.-]{1,64}:[a-z0-9_./-]{1,160}',identifier):raise ValueError('ADVANCEMENT_ID')
            if not isinstance(row,dict) or type(row.get('done')) is not bool:raise ValueError('ADVANCEMENT_SCHEMA')
            criteria=row.get('criteria',{})
            if not isinstance(criteria,dict) or len(criteria)>1000:raise ValueError('ADVANCEMENT_CRITERIA')
            stamps=[]
            for stamp in criteria.values():
                if not isinstance(stamp,str) or len(stamp)>40:raise ValueError('ADVANCEMENT_DATE')
                stamps.append(datetime.strptime(stamp,'%Y-%m-%d %H:%M:%S %z').timestamp())
            if row['done'] and not identifier.startswith('minecraft:recipes/'):
                count+=1
                if identifier in KNOWN_ADVANCEMENTS:known.append((max(stamps,default=0),KNOWN_ADVANCEMENTS[identifier]))
        return dict(count=count,latest=max(known,default=(0,None))[1])
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None


class PlayerPortraits:
    def __init__(self,stats_dir,usercache,advancements=None,clock=time.monotonic):
        self.stats_dir,self.usercache,self.advancements=stats_dir,usercache,advancements
        self.clock=clock;self.context=OrderedDict();self.lock=threading.Lock()

    def clear(self,scope):
        with self.lock:self.context.pop(scope,None)

    def answer(self,question,principal,scope,block_items=()):
        if re.search(r'bogen|\bbow\b',question,re.I) and re.search(r'kills|töt|toet|getötet',question,re.I):
            self.clear(scope)
            return 'Bogennutzungen und einzelne Fortschritte kann ich einordnen, aber daraus keine Bogenkills zählen. Dafür fehlt mir ein geprüfter Ereigniszähler.'
        followup=bool(re.fullmatch(r'\s*und (?:er|sie|der|die|was ist mit (?:ihm|ihr))\s*[?.!]*',question,re.I))
        if not INTENT.search(question) and not followup:self.clear(scope);return None
        try:
            data=stats.snapshot(self.stats_dir,self.usercache,include_items=True);stats.require_complete(data)
        except (OSError,ValueError,KeyError,TypeError):
            self.clear(scope);return 'für ein faires Spielerporträt sind die gespeicherten Statistiken gerade unvollständig. Ich möchte niemandem falsche Werte anhängen.'
        matches=targets(question,data['players'])
        if not matches and not SELF.search(question) and re.search(r'\b(?:minecraft|redstone|vector|mods?|backpack|rucksack|claims?|partys)\b',question,re.I):
            self.clear(scope);return None
        if SELF.search(question):
            if principal is None:self.clear(scope);return 'welchen Minecraft-Spielernamen meinst du? Dein Discord-Anzeigename ist keine bestätigte Minecraft-Verknüpfung.'
            matches=[p for p in data['players'] if p['uuid']==principal]
        if not matches and followup:
            with self.lock:
                prior=self.context.get(scope)
                if prior and prior[1]>self.clock():matches=[p for p in data['players'] if p['uuid']==prior[0]]
        if len(matches)!=1:
            self.clear(scope);return 'nenne bitte einen eindeutigen Minecraft-Spielernamen, dann gebe ich dir ein kurzes Spielerporträt aus seinen Spielwerten.'
        p=matches[0];v=p['values'];rank=lambda metric:stats.rank(data,p,metric)
        details=[];joke='noch kein eindeutiger Spielstil erkennbar. Ein paar weitere Abenteuer fehlen mir fürs grosse Urteil.'
        def n(x):return f'{int(x):,}'.replace(',',"'")
        def metric(key,label):return n(v[key])+' '+label+' (Rang '+str(rank(key))+')'
        if v['deaths']>=100 and rank('deaths')<=2:
            details=[metric('deaths','Tode')]
            joke=('Respawn-Stammkunde. Der Wiederbelebungspunkt kennt ihn wohl schon beim Vornamen.' if rank('deaths')==1
                  else 'Respawn-Vizechampion. Er erkundet die Welt offenbar gern auch vom Wiederbelebungspunkt aus.')
        elif v['player_kills']>0 and rank('player_kills')<=2 and rank('mob_kills')<=3:
            details=[metric('mob_kills','Mobkills'),metric('player_kills','Spielerkills')]
            joke='Endgegner mit leicht blutdurstiger Kill-Liste. Auf ein Duell würde ich trotzdem nicht nur nach Zahlen wetten.'
        elif v['play_time']>0 and rank('play_time')<=3 and v['distance']>0 and rank('distance')<=3:
            details=[f"{v['play_time']:.1f} h Spielzeit",f"{v['distance']:.1f} km Strecke"]
            blocks=sum(p['used'].get(k,0) for k in set(block_items))
            if blocks>0:details.append(n(blocks)+' platzierte Blöcke')
            joke='Architekt auf Weltreise und offenbar ein treuer Stammgast.' if blocks>=500 else 'Weltenbummler mit Dauerticket. Das Zuhause ist offenbar der ganze Server.'
        else:
            selected=sorted((k for k in stats.METRICS if v[k]>0),key=lambda k:(rank(k),list(stats.METRICS).index(k)))[:2]
            for key in selected:
                label,unit,_,_=stats.METRICS[key];amount=f'{v[key]:.1f}' if unit in ('h','km') else n(v[key])
                details.append(amount+' '+unit+' '+label+' (Rang '+str(rank(key))+')')
            if selected:joke={'mob_kills':'Monster haben hier wohl keine ruhige Nachbarschaft.','player_kills':'Für friedliche Verhandlungen wird offenbar nicht immer Zeit eingeplant.',
                 'play_time':'Der Server scheint ein gemütliches zweites Zuhause zu sein.','distance':'Reiselust statt Stillstand. Die Schuhe haben sich ihre Pause verdient.',
                 'deaths':'Abenteuerlust ist vorhanden; die Landung braucht gelegentlich noch Feinschliff.'}[selected[0]]
        bow=p['used'].get('minecraft:bow',0)
        if bow>0 and bow==max(x['used'].get('minecraft:bow',0) for x in data['players']):details.append(n(bow)+' Bogennutzungen (Rang 1)')
        advancement=advancement_summary(self.advancements,p['uuid'])
        if advancement and advancement['count']:details.append(str(advancement['count'])+' Fortschritte'+(' inkl. '+advancement['latest'] if advancement['latest'] else ''))
        suffix=' Mein Spieleindruck: '+joke
        lead=p['name']+': '+('; '.join(details) if details else 'noch wenig gespeicherte Spielwerte')+'.'
        if len(lead+suffix)>355:suffix=' Mein Spieleindruck: '+joke.split('. ')[0]+'.'
        while len(lead+suffix)>355 and len(details)>1:
            details.pop(1);lead=p['name']+': '+'; '.join(details)+'.'
        with self.lock:
            for key in list(self.context):
                if self.context[key][1]<=self.clock():self.context.pop(key,None)
            self.context.pop(scope,None);self.context[scope]=(p['uuid'],self.clock()+180)
            while len(self.context)>256:self.context.popitem(last=False)
        return lead+suffix
