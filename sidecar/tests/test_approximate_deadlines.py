"""An approximate source deadline must never certify an invented calendar day."""
import json
from datetime import date, datetime, timezone

import pytest

from icarus_memory import akten as akten_modul, akten_kontext, akten_markdown
from icarus_memory.fristen import fristen_in
from icarus_memory.lage import eingabe_aus_akte
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen
from tests.test_akten import JETZT, SACHE, akten, mail, welt  # noqa: F401
from tests.test_lage import LageModell, lagen  # noqa: F401

BEZUG = datetime(2026, 10, 15, tzinfo=timezone.utc)


@pytest.mark.parametrize('expression', [
    'Ende Oktober', 'Ende Oktober 2026', 'Ende Februar 2028',
    'Ende des Monats', 'Ende dieses Monats', 'zum Monatsende', 'Monatsende',
    'Ende des Jahres', 'Ende dieses Jahres', 'zum Jahresende', 'Jahresende',
])
@pytest.mark.parametrize('reference', [BEZUG, None])
def test_approximate_ends_remain_original_text_without_calendar_day(expression, reference):
    result = fristen_in(f'Manuskriptabgabe {expression}', reference)
    assert result.fristen == []
    assert result.ohne_datum == [expression]


def test_explicit_calendar_dates_keep_their_order_and_leap_day():
    result = fristen_in('Abgabe 31.10.2026, Prüfung 29. Februar 2028.', BEZUG)
    assert [item.datum for item in result.fristen] == [date(2026, 10, 31), date(2028, 2, 29)]
    assert result.ohne_datum == []


@pytest.mark.parametrize('expression,invented', [
    ('Ende Oktober', '31.10.2026'), ('Ende Februar 2028', '29.02.2028'),
    ('Ende des Monats', '31.10.2026'), ('Jahresende', '31.12.2026'),
])
def test_approximate_deadline_cannot_support_an_exact_day_in_an_answer(expression, invented):
    source = f'Die Manuskriptabgabe ist {expression}.'
    evidence = {'1': Beleg('1', source, BEZUG)}
    assert not satz_pruefen(Satz(f'Die Manuskriptabgabe ist am {invented}.', ('1',)), evidence).bestanden
    assert satz_pruefen(Satz(source, ('1',)), evidence).bestanden


def test_akte_exports_and_model_context_keep_the_approximate_original(welt, akten):
    episodes = welt[0]
    source = mail(episodes, 'Manuskript', [('Bitte Manuskriptabgabe Ende Oktober.', 'request')], tage=1)
    akten.bezuege.aktualisieren()
    profile = akten.akte(SACHE, jetzt=JETZT)
    assert profile['fristen']['kommend'] == []
    assert profile['fristen']['ohne_datum']['eintraege'][0]['ausdruck'] == 'Ende Oktober.'
    assert profile['offen']['eintraege'][0]['text'] == 'Bitte Manuskriptabgabe Ende Oktober.'
    payload = eingabe_aus_akte(profile).nutzlast()
    assert 'Ende Oktober' in payload and '31.10.2026' not in payload
    context = akten_kontext.aufbauen(episodes, None, [source.id], [SACHE], akten=akten)
    assert not any(row.datum == '2026-10-31' for row in context.zeilen)
    files = akten_markdown.bauen(
        [akten_markdown.AkteIn(SACHE, 'person', 'Förderteam', profile)],
        stand=JETZT.date(), version='test', info=lambda _: None)
    exported = '\n'.join(files.values())
    assert 'Ende Oktober' in exported
    assert '31.10.2026' not in exported and '2026-10-31' not in exported


def test_old_akte_cache_does_not_reintroduce_an_invented_day(welt, akten, monkeypatch):
    episodes = welt[0]
    mail(episodes, 'Manuskript', [('Bitte Manuskriptabgabe Ende Oktober.', 'request')], tage=1)
    akten.bezuege.aktualisieren()
    sources = akten.bezuege.quellen_von(SACHE)
    with monkeypatch.context() as old:
        old.setattr(akten_modul, 'AKTEN_VERSION', 4)
        raw = akten.roh(SACHE, sources)
        ref = raw['offen'][0]['ref']
        raw['fristen'] = [{'ref': ref, 'start': 25, 'ende': 37,
                          'datum': '2026-10-31', 'art': 'monatsende', 'ersetzt_durch': None}]
        akten._speichern(SACHE, akten._eingabe(SACHE, sources), raw)
    profile = akten.akte(SACHE, jetzt=JETZT)
    assert profile['fristen']['kommend'] == []
    assert profile['fristen']['ohne_datum']['gesamt'] == 1


def test_new_lage_cannot_save_invented_day_from_approximate_deadline(welt, akten, lagen):
    mail(welt[0], 'Manuskript', [('Die Manuskriptabgabe ist Ende Oktober.', 'request')], tage=1)
    akten.bezuege.aktualisieren()
    model = LageModell({'saetze': [
        {'text': 'Die Manuskriptabgabe ist am 31.10.2026.', 'belege': [1]},
        {'text': 'Die Manuskriptabgabe ist Ende Oktober.', 'belege': [1]},
    ]})
    result = lagen.erzeugen(SACHE, model, jetzt=JETZT)
    assert (result.saetze, result.verworfen) == (1, 1)
    assert '31.10.2026' not in model.aufrufe[0][0][1]['content']
    saved = lagen.lage(SACHE, akten.akte(SACHE, jetzt=JETZT))
    assert [item['text'] for item in saved['saetze']] == ['Die Manuskriptabgabe ist Ende Oktober.']


@pytest.mark.parametrize('stale', [False, True])
def test_saved_lage_hides_invented_day_without_writes_or_model_run(welt, akten, lagen, stale):
    episodes = welt[0]
    source = mail(episodes, 'Manuskript', [
        ('Die Manuskriptabgabe ist Ende Oktober.', 'request'),
        ('Die Unterlagen liegen vor.', 'fact'),
    ], tage=1)
    akten.bezuege.aktualisieren()
    profile = akten.akte(SACHE, jetzt=JETZT)
    fingerprint = akten.bezuege.quellen_von(SACHE)[0]['fp']
    saved = {'version': 1, 'saetze': [
        {'text': text, 'belege': [{'nummer': 1, 'episode_id': source.id, 'fp': fingerprint}]}
        for text in ('Die Manuskriptabgabe ist am 31.10.2026.',
                     'Die Manuskriptabgabe ist Ende Oktober.', 'Die Unterlagen liegen vor.')
    ]}
    lagen._speichern(SACHE, 'old-input' if stale else eingabe_aus_akte(profile).fingerabdruck, 'old-model', saved)
    before = '\n'.join(episodes._conn.iterdump())
    result = lagen.lage(SACHE, profile)
    assert [item['text'] for item in result['saetze']] == [
        'Die Manuskriptabgabe ist Ende Oktober.', 'Die Unterlagen liegen vor.']
    assert '\n'.join(episodes._conn.iterdump()) == before
    assert json.loads(lagen._zeile(SACHE)['daten']) == saved


@pytest.mark.parametrize('same_source', [False, True])
def test_saved_lage_keeps_explicit_exact_day_with_an_approximate_deadline(welt, akten, lagen, same_source):
    episodes = welt[0]
    mail(episodes, 'Manuskript', [('Die Manuskriptabgabe ist Ende Oktober.', 'request')], tage=2)
    text = 'Die Prüfung ist am 31. Oktober 2026.'
    if same_source:
        text += ' Die Manuskriptabgabe ist Ende Oktober.'
    exact = mail(episodes, 'Prüfung', [(text, 'request')], tage=1)
    akten.bezuege.aktualisieren()
    profile = akten.akte(SACHE, jetzt=JETZT)
    fp = next(item['fp'] for item in akten.bezuege.quellen_von(SACHE) if item['episode_id'] == exact.id)
    saved = {'version': 1, 'saetze': [{'text': 'Die Prüfung ist am 31.10.2026.',
              'belege': [{'nummer': 1, 'episode_id': exact.id, 'fp': fp}]}]}
    lagen._speichern(SACHE, 'old-input', 'old-model', saved)
    assert lagen.lage(SACHE, profile)['saetze'][0]['text'] == 'Die Prüfung ist am 31.10.2026.'
