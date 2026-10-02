#!/usr/bin/env python3
"""Welches Modell ordnet ein und wählt Quellen gut aus? Synthetisch, modellunabhängig.

Misst die beiden Gedächtnisaufgaben, die ein Modell im Arbeitsstand erledigt,
über den echten Produktcode:

* Einordnung (``working_memory_analysis.interpret``): Art je Absatz,
* Auswahl (``working_memory_answers.prepare``): Status und Quellen zur Frage,
  einschließlich der festen Schutzregeln, die das Modellergebnis nachprüfen.

Jedes Modell ist ein Arm, zum Beispiel ``ollama:qwen3.5:4b``,
``kompatibel:mistral-small@http://localhost:1234/v1``, ``anthropic:claude-sonnet-5``
oder ``openai:gpt-4.1-mini``. Schlüssel kommen aus der Umgebung wie in der App.

Nur der eingefrorene synthetische Katalog verlässt den Rechner, nie Nutzerdaten.
Cloud-Arme laufen trotzdem nur mit ``--cloud-erlaubt``. Im Produkt bleibt der
Arbeitsstand lokal; dieses Skript ändert daran nichts. Eine
Entscheidungsgrundlage, keine Produktabnahme.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sidecar'))

from icarus_memory.claims import ClaimStore  # noqa: E402
from icarus_memory.episodes import EpisodeKind, EpisodeStore  # noqa: E402
from icarus_memory.model import Provenance, SourceType  # noqa: E402
from icarus_memory.providers import Anthropic, OpenAICompatible, ProviderError, Reply  # noqa: E402
from icarus_memory.working_memory_analysis import UnsupportedSource, _blocks, interpret  # noqa: E402
from icarus_memory.working_memory_answers import prepare  # noqa: E402
from icarus_memory.working_memory_store import WorkingMemoryStore  # noqa: E402

CATALOG = Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality/models/catalog.json'
FENCE = re.compile(r'^\s*```(?:json)?\s*(.*?)\s*```\s*$', re.S)


def catalog_digest():
    return hashlib.sha256(CATALOG.read_bytes()).hexdigest()


class Arm:
    """Ein Modell für den synthetischen Vergleich.

    Gilt hier als lokal, damit der Produktcode es aufruft. Das ist nur
    vertretbar, weil ausschließlich der synthetische Katalog verarbeitet wird.
    Cloud-Modelle bekommen keine Schema-Schnittstelle; ihre JSON-Antwort wird
    aus einem Codeblock gelöst und das gezählt.
    """
    is_local = True

    def __init__(self, label, inner):
        self.label, self.inner = label, inner
        self.name = getattr(inner, 'name', 'arm')
        self.model = getattr(inner, 'model', label)
        self.calls, self.seconds, self.fenced = 0, 0.0, 0
        if getattr(inner, 'is_local', False) and callable(getattr(inner, 'complete_json', None)):
            self.complete_json = self._complete_json

    def _timed(self, call):
        started = time.perf_counter()
        try:
            return call()
        finally:
            self.calls += 1
            self.seconds += time.perf_counter() - started

    def _complete_json(self, messages, **kwargs):
        return self._timed(lambda: self.inner.complete_json(messages, **kwargs))

    def complete(self, messages, tools):
        reply = self._timed(lambda: self.inner.complete(messages, tools))
        match = FENCE.match(reply.text or '')
        if match:
            self.fenced += 1
            return Reply(text=match.group(1), tool_calls=reply.tool_calls)
        return reply


def build_arm(spec, *, cloud_allowed):
    provider, _, rest = spec.partition(':')
    model, _, base = rest.partition('@')
    if provider == 'ollama':
        inner = OpenAICompatible(model, api_key='ollama', base_url=base or 'http://localhost:11434/v1')
    elif provider == 'kompatibel':
        if not base:
            raise SystemExit(f'{spec}: kompatibel braucht eine Adresse, z. B. kompatibel:modell@http://localhost:1234/v1')
        inner = OpenAICompatible(model, api_key=os.environ.get('OPENAI_API_KEY') or 'kein-schluessel', base_url=base)
    elif provider == 'anthropic':
        key = os.environ.get('ANTHROPIC_API_KEY')
        if not key:
            raise SystemExit('ANTHROPIC_API_KEY fehlt.')
        inner = Anthropic(model, key, **({'base_url': base} if base else {}))
    elif provider == 'openai':
        key = os.environ.get('OPENAI_API_KEY') or os.environ.get('LLM_API_KEY')
        if not key:
            raise SystemExit('OPENAI_API_KEY fehlt.')
        inner = OpenAICompatible(model, api_key=key, base_url=base or 'https://api.openai.com/v1')
    else:
        raise SystemExit(f'Unbekannter Anbieter in {spec}: ollama, kompatibel, anthropic, openai')
    if not inner.is_local and not cloud_allowed:
        raise SystemExit(f'{spec} ist kein lokales Modell. Nur mit --cloud-erlaubt (synthetische Daten).')
    return Arm(spec, inner)


def _score_interpretation(arm, case):
    body = '\n\n'.join(block['text'] for block in case['blocks'])
    with tempfile.TemporaryDirectory() as directory:
        episodes = EpisodeStore(Path(directory) / 'e.sqlite3')
        try:
            episode, _ = episodes.record(EpisodeKind.MESSAGE, case['title'], body,
                                         Provenance(SourceType.EMAIL, source_ref=f"probe:{case['id']}"))
            spans = _blocks(body)
            if len(spans) != len(case['blocks']):
                return {'id': case['id'], 'valid': False, 'reason': 'block_mismatch', 'correct': 0,
                        'blocks': len(case['blocks'])}
            try:
                items = interpret(arm, episode)
            except (ProviderError, UnsupportedSource, ValueError, TypeError) as exc:
                return {'id': case['id'], 'valid': False, 'reason': type(exc).__name__, 'correct': 0,
                        'blocks': len(case['blocks'])}
        finally:
            episodes.close()
    got = {(item['start'], item['end']): item['kind'] for item in items}
    kinds = [got.get(span, 'irrelevant') for span in spans]
    correct = [kind in block['kinds'] for kind, block in zip(kinds, case['blocks'])]
    return {'id': case['id'], 'valid': True, 'correct': sum(correct), 'blocks': len(correct), 'kinds': kinds}


def _score_selection(arm, case):
    with tempfile.TemporaryDirectory() as directory:
        episodes = EpisodeStore(Path(directory) / 'e.sqlite3')
        claims = ClaimStore(Path(directory) / 'k.sqlite3')
        store = WorkingMemoryStore(episodes)
        try:
            alias = {}
            for source in case['sources']:
                occurred = source.get('occurred_at', '2026-09-20T09:00:00+00:00')
                episode, _ = episodes.record(
                    EpisodeKind.MESSAGE, source['title'], source['text'],
                    Provenance(SourceType.EMAIL, source_ref=f"probe:<{case['id']}-{source['id']}>"),
                    participants=[source['sender']] if source.get('sender') else [],
                    occurred_at=datetime.fromisoformat(occurred) if occurred else None)
                snapshot = store.pending(episode_ids=[episode.id])[0]
                assert store.commit(snapshot, [{'start': 0, 'end': len(source['text']), 'kind': 'fact'}],
                                    model='probe:deterministic')
                alias[episode.id] = source['id']
            answer = prepare(case['question'], episodes, claims, arm)
        finally:
            claims.close()
            episodes.close()
    if answer is None:
        status, chosen = 'unknown', []
    else:
        status = answer['uncertainty'] if answer['status'] == 'unclear' else answer['status']
        chosen = sorted({alias[ref['episode_id']] for ref in answer.get('refs', [])})
    return {'id': case['id'], 'status': status, 'expected_status': case['status'],
            'sources': chosen, 'expected_sources': sorted(case['expect']),
            'status_ok': status == case['status'], 'sources_ok': chosen == sorted(case['expect']),
            'valid': status != 'selection_failed'}


def run_arm(arm, catalog):
    interpretation = [_score_interpretation(arm, case) for case in catalog['interpretation']]
    selection = [_score_selection(arm, case) for case in catalog['selection']]
    blocks = sum(row['blocks'] for row in interpretation)
    return {
        'arm': arm.label, 'model': arm.model, 'local': bool(getattr(arm.inner, 'is_local', False)),
        'einordnung': {'absaetze_richtig': sum(row['correct'] for row in interpretation), 'absaetze': blocks,
                       'faelle_ganz_richtig': sum(row['valid'] and row['correct'] == row['blocks']
                                                  for row in interpretation),
                       'ungueltige_antworten': sum(not row['valid'] for row in interpretation),
                       'faelle': len(interpretation), 'rows': interpretation},
        'auswahl': {'status_richtig': sum(row['status_ok'] for row in selection),
                    'quellen_richtig': sum(row['sources_ok'] for row in selection),
                    'beides_richtig': sum(row['status_ok'] and row['sources_ok'] for row in selection),
                    'ungueltige_antworten': sum(not row['valid'] for row in selection),
                    'faelle': len(selection), 'rows': selection},
        'aufrufe': arm.calls, 'sekunden_je_aufruf': round(arm.seconds / arm.calls, 2) if arm.calls else None,
        'json_aus_codeblock': arm.fenced,
    }


def run(arms):
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    return {'suite': catalog['suite'], 'catalog_sha256': catalog_digest(), 'synthetic_only': True,
            'arms': [run_arm(arm, catalog) for arm in arms]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--arm', action='append', required=True,
                        help='anbieter:modell[@adresse], mehrfach möglich')
    parser.add_argument('--cloud-erlaubt', action='store_true',
                        help='Nicht-lokale Modelle zulassen (nur synthetischer Katalog wird gesendet)')
    parser.add_argument('--output', type=Path, required=True, help='Neue JSON-Datei; wird nie überschrieben')
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'{args.output} existiert bereits; Ergebnisse werden nicht überschrieben.')
    arms = [build_arm(spec, cloud_allowed=args.cloud_erlaubt) for spec in args.arm]
    report = run(arms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    for arm in report['arms']:
        e, a = arm['einordnung'], arm['auswahl']
        print(f"{arm['arm']}: Einordnung {e['absaetze_richtig']}/{e['absaetze']} Absätze, "
              f"Auswahl {a['beides_richtig']}/{a['faelle']} ganz richtig, "
              f"{arm['sekunden_je_aufruf']} s je Aufruf")


if __name__ == '__main__':
    main()
