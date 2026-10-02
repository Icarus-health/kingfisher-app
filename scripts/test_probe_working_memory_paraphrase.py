"""Die Paraphrasen-Messung ist reproduzierbar, netzfrei und überschreibt nichts."""
import json
from pathlib import Path
import subprocess
import sys

import probe_working_memory_paraphrase as probe

SCRIPT = Path(probe.__file__)


def test_lexical_arm_runs_offline_on_the_frozen_catalog():
    report = probe.run()
    catalog = json.loads(probe.CATALOG.read_text(encoding='utf-8'))
    rows = report['arms']['lexikalisch']['rows']
    assert report['network_used'] is False and report['synthetic_only'] is True
    assert report['catalog_sha256'] == probe.catalog_digest()
    assert [row['q'] for row in rows] == [item['q'] for item in catalog['questions']]
    score = report['arms']['lexikalisch']['score']
    # Direkte Fragen mit Wortüberschneidung findet die heutige Suche.
    assert score['direct'][f'treffer_in_top_{probe.MAX_REFS}'] == score['direct']['n']
    assert score['unanswerable']['mit_kandidaten'] == 0


class FakeEmbedder:
    """Ein Wort je Dimension; einige Synonyme teilen sich eine Dimension."""
    model_key = 'fake:synonyms'
    is_local = True
    SAME = {'ausweis': 'zugangskarte', 'reinkommen': 'zugangskarte', 'zulieferern': 'lieferantenverträge'}

    def __init__(self):
        catalog = json.loads(probe.CATALOG.read_text(encoding='utf-8'))
        texts = [s['title'] + ' ' + s['text'] for s in catalog['sources']] + [q['q'] for q in catalog['questions']]
        self.vocabulary = sorted({self.SAME.get(w, w) for t in texts for w in probe.content_words(t)})

    def embed(self, texts):
        return [[1.0 if word in {self.SAME.get(w, w) for w in probe.content_words(text)} else 0.0
                 for word in self.vocabulary] for text in texts]


def test_semantic_and_hybrid_arms_use_the_embedder_ranking():
    report = probe.run(FakeEmbedder(), threshold=0.2)
    semantic = {row['q']: row['ranking'] for row in report['arms']['semantisch']['rows']}
    assert semantic['Wo finde ich den Ausweis zum Reinkommen?'][:1] == ['S3']
    hybrid = {row['q']: row['ranking'] for row in report['arms']['gemischt']['rows']}
    # Wörtliche Treffer bleiben vorne, semantische kommen dazu.
    assert hybrid['Wo liegt die Zugangskarte?'][0] == 'S3'
    assert 'S3' in hybrid['Wo finde ich den Ausweis zum Reinkommen?']
    assert report['arms']['semantisch']['model'] == 'fake:synonyms'
    # Der produktive Weg findet die Umschreibung ebenfalls.
    production = {row['q']: row['ranking'] for row in report['arms']['produktiv']['rows']}
    assert 'S3' in production['Wo finde ich den Ausweis zum Reinkommen?']
    assert report['arms']['produktiv']['semantic_status'] == 'ok'


def test_existing_output_is_never_overwritten(tmp_path):
    target = tmp_path / 'ergebnis.json'
    target.write_text('{}', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), '--output', str(target)], capture_output=True, text=True)
    assert result.returncode != 0 and target.read_text(encoding='utf-8') == '{}'
