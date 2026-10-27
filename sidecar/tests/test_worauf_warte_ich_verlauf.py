"""Persona-Prüfung, Befund A3: „Worauf warte ich noch?“ lässt Erledigtes weg, nennt keine Einladung als Zusage und
stellt das Wichtige vorn.

Zusicherungen:
1. Deine Bitte ist beantwortet, sobald die Gegenseite im selben Mailverlauf antwortet (genaue Kopfzeilen); eine
   automatische Antwort oder eine bloße Verzögerung beantwortet nichts.
2. Eine Zusage an dich ist eingelöst, wenn der Zusagende im Verlauf das Zugesagte mitbringt („hiermit“, „anbei“);
   eine andere spätere Mail von ihm (Absage, Verzögerung) oder die eines Dritten löst sie nicht ein.
3. „Doch noch offen“ holt einen so beantworteten Punkt zurück.
4. Eine Einladung (auch eine Kalendereinladung) ist keine Zusage ihres Absenders, sondern eine Bitte an dich; wer
   im Text zusagt, sagt weiter zu. Deine eigene Einladung ist etwas, worauf du wartest.
5. Reihenfolge: deine „wartet auf“-Aufgaben, dann Punkte, bei denen du nachgefragt hast, dann verstrichene, dann
   bald fällige Fristen; eine seit Wochen verstrichene Frist hebt nichts nach vorn. Ein Verlauf ist eine Zeile.
6. Die Messlatte-Lage (Zimmermann, Brandl, Maurer): Zimmermann und Brandl stehen vorn, Maurer nicht.
"""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType, offene_punkte
from icarus_memory.akten_entscheidungen import Entscheidungen
from icarus_memory.antwort_im_verlauf import automatisch, einladung, liefert, verzoegert
from icarus_memory.tasks import TaskStatus
from tests.test_akten import akten, einordnen, neu_rechnen  # noqa: F401 - Fixture und Hilfen
from tests.test_bezuege import ICH, JETZT, welt  # noqa: F401 - Fixture

LEA = f'Lea Hartmann <{ICH}>'
MAURER = 'Stefan Maurer <s.maurer@datenschutz-maurer.example>'
ZIMMERMANN = 'Petra Zimmermann <p.zimmermann@rehaklinik-eichenberg.example>'
BRANDL = 'Lisa Brandl <lisa@brandl-grafik.example>'
DRITTE = 'Ute Dritte <ute@andere.example>'


def mail(episodes, titel, abschnitte, tage, *, von, an, kennung, antwort_auf=None, text=None):
    """Mail mit Message-ID und Antwortbezug; `abschnitte` sind (Text, Art), `text` der ganze Körper."""
    koerper = text or ' '.join(t for t, _ in abschnitte)
    tags = [f'mail:message:{kennung}'] + ([f'mail:reply:{antwort_auf}'] if antwort_auf else [])
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, koerper,
                                 Provenance(SourceType.EMAIL, source_ref=f'test:{kennung}'),
                                 participants=[von, an], occurred_at=JETZT - timedelta(days=tage), tags=tags)
    if abschnitte:
        einordnen(episodes, episode, abschnitte)
    return episode


def warten(akten, **kwargs):
    neu_rechnen(akten)
    return offene_punkte.sammeln(akten, akten.bezuege, 'wartet_auf', jetzt=JETZT, **kwargs)


def texte(gesammelt):
    return [p['text'] for p in gesammelt['punkte']]


# -- 1. Antwort im Verlauf ------------------------------------------------------------------------

FREIGABE = 'Könnten Sie mir Ihre Freigabe für das Datenschutzkonzept geben?'


def test_antwort_der_gegenseite_im_verlauf_beantwortet_deine_bitte(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Datenschutzkonzept', [(FREIGABE, 'request')], 20, von=LEA, an=MAURER, kennung='m1')
    antwort = mail(episodes, 'AW: Datenschutzkonzept', [], 18, von=MAURER, an=LEA, kennung='m2', antwort_auf='m1',
                   text='Guten Tag Frau Hartmann,\n\nhiermit erteile ich die Freigabe für Ihr Konzept.\n\nBeste Grüße')
    assert FREIGABE not in texte(warten(akten))
    akte = akten.akte('person:a:s.maurer@datenschutz-maurer.example', jetzt=JETZT)
    erledigt = next(e for e in akte['offen']['erledigt']['eintraege'] if e['text'] == FREIGABE)
    # Mit Grund und der Antwort, die ihn trägt (ihr erster Satz nach der Anrede).
    assert erledigt['grund'] == 'antwort' and erledigt['durch']['episode_id'] == antwort.id
    assert erledigt['durch']['text'].startswith('hiermit erteile ich die Freigabe')


@pytest.mark.parametrize('titel,text', [
    ('Automatische Antwort: Abwesend', 'Ich bin bis Mittwoch nicht im Büro und melde mich danach.'),
    ('AW: Datenschutzkonzept', 'Danke, ich bin noch nicht dazu gekommen und melde mich später.'),
])
def test_automatische_oder_verzoegernde_antwort_beantwortet_nichts(welt, akten, titel, text):
    episodes, _, _ = welt
    mail(episodes, 'Datenschutzkonzept', [(FREIGABE, 'request')], 20, von=LEA, an=MAURER, kennung='m1')
    mail(episodes, titel, [], 18, von=MAURER, an=LEA, kennung='m2', antwort_auf='m1', text=text)
    assert FREIGABE in texte(warten(akten))


def test_mail_ohne_kopfzeilenbezug_oder_eigene_mail_beantwortet_nichts(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Datenschutzkonzept', [(FREIGABE, 'request')], 20, von=LEA, an=MAURER, kennung='m1')
    # Gleicher Betreff, aber kein Antwortbezug: kein Verlauf (Betreff und Namen zählen nicht).
    mail(episodes, 'AW: Datenschutzkonzept', [], 18, von=MAURER, an=LEA, kennung='m2',
         text='hiermit erteile ich die Freigabe.')
    # Deine eigene weitere Mail im Verlauf beantwortet deine Bitte nicht.
    mail(episodes, 'Erinnerung', [], 10, von=LEA, an=MAURER, kennung='m3', antwort_auf='m1',
         text='Ich wollte kurz nachfragen, ob Sie schon dazu gekommen sind.')
    assert FREIGABE in texte(warten(akten))


# -- 2. Zusage an dich ------------------------------------------------------------------------------

VERTRAG = 'Ich schicke Ihnen das unterschriebene Exemplar nach der Gremiumssitzung zurück.'


def test_zusage_ist_eingeloest_wenn_der_zusagende_liefert(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Beratungsvertrag', [(VERTRAG, 'commitment')], 20, von=ZIMMERMANN, an=LEA, kennung='z1')
    mail(episodes, 'AW: Beratungsvertrag', [], 5, von=ZIMMERMANN, an=LEA, kennung='z2', antwort_auf='z1',
         text='Sehr geehrte Frau Hartmann,\n\nanbei der unterschriebene Vertrag.\n\nFreundliche Grüße')
    assert VERTRAG not in texte(warten(akten))


@pytest.mark.parametrize('von,text', [
    (ZIMMERMANN, 'Das Gremium hat den Punkt leider vertagt, die Unterschrift folgt Anfang nächster Woche.'),
    (ZIMMERMANN, 'Kurze Frage: Passt Ihnen der Termin am Donnerstag?'),
    (DRITTE, 'Anbei die Unterlagen für Frau Hartmann.'),
])
def test_zusage_bleibt_offen_ohne_lieferung_des_zusagenden(welt, akten, von, text):
    episodes, _, _ = welt
    mail(episodes, 'Beratungsvertrag', [(VERTRAG, 'commitment')], 20, von=ZIMMERMANN, an=LEA, kennung='z1')
    mail(episodes, 'AW: Beratungsvertrag', [], 5, von=von, an=LEA, kennung='z2', antwort_auf='z1', text=text)
    assert VERTRAG in texte(warten(akten))


def test_doch_noch_offen_holt_einen_beantworteten_punkt_zurueck(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Datenschutzkonzept', [(FREIGABE, 'request')], 20, von=LEA, an=MAURER, kennung='m1')
    mail(episodes, 'AW: Datenschutzkonzept', [], 18, von=MAURER, an=LEA, kennung='m2', antwort_auf='m1',
         text='Danke, ich schaue es mir an.')
    neu_rechnen(akten)
    akte = akten.akte('person:a:s.maurer@datenschutz-maurer.example', jetzt=JETZT)
    ziel = akte['offen']['erledigt']['eintraege'][0]['ziel']
    Entscheidungen(episodes).setzen(ziel, 'offen')
    assert FREIGABE in texte(warten(akten))


# -- 3. Einladungen ---------------------------------------------------------------------------------

EINLADUNG = ('Wir möchten Sie zu einem Gastvortrag am 18. November einladen. Über eine Zusage würde ich mich sehr '
             'freuen.')


@pytest.mark.parametrize('text,ist', [
    (EINLADUNG, True),
    ('Hiermit lade ich Sie herzlich zu unserem Fachtag ein.', True),
    ('Sie wurden zu folgendem Termin eingeladen. Zusagen | Vielleicht | Absagen', True),
    ('Wir würden uns über Ihre Teilnahme freuen.', True),
    ('Danke für die Einladung, ich sage gern zu und komme am 18. November.', False),
    ('Vielen Dank für die Einladung! Wir nehmen gern teil.', False),
    ('Ich schicke Ihnen die Unterlagen bis Freitag.', False),
])
def test_einladung_erkennen(text, ist):
    assert einladung(text) is ist


def test_kalendereinladung_am_betreff():
    assert einladung('Jour fixe, Mittwoch 9 Uhr, Konferenzraum 2', 'Einladung: Jour fixe @ Mi 30. Sep 09:00')
    assert not einladung('Ich bringe die Zahlen mit.', 'AW: Jour fixe')


def test_einladung_an_dich_ist_keine_zusage_sondern_eine_bitte(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Gastvortrag', [(EINLADUNG, 'commitment')], 5, von='Alex Winter <alex@ifeh.example>', an=LEA,
         kennung='e1')
    mail(episodes, 'Einladung: Jour fixe @ Mi', [('Sie wurden eingeladen. Zusagen | Vielleicht | Absagen', 'commitment')],
         4, von='Kalender <kalender@firma.example>', an=LEA, kennung='e2')
    assert warten(akten)['punkte'] == []
    akte = akten.akte('person:a:alex@ifeh.example', jetzt=JETZT)
    eintrag = akte['offen']['eintraege'][0]
    assert eintrag['art'] == 'Bitte' and eintrag['richtung'] == 'an_mich' and eintrag['einladung'] is True


def test_angenommene_einladung_bleibt_zusage_und_deine_einladung_wartet(welt, akten):
    episodes, _, _ = welt
    annahme = 'Danke für die Einladung, ich sage gern zu und schicke Ihnen die Folien bis Freitag.'
    mail(episodes, 'AW: Gastvortrag', [(annahme, 'commitment')], 5, von='Alex Winter <alex@ifeh.example>', an=LEA,
         kennung='e3')
    eigene = 'Ich lade Sie herzlich zu unserem Fachtag am 12. Dezember ein und freue mich über Ihre Zusage.'
    mail(episodes, 'Fachtag', [(eigene, 'commitment')], 6, von=LEA, an='Ina Gast <ina@gast.example>', kennung='e4')
    gesammelt = warten(akten)
    assert set(texte(gesammelt)) == {annahme, eigene}
    text, _ = offene_punkte.als_text(gesammelt, 'wartet_auf')
    assert 'Deine Einladung an' in text and 'Alex Winter, Zusage' in text


def test_regeln_fuer_antworten():
    assert automatisch('Automatische Antwort: Krankheitsbedingt eingeschränkt erreichbar')
    assert automatisch('Out of Office: back Monday') and automatisch('AW: Abwesenheitsnotiz')
    assert not automatisch('AW: Flyer Fachtag', 'Hier ist das Layout.')
    assert verzoegert('Das Gremium hat den Punkt vertagt.') and not verzoegert('Hiermit erteile ich die Freigabe.')
    assert liefert('Hiermit erteile ich die Freigabe.') and liefert('Anbei das Layout.')
    assert not liefert('Kurze Frage zum Termin.')


# -- 4. Reihenfolge ---------------------------------------------------------------------------------

class _Aufgabe:
    def __init__(self, titel, wer, *, due=None, quelle=None):
        self.id, self.title, self.wartet_auf, self.due = f't-{titel}', titel, wer, due
        self.status = TaskStatus.OPEN
        self.created_at = JETZT - timedelta(days=1)
        self.provenance = Provenance(SourceType.USER_STATED, source_ref=f'episode:{quelle}' if quelle else None)


def test_wichtiges_steht_vorn(welt, akten):
    episodes, _, _ = welt
    # Neueste, aber gewöhnliche Bitte.
    neu = 'Könnten Sie mir bitte die Teilnehmerliste schicken?'
    mail(episodes, 'Teilnehmerliste', [(neu, 'request')], 1, von=LEA, an='Tom Neu <tom@neu.example>', kennung='n1')
    # Eine Zusage mit verstrichener Frist (vor 5 Tagen).
    frist = 'Ich schicke Ihnen die Zahlen bis 24. September.'
    mail(episodes, 'Zahlen', [(frist, 'commitment')], 9, von='Kai Frist <kai@frist.example>', an=LEA, kennung='f1')
    # Eine seit Wochen verstrichene Frist hebt nichts nach vorn.
    alt = 'Ich schicke Ihnen den Bericht bis 1. Juli.'
    mail(episodes, 'Bericht', [(alt, 'commitment')], 100, von='Olaf Alt <olaf@alt.example>', an=LEA, kennung='o1')
    # Eine ältere Zusage, bei der du nachgefragt hast (deine Mail im selben Verlauf, nicht als Bitte eingeordnet).
    mail(episodes, 'Beratungsvertrag', [(VERTRAG, 'commitment')], 30, von=ZIMMERMANN, an=LEA, kennung='z1')
    mail(episodes, 'Erinnerung', [], 6, von=LEA, an=ZIMMERMANN, kennung='z2', antwort_auf='z1',
         text='Ich wollte nachfragen, ob der Vertrag inzwischen vorliegt.')
    aufgabe = _Aufgabe('Angebot Druckerei', 'Druckerei Kranz')
    gesammelt = warten(akten, aufgaben=[aufgabe])
    assert texte(gesammelt) == ['Angebot Druckerei', VERTRAG, frist, neu, alt]
    assert gesammelt['wichtig'] == 3
    text, links = offene_punkte.als_text(gesammelt, 'wartet_auf')
    assert '1. Deine Aufgabe „Angebot Druckerei“, wartet auf Druckerei Kranz' in text
    assert '(du hast am 23. September 2026 nachgefragt)' in text
    assert '(Frist seit 5 Tagen verstrichen)' in text
    assert 'Frist seit 90 Tagen' not in text and 'Die wichtigsten' not in text
    # Die Aufgabe ohne Quelle trägt keine Quellennummer; die Nummern der Quellen bleiben lückenlos.
    assert [l['label'] for l in links] == ['Quelle 1 öffnen', 'Quelle 2 öffnen', 'Quelle 3 öffnen', 'Quelle 4 öffnen']


def test_ein_verlauf_ist_eine_zeile_die_zusage_vor_deiner_nachfrage(welt, akten):
    episodes, _, _ = welt
    layout = 'Das Layout schicke ich Ihnen bis Mittwoch, 23. September.'
    mail(episodes, 'Auftrag Flyer', [('Bis wann wäre ein erster Entwurf möglich?', 'request')], 27, von=LEA,
         an=BRANDL, kennung='b1')
    mail(episodes, 'AW: Auftrag Flyer', [(layout, 'commitment')], 25, von=BRANDL, an=LEA, kennung='b2',
         antwort_auf='b1')
    nachfrage = 'Könnten Sie mir bitte kurz sagen, wann ich mit dem Layout rechnen kann?'
    mail(episodes, 'Wo bleibt das Layout?', [(nachfrage, 'request')], 1, von=LEA, an=BRANDL, kennung='b3',
         antwort_auf='b2')
    mail(episodes, 'Automatische Antwort: Krankheitsbedingt eingeschränkt erreichbar', [], 1, von=BRANDL, an=LEA,
         kennung='b4', antwort_auf='b3', text='Ich bin bis Mittwoch eingeschränkt erreichbar.')
    gesammelt = warten(akten)
    # Die erste Frage ist beantwortet (Frau Brandl sagte zu); Zusage und Nachfrage sind eine Zeile.
    assert texte(gesammelt) == [layout] and gesammelt['punkte'][0]['nachgefasst']


# -- 5. Die Lage der Messlatte („wartet-auf“) ----------------------------------------------------------

def test_messlatte_lage_zimmermann_und_brandl_vorn_maurer_erledigt(welt, akten):
    episodes, _, _ = welt
    # Viel gewöhnliches Rauschen: neuere einfache Bitten an andere.
    for i in range(14):
        mail(episodes, f'Rauschen {i}', [(f'Könnten Sie mir bitte Unterlage {i} schicken?', 'request')], 1 + i * 0.1,
             von=LEA, an=f'Person {i} <p{i}@rauschen.example>', kennung=f'r{i}')
    mail(episodes, 'Beratungsvertrag', [(VERTRAG, 'commitment')], 21, von=ZIMMERMANN, an=LEA, kennung='z1')
    mail(episodes, 'AW: Beratungsvertrag', [], 13, von=ZIMMERMANN, an=LEA, kennung='z2', antwort_auf='z1',
         text='Das Gremium hat den Punkt leider vertagt. Ich schicke Ihnen den Vertrag dann sofort zu.')
    mail(episodes, 'Erinnerung', [], 6, von=LEA, an=ZIMMERMANN, kennung='z3', antwort_auf='z2',
         text='Ich wollte kurz nachfragen, ob der unterschriebene Beratungsvertrag inzwischen vorliegt.')
    mail(episodes, 'Freigabe', [(FREIGABE, 'request')], 19, von=LEA, an=MAURER, kennung='m1')
    mail(episodes, 'AW: Freigabe', [('Ich prüfe das bis Ende nächster Woche und melde mich mit der Freigabe.',
                                     'commitment')], 18, von=MAURER, an=LEA, kennung='m2', antwort_auf='m1')
    mail(episodes, 'Freigabe Datenschutzkonzept', [], 4, von=MAURER, an=LEA, kennung='m3', antwort_auf='m2',
         text='Guten Tag Frau Hartmann,\n\nhiermit erteile ich die Freigabe für Ihr Datenschutzkonzept.')
    gesammelt = warten(akten)
    text, _ = offene_punkte.als_text(gesammelt, 'wartet_auf')
    assert texte(gesammelt)[0] == VERTRAG and 'Maurer' not in text and 'Freigabe' not in text
    assert gesammelt['gesamt'] == 15 and len(gesammelt['punkte']) == offene_punkte.MAX_PUNKTE
    assert 'Die wichtigsten 12 von 15' in text
