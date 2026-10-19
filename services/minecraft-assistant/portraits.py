"""Fresh public game portraits; no stored labels, private logs or channel transcript."""
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import re
import threading
import time
import unicodedata
import stats

INTENT=re.compile(r'einschätz|einschaetz|beurteil|bewert|\b(?:bin ich|ist \w+) (?:ein |eine |wirklich |eigentlich )?gut\w* spieler|(?:was )?(?:hältst|haltest|denkst|meinst|findest) du (?:eigentlich |so )?(?:von|über|ueber)|wie findest du|beschreib\w* (?:mich|den spieler)|spielerportr|spielertyp|was bin ich für ein spieler',re.I)
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
    exact=[p for p in players if normalized(p['name']) in tokens or re.search(r'\b(?:von|über|ueber)'+re.escape(p['name'])+r'(?![A-Za-z0-9_])',question,re.I)]
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
            if row['done'] and not identifier.split(':',1)[1].startswith('recipes/'):
                count+=1
                if identifier in KNOWN_ADVANCEMENTS:known.append((max(stamps,default=0),KNOWN_ADVANCEMENTS[identifier]))
        return dict(count=count,latest=max(known,default=(0,None))[1])
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None


class PlayerPortraits:
    def __init__(self,stats_dir,usercache,advancements=None,clock=time.monotonic):
        self.stats_dir,self.usercache,self.advancements=stats_dir,usercache,advancements
        self.clock=clock;self.context=OrderedDict();self.variants=OrderedDict();self.lock=threading.Lock()

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
        key=(scope,p['uuid']);now=self.clock()
        with self.lock:
            for old in list(self.variants):
                if self.variants[old][1]<=now:self.variants.pop(old,None)
            previous=self.variants.pop(key,(0,0))[0]
            self.variants[key]=(previous+1,now+180)
            while len(self.variants)>256:self.variants.popitem(last=False)
        n=lambda x:f'{int(x):,}'.replace(',',"'")
        own=principal==p['uuid']
        subject='Du' if own else p['name']
        has='hast' if own else 'hat'
        # Describe multiple observable strengths, not a permanent label. Every
        # clause is tied to this fresh snapshot; no invented victims or weapon kills.
        traits=[]
        def add(score,kind,text):traits.append((score,kind,text))
        if v['player_kills']>0 and rank('player_kills')<=2:
            add(1.55,'fighter',f"{subject} {has} {n(v['player_kills'])} Spielerkills (Rang {rank('player_kills')}) – friedliche Verhandlungen sind offenbar nicht immer die erste Wahl.")
        if v['mob_kills']>=100 and rank('mob_kills')<=3:
            add(1.5,'hunter',f"Mit {n(v['mob_kills'])} Mobkills (Rang {rank('mob_kills')}) sieht die Nachbarschaft für Monster ziemlich ungemütlich aus.")
        blocks=sum(p['used'].get(k,0) for k in set(block_items))
        if blocks>=500:
            add(1.3,'builder',f"{n(blocks)} platzierte Blöcke sprechen für ordentlich Baulust.")
        if v['distance']>=1 and rank('distance')<=3:
            add(1.25,'traveler',f"{v['distance']:,.1f} km Strecke (Rang {rank('distance')}) – Stillstehen scheint nicht die Lieblingsbeschäftigung zu sein.".replace(',',"'"))
        bow=p['used'].get('minecraft:bow',0)
        if bow>0 and bow==max(x['used'].get('minecraft:bow',0) for x in data['players']):
            add(1.05,'archer',f"Dazu {n(bow)} Bogennutzungen (Rang 1): Der Bogen liegt wohl selten nur zur Dekoration herum.")
        if v['deaths']>=100 and rank('deaths')<=2:
            add(1.35,'respawn',f"Bei {n(v['deaths'])} Toden (Rang {rank('deaths')} nach Anzahl) kennt der Respawn-Punkt vermutlich schon die Lieblingsposition.")
        if v['play_time']>=1:
            add(.85,'regular',f"{v['play_time']:.1f} h Spielzeit: Das hier scheint ein recht gemütliches zweites Zuhause zu sein.")
        advancement=advancement_summary(self.advancements,p['uuid'])
        if advancement and advancement['latest']:
            add(.9,'adventure',f"{advancement['count']} Fortschritte, darunter {advancement['latest']}: Ein bisschen Abenteuergeist ist jedenfalls belegt.")
        elif advancement and advancement['count']:
            add(.7,'adventure',f"{advancement['count']} Fortschritte zeigen, dass auch abseits der Ranglisten etwas passiert.")
        if not traits:
            positive=[k for k in stats.METRICS if v[k]>0]
            if positive:
                metric=min(positive,key=rank);label,unit,_,_=stats.METRICS[metric]
                amount=f'{v[metric]:.1f}' if unit in ('h','km') else n(v[metric])
                add(.5,'new',f"Bisher stehen {amount} {unit} bei {label} in den Spielwerten. Für ein grosses Urteil ist das noch eine kleine Grundlage.")
        if re.search(r'bogen|bow',question,re.I):
            traits=[(score+3 if kind=='archer' else score,kind,text) for score,kind,text in traits]
        if re.search(r'fortschritt|achievement|advancement',question,re.I):
            traits=[(score+3 if kind=='adventure' else score,kind,text) for score,kind,text in traits]
        traits.sort(key=lambda row:-row[0])
        chosen=traits[:2]
        kinds={kind for _,kind,_ in chosen}
        if {'builder','traveler'}<=kinds:
            labels=('Architekt auf Weltreise','Bauprofi mit Fernweh','Baustelle und Weltreise in einer Person')
        elif {'fighter','hunter'}<=kinds:
            labels=('Endgegner mit leicht blutdurstiger Kill-Liste','Monsterjäger mit Duell-Ambitionen','ordentlich kampflustiges Gesamtpaket')
        elif 'respawn' in kinds:
            labels=('Abenteurer mit Respawn-Stammkarte','mutig unterwegs, Landung noch ausbaufähig','Entdecker mit kurzer Rückfahrt zum Spawn')
        elif 'traveler' in kinds:
            labels=('Weltenbummler mit Dauerticket','Entdecker mit akutem Fernweh','Reisender, dessen Zuhause die ganze Karte ist')
        elif 'archer' in kinds:
            labels=('Bogenschütze mit reichlich Übung','jemand, dessen Bogen kaum Pause bekommt','Fernkämpfer nach Trainingsstand, nicht nach bestätigten Kills')
        elif 'builder' in kinds:
            labels=('Baumeister mit gut gefülltem Blockvorrat','jemand, der eine leere Fläche als Einladung sieht','Baulust statt Langeweile')
        elif 'fighter' in kinds or 'hunter' in kinds:
            labels=('eher Gegner als Zuschauer','Monster-Schreck im Aufbau','jemand mit reichlich Kampflust')
        else:
            labels=('ein eigener Spielstil im Aufbau','jemand mit Lust aufs nächste Abenteuer','ein Spieler, dessen Geschichte noch weitergeht')
        label=labels[previous%len(labels)]
        intro=(f'Du? Für mich: {label}.' if own else f'{p["name"]}? Für mich: {label}.')
        if previous%3==1:intro=(f'Zu dir passt für mich: {label}.' if own else f'Bei {p["name"]} denke ich an {label}.')
        elif previous%3==2:intro=(f'Mein Eindruck von dir: {label}.' if own else f'Mein Eindruck von {p["name"]}: {label}.')
        if not chosen:
            lead=f'{p["name"]} ist in den gespeicherten Spielerdaten dabei, aber für eine faire Einschätzung fehlen mir noch Aktivitäten. Ein unbeschriebenes Abenteuerbuch, sozusagen.'
        else:
            lead=intro+' '+' '.join(text for _,_,text in chosen)
        if len(lead)>350:lead=intro+' '+chosen[0][2]
        if chosen and previous%2:
            lead=lead.replace('sprechen für ordentlich Baulust.', '– da wächst vermutlich mehr als nur eine kleine Hütte.').replace('sieht die Nachbarschaft für Monster ziemlich ungemütlich aus.', 'dürften Monster selten freiwillig Hallo sagen.').replace('friedliche Verhandlungen sind offenbar nicht immer die erste Wahl.', 'das sieht nach etwas Duell-Erfahrung aus, auch wenn Zahlen nicht jeden Kampf erklären.').replace('kennt der Respawn-Punkt vermutlich schon die Lieblingsposition.', 'wäre eine Treuekarte am Respawn-Punkt langsam angemessen.')
        if len(lead)>350 and chosen:lead=intro+' '+chosen[0][2]
        with self.lock:
            for key in list(self.context):
                if self.context[key][1]<=self.clock():self.context.pop(key,None)
            self.context.pop(scope,None);self.context[scope]=(p['uuid'],self.clock()+180)
            while len(self.context)>256:self.context.popitem(last=False)
        return lead

