"""Erste Suchstufe: Bedeutungen eines Begriffs, ohne Modell, ohne Raten."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.bedeutungen import begriff_aus_frage, bedeutungen
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType

JETZT = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize('frage', [
    'Was ist mit Mainz los?', 'was ist bei Mainz los', 'Erzähl mir was zu Mainz',
    'Erzähl mir mal etwas über Mainz!', 'Was gibt es Neues zu Mainz?', 'Was läuft bei Mainz?',
    'Wie steht es um Mainz?', 'Was weißt du über Mainz?', 'Update zu Mainz',
    'Was ist mit dem Projekt Mainz los?', 'Und was ist mit Mainz?',
    'Was ist mit Mainz diese Woche los?', 'Was ist mit Mainz gerade los?',
])
def test_open_questions_name_their_subject(frage):
    assert begriff_aus_frage(frage) == 'Mainz'


@pytest.mark.parametrize('frage', [
    'Wann liefert Anna die Prüfmuster für Mainz?', 'Mainz', 'Was ist los?',
    'Schreib Anna wegen Mainz', None, 'Was ist mit ' + 'sehr ' * 20 + 'langem Zeug los?',
    'Was ist mit dir los?', 'Was weißt du über mich?', 'Wie steht es um uns?', 'Was ist mit dem los?',
])
def test_precise_or_other_questions_are_left_alone(frage):
    assert begriff_aus_frage(frage) is None


@pytest.fixture
def bestand(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield episodes, claims
    claims.close()
    episodes.close()


def _mail(episodes, titel, text, absender, tage, project=None):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL),
                                 participants=[absender], occurred_at=JETZT - timedelta(days=tage),
                                 project_id=project)
    return episode


def _ausstattung(episodes, claims, *, mit_projekt=True):
    projekt = [_mail(episodes, 'Druckfreigabe', 'Die Freigabe kommt.', 'Anna <anna@agentur.de>', 1, 'p-mainz'),
               _mail(episodes, 'Angebot', 'Das Angebot für Mainz liegt bei.', 'Ben <ben@agentur.de>', 3, 'p-mainz')] \
        if mit_projekt else []
    klinik = [_mail(episodes, 'Studie', 'Die Unterlagen folgen.', 'Dr. Kranz <kranz@unimedizin-mainz.de>', 5),
              _mail(episodes, 'Rückfrage', 'Kurze Rückfrage.', 'Dr. Kranz <kranz@unimedizin-mainz.de>', 9)]
    standort = [_mail(episodes, 'Standort Mainz', 'Die Halle ist frei.', 'Makler <info@makler.de>', 12),
                _mail(episodes, 'AW: Standort Mainz', 'Danke.', 'Makler <info@makler.de>', 11)]
    _mail(episodes, 'Kinder', 'Die Mainzelmännchen sind wieder da.', 'Oma <oma@example.de>', 2)
    _mail(episodes, 'Ausflug', 'Wir waren in Mainz am Dom.', 'Oma <oma@example.de>', 40)
    claims.entities.create('organization', 'Uniklinik Mainz')
    termine = [{'uid': 't1', 'summary': 'Workshop', 'location': 'Mainz, Rheinufer',
                'start': (JETZT + timedelta(days=3)).isoformat()},
               {'uid': 't2', 'summary': 'Mainz Rückblick', 'start': (JETZT - timedelta(days=90)).isoformat()}]
    return projekt, klinik, standort, termine


def test_all_meanings_are_collected_and_each_source_counts_once(bestand):
    episodes, claims = bestand
    projekt, klinik, standort, termine = _ausstattung(episodes, claims)
    result = bedeutungen('Mainz', episodes=episodes, projects=[('p-mainz', 'Mainz'), ('p-orion', 'Orion')],
                         entities=claims.entities, termine=termine, jetzt=JETZT)
    by_art = {}
    for bedeutung in result['bedeutungen']:
        by_art.setdefault(bedeutung['art'], []).append(bedeutung)
    assert by_art['projekt'][0]['label'] == 'Projekt Mainz'
    assert set(by_art['projekt'][0]['quellen']) == {e.id for e in projekt}
    assert by_art['eintrag'][0]['label'] == 'Organisation Uniklinik Mainz'
    assert by_art['absender'][0]['label'] == 'Mails von unimedizin-mainz.de'
    assert set(by_art['absender'][0]['quellen']) == {e.id for e in klinik}
    # Die Gegenpartei (Adresse) trägt die Bedeutung; der Betreff steht als Kontext in der Zeile.
    makler = next(b for b in by_art['gegenpartei'] if 'Makler' in b['label'])
    assert makler['label'] == 'Mails mit Makler (makler.de)' and 'Standort Mainz' in makler['detail']
    assert set(makler['quellen']) == {e.id for e in standort}
    [termin] = by_art['termin']
    assert termin['ref'] == 't1' and termin['detail'].startswith('am 29.9.')
    # Die Mainzelmännchen zählen nicht, der Dom schon: als eigene, schwache Zeile statt als Sammelposten.
    oma = next(b for b in by_art['gegenpartei'] if 'Oma' in b['label'])
    assert oma['anzahl'] == 1 and not oma['stark']
    # Keine Quelle zählt doppelt: das Angebot steht beim Projekt, nicht bei den Gegenparteien.
    alle = [q for b in result['bedeutungen'] for q in b['quellen']]
    assert len(alle) == len(set(alle))
    # Projekt, bestätigte Uniklinik mit eigenen Mails und ein Termin in drei
    # Tagen: Das ist offen, also wird gefragt statt geraten.
    assert result['eindeutig'] is None
    assert result['bedeutungen'][0]['art'] == 'projekt'


def test_own_project_outweighs_side_mentions(bestand):
    episodes, _ = bestand
    for n in range(4):
        _mail(episodes, f'Druck {n}', f'Freigabe Teil {n}.', 'Anna <anna@agentur.de>', n + 1, 'p-mainz')
    _mail(episodes, 'Ausflug', 'Wir waren in Mainz am Dom.', 'Oma <oma@example.de>', 3)
    result = bedeutungen('Mainz', episodes=episodes, projects=[('p-mainz', 'Mainz')], jetzt=JETZT)
    assert result['eindeutig']['label'] == 'Projekt Mainz'
    assert [b['art'] for b in result['bedeutungen']] == ['projekt', 'gegenpartei']


def test_without_a_project_the_question_stays_open(bestand):
    episodes, claims = bestand
    _, _, _, termine = _ausstattung(episodes, claims, mit_projekt=False)
    result = bedeutungen('Mainz', episodes=episodes, projects=[], entities=claims.entities,
                         termine=termine, jetzt=JETZT)
    assert result['eindeutig'] is None
    assert [b['art'] for b in result['bedeutungen']][:2] != ['erwaehnung']
    # Was übrig bleibt, verschwindet nicht: Die Mail der Oma steht als letzte, schwächste Zeile da.
    assert result['bedeutungen'][-1]['label'].startswith('Mails mit Oma')


def test_single_meaning_is_unambiguous_and_nothing_is_invented(bestand):
    episodes, claims = bestand
    _mail(episodes, 'Standort Mainz', 'Die Halle ist frei.', 'Makler <info@makler.de>', 2)
    _mail(episodes, 'Re: Standort Mainz', 'Danke.', 'Makler <info@makler.de>', 1)
    result = bedeutungen('Mainz', episodes=episodes, jetzt=JETZT)
    assert [b['art'] for b in result['bedeutungen']] == ['gegenpartei']
    assert result['eindeutig']['label'] == 'Mails mit Makler (makler.de)'
    assert bedeutungen('Wiesbaden', episodes=episodes, jetzt=JETZT)['bedeutungen'] == []


def test_ignored_sources_do_not_count(bestand):
    episodes, claims = bestand
    mail = _mail(episodes, 'Standort Mainz', 'Text', 'Makler <info@makler.de>', 2)
    episodes.ignore(mail.id)
    assert bedeutungen('Mainz', episodes=episodes, jetzt=JETZT)['bedeutungen'] == []


def test_too_many_mentions_are_reported_not_hidden(bestand):
    episodes, _ = bestand
    for n in range(3):
        _mail(episodes, f'Mainz {n}', f'Text {n}', f'P{n} <p{n}@x.de>', n)
    found, truncated = episodes.mentions('Mainz', limit=2)
    assert len(found) == 2 and truncated is True
    assert episodes.mentions('Mainz', limit=3)[1] is False


def test_chat_lookups_do_not_count_as_mentions(bestand):
    from icarus_memory.episodes import CHAT_LOOKUP_TAG
    episodes, _ = bestand
    episodes.record(EpisodeKind.MESSAGE, 'Frage', 'Was ist mit Mainz los?',
                    Provenance(SourceType.CHAT), tags=[CHAT_LOOKUP_TAG])
    assert episodes.mentions('Mainz') == ([], False)


def test_range_of_a_meaning_is_complete_and_fresh(bestand):
    from icarus_memory.bedeutungen import bereich
    episodes, claims = bestand
    projekt, klinik, standort, _ = _ausstattung(episodes, claims)
    assert set(bereich({'begriff': 'Mainz', 'art': 'projekt', 'ref': 'p-mainz'}, episodes=episodes)[0]) \
        == {e.id for e in projekt}
    absender = bereich({'begriff': 'Mainz', 'art': 'absender', 'ref': 'unimedizin-mainz.de'}, episodes=episodes)
    assert set(absender[0]) == {e.id for e in klinik} and absender[1] is False
    betreff = bereich({'begriff': 'Mainz', 'art': 'betreff', 'ref': 'standort mainz'}, episodes=episodes)[0]
    assert set(betreff) == {e.id for e in standort}
    # Eine neue Mail der Klinik gehört beim nächsten Mal dazu.
    neu = _mail(episodes, 'Nachtrag', 'Noch etwas.', 'Dr. Kranz <kranz@unimedizin-mainz.de>', 0)
    assert neu.id in bereich({'begriff': 'Mainz', 'art': 'absender', 'ref': 'unimedizin-mainz.de'},
                             episodes=episodes)[0]
    [uniklinik] = [e for e in claims.entities.list() if e['label'] == 'Uniklinik Mainz']
    assert bereich({'begriff': 'Mainz', 'art': 'eintrag', 'ref': uniklinik['id']}, episodes=episodes,
                   entities=claims.entities) == ([], False)
    assert bereich({'begriff': 'Mainz', 'art': 'eintrag', 'ref': 'gibt-es-nicht'}, episodes=episodes,
                   entities=claims.entities) == ([], False)
    with pytest.raises(ValueError):
        bereich({'begriff': 'Mainz', 'art': 'erfunden', 'ref': 'x'}, episodes=episodes)


def test_person_in_a_shared_domain_is_grouped_as_that_person(bestand):
    from icarus_memory.bedeutungen import bereich
    episodes, _ = bestand
    anna = [_mail(episodes, f'Entwurf {n}', 'Text.', 'Anna Keller <anna@agentur.de>', n + 1) for n in range(2)]
    _mail(episodes, 'Rechnung', 'Text.', 'Ben Roth <ben@agentur.de>', 1)
    result = bedeutungen('Anna', episodes=episodes, jetzt=JETZT)
    [absender] = [b for b in result['bedeutungen'] if b['art'] == 'absender']
    assert absender['label'] == 'Mails von Anna Keller'
    assert set(absender['quellen']) == {e.id for e in anna}
    assert set(bereich({'begriff': 'Anna', 'art': 'absender', 'ref': absender['ref']}, episodes=episodes)[0]) \
        == {e.id for e in anna}


def test_many_single_mentions_are_collected_and_stay_reachable(bestand):
    from icarus_memory.bedeutungen import bereich
    episodes, _ = bestand
    _mail(episodes, 'Studie', 'Die Unterlagen folgen für Mainz.', 'Dr. Kranz <kranz@unimedizin-mainz.de>', 5)
    einzelne = [_mail(episodes, f'Reise {n}', f'Wir fahren nach Mainz, Teil {n}.', f'P{n} <p{n}@firma{n}.de>', n + 1)
                for n in range(5)]
    result = bedeutungen('Mainz', episodes=episodes, jetzt=JETZT)
    # Fünf einzelne Erwähnungen sind keine fünf Bedeutungen: eine Sammelzeile trägt sie alle.
    assert [b['art'] for b in result['bedeutungen']] == ['absender', 'erwaehnung']
    sammel = result['bedeutungen'][1]
    assert set(sammel['quellen']) == {e.id for e in einzelne}
    ids, _ = bereich({'art': 'erwaehnung', 'ref': sammel['ref'], 'begriff': 'Mainz'}, episodes=episodes)
    assert {e.id for e in einzelne} <= set(ids)


def test_gegenpartei_der_eigenen_adresse_ist_immer_der_andere(bestand):
    episodes, _ = bestand
    for n in range(2):
        _mail(episodes, f'Angebot {n}', f'Mein Angebot für Mainz {n}.', 'Lea <lea@hartmann.example>', n + 1)
    # Der Absender ist der Nutzer selbst; die Gegenpartei steht im Empfängerkreis.
    episodes.record(EpisodeKind.MESSAGE, 'Angebot Klinik', 'Angebot für Mainz.', Provenance(SourceType.EMAIL),
                    participants=['Lea <lea@hartmann.example>', 'Frau Becker <becker@klinikum.example>'],
                    occurred_at=JETZT - timedelta(days=3))
    episodes.record(EpisodeKind.MESSAGE, 'Rückfrage Klinik', 'Rückfrage zu Mainz.', Provenance(SourceType.EMAIL),
                    participants=['Frau Becker <becker@klinikum.example>'], occurred_at=JETZT - timedelta(days=2))
    result = bedeutungen('Mainz', episodes=episodes, jetzt=JETZT, eigene=['lea@hartmann.example'])
    starke = [b for b in result['bedeutungen'] if b['stark']]
    assert [b['label'] for b in starke] == ['Mails mit Frau Becker (klinikum.example)']
    assert starke[0]['anzahl'] == 2


def test_ein_austausch_mit_dem_nutzer_wiegt_schwerer_als_bloss_empfangene_mails(bestand):
    episodes, _ = bestand
    # Zwei frischere Werbemails, nur empfangen.
    for n in range(2):
        _mail(episodes, f'Angebot im Herbst {n}', f'Unser Angebot {n}.', 'Werbung <info@werbung.example>', 2 + n)
    # Zwei ältere Mails eines Kunden, an die der Nutzer selbst geschrieben hat.
    episodes.record(EpisodeKind.MESSAGE, 'Ihr Angebot', 'Ich sende Ihnen mein Angebot.', Provenance(SourceType.EMAIL),
                    participants=['Lea <lea@hartmann.example>', 'Kunde <k@kunde.example>'],
                    occurred_at=JETZT - timedelta(days=40))
    _mail(episodes, 'Re: Ihr Angebot', 'Danke, das Angebot passt.', 'Kunde <k@kunde.example>', 35)
    result = bedeutungen('Angebot', episodes=episodes, jetzt=JETZT, eigene=['lea@hartmann.example'])
    assert [b['label'] for b in result['bedeutungen']][:2] == ['Mails mit Kunde (kunde.example)',
                                                               'Mails mit Werbung (werbung.example)']
    # Ohne die eigenen Adressen ist der Austausch nicht erkennbar; dann zählt die frischere Werbung mehr.
    ohne = bedeutungen('Angebot', episodes=episodes, jetzt=JETZT)
    assert [b['label'] for b in ohne['bedeutungen']][0] == 'Mails mit Werbung (werbung.example)'
