#!/usr/bin/env python3
"""Qualify offline passage selection with the existing unloaded local candidate.

No downloads, imports, production writes, restarts, announcement or cloud calls.
Uses the established coordinator/cleanup and full composed Assistant harness.
"""
import ast
import fcntl
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/root/vector-workspace')
REPO = ROOT/'github/vector'
MODEL = 'vector-qwen3-instruct2507:4b-q4km'
DIGEST = 'b7613a8eda1dbb8ce133679f38f5791e4fd70017c2f37fe8eaa0d5a0d7a9e9c1'
CATALOG_SHA256 = '87728b36f9a97313428a7c18a74259873c5cf5c7fef8ced6ffc9166250f2130c'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Evaluation source changed; no silent gate change.')
    return text.replace(old, new)


def sources(base):
    coordinator = replace_once(base.COORDINATOR, "const model='vector-qwen3:1.7b-q8';", "const model='"+MODEL+"';")
    coordinator = replace_once(coordinator, '97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0', DIGEST)
    harness = replace_once(base.HARNESS, 'import runtime,knowledge',
        'import runtime,knowledge,documentation\nfrom documentation import DocumentationIndex\ndocumentation.local_slot=lambda dsn:nullcontext()')
    harness = replace_once(harness, 'class ObservedKnowledge(knowledge.GeneralKnowledge):', 'class ObservedKnowledge(documentation.DocumentationKnowledge):')
    harness = replace_once(harness, "ObservedKnowledge('outer-shared-lock',usage=", "ObservedKnowledge('outer-shared-lock',documentation=DocumentationIndex('/code/services/fegcraft-assistant/public-knowledge.json',"+repr(CATALOG_SHA256)+"),usage=")
    # Source lookup replaces the classifier, not factual/safety/latency checks.
    harness = replace_once(harness, "('unknown-other-topic','Kannst du ein Liebesgedicht über den Herbst schreiben?',(r'bei Minecraft',),1)",
        "('unknown-other-topic','Kannst du ein Liebesgedicht über den Herbst schreiben?',(r'bei Minecraft',),0)")
    harness = replace_once(harness, "('unknown-game-topic','Wie vermehre ich Schafe?',(r'weizen',r'fütter|zwei|\\b2\\b'),2)",
        "('unknown-game-topic','Wie vermehre ich Schafe?',(r'weizen',r'fütter|zwei|\\b2\\b'),1)")
    harness = replace_once(harness, "if diagnostic:fixtures=", "fixtures += [\n ('voice-menu','Wie öffne ich den Sprachchat?',(r'Voice|Sprachchat',r'Menü',r'Steuerung|Taste|\\bV\\b'),1),\n ('voice-group','Wie erstelle ich im Sprachchat eine Gruppe?',(r'Gruppe',r'Name|Namen',r'Schaltfläche'),1),\n ('bee-honey','Wie sammle ich Honig ohne wütende Bienen?',(r'Lagerfeuer',),1),\n ('parrot','Wie züchte ich Papageien?',(r'nicht',r'zücht'),1),\n ('uncovered-specific','Wie viele Lebenspunkte hat eine Kuh?',(r'fehlt.*geprüfter Eintrag',),1),\n ('missing-document','Wie funktioniert der Enderkristall?',(r'fehlt.*geprüfter Eintrag',),0)]\nif diagnostic:fixtures=")
    harness = replace_once(harness, "'model':'vector-qwen3:1.7b-q8'", "'model':"+repr(MODEL))
    harness = replace_once(harness, "'evaluation_scope':'current-subject-local-adapter'", "'evaluation_scope':'offline-reviewed-passage-selection'")
    harness = replace_once(harness, "'stage':'route' if 'route' in payload.get('format',{}).get('properties',{}) else 'answer'", "'stage':'selection' if 'passage' in payload.get('format',{}).get('properties',{}) else 'answer'")
    harness = replace_once(harness, "'installed_mod_ids_count':mod_count", "'answer_mode':'reviewed-extractive','catalog_sha256':"+repr(CATALOG_SHA256)+",'reviewed_mod_ids':['openpartiesandclaims','voicechat','travelersbackpack'],'exact_installed_mod_versions_qualified':False,'installed_mod_ids_count':mod_count")
    return coordinator, harness


def main():
    os.umask(0o077)
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('Root and exact VECTOR_FEGCRAFT_REV required.')
    if os.environ.get('VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC', '0') != '0':
        raise RuntimeError('Documentation qualification requires all cases.')
    subprocess.run(['git', '-C', str(REPO), 'merge-base', '--is-ancestor', revision, 'origin/main'], check=True, capture_output=True, timeout=15)
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        content = subprocess.check_output(['git', '-C', str(REPO), 'show', revision+':scripts/deploy/evaluate-fegcraft-general-help.py'], timeout=15)
        ast.parse(content)
        # Load only this repository's pinned evaluator; no model repository code.
        namespace = {'__name__': 'documentation_qualification_support', '__file__': str(REPO/'scripts/deploy/evaluate-fegcraft-general-help.py')}
        exec(compile(content, namespace['__file__'], 'exec'), namespace)
        from types import SimpleNamespace
        coordinator, harness = sources(SimpleNamespace(**namespace))
        # evaluate() retains its module globals, so update that exact namespace.
        namespace['COORDINATOR'], namespace['HARNESS'] = coordinator, harness
        print('Prüfe lokale Quellenauswahl mit 26 Fällen. Keine erneuten Modell-Downloads; Minecraft bleibt unverändert.', flush=True)
        result = namespace['evaluate'](report_only=True)
        if not result['passed']:
            raise RuntimeError('Documentation selection quality/latency failed. General help stays OFF; no activation.')
        print('Quellenauswahl bestanden. Noch keine Aktivierung: dedizierte CPU-Sperrrolle, Dienst-Rollout und realer Chat bleiben zu qualifizieren.')
        return result


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
