"""E2: Akten als Kontext einer Frage. Überholtes wird gekennzeichnet (nie still entfernt), Sachen lösen nur eindeutig auf."""
from datetime import date

import pytest

from icarus_memory import akten_kontext
from icarus_memory.akten import Akten
from icarus_memory.akten_kontext import Kontext, Ueberholt, aufbauen, hinweis_fuer_modell, nachrangig_sortiert, sachen_finden
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_akten import SACHE, STIFTUNG, einordnen, mail  # noqa: F401 - Hilfen
from tests.test_bezuege import ICH, JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen

HEUTE = date(2026, 9, 29)


@pytest.fixture(autouse=True)
def fester_tag(monkeypatch):
    monkeypatch.setattr(akten_kontext, '_heute', lambda: HEUTE)


@pytest.fixture
def akten(welt):
    episodes, workspace, bezuege = welt
    a = Akten(episodes, bezuege, claims=None, aufgaben=lambda sache, ids: [])
    episodes.akten_zugang = lambda: a
    bezuege.aktualisieren()
    return a


def neu(akten):
    akten.bezuege.aktualisieren()
    return akten


def ausschreibung_und_verlaengerung(episodes):
    alt = mail(episodes, 'Ausschreibung', [('Die Einreichfrist ist der 15. Oktober 2026.', 'fact')], tage=30)
    neue = mail(episodes, 'Verlängerung', [('Die neue Einreichfrist ist der 12. November 2026.', 'change')], tage=10)
    return alt, neue


# -- Kennzeichnung ----------------------------------------------------------------


def test_ueberholte_frist_wird_mit_altem_und_neuem_wert_und_neuer_quelle_gekennzeichnet(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    kontext = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    marken = kontext.ueberholt[alt.id]
    assert [(m.grund, m.alt_wert, m.neu_wert, m.durch) for m in marken] == [
        ('frist', '15. Oktober 2026', '12. November 2026', neue.id)]
    assert 'Einreichfrist' in marken[0].alt and 'Einreichfrist' in marken[0].neu
    assert marken[0].ref['episode_id'] == alt.id and marken[0].durch_ref['episode_id'] == neue.id
    assert not kontext.gekennzeichnet(neue.id), 'Die neue Quelle ist der aktuelle Stand und wird nie gekennzeichnet'


def test_ohne_neuere_quelle_bleibt_die_frist_ungekennzeichnet(welt, akten):
    episodes, _, _ = welt
    alt = mail(episodes, 'Ausschreibung', [('Die Einreichfrist ist der 15. Oktober 2026.', 'fact')], tage=30)
    kontext = aufbauen(episodes, None, [alt.id], akten=neu(akten))
    assert not kontext.ueberholt and kontext.zaehlung['gekennzeichnet'] == 0


def test_nur_die_kandidaten_werden_gekennzeichnet_die_akte_kennt_mehr(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    assert aufbauen(episodes, None, [neue.id], akten=neu(akten)).ueberholt == {}


@pytest.mark.parametrize('grund, alt_text, neu_text', [
    ('stand', ('Die Anmeldung läuft über das Portal.', 'status'), ('Die Anmeldung läuft jetzt über das Formular.', 'change')),
    ('erledigt', ('Bitte schicken Sie die Unterlagen zu.', 'request'), ('Die Unterlagen sind bei uns erhalten.', 'status')),
    ('abgesagt', ('Wir sagen die Teilnahme am Workshop zu.', 'commitment'), ('Der Workshop wurde abgesagt.', 'change')),
])
def test_stand_erledigt_und_absage_werden_gekennzeichnet(welt, akten, grund, alt_text, neu_text):
    episodes, _, _ = welt
    alt = mail(episodes, 'Früher', [alt_text], tage=20)
    neue = mail(episodes, 'Später', [neu_text], tage=5)
    kontext = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    assert [(m.grund, m.durch) for m in kontext.ueberholt[alt.id]] == [(grund, neue.id)]
    assert not kontext.gekennzeichnet(neue.id)


def test_abgesagter_termin_wird_gekennzeichnet(welt, akten):
    from icarus_memory import EpisodeKind
    episodes, _, _ = welt
    termin = quelle(episodes, 'Workshop Akademie', 'Workshop der Akademie Taunus.\nOrt: Bad Homburg', [STIFTUNG],
                    art=EpisodeKind.EVENT, tage=-20)
    absage = mail(episodes, 'Absage', [(f'Der Workshop am {termin.reference_time().strftime("%d.%m.%Y")} wurde abgesagt.', 'change')], tage=3)
    kontext = aufbauen(episodes, None, [termin.id, absage.id], akten=neu(akten))
    assert [(m.grund, m.durch) for m in kontext.ueberholt[termin.id]] == [('abgesagt', absage.id)]


def test_ohne_akten_zugang_und_bei_fehlern_gibt_es_den_leeren_kontext(welt):
    episodes, _, _ = welt
    assert aufbauen(episodes, None, ['x']) is akten_kontext.LEER

    class Kaputt:
        bezuege = None

    assert aufbauen(episodes, None, ['x'], akten=Kaputt()) is akten_kontext.LEER


def test_der_schalter_aktiv_schaltet_den_zugang_ab(welt, akten, monkeypatch):
    episodes, _, _ = welt
    monkeypatch.setattr(akten_kontext, 'AKTIV', False)
    assert akten_kontext.zugang(episodes) is None


# -- Fingerabdruck --------------------------------------------------------------------


def test_fremde_neue_mail_aendert_den_fingerabdruck_nicht(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    vorher = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten)).signatur
    quelle(episodes, 'Newsletter', 'Ganz anderes Thema, keine Frist.', ['News <news@anders.example>'], tage=2)
    assert aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten)).signatur == vorher


def test_eine_neue_frist_aendert_den_fingerabdruck_und_die_kennzeichnung(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    vorher = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    juengste = mail(episodes, 'Nochmal verlängert', [('Die neue Einreichfrist ist der 10. Dezember 2026.', 'change')], tage=1)
    nachher = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    assert nachher.signatur != vorher.signatur
    assert nachher.gekennzeichnet(neue.id) and nachher.ueberholt[neue.id][0].durch == juengste.id


def test_der_kontext_ist_reproduzierbar_und_serialisierbar(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    a = aufbauen(episodes, None, [alt.id, neue.id], [SACHE], akten=neu(akten))
    b = aufbauen(episodes, None, [alt.id, neue.id], [SACHE], akten=neu(akten))
    assert a.signatur == b.signatur and a.als_dict() == b.als_dict()
    zurueck = Kontext.aus_dict(a.als_dict())
    assert zurueck is not None and zurueck.signatur == a.signatur and zurueck.ueberholt == a.ueberholt
    assert Kontext.aus_dict({**a.als_dict(), 'version': 99}) is None
    kaputt = a.als_dict()
    kaputt['ueberholt'][alt.id][0]['grund'] = 'erfunden'
    assert Kontext.aus_dict(kaputt) is None


# -- Von oben --------------------------------------------------------------------------


def test_von_oben_liefert_stand_und_kommende_frist_der_aufgeloesten_sache(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    kontext = aufbauen(episodes, None, [], [SACHE], akten=neu(akten))
    # Stand und kommende Frist stehen in derselben Textstelle: eine Zeile, beide Rollen.
    assert [z.rolle for z in kontext.zeilen] == ['Stand · Frist']
    frist = kontext.zeilen[0]
    assert frist.datum == '2026-11-12' and frist.ref['episode_id'] == neue.id
    assert all(WorkingMemoryStore(episodes).resolve(ref) is not None for ref in kontext.oben)
    # Die überholte Frist ist nicht „von oben“: Sie steht nur als Kennzeichnung, wenn sie in den Kandidaten steht.
    assert alt.id not in {ref['episode_id'] for ref in kontext.oben}


def test_sachen_finden_loest_nur_eindeutige_namen_auf(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Angebot', [('Das Angebot liegt bei 100 Euro.', 'fact')], tage=4,
         absender='Alex Winter <alex@winter-catering.example>')
    mail(episodes, 'Fragebogen', [('Bitte geben Sie Feedback.', 'request')], tage=3,
         absender='Alex Winter <alex.winter@institut-hessen.example>')
    mail(episodes, 'Hallo', [('Guten Tag zusammen.', 'fact')], tage=2, absender='Sabine Becker <s.becker@klinikum-albanus.example>')
    neu(akten)
    gefunden = sachen_finden(akten, ['Alex Winter', 'Sabine Becker', 'Unbekannt Nirgends'])
    assert 'person:a:s.becker@klinikum-albanus.example' in gefunden.sachen
    assert 'Alex Winter' in gefunden.mehrdeutig, 'Zwei Namensvettern lösen keine Sache auf'
    assert not any('winter' in s for s in gefunden.sachen if s.startswith('person:'))
    assert 'Unbekannt Nirgends' in gefunden.ohne_treffer


def test_organisation_wird_ueber_die_kennung_gefunden(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Angebot', [('Das Angebot liegt bei 100 Euro.', 'fact')], tage=4,
         absender='Alex <alex@winter-catering.example>')
    gefunden = sachen_finden(neu(akten), ['Winter Catering'])
    assert gefunden.sachen == ('organisation:wintercatering',)


# -- Für das Modell ---------------------------------------------------------------------


def test_hinweis_fuer_das_modell_nennt_alten_und_neuen_wert_und_die_neue_quelle(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    kontext = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    hinweise = hinweis_fuer_modell(kontext, alt.id, {alt.id: 'S1', neue.id: 'S2'}, {})
    assert hinweise == [{'grund': 'Frist verschoben', 'ueberholte_angabe': '15. Oktober 2026',
                         'neu': '12. November 2026', 'neue_quelle': 'S2'}]
    assert hinweis_fuer_modell(kontext, alt.id, {}, {neue.id: 'Verlängerung'})[0]['neue_quelle'] == 'Verlängerung'
    assert hinweis_fuer_modell(kontext, neue.id, {}, {}) == []


def test_gekennzeichnetes_steht_nachrangig_und_nichts_faellt_weg(welt, akten):
    episodes, _, _ = welt
    alt, neue = ausschreibung_und_verlaengerung(episodes)
    kontext = aufbauen(episodes, None, [alt.id, neue.id], akten=neu(akten))
    reihe = nachrangig_sortiert([alt.id, neue.id], kontext, lambda x: x)
    assert reihe == [neue.id, alt.id]
    assert nachrangig_sortiert(['a', 'b'], akten_kontext.LEER, lambda x: x) == ['a', 'b']
