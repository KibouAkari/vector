"""Fresh public game portraits; no stored labels, private logs or channel transcript."""
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import re
import threading
import time
import unicodedata
import stats

INTENT=re.compile(r'einschätz|einschaetz|beurteil|bewert|\b(?:bin ich|ist \w+) (?:ein |eine |wirklich |eigentlich )?gut\w* spieler|(?:was )?(?:hältst|hälst|haltest|halst|denkst|meinst|findest) du (?:eigentlich |so )?(?:von|über|ueber)|wie findest du|beschreib\w* (?:mich|den spieler)|spielerportr|spielertyp|was bin ich für ein spieler',re.I)
COMBAT=re.compile(r'kampfstil|kampfstyle|fighting\s*style|combat\s*style|(?:welche|meine|bevorzugte)\s+waff|(?:bogen|schwert|mace|streitkolben|speer|scharfschütz|scharfschuetz).*(?:typ|kämpfer|kaempfer|nutz|benutz)',re.I)
SELF=re.compile(r'\b(?:bin ich|mich|von mir|über mich|ueber mich|mein(?:e[rmns]?)? (?:spielstil|profil|spieler|kampfstil|kampfstyle|fighting\s*style|waff\w*))\b',re.I)
KNOWN_ADVANCEMENTS={'minecraft:adventure/sniper_duel':'Sniper-Duell','minecraft:adventure/kill_all_mobs':'Monsterjäger',
 'minecraft:adventure/adventuring_time':'Abenteurer','minecraft:nether/explore_nether':'Nether-Erkundung',
 'minecraft:end/kill_dragon':'Drachensieg','minecraft:husbandry/bred_all_animals':'Tierzüchter'}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if c.isalnum() and not unicodedata.combining(c))


def distance_one(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):
        different=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        return len(different)<=1 or (len(different)==2 and different[1]==different[0]+1 and a[different[0]]==b[different[1]] and a[different[1]]==b[different[0]])
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

    def answer(self,question,principal,scope,block_items=(),*,metrics=()):
        if any(metric not in stats.METRICS for metric in metrics):
            raise ValueError('INVALID_PORTRAIT_METRIC')
        if re.search(r'bogen|\bbow\b',question,re.I) and re.search(r'kills|töt|toet|getötet',question,re.I):
            self.clear(scope)
            return 'Bogennutzungen und einzelne Fortschritte kann ich einordnen, aber daraus keine Bogenkills zählen. Dafür fehlt mir ein geprüfter Ereigniszähler.'
        followup=bool(re.fullmatch(r'\s*und (?:er|sie|der|die|was ist mit (?:ihm|ihr))\s*[?.!]*',question,re.I))
        combat=bool(COMBAT.search(question))
        if not INTENT.search(question) and not combat and not followup:self.clear(scope);return None
        try:
            data=stats.snapshot(self.stats_dir,self.usercache,include_items=True);stats.require_complete(data)
        except (OSError,ValueError,KeyError,TypeError):
            self.clear(scope);return 'für ein faires Spielerporträt sind die gespeicherten Statistiken gerade unvollständig. Ich möchte niemandem falsche Werte anhängen.'
        matches=targets(question,data['players'])
        self_intent=bool(SELF.search(question) or combat and re.search(r'\b(?:ich|mir|mein\w*)\b',question,re.I))
        if not matches and not self_intent and re.search(r'\b(?:minecraft|redstone|vector|mods?|backpack|rucksack|claims?|partys)\b',question,re.I):
            self.clear(scope);return None
        if self_intent:
            if principal is None:self.clear(scope);return 'welchen Minecraft-Spielernamen meinst du? Dein Discord-Anzeigename ist keine bestätigte Minecraft-Verknüpfung.'
            matches=[p for p in data['players'] if p['uuid']==principal]
        if not matches and followup:
            with self.lock:
                prior=self.context.get(scope)
                if prior and prior[1]>self.clock():matches=[p for p in data['players'] if p['uuid']==prior[0]]
        if len(matches)!=1:
            self.clear(scope);return 'nenne bitte einen eindeutigen Minecraft-Spielernamen, dann gebe ich dir ein kurzes Spielerporträt aus seinen Spielwerten.'
        p=matches[0]
        if combat:
            counters=p['used'];groups={
                'Bogen':('bow',), 'Armbrust':('crossbow',),
                'Schwert':('sword',), 'Streitkolben':('mace',),
                'Speer':('spear',), 'Dreizack':('trident',)}
            counts={label:sum(value for identifier,value in counters.items()
                if any(identifier.split(':',1)[1]==kind or identifier.split(':',1)[1].endswith('_'+kind) for kind in kinds))
                for label,kinds in groups.items()}
            highest=max(counts.values(),default=0)
            if not highest:return 'für einen Waffenstil fehlen mir noch passende gespeicherte Nutzungszähler. Aus Mobkills allein mache ich niemanden zum Scharfschützen.'
            favorites=[label for label,count in counts.items() if count==highest]
            n=lambda x:f'{int(x):,}'.replace(',',"'")
            own=principal==p['uuid'];who='du' if own else p['name']
            if len(favorites)>1:
                return ('bei dir' if own else 'bei '+who)+' liegen '+', '.join(favorites)+' gleichauf: je '+n(highest)+' Nutzungen. Klingt nach einem flexiblen Allrounder; Treffer oder Siege kann ich daraus nicht ablesen.'
            weapon=favorites[0]
            styles={'Bogen':'Fernkämpfer mit Scharfschützen-Ambitionen', 'Armbrust':'geduldiger Fernkämpfer mit Armbrust',
                'Schwert':'Schwertkämpfer, irgendwo zwischen Samurai und Kreuzritter',
                'Streitkolben':'Nahkämpfer mit einer Vorliebe fürs Grobe',
                'Speer':'Speerkämpfer mit Sinn für Abstand', 'Dreizack':'Dreizack-Kämpfer mit Meeresflair'}
            text=(('du wirkst' if own else who+' wirkt')+' auf mich wie ein '+styles[weapon]+'. '
                  +weapon+': '+n(highest)+' gespeicherte Nutzungen, '+('deine' if own else 'die')+' häufigste erfasste Waffenart.')
            return text+' Das zeigt eine Vorliebe, keine Trefferquote.'
        v=p['values'];rank=lambda metric:stats.rank(data,p,metric)

        key=(scope,p['uuid']);now=self.clock()
        with self.lock:
            for old in list(self.variants):
                if self.variants[old][1]<=now:self.variants.pop(old,None)
            previous=self.variants.pop(key,(0,0))[0]
            # A bounded style counter may outlive conversational context. No
            # chat text or player judgement is retained in this counter.
            self.variants[key]=(previous+1,now+86400)
            while len(self.variants)>256:self.variants.popitem(last=False)
        n=lambda x:f'{int(x):,}'.replace(',',"'")
        own=principal==p['uuid']
        subject='Du' if own else p['name']
        has='hast' if own else 'hat'
        if metrics:
            # A focused assessment must not substitute an unrelated stronger
            # achievement. Zero and small counts are still meaningful evidence.
            metric_text=[]
            for metric in dict.fromkeys(metrics):
                label,unit,_,_=stats.METRICS[metric]
                amount=f'{v[metric]:.1f}' if unit in ('h','km') else n(v[metric])
                metric_text.append(f'{label}: {amount} {unit}, Rang {rank(metric)}')
            lines={
                'mob_kills':('Monster haben hier wohl keine ruhige Nachbarschaft.', 'Das Monsterkonto wächst offenbar; zum Endgegner ernenne ich deshalb noch niemanden.', 'Die Monster warten offenbar noch auf die erste Begegnung.'),
                'player_kills':('Das wirkt kampflustig; wie die Kämpfe abliefen, verraten die Zahlen nicht.', 'Ein paar Spielerkills im Gepäck, aber noch kein Beweis für einen unbesiegbaren Samurai.', 'Ein friedliches Kill-Konto; Können im Duell bleibt damit offen.'),
                'play_time':('Klingt nach einem zweiten Zuhause auf dem Server.', 'Noch mitten im Abenteuer; die Stammgastkarte hat Zeit.', 'Das Abenteuerbuch ist hier noch ziemlich leer.'),
                'distance':('Stillstehen scheint nicht die Lieblingsbeschäftigung zu sein.', 'Ein bisschen Fernweh ist schon erkennbar.', 'Die grosse Weltreise steht wohl noch bevor.'),
                'deaths':('Der Respawn-Punkt dürfte den Namen langsam kennen.', 'Ein paar unfreiwillige Rückreisen gehören offenbar dazu.', 'Noch keine unfreiwillige Rückreise im Zähler.')}
            metric=metrics[0];value=v[metric]
            comment=lines[metric][2 if value==0 else 0 if rank(metric)==1 else 1]
            if metric=='play_time' and value<24:comment='Noch ein frisches Abenteuer; für die Stammgastkarte ist Zeit.'
            return subject+' – '+'; '.join(metric_text)+'. '+comment
        # Describe multiple observable strengths, not a permanent label. Every
        # clause is tied to this fresh snapshot; no invented victims or weapon kills.
        traits=[]
        pick=lambda variants:variants[previous%len(variants)]
        def add(score,kind,text):traits.append((score,kind,text))
        if v['player_kills']>=10 and rank('player_kills')<=2:
            peak=max(x['values']['player_kills'] for x in data['players'])
            add(.6+.95*v['player_kills']/peak,'fighter',f"{subject} {has} {n(v['player_kills'])} Spielerkills (Rang {rank('player_kills')}). "+pick(('Nachbarschaftshilfe offenbar mit Klinge.', 'Diplomatie mit sehr kurzer Verhandlungsphase.', 'Der Friedenspreis muss wohl warten.')))
        if v['mob_kills']>=100 and rank('mob_kills')<=3:
            add(1.5,'hunter',f"{n(v['mob_kills'])} Mobkills (Rang {rank('mob_kills')}). "+pick(('Monster buchen hier wohl keinen Urlaub.', 'Für Monster ist das eine schlechte Wohnadresse.', 'Die Monstergewerkschaft wird sich noch melden.')))
        blocks=sum(p['used'].get(k,0) for k in set(block_items))
        if blocks>=500:
            peak=max(sum(x['used'].get(k,0) for k in set(block_items)) for x in data['players'])
            add(.65+.9*blocks/peak,'builder',f"{n(blocks)} Block-Item-Nutzungen. "+pick(('Klingt nach Baulust.', 'Die Baustelle kennt wohl keinen Feierabend.', 'Leere Flächen leben offenbar gefährlich.')))
        if v['distance']>=1 and rank('distance')<=3:
            peak=max(x['values']['distance'] for x in data['players'])
            add(.85+.6*v['distance']/peak,'traveler',f"{v['distance']:,.1f} km Strecke (Rang {rank('distance')}). ".replace(',',"'")+pick(('Die Karte ist offenbar ein Wohnzimmer.', 'Stillstehen gehört wohl nicht zum Reiseplan.', 'Fernweh mit eindrücklichem Kilometerstand.')))
        bow=p['used'].get('minecraft:bow',0)
        if bow>0 and bow==max(x['used'].get('minecraft:bow',0) for x in data['players']):
            add(1.05,'archer',f"{n(bow)} Bogennutzungen (Rang 1). "+pick(('Der Bogen kennt kaum Feierabend.', 'Reichlich Training, Trefferquote unbekannt.', 'Fernkampf scheint die bevorzugte Gesprächsdistanz.')))
        if v['deaths']>=100 and rank('deaths')<=2:
            add(1.35,'respawn',f"{n(v['deaths'])} Tode (Rang {rank('deaths')} nach Anzahl). "+pick(('Respawn mit Stammkundenrabatt?', 'Der Rückweg zum Spawn scheint bestens bekannt.', 'Die Sicherheitsunterweisung wäre vielleicht doch spannend.')))
        if v['play_time']>0:
            hours=v['play_time'];position=rank('play_time')
            comment=(pick(('Noch frisch im Abenteuer.', 'Das Abenteuer läuft gerade erst an.', 'Noch am Hineinschnuppern.')) if hours<10 else
                     pick(('Schon ordentlich unterwegs.', 'Das Abenteuerbuch füllt sich.', 'Ein paar Spielabende sind schon belegt.')) if hours<100 else
                     pick(('Die Stammgastkarte ist wohl aus Gold.', 'Hier ist offenbar ein zweites Zuhause entstanden.', 'Das Ausloggen ist wohl die schwerste Quest.')))
            add(2.2 if position==1 else .85,'regular',f"{hours:.1f} h Spielzeit (Rang {position}). "+comment)
        advancement=advancement_summary(self.advancements,p['uuid'])
        if advancement and advancement['latest']:
            add(.9,'adventure',f"{advancement['count']} Fortschritte, darunter {advancement['latest']}.")
        elif advancement and advancement['count']:
            add(.7,'adventure',f"{advancement['count']} Fortschritte – das Abenteuerbuch füllt sich.")
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
        chosen=traits[:2]+([traits[2+previous%(len(traits)-2)]] if len(traits)>2 else [])
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
        elif 'regular' in kinds and rank('play_time')==1 and v['play_time']>=100:
            labels=('Stammgast mit Dauerkarte','jemand mit Ausdauer am Spielzeitzähler','ein vertrautes Gesicht auf dem Server')
        else:
            labels=('ein eigener Spielstil im Aufbau','jemand mit Lust aufs nächste Abenteuer','ein Spieler, dessen Geschichte noch weitergeht')
        label=labels[previous%len(labels)]
        intro=(f'Du? Für mich: {label}.' if own else f'{p["name"]}? Für mich: {label}.')
        if previous%4==1:intro=(f'Zu dir passt für mich: {label}.' if own else f'Bei {p["name"]} denke ich an {label}.')
        elif previous%4==2:intro=(f'Mein Eindruck von dir: {label}.' if own else f'Mein Eindruck von {p["name"]}: {label}.')
        elif previous%4==3:intro=(f'Zu dir fällt mir ein: {label}.' if own else f'{p["name"]} passt für mich zu {label}.')
        if not chosen:
            lead=f'{p["name"]} ist in den gespeicherten Spielerdaten dabei, aber für eine faire Einschätzung fehlen mir noch Aktivitäten. Ein unbeschriebenes Abenteuerbuch, sozusagen.'
        else:
            lead=intro
            # The strongest fresh fact is first, especially a play-time lead.
            # Fit additional complete clauses rather than dropping back to one.
            for _,_,text in chosen:
                if len(lead+' '+text)<=350:lead+=' '+text
        if len(lead)>350:lead=intro+' '+chosen[0][2]
        with self.lock:
            for key in list(self.context):
                if self.context[key][1]<=self.clock():self.context.pop(key,None)
            self.context.pop(scope,None);self.context[scope]=(p['uuid'],self.clock()+180)
            while len(self.context)>256:self.context.popitem(last=False)
        return lead


