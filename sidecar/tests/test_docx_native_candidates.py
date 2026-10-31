"""Ganze native Rawrecords sind Kandidaten, niemals ungeprüfte Antworten."""
import json
import copy
from types import SimpleNamespace
from dataclasses import replace

import pytest

from icarus_memory import satzantwort as sa, satzpruefung_modell as spm, working_memory_answers as wma
from tests.test_docx_native_rows import stores  # noqa: F401
from tests.test_docx_native_selection import Auswahl, QUESTION, ROW, answer, intake
from tests.test_satzpruefung_modell import Pruefer, beleg
from tests.test_docx_table_context import p, packed
from tests.test_mail_docx_attachments import fetch, DOCX_MIME
from icarus_memory.akten_kontext import Kontext
from icarus_memory.mail_ingestion import remember
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_answer_source_boundaries import AT


@pytest.mark.parametrize('count', [1, 2])
def test_zwei_valide_leere_auswahlen_erzeugen_nur_gepruefte_literal_kandidaten(stores, monkeypatch, count):
    sources = intake(stores, monkeypatch, count)
    provider, judge = Auswahl(empty=10), Pruefer()
    saved, _, rendered, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == 'saetze'
    assert len(provider.requests) == 2 and len(judge.anfragen) == count
    assert rendered.count('Quelle berichtet: „' + ROW + '“') == count
    sentences = saved['satzantwort']['saetze']
    assert len(sentences) == count and all(s['roh'] == ROW and not s['vom_programm'] for s in sentences)
    assert len({s['native_review'] for s in sentences}) == count
    payloads = [json.loads(r[-1]['content']) for r in judge.anfragen]
    assert all(r['satz'] == ROW and r['frage'] == QUESTION for r in payloads)
    assert all(sum(s.body in r['belege'] for s in sources) == 1 for r in payloads)
    assert {l['episode_id'] for l in wma.render(saved, *stores)[1]} == {s.id for s in sources}
    assert len(wma.satz_struktur(saved, *stores)['saetze']) == count
    assert stores[1].all_claims() == []


def test_native_profilpaar_hat_16_gesamt_und_8_je_satz_ohne_echte_wartezeit(monkeypatch):
    elapsed, budgets = [0.0], []
    def verdict(adapter, provider, sentence, sources, deadline):
        budgets.append(deadline)
        elapsed[0] += 7.0
        return spm.Urteil('ja' if deadline >= 7.0 else 'unklar')
    monkeypatch.setattr(spm, '_ein_urteil', verdict)
    result = spm.urteilen([(ROW, [beleg()]), (ROW, [beleg(2)])],
        spm.tor('an', Pruefer(model='kingfisher-qwen:9b-32k')), native_fragen=[QUESTION, QUESTION],
        uhr=lambda: elapsed[0])
    assert [r.wert for r in result] == ['ja', 'ja'] and budgets == [8.0, 8.0]


@pytest.mark.parametrize('bad', [
    '{"status":"unklar","originalstellen":[]}', 'invalid json',
    '{"status":"nichts_vorliegend","originalstellen":[{"beleg":99,"satz":1}]}',
    '{"status":"antwort","originalstellen":[]}',
    '{"status":"nichts_vorliegend","originalstellen":[{"beleg":1,"satz":1}]}',
])
@pytest.mark.parametrize('stage', [1, 2])
def test_nur_zwei_korrekt_leere_ausgaben_erlauben_kandidaten(stores, monkeypatch, bad, stage):
    intake(stores, monkeypatch)
    class Fehlerauswahl(Auswahl):
        def complete_json(self, messages, **kwargs):
            reply = super().complete_json(messages, **kwargs)
            return Reply(text=bad) if sa.ist_satzanfrage(messages) and len(self.requests) == stage else reply
    from icarus_memory.providers import Reply
    provider, judge = Fehlerauswahl(empty=10), Pruefer()
    saved, _, _, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == 'zitate' and judge.anfragen == []
    assert len(provider.requests) == stage


@pytest.mark.parametrize('case', ['inactive', 'unsupported', 'three', 'many_rows', 'without_row', 'raw_budget'])
def test_alle_belege_muessen_die_enge_grenze_erfuellen(stores, monkeypatch, case):
    if case in {'inactive', 'unsupported', 'three'}:
        intake(stores, monkeypatch, 3 if case == 'three' else 1)
    else:
        row = '<w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026') + '</w:tc><w:tc>' + p('Prüfstelle') + '</w:tc></w:tr>'
        extra = '<w:tr><w:tc>' + p('Bearbeitungsnummer') + p('12345') + '</w:tc></w:tr>' if case == 'many_rows' else ''
        content = '<w:tbl>' + row + extra + '</w:tbl>'
        if case == 'raw_budget':
            content += p('Unabhängige Zusatzinformation. ' * 150)
        files = [('Pruefung.docx', packed(content), DOCX_MIME)]
        if case == 'without_row':
            files.append(('Information.docx', packed(p('Prüfdatum ist nicht angegeben.')), DOCX_MIME))
        result = remember(stores[0], fetch(monkeypatch, *files), claims=stores[1])
        for identifier in result['anhaenge']:
            source = stores[0].get(identifier)
            items = [{'start': 0, 'end': len(source.body), 'kind': 'uncertain'}] if case == 'without_row' else []
            if case == 'raw_budget':
                start = source.body.index(ROW)
                items = [{'start': start, 'end': start + len(ROW), 'kind': 'uncertain'}]
            assert WorkingMemoryStore(stores[0]).commit(stores[0].support_snapshot(identifier), items, model='synthetic')
    judge = None if case == 'inactive' else Pruefer(model='tev1:4b' if case == 'unsupported' else 'pruef-1')
    provider = Auswahl(empty=10)
    saved, _, _, _ = answer(stores, provider, judge)
    assert saved['satzantwort']['status'] == 'zitate' and len(provider.requests) == 2
    assert not judge or judge.anfragen == []


@pytest.mark.parametrize('case', ['default_false', 'missing', 'extra', 'omitted'])
def test_nur_exakte_gewaehlte_quellenmenge_ohne_auslassung_erlaubt_kandidaten(stores, monkeypatch, case):
    intake(stores, monkeypatch, 2)
    episodes, claims = stores
    refs = WorkingMemoryStore(episodes).inventory()['refs']
    belege, omitted = sa.belege_sammeln(refs, Kontext(), episodes, claims)
    assert len(refs) == len(belege) == 2 and omitted == 0
    provider, judge = Auswahl(empty=10), Pruefer()
    if case == 'default_false':
        result = sa.formulieren(QUESTION, belege, provider, jetzt=AT, pruefung=spm.tor('an', judge))
        assert result.status == 'zitate'
    else:
        monkeypatch.setattr(sa, 'belege_sammeln', lambda *args: (belege[:1] if case == 'missing' else belege,
                                                               1 if case == 'omitted' else 0))
        result = sa.erzeugen(QUESTION, refs[:1] if case == 'extra' else refs, Kontext(), episodes, claims,
                            provider, jetzt=AT, pruefung=spm.tor('an', judge))
        assert result['status'] == 'zitate'
    assert len(provider.requests) == 2 and judge.anfragen == []


@pytest.mark.parametrize('verdict', ['nein', 'unklar', 'timeout'])
def test_zwei_identische_rows_mit_einem_tragenden_vorbehalt_lassen_keinen_teilrest(stores, monkeypatch, verdict):
    condition = 'Die folgenden Termine gelten nur nach schriftlicher Freigabe.'
    row = '<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026') + '</w:tc><w:tc>' + p('Prüfstelle') + '</w:tc></w:tr></w:tbl>'
    result = remember(stores[0], fetch(monkeypatch, ('A.docx', packed(row), DOCX_MIME),
        ('B.docx', packed(p(condition) + row), DOCX_MIME)), claims=stores[1])
    for identifier in result['anhaenge']:
        assert WorkingMemoryStore(stores[0]).commit(stores[0].support_snapshot(identifier), [], model='synthetic')
    collect = sa.belege_sammeln
    def ordered(*args, **kwargs):
        belege, omitted = collect(*args, **kwargs)
        # Pflichtfall: erst JA zur unbedingten Quelle, dann Ablehnung/Timeout
        # zur tatsächlich vorbehaltenen Quelle. Proofs und Rawbelege bleiben gleich.
        belege.sort(key=lambda b: condition in b.native_raw)
        return [replace(b, nummer=i + 1) for i, b in enumerate(belege)], omitted
    monkeypatch.setattr(sa, 'belege_sammeln', ordered)
    judge = Pruefer()
    def controlled(adapter, provider, sentence, sources, deadline):
        adapter.fragen(provider, sentence, sources)  # unveränderter tatsächlicher Prüfauftrag
        return spm.Urteil('unklar' if verdict == 'timeout' else verdict, 'zeit' if verdict == 'timeout' else 'fehler') if condition in sources else spm.Urteil('ja')
    monkeypatch.setattr(spm, '_ein_urteil', controlled)
    saved, _, _, _ = answer(stores, Auswahl(empty=10), judge)
    assert saved['satzantwort']['status'] == 'zitate' and len(judge.anfragen) == 2
    assert condition not in json.loads(judge.anfragen[0][-1]['content'])['belege']
    assert condition in json.loads(judge.anfragen[1][-1]['content'])['belege']
    assert sum(condition in json.loads(r[-1]['content'])['belege'] for r in judge.anfragen) == 1
    assert wma.satz_struktur(saved, *stores) is None and stores[1].all_claims() == []


def test_falsche_datumsrolle_bleibt_trotz_literal_kandidat_geschlossen(stores, monkeypatch):
    intake(stores, monkeypatch)
    judge = Pruefer(standard='{"urteil":"nein"}')
    question = 'Bis wann muss ich das Formular zurücksenden? Prüfdatum ist nicht die Rücksendefrist.'
    saved, _, _, _ = answer(stores, Auswahl(empty=10), judge, question)
    assert saved['satzantwort']['status'] == 'zitate' and len(judge.anfragen) == 1
    data = json.loads(judge.anfragen[0][-1]['content'])
    assert data['frage'] == question and data['satz'] == ROW


@pytest.mark.parametrize('mutation', ['review', 'row', 'question', 'program', 'parent', 'source'])
def test_kandidaten_behalten_native_review_frische_und_legacy_inferenzsperre(stores, monkeypatch, mutation):
    source, = intake(stores, monkeypatch)
    saved = answer(stores, Auswahl(empty=10), Pruefer())[0]
    assert wma.satz_struktur(saved, *stores)['saetze'][0]['text'] == 'Quelle berichtet: „' + ROW + '“'
    changed = copy.deepcopy(saved)
    sentence = changed['satzantwort']['saetze'][0]
    if mutation == 'review':
        sentence['native_review'] = '0' * 64
    elif mutation == 'row':
        sentence['roh'] = 'Prüfdatum\n20.11.2026\tPrüfstelle'
    elif mutation == 'question':
        changed['satzantwort']['native_frage'] = 'Was ist die Rücksendefrist?'
    elif mutation == 'program':
        sentence['vom_programm'] = True
    elif mutation == 'parent':
        stores[0].ignore(next(t.removeprefix('mail-parent:') for t in source.tags if t.startswith('mail-parent:')))
    else:
        stores[0].add_mail_headers(source.id, ['synthetic:source-change'])
    assert wma.satz_struktur(changed, *stores) is None


@pytest.mark.parametrize('model,native,per,total,expected', [
    ('kingfisher-qwen:9b-32k', [None, None], None, None, [8., 5.]),
    ('kingfisher-qwen:9b-32k', [QUESTION, None], None, None, [8., 5.]),
    ('kingfisher-qwen:9b-32k', [QUESTION], None, None, [8.]),
    ('kingfisher-qwen:9b-32k', [QUESTION] * 3, None, None, [8., 5.]),
    ('qwen:9b', [QUESTION, QUESTION], None, None, [2., 2.]),
    ('kingfisher-qwen:9b-32k', [QUESTION, QUESTION], None, 12., [8., 5.]),
    ('kingfisher-qwen:9b-32k', [QUESTION, QUESTION], None, 10., [8., 3.]),
    ('kingfisher-qwen:9b-32k', [QUESTION, QUESTION], .1, None, [.1, .1]),
    ('kingfisher-qwen:9b-32k', [QUESTION, QUESTION], 1., 3., [1., 1.]),
])
def test_alle_anderen_und_expliziten_budgets_bleiben_unveraendert(monkeypatch, model, native, per, total, expected):
    elapsed, budgets = [0.], []
    def verdict(adapter, provider, sentence, sources, deadline):
        budgets.append(deadline)
        elapsed[0] += min(7., deadline)
        return spm.Urteil('ja' if deadline >= 7. else 'unklar')
    monkeypatch.setattr(spm, '_ein_urteil', verdict)
    spm.urteilen([(ROW, [beleg(i + 1)]) for i in range(len(native))], spm.tor('an', Pruefer(model=model)),
        native_fragen=native, satz_budget=per, gesamt_budget=total, uhr=lambda: elapsed[0])
    assert budgets == expected


@pytest.mark.parametrize('outer,expected', [(10., [8., 3.]), (-1., [])])
def test_engere_aeussere_frist_wird_durch_native_paarbudget_nicht_verlaengert(monkeypatch, outer, expected):
    from icarus_memory import providers
    elapsed, budgets = [0.], []
    monkeypatch.setattr(providers, 'time', SimpleNamespace(monotonic=lambda: elapsed[0]))
    def verdict(adapter, provider, sentence, sources, deadline):
        budgets.append(deadline)
        elapsed[0] += min(7., deadline)
        return spm.Urteil('ja' if deadline >= 7. else 'unklar')
    monkeypatch.setattr(spm, '_ein_urteil', verdict)
    with providers.json_request_deadline(outer):
        result = spm.urteilen([(ROW, [beleg()]), (ROW, [beleg(2)])],
            spm.tor('an', Pruefer(model='kingfisher-qwen:9b-32k')), native_fragen=[QUESTION, QUESTION],
            uhr=lambda: elapsed[0])
    assert budgets == expected and result[-1].wert == 'unklar'
