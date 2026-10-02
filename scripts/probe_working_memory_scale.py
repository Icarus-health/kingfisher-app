#!/usr/bin/env python3
"""Wie verhält sich der Arbeitsstand bei einem großen Postfach? Synthetisch, ohne Chatmodell.

Erzeugt ein reproduzierbares Postfach aus geschäftlichen Mails. Darin stehen
eindeutige Nadel-Angaben („Wer liefert was für welches Projekt wann?“) neben
vielen Ablenkern, die Person, Projekt oder Gegenstand teilen. Die Einordnung
wird ohne Modell nachgebildet: je Absatz ein Abschnitt, wie ihn die lokale
Einordnung liefert.

Gemessen wird, was ohne Modell messbar ist:

* Zeit für Aufnahme und Einordnung (ohne Modellzeit) und Größe der Datenbank,
* Suchzeit je Frage (Median und 95. Perzentil),
* ob die Nadel unter den Suchtreffern ist und ob sie auch nach dem
  Kontextbudget noch beim Auswahlmodell ankommt,
* wie oft die Kandidatenliste als begrenzt gilt.

Die Modellzeit für das erste Einordnen hängt vom Rechner ab. Sie wird nicht
geraten, sondern aus ``--sekunden-je-quelle`` hochgerechnet, sobald sie auf
dem Zielrechner gemessen ist. Das ist eine Entscheidungsgrundlage, keine
Produktabnahme.
"""
import argparse
import json
import os
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sidecar'))

from icarus_memory.claims import ClaimStore  # noqa: E402
from icarus_memory.episodes import EpisodeKind, EpisodeStore  # noqa: E402
from icarus_memory.model import Provenance, SourceType  # noqa: E402
from icarus_memory.working_memory_analysis import _blocks  # noqa: E402
from icarus_memory.working_memory_answers import MAX_REFS, _candidates  # noqa: E402
from icarus_memory.working_memory_store import WorkingMemoryStore  # noqa: E402

SUITE = 'working-memory-scale-v1'
PEOPLE = ['Anna Keller', 'Ben Wolter', 'Clara Brandt', 'David Nowak', 'Eva Lindner', 'Felix Haas',
          'Greta Sommer', 'Hanna Vogt', 'Ilias Demir', 'Jonas Weller', 'Katrin Maurer', 'Lena Roth',
          'Moritz Engel', 'Nora Beck', 'Oskar Frei', 'Paula Stein', 'Rafael Kunz', 'Sara Winter']
PROJECTS = ['Mainz', 'Orion', 'Atlas', 'Vega', 'Nordlicht', 'Hafenblick', 'Kranich', 'Lotus',
            'Merkur', 'Polaris', 'Saphir', 'Tessin']
OBJECTS = ['den Entwurf', 'die Prüfmuster', 'das Angebot', 'die Rechnung', 'den Prüfbericht',
           'die Stückliste', 'das Lastenheft', 'die Zeichnungen', 'den Messplan', 'die Freigabeliste']
MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September',
          'Oktober', 'November', 'Dezember']
FILLER = [
    'Vielen Dank für die schnelle Rückmeldung von gestern.',
    'Im Anhang findest du die aktuelle Übersicht mit allen offenen Punkten.',
    'Die Abstimmung mit der Buchhaltung läuft noch, dazu melde ich mich separat.',
    'Bitte gib mir kurz Bescheid, falls sich an der Planung etwas ändert.',
    'Das Protokoll der letzten Runde liegt im gemeinsamen Ordner.',
    'Für Rückfragen bin ich morgen Vormittag gut erreichbar.',
    'Die Kollegen aus dem Einkauf sind informiert und warten auf das Signal.',
]
GREETING = ['Viele Grüße', 'Beste Grüße', 'Schöne Grüße', 'Danke und Gruß']


def _date(rng):
    return f'{rng.randint(1, 28)}. {rng.choice(MONTHS)} 2026'


def _mail(rng, person, project, obj, date):
    fact = f'{person.split()[0]} liefert {obj} für {project} am {date}.'
    paragraphs = [f'Hallo zusammen,', *rng.sample(FILLER, rng.randint(1, 3)), fact,
                  *rng.sample(FILLER, rng.randint(0, 2)), f'{rng.choice(GREETING)}\n{person}']
    rng.shuffle(paragraphs[1:-1])
    return {'title': f'Re: {obj.split()[-1]} {project}', 'body': '\n\n'.join(paragraphs),
            'sender': f'{person} <{person.split()[0].lower()}@example.test>', 'fact': fact}


def mailbox(size, needles, seed):
    """Nadeln mit eindeutiger Kombination, der Rest teilt jeweils zwei Merkmale mit einer Nadel."""
    rng = random.Random(seed)
    combinations = [(p, pr, o) for p in PEOPLE for pr in PROJECTS for o in OBJECTS]
    rng.shuffle(combinations)
    chosen, rest = combinations[:needles], combinations[needles:]
    items = []
    for index, (person, project, obj) in enumerate(chosen):
        date = _date(rng)
        mail = _mail(rng, person, project, obj, date)
        items.append({**mail, 'id': f'N{index + 1:03d}', 'needle': True,
                      'question': f'Wann liefert {person.split()[0]} {obj} für {project}?', 'answer': date})
    used = set(chosen)
    for index in range(size - needles):
        base = chosen[index % needles]
        # Ablenker: gleiche Person und gleiches Projekt, anderer Gegenstand, usw.
        variant = [(base[0], base[1], None), (base[0], None, base[2]), (None, base[1], base[2])][index % 3]
        candidates = [c for c in rest if all(v is None or v == c[i] for i, v in enumerate(variant))
                      and c not in used] or rest
        person, project, obj = rng.choice(candidates)
        items.append({**_mail(rng, person, project, obj, _date(rng)), 'id': f'D{index + 1:05d}',
                      'needle': False})
    rng.shuffle(items)
    return items


def _percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def run(size, needles=40, seed=20260925, seconds_per_source=None):
    items = mailbox(size, needles, seed)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'episodes.sqlite3'
        episodes = EpisodeStore(path)
        claims = ClaimStore(Path(directory) / 'knowledge.sqlite3')
        store = WorkingMemoryStore(episodes)
        try:
            alias = {}
            started = time.perf_counter()
            for item in items:
                episode, _ = episodes.record(EpisodeKind.MESSAGE, item['title'], item['body'],
                                             Provenance(SourceType.EMAIL, source_ref=f"probe:<{item['id']}>"),
                                             participants=[item['sender']])
                alias[episode.id] = item['id']
            recorded = time.perf_counter() - started
            started = time.perf_counter()
            interpreted = 0
            while True:
                batch = store.pending(limit=200)
                if not batch:
                    break
                for snapshot in batch:
                    body = snapshot.episode.body
                    blocks = [{'start': start, 'end': end,
                               'kind': 'commitment' if 'liefert' in body[start:end] else 'status'}
                              for start, end in _blocks(body)
                              if not body[start:end].startswith(('Hallo', *GREETING))]
                    store.commit(snapshot, blocks, model='probe:deterministic')
                    interpreted += 1
            indexed = time.perf_counter() - started
            rows, latencies = [], []
            for item in items:
                if not item['needle']:
                    continue
                started = time.perf_counter()
                refs, model_rows, limited = _candidates(item['question'], episodes, claims)[:3]
                latencies.append(time.perf_counter() - started)
                found = [alias[ref['episode_id']] for ref in store.search(item['question'], limit=MAX_REFS)['refs']]
                shown = list(dict.fromkeys(alias[ref['episode_id']] for ref in refs))
                rows.append({'id': item['id'], 'q': item['question'],
                             'suchtreffer_rang': found.index(item['id']) + 1 if item['id'] in found else None,
                             'beim_modell': item['id'] in shown, 'quellen_beim_modell': len(shown),
                             'begrenzt': limited})
            coverage = store.coverage()
            size_bytes = os.path.getsize(path)
        finally:
            claims.close()
            episodes.close()
    n = len(rows)
    report = {
        'suite': SUITE, 'synthetic_only': True, 'network_used': False, 'model_called': False,
        'postfach': {'mails': size, 'nadeln': needles, 'seed': seed},
        'zeit_sekunden': {'aufnahme': round(recorded, 3), 'einordnung_ohne_modell': round(indexed, 3),
                          'suche_median': round(statistics.median(latencies), 4),
                          'suche_p95': round(_percentile(latencies, 0.95), 4)},
        'datenbank_mb': round(size_bytes / 1_000_000, 2),
        'eingeordnet': interpreted, 'abdeckung': coverage,
        'ergebnis': {
            'nadel_auf_platz_1': sum(row['suchtreffer_rang'] == 1 for row in rows),
            f'nadel_in_top_{MAX_REFS}': sum(row['suchtreffer_rang'] is not None for row in rows),
            'nadel_beim_modell': sum(row['beim_modell'] for row in rows),
            'antworten_begrenzt': sum(row['begrenzt'] for row in rows),
            'quellen_beim_modell_im_mittel': round(sum(r['quellen_beim_modell'] for r in rows) / n, 2),
            'fragen': n,
        },
        'rows': rows,
    }
    if seconds_per_source:
        report['erste_einordnung_hochgerechnet_stunden'] = round(size * seconds_per_source / 3600, 2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Neue JSON-Datei; wird nie überschrieben')
    parser.add_argument('--sizes', type=int, nargs='+', default=[200, 1000, 3000])
    parser.add_argument('--needles', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--sekunden-je-quelle', type=float,
                        help='Gemessene Modellzeit je Quelle auf dem Zielrechner, für die Hochrechnung')
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'{args.output} existiert bereits; Ergebnisse werden nicht überschrieben.')
    reports = [run(size, args.needles, args.seed, args.sekunden_je_quelle) for size in args.sizes]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump({'suite': SUITE, 'runs': reports}, handle, ensure_ascii=False, indent=1)
    for report in reports:
        print(report['postfach']['mails'], json.dumps(
            {**report['zeit_sekunden'], 'db_mb': report['datenbank_mb'], **report['ergebnis']},
            ensure_ascii=False))


if __name__ == '__main__':
    main()
