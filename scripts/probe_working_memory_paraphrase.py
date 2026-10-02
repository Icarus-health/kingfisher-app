#!/usr/bin/env python3
"""Wie gut findet der Arbeitsstand umschriebene Fragen? Synthetisch, ohne Chatmodell.

Misst die produktive Quellensuche (``WorkingMemoryStore.search``) auf einem
eingefrorenen Katalog: direkte Fragen mit Wortüberschneidung, Umschreibungen
ohne gemeinsames Inhaltswort und unbeantwortbare Fragen. Optional misst ein
zweiter Arm dieselben Fragen mit lokalen Embeddings (``--embedder bge-m3``,
nur mit bereits installiertem Modell, kein Download) und eine Mischung aus
beiden. Das ist eine Entscheidungsgrundlage, keine Produktabnahme.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sidecar'))

from icarus_memory.episodes import EpisodeKind, EpisodeStore  # noqa: E402
from icarus_memory.lexical import terms_v1  # noqa: E402
from icarus_memory.model import Provenance, SourceType  # noqa: E402
from icarus_memory.working_memory_answers import MAX_REFS  # noqa: E402
from icarus_memory.working_memory_store import WorkingMemoryStore  # noqa: E402

CATALOG = Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality/paraphrase/catalog.json'
STOPWORDS = {'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen', 'einem', 'eines', 'und',
             'ist', 'sind', 'wird', 'wurde', 'für', 'fürs', 'mit', 'von', 'zum', 'zur', 'im', 'in', 'am',
             'an', 'auf', 'bei', 'beim', 'bis', 'ab', 'nach', 'wann', 'wie', 'was', 'wer', 'wo', 'welche',
             'welcher', 'welches', 'warum', 'weshalb', 'worauf', 'ich', 'wir', 'mich', 'man', 'muss', 'kann',
             'darf', 'dürfen', 'haben', 'habe', 'hat', 'schon', 'noch', 'nicht', 'des', 'sie', 'es', 'um'}


def catalog_digest():
    return hashlib.sha256(CATALOG.read_bytes()).hexdigest()


def content_words(text):
    return {word for word in terms_v1(text) if word.isalpha() and word not in STOPWORDS}


def build(directory):
    """Quellen aufnehmen und ohne Modell einordnen (je Quelle ein Abschnitt)."""
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    episodes = EpisodeStore(Path(directory) / 'episodes.sqlite3')
    store = WorkingMemoryStore(episodes)
    alias = {}
    for source in catalog['sources']:
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, source['title'], source['text'],
                                     Provenance(SourceType.DOCUMENT, source_ref=f"probe:{source['id']}"))
        snapshot = store.pending(episode_ids=[episode.id])[0]
        assert store.commit(snapshot, [{'start': 0, 'end': len(source['text']), 'kind': 'fact'}],
                            model='probe:deterministic')
        alias[episode.id] = source['id']
    return catalog, episodes, store, alias


def lexical_ranking(store, alias, question):
    found = store.search(question, limit=MAX_REFS)['refs']
    ranking = []
    for ref in found:
        name = alias.get(ref['episode_id'])
        if name and name not in ranking:
            ranking.append(name)
    return ranking


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def semantic_rankings(embedder, catalog):
    sources = catalog['sources']
    vectors = embedder.embed([f"{s['title']}: {s['text']}" for s in sources])
    questions = embedder.embed([item['q'] for item in catalog['questions']])
    rankings = []
    for vector in questions:
        scored = sorted(((cosine(vector, source_vector), source['id'])
                         for source, source_vector in zip(sources, vectors)), reverse=True)
        rankings.append([(name, round(score, 4)) for score, name in scored])
    return rankings


def hybrid(lexical, semantic, threshold, limit=MAX_REFS):
    """Wörtliche Treffer zuerst, dann semantische über der Schwelle."""
    merged = list(lexical)
    for name, score in semantic:
        if score >= threshold and name not in merged:
            merged.append(name)
    return merged[:limit]


def score(rows):
    result = {}
    for kind in ('direct', 'paraphrase', 'unanswerable'):
        subset = [row for row in rows if row['type'] == kind]
        if not subset:
            continue
        if kind == 'unanswerable':
            result[kind] = {'n': len(subset), 'mit_kandidaten': sum(bool(row['ranking']) for row in subset)}
            continue
        result[kind] = {
            'n': len(subset),
            'treffer_platz_1': sum(row['ranking'][:1] == row['expect'] for row in subset),
            f'treffer_in_top_{MAX_REFS}': sum(set(row['expect']) <= set(row['ranking']) for row in subset),
            'kandidaten_im_mittel': round(sum(len(row['ranking']) for row in subset) / len(subset), 2),
        }
    return result


def production_rankings(embedder, episodes, alias, catalog, lexical_rows, threshold):
    """Der produktive Weg: Wortsuche zuerst, dann WorkingMemorySemantic."""
    from icarus_memory.working_memory_semantic import WorkingMemorySemantic
    search = WorkingMemorySemantic(embedder, threshold=threshold)
    rankings = []
    for item, row in zip(catalog['questions'], lexical_rows):
        merged = list(row['ranking'])
        for ref in search.search(episodes, item['q'], MAX_REFS):
            name = alias.get(ref['episode_id'])
            if name and name not in merged and len(merged) < MAX_REFS:
                merged.append(name)
        rankings.append(merged)
    return rankings, search.status


def run(embedder=None, threshold=0.55):
    with tempfile.TemporaryDirectory() as directory:
        catalog, episodes, store, alias = build(directory)
        production = None
        try:
            source_words = {s['id']: content_words(s['title'] + ' ' + s['text']) for s in catalog['sources']}
            rows = []
            for item in catalog['questions']:
                overlap = sorted(set().union(*(content_words(item['q']) & source_words[name]
                                               for name in item['expect']))) if item['expect'] else []
                rows.append({'q': item['q'], 'type': item['type'], 'expect': item['expect'],
                             'gemeinsame_inhaltswoerter': overlap,
                             'ranking': lexical_ranking(store, alias, item['q'])})
            if embedder is not None:
                production = production_rankings(embedder, episodes, alias, catalog, rows, threshold)
        finally:
            episodes.close()
    report = {'suite': catalog['suite'], 'catalog_sha256': catalog_digest(), 'synthetic_only': True,
              'network_used': embedder is not None,
              'arms': {'lexikalisch': {'score': score(rows), 'rows': rows}}}
    if embedder is not None:
        semantic = semantic_rankings(embedder, catalog)
        semantic_rows, hybrid_rows = [], []
        for row, ranked in zip(rows, semantic):
            above = [name for name, value in ranked if value >= threshold][:MAX_REFS]
            semantic_rows.append({**row, 'ranking': above, 'scores': ranked[:5]})
            hybrid_rows.append({**row, 'ranking': hybrid(row['ranking'], ranked, threshold)})
        report['arms']['semantisch'] = {'score': score(semantic_rows), 'threshold': threshold,
                                        'model': getattr(embedder, 'model_key', None), 'rows': semantic_rows}
        report['arms']['gemischt'] = {'score': score(hybrid_rows), 'threshold': threshold, 'rows': hybrid_rows}
        ranked, status = production
        production_rows = [{**row, 'ranking': ranking} for row, ranking in zip(rows, ranked)]
        report['arms']['produktiv'] = {'score': score(production_rows), 'threshold': threshold,
                                       'semantic_status': status, 'rows': production_rows}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Neue JSON-Datei; wird nie überschrieben')
    parser.add_argument('--embedder', choices=['bge-m3'], help='Zusätzlich lokale Embeddings messen')
    parser.add_argument('--threshold', type=float, default=0.55, help='Mindestähnlichkeit für semantische Treffer')
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'{args.output} existiert bereits; Ergebnisse werden nicht überschrieben.')
    embedder = None
    if args.embedder:
        from icarus_memory.local_embeddings import LocalEmbedder
        embedder = LocalEmbedder().__enter__()
    try:
        report = run(embedder, args.threshold)
    finally:
        if embedder is not None:
            embedder.__exit__(None, None, None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    for arm, data in report['arms'].items():
        print(arm, json.dumps(data['score'], ensure_ascii=False))


if __name__ == '__main__':
    main()
