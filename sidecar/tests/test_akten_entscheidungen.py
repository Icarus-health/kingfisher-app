"""Akte wie ein Stabschef: Entscheidungen des Nutzers, „Braucht dich“, Richtung, Zeitstrahl."""
from datetime import timedelta

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.akten_entscheidungen import Entscheidungen, gueltiges_ziel, ziel_termin
from icarus_memory.fristlage import aus_akte
from tests.test_akten import akten, einordnen, mail, neu_rechnen  # noqa: F401 - Fixture und Hilfen
from tests.test_bezuege import ICH, JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen

SILKE = 'Silke Vogt <s.vogt@akademie.example>'
LEA = f'Lea Hartmann <{ICH}>'
AKADEMIE = 'organisation:akademie'
PERSON = 'person:a:s.vogt@akademie.example'

ANFRAGE = 'Wir würden Sie gern als Referentin für den Workshop am 28. Oktober gewinnen.'
ABLAUF = 'Den Ablauf schicken wir Ihnen im August.'
ABSAGE = 'Leider müssen wir den Workshop am 28. Oktober absagen.'
NACHHOLEN = 'Sehr gern bin ich im Frühjahr dabei, schicken Sie mir einfach den neuen Termin.'


def verlaufsmail(episodes, titel, abschnitte, tage, *, absender=SILKE, an=LEA, kennung, antwort_auf=None):
    """Eine Mail mit genauen Kopfzeilenbezügen (Message-ID, In-Reply-To), wie sie die Aufnahme ablegt."""
    text = ' '.join(t for t, _ in abschnitte)
    tags = [f'mail:message:{kennung}'] + ([f'mail:reply:{antwort_auf}'] if antwort_auf else [])
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'test:{titel}'),
                                 participants=[absender, an], occurred_at=JETZT - timedelta(days=tage), tags=tags)
    einordnen(episodes, episode, abschnitte)
    return episode


def workshop(episodes, *, verlauf=True):
    """Die Akademie: Anfrage, Zusage „Ablauf im August“, Termin am 28.10., Absage im selben Verlauf."""
    verlaufsmail(episodes, 'Anfrage Referentin', [(ANFRAGE, 'request')], 80, kennung='a1')
    ablauf = verlaufsmail(episodes, 'Honorar und Ablauf', [(ABLAUF, 'commitment')], 75, kennung='a2',
                          antwort_auf='a1')
    quelle(episodes, 'Workshop Mangelernährung', 'Termin: Workshop Mangelernährung\nOrt: Bad Homburg',
           [SILKE, LEA], art=EpisodeKind.EVENT, tage=-29)
    absage = verlaufsmail(episodes, 'Absage Workshop', [(ABSAGE, 'change')], 12, kennung='a3',
                          antwort_auf='a2' if verlauf else None)
    return ablauf, absage


def braucht(daten, art=None):
    return [p for p in daten['braucht_dich']['eintraege'] if art is None or p['art'] == art]


# -- Ablage ------------------------------------------------------------------


def test_ablage_nimmt_nur_gueltige_ziele_und_passende_entscheidungen(welt):
    episodes, _, _ = welt
    ablage = Entscheidungen(episodes)
    assert not gueltiges_ziel('irgendwas') and not gueltiges_ziel('a:e-1:1:fp')
    with pytest.raises(ValueError):
        ablage.setzen('irgendwas', 'erledigt')
    with pytest.raises(ValueError):
        ablage.setzen(ziel_termin('e-1', 'fassung'), 'gilt_nicht')   # ein Termin „gilt“ nicht, er findet statt
    with pytest.raises(ValueError):
        ablage.setzen('a:e-1:1:5:fp', 'vielleicht')
    ablage.setzen('a:e-1:1:5:fp', 'erledigt')
    ablage.setzen('a:e-1:1:5:fp', 'gilt_nicht')
    assert ablage.zu(['a:e-1:1:5:fp', 'a:e-2:1:5:fp'])['a:e-1:1:5:fp']['entscheidung'] == 'gilt_nicht'
    assert ablage.zuruecknehmen('a:e-1:1:5:fp') is True and ablage.zuruecknehmen('a:e-1:1:5:fp') is False
    # Gespeichert sind nur Verweise: kein Text, keine Sache, keine Adresse.
    spalten = [z[1] for z in episodes._conn.execute('PRAGMA table_info(akten_entscheidungen)')]
    assert spalten == ['ziel', 'entscheidung', 'entschieden_am']


# -- Erledigt, gilt nicht, gilt weiter ----------------------------------------


def test_erledigt_legt_den_punkt_in_jeder_akte_ab_und_ist_umkehrbar(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT)
    eintrag = next(e for e in daten['offen']['eintraege'] if e['text'] == ABLAUF)
    Entscheidungen(episodes).setzen(eintrag['ziel'], 'erledigt')
    for sache in (AKADEMIE, PERSON):
        daten = akten.akte(sache, jetzt=JETZT)
        assert ABLAUF not in [e['text'] for e in daten['offen']['eintraege']]
        abgelegt = next(e for e in daten['offen']['erledigt']['eintraege'] if e['text'] == ABLAUF)
        assert abgelegt['grund'] == 'nutzer_erledigt' and abgelegt['durch'] is None
    # Der Zwischenspeicher der Akte bleibt: Die Entscheidung gilt nur bei der Anzeige.
    assert akten.akte(AKADEMIE, jetzt=JETZT)['aus_zwischenspeicher'] is True
    Entscheidungen(episodes).zuruecknehmen(eintrag['ziel'])
    assert ABLAUF in [e['text'] for e in akten.akte(AKADEMIE, jetzt=JETZT)['offen']['eintraege']]


def test_gilt_weiter_holt_einen_vermutlich_erledigten_punkt_zurueck(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten.', 'request')], tage=10, absender=SILKE)
    mail(episodes, 'Erhalten', [('Die Druckdaten sind erhalten, danke.', 'status')], tage=4, absender=SILKE)
    daten = neu_rechnen(akten).akte(PERSON, jetzt=JETZT)
    vermutet = daten['offen']['erledigt']['eintraege'][0]
    assert vermutet['grund'] == 'erledigt' and daten['offen']['gesamt'] == 0
    Entscheidungen(episodes).setzen(vermutet['ziel'], 'offen')
    daten = akten.akte(PERSON, jetzt=JETZT)
    zurueck = daten['offen']['eintraege'][0]
    assert zurueck['text'] == 'Bitte schicken Sie uns die Druckdaten.' and zurueck['bestaetigt'] is True
    # Die Meldung, die die Akte für die Erledigung hielt, steht als „danach“ dabei.
    assert zurueck['danach_geaendert']['text'] == 'Die Druckdaten sind erhalten, danke.'


def test_abgelegter_punkt_mahnt_keine_frist_mehr_an_auch_nicht_im_briefing(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Zusage', [('Wir schicken Ihnen das Programm bis 2. Oktober.', 'commitment')], tage=3,
         absender=SILKE)
    mail(episodes, 'Bitte', [('Bitte senden Sie uns die Folien bis 20. September.', 'request')], tage=20,
         absender=SILKE)
    daten = neu_rechnen(akten).akte(PERSON, jetzt=JETZT, alle=True)
    assert len(aus_akte(daten, heute=JETZT.date(), eigene=[ICH])) == 2
    for eintrag in daten['offen']['eintraege']:
        Entscheidungen(episodes).setzen(eintrag['ziel'], 'erledigt')
    daten = akten.akte(PERSON, jetzt=JETZT, alle=True)
    assert daten['fristen']['kommend'] == [] and daten['fristen']['verstrichen'] == []
    assert daten['fristen']['abgelegt'] == 2
    assert aus_akte(daten, heute=JETZT.date(), eigene=[ICH]) == []


def test_entscheidung_macht_die_lage_veraltet_und_zuruecknehmen_wieder_aktuell(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    vorher = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT)
    eintrag = next(e for e in vorher['offen']['eintraege'] if e['text'] == ABLAUF)
    Entscheidungen(episodes).setzen(eintrag['ziel'], 'gilt_nicht')
    assert akten.akte(AKADEMIE, jetzt=JETZT)['eingabestand'] != vorher['eingabestand']
    Entscheidungen(episodes).zuruecknehmen(eintrag['ziel'])
    assert akten.akte(AKADEMIE, jetzt=JETZT)['eingabestand'] == vorher['eingabestand']


# -- Richtung ----------------------------------------------------------------


def test_offene_punkte_sagen_ob_sie_von_dir_stammen(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    verlaufsmail(episodes, 'AW: Absage Workshop', [(NACHHOLEN, 'commitment')], 11, absender=LEA, an=SILKE,
                 kennung='a4', antwort_auf='a3')
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT)
    richtung = {e['text']: e['richtung'] for e in daten['offen']['eintraege']}
    assert richtung[NACHHOLEN] == 'von_mir' and richtung[ABLAUF] == 'an_mich'


# -- Braucht dich ------------------------------------------------------------


def test_abgesagter_termin_im_kalender_braucht_eine_entscheidung(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    punkt = braucht(daten, 'abgesagter_termin')[0]
    assert punkt['satz'].startswith('„Workshop Mangelernährung“ am 28. Oktober ist laut „Absage Workshop“')
    assert punkt['satz'].endswith('steht aber noch in deinem Kalender.') and punkt['laut']['text'] == ABSAGE
    assert [w['entscheidung'] for w in punkt['wahl']] == ['erledigt', 'offen']
    # Abgesagtes steht vorn: Es ist das Dringendste.
    assert daten['braucht_dich']['eintraege'][0]['art'] == 'abgesagter_termin'
    Entscheidungen(episodes).setzen(punkt['ziel'], 'erledigt')
    daten = akten.akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert braucht(daten, 'abgesagter_termin') == []
    termin = daten['termine']['kommend'][0]
    assert termin['entscheidung'] == 'erledigt' and termin['vermutlich_abgesagt']['text'] == ABSAGE
    # „Findet doch statt“ hebt die Vermutung auf, auch im Zeitstrahl.
    Entscheidungen(episodes).setzen(punkt['ziel'], 'offen')
    daten = akten.akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert daten['termine']['kommend'][0]['vermutlich_abgesagt'] is None
    assert [p['abgesagt'] for p in daten['zeitstrahl']['punkte'] if p['art'] == 'termin'] == [False]


def test_zusage_vor_der_absage_im_selben_verlauf_fragt_ob_sie_noch_gilt(welt, akten):
    episodes, _, _ = welt
    ablauf, absage = workshop(episodes)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    # Die Absage nennt den Ablauf nicht: Die Akte entscheidet nicht selbst, sie fragt.
    assert ABLAUF in [e['text'] for e in daten['offen']['eintraege']]
    punkt = braucht(daten, 'gilt_noch')[0]
    assert punkt['zeile']['text'] == ABLAUF and punkt['laut']['episode_id'] == absage.id
    assert punkt['satz'] == '„Workshop Mangelernährung“ ist seit 17. September abgesagt. Gilt diese frühere Zusage noch?'
    assert [w['entscheidung'] for w in punkt['wahl']] == ['gilt_nicht', 'offen']
    Entscheidungen(episodes).setzen(punkt['ziel'], 'gilt_nicht')
    daten = akten.akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert braucht(daten, 'gilt_noch') == []
    assert next(e for e in daten['offen']['erledigt']['eintraege'] if e['text'] == ABLAUF)['grund'] == 'nutzer_gilt_nicht'
    # „Gilt weiter“: bleibt offen, und die Frage kommt nicht wieder.
    Entscheidungen(episodes).setzen(punkt['ziel'], 'offen')
    daten = akten.akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert ABLAUF in [e['text'] for e in daten['offen']['eintraege']] and braucht(daten, 'gilt_noch') == []


def test_ohne_gemeinsamen_verlauf_und_ohne_den_tag_fragt_die_akte_nicht(welt, akten):
    episodes, _, _ = welt
    workshop(episodes, verlauf=False)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert ABLAUF in [e['text'] for e in daten['offen']['eintraege']]
    assert braucht(daten, 'gilt_noch') == []


def test_punkt_nach_der_absage_ist_keine_frage(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    verlaufsmail(episodes, 'AW: Absage Workshop', [(NACHHOLEN, 'commitment')], 11, absender=LEA, an=SILKE,
                 kennung='a4', antwort_auf='a3')
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    assert [p['zeile']['text'] for p in braucht(daten, 'gilt_noch')] == [ABLAUF]


def test_fristen_offener_punkte_kommen_in_braucht_dich(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Zusage', [('Wir schicken Ihnen das Programm bis 30. September.', 'commitment')], tage=3,
         absender=SILKE)
    mail(episodes, 'Eigene', [('Ich schicke Ihnen die Folien bis 5. Oktober.', 'commitment')], tage=2,
         absender=LEA, weitere=[SILKE])
    mail(episodes, 'Bitte', [('Bitte senden Sie uns die Rechnung bis 20. September.', 'request')], tage=20,
         absender=SILKE)
    mail(episodes, 'Später', [('Bitte senden Sie uns die Fotos bis 30. Oktober.', 'request')], tage=1, absender=SILKE)
    daten = neu_rechnen(akten).akte(PERSON, jetzt=JETZT, ansicht=True)
    saetze = [(p['art'], p['satz']) for p in braucht(daten)]
    # Morgen fällig zuerst, dann Verstrichenes, dann Kommendes; was erst in einem Monat fällig ist, wartet.
    assert saetze == [
        ('frist', 'Silke Vogt hat bis 30. September zugesagt, das ist morgen.'),
        ('frist_verstrichen', 'Silke Vogt bat um etwas bis 20. September, seit 9 Tagen vermutlich noch offen.'),
        ('frist', 'Du hast bis 5. Oktober zugesagt, das ist in 6 Tagen.'),
    ]
    verstrichen = braucht(daten, 'frist_verstrichen')[0]
    assert [w['entscheidung'] for w in verstrichen['wahl']] == ['erledigt', 'gilt_nicht']
    Entscheidungen(episodes).setzen(verstrichen['ziel'], 'erledigt')
    assert [p['art'] for p in braucht(akten.akte(PERSON, jetzt=JETZT, ansicht=True))] == ['frist', 'frist']


def test_ohne_ansicht_rechnet_die_akte_weder_braucht_dich_noch_zeitstrahl(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT)
    assert 'braucht_dich' not in daten and 'zeitstrahl' not in daten


# -- Zeitstrahl --------------------------------------------------------------


def test_zeitstrahl_zeigt_quellen_termine_und_fristen(welt, akten):
    episodes, _, _ = welt
    workshop(episodes)
    mail(episodes, 'Bitte', [('Bitte senden Sie uns die Folien bis 20. Oktober.', 'request')], tage=2, absender=SILKE)
    daten = neu_rechnen(akten).akte(AKADEMIE, jetzt=JETZT, ansicht=True)
    strahl = daten['zeitstrahl']
    arten = sorted(p['art'] for p in strahl['punkte'])
    assert arten == ['frist', 'quelle', 'quelle', 'quelle', 'quelle', 'termin']
    termin = next(p for p in strahl['punkte'] if p['art'] == 'termin')
    assert termin['titel'] == 'Workshop Mangelernährung' and termin['abgesagt'] is True
    frist = next(p for p in strahl['punkte'] if p['art'] == 'frist')
    assert frist['datum'] == '2026-10-20' and frist['offen'] is True
    assert strahl['quellen'] == 5 and strahl['heute'] == JETZT.isoformat()
