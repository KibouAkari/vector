"""Public completed advancements: exact counts, categories and competition ranks."""
from pathlib import Path
import re

import stats
from portraits import KNOWN_ADVANCEMENTS, targets, normalized
from dialogue import personal_reference, portrait_request
from runtime import ranking_numbers, ranking_position

IDENTIFIER = re.compile(r'[a-z0-9_.-]{1,64}:[a-z0-9_./-]{1,160}')
INTENT = re.compile(r'fortschritt|advancement|achievement|errungenschaft', re.I)
CATEGORIES = {
    'minecraft:story': ('Minecraft', r'\bstory\b|\bgeschichte\b'),
    'minecraft:adventure': ('Abenteuer', r'abenteuer|\badventure\b'),
    'minecraft:nether': ('Nether', r'nether'),
    'minecraft:end': ('End', r'\bend\b|\bende\b'),
    'minecraft:husbandry': ('Landwirtschaft', r'landwirtschaft|tierhaltung|\bhusbandry\b'),
}


def completed(directory, uid):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('ADVANCEMENTS_UNAVAILABLE')
    value, _ = stats.read_json(root/(uid+'.json'))
    if not isinstance(value, dict) or len(value) > 20000:
        raise ValueError('ADVANCEMENTS_SCHEMA')
    result, known = set(), set()
    for identifier, row in value.items():
        if identifier == 'DataVersion':
            continue
        if (not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier)
                or not isinstance(row, dict) or type(row.get('done')) is not bool):
            raise ValueError('ADVANCEMENTS_SCHEMA')
        if not identifier.split(':', 1)[1].startswith('recipes/'):
            known.add(identifier)
            if row['done']:
                result.add(identifier)
    return result, known


def category(identifier):
    namespace, path = identifier.split(':', 1)
    return namespace+':'+path.split('/', 1)[0]


def snapshot(ai):
    data = stats.snapshot(ai.stats_dir, ai.usercache)
    stats.require_complete(data)
    directory = getattr(getattr(ai, 'portraits', None), 'advancements', None)
    rows, unavailable, total = [], 0, 0
    for player in data['players']:
        try:
            done, known = completed(directory, player['uuid']) if directory is not None else (None, set())
        except (OSError, ValueError, KeyError, TypeError):
            done, known = None, set()
        total += len(known)
        if total > 100000:
            raise ValueError('ADVANCEMENTS_TOTAL_LIMIT')
        unavailable += done is None
        rows.append(dict(player, completed=done, known=known))
    return rows, unavailable


def answer(question, observations, history=()):
    # General opinions still use the portrait path, not counter rendering.
    if (history and history[-1]['origin']=='tool-advancements'
            and re.match(r'\s*(?:und|aber)\b',question,re.I)
            and ranking_position(ranking_numbers(question)) is not None
            and not re.search(r'\b(?:bei|im|in|mit|gegen|von)\b',question,re.I)):
        topic=re.search(r'Fortschritte \(([^)]+)\)',history[-1]['answer'])
        if not topic:
            return 'Welche Fortschrittskategorie oder welchen einzelnen Fortschritt meinst du?'
        label=topic[1]
        key=next((k for k,(name,_) in CATEGORIES.items() if name==label),label)
        question+=' Fortschritte '+('' if label=='alle Kategorien' else key)
    if re.search(r'\bwie\s+(?:bekomm|erhalt|mach|schaff|funktionier)|\bwas\s+bedeut', question, re.I):
        return None
    named = [identifier for identifier, label in KNOWN_ADVANCEMENTS.items()
             if normalized(label) in normalized(question)]
    if portrait_request(question) or not (INTENT.search(question) or named):
        return None
    try:
        rows, unavailable = snapshot(observations.assistant)
    except (OSError, ValueError, KeyError, TypeError):
        return 'Die gespeicherten Spielerstatistiken sind unvollständig. Ich nenne deshalb keinen Fortschrittsrekord.'
    groups = set(CATEGORIES) | {category(i) for p in rows for i in p['known']}
    scope_query=re.sub(IDENTIFIER.pattern,' ',question,flags=re.I)
    for player in rows:
        scope_query=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(player['name'])+r'(?![A-Za-z0-9_])',' ',scope_query,flags=re.I)
    if re.search(r'\b(?:wenigst\w*|keine\w*|null|nicht|wann|morgen|verloren|wird|werden|bald)\b',scope_query,re.I):
        return 'Diese Bedingung kann ich mit der Fortschrittsrangliste nicht beantworten. Ich kann abgeschlossene Gesamtzahlen, die höchsten Werte, Kategorien und einzelne Fortschritte auslesen.'
    if re.search(r'\b(?:ohne|außer|ausser|minus|ausgenommen)\b',scope_query,re.I):
        return 'Diese Einschränkung ist für Fortschrittsranglisten nicht unterstützt. Ich kann Gesamtwerte, eine Kategorie oder einen einzelnen Fortschritt vergleichen.'
    if re.search(r'\bauf\s+(?!(?:rang|platz|welch\w*|(?:den|dem)\s+(?:rang|platz))\b)',scope_query,re.I):
        return 'Ich lese Fortschritte nur vom aktuellen Minecraft-Server. Bitte kläre die zusätzliche Server- oder Bereichsangabe.'
    ids = set(re.findall(IDENTIFIER.pattern, question.casefold()))
    if any(i.split(':', 1)[1].startswith('recipes/') for i in ids):
        return 'Rezeptfreischaltungen zählen hier nicht als Spielfortschritte.'
    selected_ids = ids - groups
    if len(selected_ids) > 1 or len(ids & groups) > 1 or len(named) > 1:
        return 'Bitte frage nach einer Fortschrittskategorie oder einem einzelnen Fortschritt.'
    particular = next(iter(selected_ids), named[0] if named else None)
    if particular and particular not in KNOWN_ADVANCEMENTS and not any(particular in p['known'] for p in rows):
        return 'Diesen Fortschritt finde ich nicht in den gespeicherten Dateien. Seine Existenz oder einen Rekord kann ich daraus nicht bestätigen.'
    selected = next(iter(ids & groups), None)
    if selected is None and not particular:
        matches = [key for key, (_, pattern) in CATEGORIES.items() if re.search(pattern, scope_query, re.I)]
        if len(matches) > 1:
            return 'Welche Fortschrittskategorie meinst du: '+', '.join(CATEGORIES[k][0] for k in matches)+'?'
        selected = matches[0] if matches else None
    if re.search(r'kategorien|categories|welche.*kategorie', question, re.I):
        labels = [CATEGORIES.get(k, (k, None))[0] for k in sorted(groups)]
        return 'Fortschrittskategorien: '+', '.join(labels)+'.' if len(', '.join(labels)) <= 270 else 'Es gibt viele Mod-Kategorien. Frage mit ihrer Kategorie-ID, zum Beispiel minecraft:adventure.'
    if re.search(r'\bkategorie\b', question, re.I) and selected is None and not particular:
        return 'Welche Fortschrittskategorie meinst du? Frage zum Beispiel nach Abenteuer, Nether, End oder der vollständigen Kategorie-ID.'
    if selected is None and not particular and re.search(r'\b(?:fortschritt|achievement|advancement)\b|\bim\s+(?!server\b|minecraft\b|spiel\b)', question, re.I):
        return 'Welchen einzelnen Fortschritt oder welche Kategorie meinst du? Nenne den bekannten Namen oder die vollständige Fortschritts-ID.'
    if re.search(r'\bheute\b|\bgestern\b|\bseit\b|woche|monat|jahr|zuerst|zuletzt|als erster', scope_query, re.I):
        return 'Diese Rangliste zählt abgeschlossene Fortschritte insgesamt, nicht neu erreichte Fortschritte in einem Zeitraum oder die Reihenfolge des Erreichens.'
    label = KNOWN_ADVANCEMENTS.get(particular, particular) if particular else (
        CATEGORIES.get(selected, (selected, None))[0] if selected else 'alle Kategorien')
    title = 'Fortschritte ('+label+')'
    if selected and particular:
        return 'Bitte wähle eine Kategorie oder einen einzelnen Fortschritt.'
    def count(player):
        return sum((i == particular if particular else category(i) == selected if selected else True)
                   for i in player['completed'])
    people = targets(re.sub(IDENTIFIER.pattern, ' ', question, flags=re.I), rows)
    if not people and personal_reference(question):
        people = [p for p in rows if p['uuid'] == observations.principal]
        if not people:
            return 'Welchen Minecraft-Spieler meinst du? Dein Anzeigename allein bestätigt keine Spielerverknüpfung.'
    if len(people) > 1:
        return 'Bitte nenne einen eindeutigen Minecraft-Spielernamen.'
    if people and people[0]['completed'] is None:
        return 'Die Fortschrittsdatei dieses Spielers fehlt oder ist nicht lesbar. Das ist kein belegter Nullwert.'
    ranking = bool(re.search(r'\bwer\b|\bwho\b|top|rang|platz|rekord|meist', question, re.I))
    if people and not ranking:
        return people[0]['name']+': '+title+' '+str(count(people[0]))+' abgeschlossen.'
    if unavailable:
        return 'Für '+str(unavailable)+' Spieler fehlen lesbare Fortschrittsdateien. Eine vollständige Serverrangliste oder einen Rekord kann ich deshalb nicht bestätigen.'
    values = sorted([(p['name'], count(p)) for p in rows], key=lambda p: (-p[1], p[0].casefold()))
    if people:
        if re.search(r'rekorde\b', question, re.I) and selected is None and particular is None:
            if len(groups)>128:
                return 'Für diese Rekordübersicht gibt es zu viele Mod-Kategorien. Bitte wähle eine Fortschrittskategorie.'
            records=[]
            for group in [None]+sorted(groups):
                counts=[sum(group is None or category(i)==group for i in p['completed']) for p in rows]
                own=sum(group is None or category(i)==group for i in people[0]['completed'])
                if own>0 and own==max(counts):
                    title=CATEGORIES.get(group,(group,None))[0] if group else 'Gesamt'
                    records.append(str(title)+' '+str(own)+(' (geteilt)' if counts.count(own)>1 else ''))
            text=people[0]['name']+': Fortschrittsrekorde: '+('; '.join(records) if records else 'keine belegte Führung')+'.'
            return text if len(text)<=320 else 'Diese Fortschrittsrekordübersicht ist zu lang. Bitte wähle eine Kategorie.'
        value = count(people[0]);rank = 1+sum(v > value for _, v in values)
        return people[0]['name']+': '+title+' '+str(value)+' abgeschlossen; Rang '+str(rank)+'.'
    if not ranking:
        return 'Möchtest du die Rangliste, den Rekord oder die Fortschritte eines bestimmten Spielers sehen?'
    if values[0][1] == 0:
        return title+': noch kein Abschluss in den gespeicherten Dateien.'
    numbered = ranking_numbers(question)
    top = re.search(r'\btop\s*(\d+)\b', numbered, re.I)
    position = ranking_position(numbered)
    limit = int(top[1]) if top else 1
    if not 1 <= limit <= 10 or position is not None and not 1 <= position <= 10:
        return 'Bitte frage nach Top 1 bis Top 10 oder einem Rang zwischen eins und zehn.'
    rank = lambda value: 1+sum(v > value for _, v in values)
    if position is not None:
        matches = [(n,v) for n,v in values if rank(v) == position]
        if not matches:
            return title+': dieser Rang ist wegen Gleichständen nicht belegt.'
    else:
        cutoff = values[min(limit, len(values))-1][1]
        matches = [(n,v) for n,v in values if v >= cutoff]
    excerpt = len(matches) > 10
    text = title+': '+'; '.join(str(rank(v))+'. '+n+' '+str(v) for n,v in matches[:10])+'.'
    if excerpt:
        text += ' Auszug bei Gleichstand.'
    return text if len(text) <= 320 else 'Diese Fortschrittsliste ist zu lang für eine Chatantwort. Bitte frage nach einer kleineren Top-Liste oder einem bestimmten Spieler.'
