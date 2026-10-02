"""Auflösung der Sachen und Weg der Frage (E1): alle Bedeutungen, Merkmal, Überwiegen, keine unnötige Rückfrage."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.bedeutungen import bedeutungen, bereich
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.frage import Anfrage, rueckfall
from icarus_memory.frage_weg import bezug_im_bestand, entscheide, hauptsache, merkmal_gewinner
from icarus_memory.model import Provenance, SourceType

JETZT = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)
ICH = ['lea@hartmann.example']


@pytest.fixture
def bestand(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield episodes, claims
    claims.close()
    episodes.close()


def _mail(episodes, titel, text, teilnehmer, tage, *, art=EpisodeKind.MESSAGE, projekt=None):
    episode, _ = episodes.record(art, titel, text,
                                 Provenance(SourceType.EMAIL if art == EpisodeKind.MESSAGE else SourceType.DOCUMENT),
                                 participants=list(teilnehmer), occurred_at=JETZT - timedelta(days=tage),
                                 project_id=projekt)
    return episode


def _mainz(episodes):
    """Drei Bedeutungen von Mainz: ein Klinikum, der Umzug eines Kollegen, ein privater Urlaub."""
    for n, titel in enumerate(['Anfrage Beratungsangebot', 'Angebot AN-41', 'Einladung zur Präsentation im Klinikum']):
        _mail(episodes, titel, f'Das Klinikum in Mainz meldet sich zu {titel}.', ['Sabine Becker <s.becker@klinikum-albanus.example>'],
              20 - n * 5)
    for n, titel in enumerate(['Wir sind umgezogen', 'Einweihungsfeier bei uns']):
        _mail(episodes, titel, f'Wir sind nach Mainz gezogen: {titel}.', ['Tobias Brandt <tobias@brandt-nutrition.example>'], 12 - n)
    _mail(episodes, 'Urlaub Mainz Ideen', 'Urlaub Mainz 23. bis 26. Oktober, Handy aus.', [], 30,
          art=EpisodeKind.DOCUMENT)
    _mail(episodes, 'Ihre Buchungsbestätigung', 'Hotel Domblick Mainz. Anreise: Freitag, 23. Oktober.',
          ['Hotel Domblick Mainz <info@hotel-domblick.example>'], 31)


def _entscheide(frage, episodes, anfrage=None, **kw):
    anfrage = anfrage or rueckfall(frage)
    return entscheide(frage, anfrage, episodes=episodes, eigene=ICH, jetzt=JETZT, **kw)


def test_rueckfrage_bietet_alle_bedeutungen_auch_private(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    v = _entscheide('Was ist eigentlich mit Mainz los?', episodes)
    assert v.aktion == 'rueckfrage' and v.begriff == 'Mainz'
    angebote = [(m['art'], m['label'], m['detail']) for m in v.gefunden['bedeutungen']]
    text = '\n'.join(f'{label} {detail}' for _, label, detail in angebote)
    # Klinikum, Kollege und der private Urlaub: jede Bedeutung mit eigener Zeile und Kontext.
    assert 'klinikum-albanus.example' in text and 'Sabine Becker' in text
    assert 'Tobias Brandt' in text
    urlaub = [m for m in v.gefunden['bedeutungen'] if 'Urlaub' in m['label'] or 'Urlaub' in m['detail']]
    assert len(urlaub) == 1 and urlaub[0]['art'] == 'zusammenhang' and urlaub[0]['anzahl'] == 2
    # Nichts geht in „Weitere Erwähnungen“ unter.
    assert not [m for m in v.gefunden['bedeutungen'] if m['art'] == 'erwaehnung']
    # Jede Quelle steht bei genau einer Bedeutung.
    alle = [q for m in v.gefunden['bedeutungen'] for q in m['quellen']]
    assert len(alle) == len(set(alle)) == 7


def test_die_private_bedeutung_ist_per_klick_erreichbar(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    gefunden = bedeutungen('Mainz', episodes=episodes, eigene=ICH, jetzt=JETZT)
    urlaub = next(m for m in gefunden['bedeutungen'] if m['art'] == 'zusammenhang')
    ids, abgeschnitten = bereich({'art': urlaub['art'], 'ref': urlaub['ref'], 'begriff': 'Mainz'},
                                 episodes=episodes, eigene=ICH)
    assert set(ids) == set(urlaub['quellen']) and not abgeschnitten
    # Auch die Firma und die Person sind per Klick erreichbar und liefern alle ihre Quellen.
    partei = next(m for m in gefunden['bedeutungen'] if m['art'] == 'gegenpartei' and 'Becker' in m['label'])
    ids, _ = bereich({'art': partei['art'], 'ref': partei['ref'], 'begriff': 'Mainz'}, episodes=episodes, eigene=ICH)
    assert set(ids) == set(partei['quellen']) and len(ids) == 3


def test_ein_unterscheidungsmerkmal_in_der_frage_entscheidet_ohne_rueckfrage(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    v = _entscheide('Was ist mit Mainz im Urlaub los?', episodes)
    assert v.aktion == 'bedeutung' and v.grund == 'merkmal'
    assert v.gewaehlt['art'] == 'zusammenhang'
    # Der Rest wird nicht verschwiegen, sondern steht unter „Auch gefunden“.
    assert {m['art'] for m in v.andere} == {'gegenpartei'}
    v = _entscheide('Was ist mit Mainz und der Präsentation los?', episodes)
    assert v.aktion == 'bedeutung' and 'Becker' in v.gewaehlt['label']


def test_eine_genaue_frage_mit_mehreren_sachen_wird_nie_aufgehalten(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    for frage in ('Wann fahre ich nach Mainz in den Urlaub?', 'Wann ist meine Präsentation beim Klinikum in Mainz?'):
        v = _entscheide(frage, episodes)
        assert v.aktion == 'weiter' and v.grund == 'keine Sache', frage


def test_eine_genaue_frage_mit_einer_sache_fragt_nur_bei_echter_mehrdeutigkeit_zurueck(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    # „Mainz“ allein und ohne Merkmal: drei Zusammenhänge, die Frage sagt nicht, welcher.
    assert _entscheide('Wann fahre ich nach Mainz?', episodes).aktion == 'rueckfrage'
    # Zwei einzelne Notizen zu einem Begriff sind keine zwei Bedeutungen.
    _mail(episodes, 'To-do Förderantrag', 'Der Förderantrag muss raus.', [], 3, art=EpisodeKind.DOCUMENT)
    _mail(episodes, 'Förderantrag Planung', 'Planung des Förderantrags.', [], 9, art=EpisodeKind.DOCUMENT)
    v = _entscheide('Bis wann muss ich den Förderantrag einreichen?', episodes)
    assert v.aktion == 'weiter' and v.grund == 'nur Erwähnungen'


def test_eine_starke_bedeutung_neben_frischen_einzelquellen_ist_keine_mehrdeutigkeit(bestand):
    episodes, _ = bestand
    for n in range(2):
        _mail(episodes, f'Vertrag {n}', f'Der Vertrag mit Zeta {n}.', ['Ben Lang <ben@agentur.example>'], 120 + n)
    _mail(episodes, 'Notiz Zeta', 'Zeta meldet sich.', [], 2, art=EpisodeKind.DOCUMENT)
    v = _entscheide('Wann ist der Termin mit Zeta?', episodes)
    assert v.aktion == 'weiter' and v.grund == 'keine zwei Bedeutungen'


def test_ueberwiegt_eine_bedeutung_klar_wird_direkt_geantwortet_und_der_rest_genannt(bestand):
    episodes, _ = bestand
    for n in range(5):
        _mail(episodes, f'Druck {n}', f'Freigabe Teil {n} für Mainz.', ['Anna <anna@agentur.example>'], n + 1, projekt='p-mainz')
    _mail(episodes, 'Ausflug', 'Wir waren in Mainz am Dom.', ['Oma <oma@familie.example>'], 3)
    v = _entscheide('Was ist mit Mainz los?', episodes, projects=[('p-mainz', 'Mainz')])
    assert v.aktion == 'bedeutung' and v.grund == 'ueberwiegt' and v.gewaehlt['art'] == 'projekt'
    assert [m['art'] for m in v.andere] == ['gegenpartei']


def test_ein_name_mit_einer_adresse_und_losen_notizen_wird_nicht_zurueckgefragt(bestand):
    episodes, _ = bestand
    _mail(episodes, 'Lieferung', 'Ich liefere morgen.', ['Herr Maurer <maurer@lieferant.example>'], 5)
    _mail(episodes, 'Notiz Maurer', 'Herr Maurer ist im Urlaub.', [], 4, art=EpisodeKind.DOCUMENT)
    _mail(episodes, 'Gespräch Maurer', 'Maurer hat zugesagt.', [], 3, art=EpisodeKind.DOCUMENT)
    v = _entscheide('Hat Herr Maurer schon geliefert?', episodes)
    assert v.aktion == 'weiter'


def test_bestaetigtes_wissen_bleibt_die_oberste_stufe(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    v = _entscheide('Was ist mit Mainz los?', episodes, bestaetigt=lambda begriff: True)
    assert v.aktion == 'weiter' and v.grund == 'bestätigtes Wissen'


def test_ohne_treffer_oder_ohne_sache_gibt_es_nichts_zu_klaeren(bestand):
    episodes, _ = bestand
    assert _entscheide('Was ist mit Mainz los?', episodes).aktion == 'weiter'
    assert _entscheide('Worauf warte ich noch?', episodes).grund == 'keine Sache'
    assert hauptsache(Anfrage()) is None
    assert hauptsache(Anfrage(('A1', 'B2'), None, 'fakt')) is None
    assert hauptsache(Anfrage(('A1', 'B2'), None, 'ueberblick')) == 'A1'


def test_bezug_im_bestand_kennt_quellen_und_projekte(bestand):
    episodes, _ = bestand
    _mainz(episodes)
    assert bezug_im_bestand(rueckfall('Was ist mit Mainz los?'), episodes)
    assert not bezug_im_bestand(rueckfall('Was ist die Hauptstadt von Frankreich?'), episodes)
    assert bezug_im_bestand(Anfrage(('Orion',), None, 'fakt'), episodes, [('p-1', 'Orion')])
    assert not bezug_im_bestand(Anfrage(), None)


def test_merkmal_gewinner_verlangt_genau_eine_passende_bedeutung():
    a = {'label': 'A', 'merkmale': ['urlaub'], 'art': 'zusammenhang'}
    b = {'label': 'B', 'merkmale': ['praese'], 'art': 'gegenpartei'}
    anfrage = Anfrage(('Mainz',), None, 'ueberblick')
    assert merkmal_gewinner('Was ist mit Mainz im Urlaub?', anfrage, 'Mainz', [a, b]) is a
    assert merkmal_gewinner('Was ist mit Mainz im Urlaub, gibt es eine Präsentation?', anfrage, 'Mainz', [a, b]) is None
    assert merkmal_gewinner('Was ist mit Mainz los?', anfrage, 'Mainz', [a, b]) is None
    assert merkmal_gewinner('Was ist mit Mainz im Urlaub?', anfrage, 'Mainz', [a]) is None


def test_ein_beteiligter_beim_namen_wird_bei_einer_genauen_frage_nie_zurueckgefragt(bestand):
    episodes, _ = bestand
    for n in range(3):
        _mail(episodes, f'Angebot {n}', f'Das Angebot {n} ist fertig.', ['Dr. Volker Amann <amann@klinikum.example>'], 10 + n)
    for n in range(3):
        _mail(episodes, f'Gremium {n}', f'Dr. Amann meldet sich {n}.', ['Nora Feldmann <feldmann@klinikum.example>'], 5 + n)
    genau = _entscheide('Was wollte Dr. Amann letzte Woche von mir?', episodes)
    assert genau.aktion == 'weiter' and genau.grund == 'benannter Beteiligter'
    # Bei einer offenen Frage zeigt Kingfisher weiter, was es zu Amann alles gibt.
    offen = _entscheide('Was ist mit Amann los?', episodes)
    assert offen.aktion in {'rueckfrage', 'bedeutung'} and offen.grund != 'benannter Beteiligter'


def test_absender_mit_dem_begriff_im_namen_und_nur_einer_mail_macht_keine_mehrdeutigkeit(bestand):
    episodes, _ = bestand
    for n in range(2):
        _mail(episodes, f'Probeverkostung {n}', f'Die Probeverkostung {n} findet statt.',
              ['Alex Winter <alex@winter-catering.example>'], 10 + n)
    for n in range(4):
        _mail(episodes, f'Newsletter {n}', f'Nur Werbung {n}.',
              [f'Apotheke Probeverkostung <info@apotheke-{n}.example>'], 3 + n)
    # Vier Werbemails, deren Absendername das Wort trägt, sind keine vier Bedeutungen der genauen Frage.
    assert _entscheide('Wann ist die Probeverkostung?', episodes).aktion == 'weiter'
