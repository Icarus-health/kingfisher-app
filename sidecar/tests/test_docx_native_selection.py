"""Native Feld-Originale: begrenzte Nachprüfung und getrennte Quellenprüfung."""
import json

import pytest

from icarus_memory import satzantwort as sa, working_memory_answers as wma
from icarus_memory.mail_ingestion import remember
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_docx_native_rows import prepare, stores  # noqa: F401
from tests.test_docx_table_context import p, packed
from tests.test_mail_docx_attachments import DOCX_MIME, fetch
from tests.test_satzpruefung_modell import Pruefer
from tests.test_answer_source_boundaries import REGEL

ROW = 'Prüfdatum\n18.11.2026\tPrüfstelle'
QUESTION = 'Welches Prüfdatum nennen die Formulare?'


def intake(stores, monkeypatch, count=1):
    content = '<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026') + '</w:tc><w:tc>' + p('Prüfstelle') + '</w:tc></w:tr></w:tbl>'
    files = [(f'Pruefung-{i}.docx', packed(content + p(f'Formularkennung {i}.')), DOCX_MIME) for i in range(count)]
    result = remember(stores[0], fetch(monkeypatch, *files), claims=stores[1])
    sources = [stores[0].get(identifier) for identifier in result['anhaenge']]
    assert len(sources) == count and len({s.id for s in sources}) == count
    for source in sources:
        assert WorkingMemoryStore(stores[0]).commit(stores[0].support_snapshot(source.id), [], model='synthetic')
    return sources


class Auswahl:
    is_local = True
    name = model = 'synthetic-native-selector'

    def __init__(self, empty=0, *, needle=ROW, duplicate=False):
        self.empty, self.needle, self.duplicate = empty, needle, duplicate
        self.requests = []

    def complete_json(self, messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if not sa.ist_satzanfrage(messages):
            return Reply(text=json.dumps({'status': 'source_reports',
                'ids': [r['id'] for r in data['sources'] if r['id'].startswith('S')]}))
        self.requests.append(messages)
        offered = [(b['nr'], s['nr'], s['text']) for b in data['belege']
                   for s in b.get('originalsaetze', []) if self.needle == s['text']]
        if len(self.requests) <= self.empty or not offered:
            return Reply(text=json.dumps({'status': 'nichts_vorliegend', 'originalstellen': []}))
        if self.duplicate:
            nr, _, text = offered[0]
            return Reply(text=json.dumps({'status': 'antwort',
                'saetze': [{'text': text, 'belege': [nr]}, {'text': text, 'belege': [nr]}]}))
        return Reply(text=json.dumps({'status': 'antwort',
            'originalstellen': [{'beleg': nr, 'satz': s} for nr, s, _ in offered]}))


def answer(stores, provider, judge=None, question=QUESTION):
    return prepare(stores, provider=provider, judge=judge, question=question)


@pytest.mark.parametrize('verdict', ['ja', 'nein', 'unklar'])
def test_native_leer_dann_gueltige_id_nutzt_eine_nachpruefung_und_aktive_pruefung(stores, monkeypatch, verdict):
    source, = intake(stores, monkeypatch)
    provider, judge = Auswahl(empty=1), Pruefer(standard=json.dumps({'urteil': verdict}))
    saved, _, rendered, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == ('saetze' if verdict == 'ja' else 'zitate')
    if verdict == 'ja':
        assert 'Quelle berichtet: „' + ROW + '“' in rendered
    assert len(provider.requests) == 2 and len(judge.anfragen) == 1
    first, second = provider.requests
    assert second[-1] == first[-1] and sa.ORIGINAL_NACHPRUEFUNG in second[0]['content']
    assert 'Feld-Datensatz' in first[0]['content'] and 'grammatischer Satz' in first[0]['content']
    assert 'Datumsrolle' in first[0]['content'] and 'keine bestätigte' in first[0]['content']
    assert first[0]['content'] in second[0]['content']
    assert source.body in json.loads(judge.anfragen[0][-1]['content'])['belege']


@pytest.mark.parametrize('needle', [ROW, 'Rücksendefrist\n18.11.2026', 'Prüfdatum\n20.11.2026'])
def test_dauerhaft_leere_auswahl_ergibt_ohne_passendes_pruefurteil_weiter_zitate(stores, monkeypatch, needle):
    intake(stores, monkeypatch)
    provider, judge = Auswahl(empty=10 if needle == ROW else 0, needle=needle), Pruefer(standard='{"urteil":"nein"}')
    saved, _, _, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == 'zitate'
    assert len(provider.requests) == 2 and len(judge.anfragen) == 1


@pytest.mark.parametrize('verdict', ['ja', 'nein', 'unklar'])
def test_identische_native_rows_aus_zwei_quellen_werden_einzeln_geprueft(stores, monkeypatch, verdict):
    sources = intake(stores, monkeypatch, 2)
    class ZweiterPruefer(Pruefer):
        def _antwort(self, messages):
            if self.anfragen:
                self.standard = json.dumps({'urteil': verdict})
            return super()._antwort(messages)
    provider, judge = Auswahl(), ZweiterPruefer()
    saved, _, rendered, _ = answer(stores, provider, judge)
    assert len(saved['refs']) == 2 and len(provider.requests) == 1
    assert len(judge.anfragen) == 2
    checked = [json.loads(r[-1]['content']) for r in judge.anfragen]
    assert all(r['satz'] == ROW and r['frage'] == QUESTION for r in checked)
    assert all(sum(s.body in r['belege'] for s in sources) == 1 for r in checked)
    assert all(sum(s.body in r['belege'] for r in checked) == 1 for s in sources)
    if verdict == 'ja':
        assert saved['satzantwort']['status'] == 'saetze' and rendered.count('Quelle berichtet: „' + ROW + '“') == 2
        structured = wma.satz_struktur(saved, *stores)
        assert len(structured['saetze']) == 2
        assert {b['episode_id'] for b in structured['belege']} == {s.id for s in sources}
        _, links, _ = wma.render(saved, *stores)
        assert {link['episode_id'] for link in links} == {s.id for s in sources}
    else:
        assert saved['satzantwort']['status'] == 'zitate' and wma.satz_struktur(saved, *stores) is None
    assert stores[1].all_claims() == []


def test_gleiche_native_row_mit_gleichem_beleg_wird_weiter_dedupliziert(stores, monkeypatch):
    intake(stores, monkeypatch)
    provider, judge = Auswahl(duplicate=True), Pruefer()
    saved, _, _, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == 'saetze'
    assert len(saved['satzantwort']['saetze']) == 1 and len(judge.anfragen) == 1


def test_herkoemmlicher_originalpfad_behaelt_beide_promptvertraege_und_den_normalen_judge(stores):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    source, _ = stores[0].record(EpisodeKind.DOCUMENT, 'Datenschutz', REGEL,
        Provenance(SourceType.DOCUMENT, source_ref='synthetic:normal-original'))
    assert WorkingMemoryStore(stores[0]).commit(stores[0].support_snapshot(source.id),
        [{'start': 0, 'end': len(REGEL), 'kind': 'conditional'}], model='synthetic')
    provider, judge = Auswahl(empty=1, needle=REGEL), Pruefer()
    saved, _, _, _ = answer(stores, provider, judge, question='Welche Datenschutzregel nennt die Quelle?')
    assert saved['satzantwort']['status'] == 'saetze' and len(provider.requests) == 2
    assert provider.requests[0][0]['content'] == sa.ORIGINAL_ANWEISUNG
    assert provider.requests[1][0]['content'] == sa.ORIGINAL_ANWEISUNG + sa.ORIGINAL_NACHPRUEFUNG
    assert len(judge.anfragen) == 1 and set(json.loads(judge.anfragen[0][-1]['content'])) == {'satz', 'belege'}
    assert 'native_frage' not in saved['satzantwort']
