"""Zweites Tor im Antwortweg: Das Prüfmodell verwirft, was die erste Prüfung nicht sieht; fail closed; gespeichert.

Der Fall, um den es geht: Eine Mail sagt „Die Geschäftsführung hat dem Vorschlag zugestimmt, der Betriebsrat hat
sich dagegen entschieden.“ Der Satz „Der Betriebsrat hat dem Vorschlag zugestimmt.“ trägt keinen Anker, den die
Prüfung ohne Modell prüft (alle Namen und das Statuswort stehen im Beleg, kein Verneinungswort). Er besteht die
erste Prüfung. Das zweite Tor muss ihn verwerfen.
"""
import copy
import json
import time

import pytest

from icarus_memory import satzantwort, satzpruefung_modell as spm, working_memory_answers as wma, zeitmessung
from tests.test_akten import mail
from tests.test_bezuege import welt  # noqa: F401 - Fixture
from tests.test_satzantwort import Skript, raum  # noqa: F401 - Fixture und Skriptmodell
from tests.test_satzpruefung_modell import Pruefer

FRAGE = 'Wer hat dem Vorschlag zugestimmt?'
RICHTIG = 'Die Geschäftsführung hat dem Vorschlag zugestimmt.'
FALSCH = 'Der Betriebsrat hat dem Vorschlag zugestimmt.'


def rueckmeldung(episodes, tage=10):
    return mail(episodes, 'Rückmeldung zum Vorschlag', [
        ('Die Geschäftsführung hat dem Vorschlag zugestimmt, der Betriebsrat hat sich dagegen entschieden.', 'fact')],
        tage=tage)


def beide(nutzer):
    nummer = nutzer['belege'][0]['nr']
    return {'status': 'antwort', 'saetze': [{'text': RICHTIG, 'belege': [nummer]}, {'text': FALSCH, 'belege': [nummer]}]}


def ideal():
    """Ein Prüfmodell, das den falschen Satz erkennt und den richtigen durchlässt."""
    return Pruefer({'Betriebsrat': '{"urteil":"nein"}', 'Geschäftsführung': '{"urteil":"ja"}'})


def fragen(raum, pruefung, saetze=beide, zeiten=None, frage=FRAGE):
    episodes, claims, akten = raum
    akten.bezuege.aktualisieren()
    return wma.prepare(frage, episodes, claims, Skript(saetze), saetze=True, pruefung=pruefung, zeiten=zeiten)


def texte(gespeichert):
    return [s['text'] for s in gespeichert['satzantwort'].get('saetze', [])]


def test_ohne_pruefmodell_kommt_der_falsche_satz_durch_die_erste_pruefung(raum):
    """Die Lücke, die das zweite Tor schließt: ohne Modell bestehen beide Sätze. Die Antwort sagt, dass es fehlt."""
    episodes, claims, _ = raum
    rueckmeldung(episodes)
    gespeichert = fragen(raum, spm.OHNE)
    assert texte(gespeichert) == [RICHTIG, FALSCH]
    assert gespeichert['satzantwort']['pruefung'] == {'zustand': 'kein_modell', 'modell': '', 'verworfen': 0}
    text, _, _ = wma.render(gespeichert, episodes, claims)
    assert 'Ohne zweite Prüfung durch ein Prüfmodell (keines eingerichtet).' in text
    struktur = wma.satz_struktur(gespeichert, episodes, claims)
    assert {s['verlaesslichkeit'] for s in struktur['saetze']} == {'einfach'}
    assert struktur['pruefung'] == {'zustand': 'kein_modell', 'modell': ''}


def test_das_pruefmodell_verwirft_den_falschen_satz_und_die_antwort_sagt_es(raum):
    episodes, claims, _ = raum
    rueckmeldung(episodes)
    pruefer = ideal()
    gespeichert = fragen(raum, spm.tor('an', pruefer))
    daten = gespeichert['satzantwort']
    assert texte(gespeichert) == [RICHTIG]
    assert daten['verworfen'] == 1 and daten['pruefung'] == {'zustand': 'an', 'modell': 'pruef-1', 'verworfen': 1}
    assert any('Prüfmodell: nicht gestützt' in g for g in daten['gruende'])
    assert [s['pruefmodell'] for s in daten['saetze']] == ['ja']
    text, _, status = wma.render(gespeichert, episodes, claims)
    assert status == 'working_reports' and FALSCH not in text
    assert '1 Satz verworfen (Prüfmodell).' in text and 'weil die Belege ihn nicht getragen haben' not in text
    struktur = wma.satz_struktur(gespeichert, episodes, claims)
    assert (struktur['verworfen'], struktur['verworfen_pruefmodell']) == (0, 1)
    assert struktur['saetze'][0]['verlaesslichkeit'] == 'gut' and struktur['saetze'][0]['hinweis'] == ''
    assert len(pruefer.anfragen) == 2, 'Jeder Satz, der die erste Prüfung bestand, wird genau einmal gefragt'


def test_das_pruefmodell_sieht_nur_den_satz_und_die_textstellen_seiner_belege(raum):
    episodes, _, _ = raum
    rueckmeldung(episodes)
    mail(episodes, 'Andere Sache', [('Die Kantine öffnet am Montag wieder.', 'fact')], tage=3)
    pruefer = ideal()
    fragen(raum, spm.tor('an', pruefer), saetze=lambda n: {'status': 'antwort', 'saetze': [
        {'text': RICHTIG, 'belege': [next(b['nr'] for b in n['belege'] if 'Rückmeldung' in b['quelle'])]}]})
    [anfrage] = pruefer.anfragen
    inhalt = json.loads(anfrage[-1]['content'])
    assert inhalt['satz'] == RICHTIG and set(inhalt) == {'satz', 'belege'}
    assert 'Betriebsrat hat sich dagegen entschieden' in inhalt['belege']
    assert 'Kantine' not in json.dumps(anfrage, ensure_ascii=False), 'Kein anderer Beleg, keine andere Quelle'
    assert FRAGE not in json.dumps(anfrage, ensure_ascii=False), 'Die Frage des Nutzers geht nicht an das Prüfmodell'


@pytest.mark.parametrize('ausgabe', ['{"urteil":"unklar"}', RuntimeError('Ollama weg'), 'vielleicht'])
def test_unklar_und_fehler_lassen_keinen_satz_durch(raum, ausgabe):
    episodes, claims, _ = raum
    rueckmeldung(episodes)
    gespeichert = fragen(raum, spm.tor('an', Pruefer(standard=ausgabe)))
    daten = gespeichert['satzantwort']
    assert daten['status'] == 'zitate' and daten['pruefung']['verworfen'] == 2
    text, _, _ = wma.render(gespeichert, episodes, claims)
    assert text.startswith('Quelle berichtet') and FALSCH not in text


def test_das_zeitbudget_wird_eingehalten_und_ueberschreitung_ist_unklar(raum, monkeypatch):
    episodes, _, _ = raum
    rueckmeldung(episodes)
    monkeypatch.setattr(spm, 'SATZ_BUDGET_S', 0.05)
    monkeypatch.setattr(spm, 'GESAMT_BUDGET_S', 0.08)
    zeiten = zeitmessung.Zeiten()
    start = time.monotonic()
    gespeichert = fragen(raum, spm.tor('an', Pruefer(warte=0.5)), zeiten=zeiten)
    assert time.monotonic() - start < 0.45, 'Die Antwort wartet nicht auf ein langsames Prüfmodell'
    daten = gespeichert['satzantwort']
    assert daten['status'] == 'zitate' and daten['pruefung']['verworfen'] == 2
    assert any('Zeitbudget' in g for g in daten['gruende'])
    assert 0 < zeiten.als_dict()['pruefung_modell'] < 0.3


def test_vom_nutzer_ausgeschaltet_fragt_niemand_und_die_antwort_sagt_es(raum):
    episodes, claims, _ = raum
    rueckmeldung(episodes)
    pruefer = ideal()
    gespeichert = fragen(raum, spm.tor('aus', pruefer))
    assert texte(gespeichert) == [RICHTIG, FALSCH] and pruefer.anfragen == []
    text, _, _ = wma.render(gespeichert, episodes, claims)
    assert 'Ohne zweite Prüfung durch ein Prüfmodell (ausgeschaltet).' in text


def test_gespeichert_und_beim_anzeigen_neu_geprueft(raum):
    episodes, claims, _ = raum
    rueckmeldung(episodes)
    gespeichert = fragen(raum, spm.tor('an', ideal()))
    daten = gespeichert['satzantwort']
    assert daten['saetze'][0]['verlaesslichkeit'] == 'gut'
    dargestellt = satzantwort.wiederherstellen(daten, episodes, claims)
    assert dargestellt is not None and dargestellt.saetze[0].pruefmodell == 'ja'
    assert dargestellt.verworfen_pruefmodell == 1
    # Ein Satz ohne das Ja des Prüfmodells, obwohl das Tor lief: nicht zeigen.
    ohne_ja = copy.deepcopy(daten)
    ohne_ja['saetze'][0]['pruefmodell'] = ''
    assert satzantwort.wiederherstellen(ohne_ja, episodes, claims) is None
    # Ein kaputter Stand des Tors ebenso.
    assert satzantwort.wiederherstellen({**daten, 'pruefung': {'zustand': 'vielleicht'}}, episodes, claims) is None
    # Eine gespeicherte Stufe wird nicht geglaubt, sondern neu eingestuft.
    geschoent = copy.deepcopy(daten)
    geschoent['saetze'][0]['verlaesslichkeit'] = 'gut'
    geschoent['stichtag'] = '2027-09-29T08:00:00+00:00'  # ein Jahr später ist der Beleg alt
    spaeter = satzantwort.wiederherstellen(geschoent, episodes, claims)
    assert spaeter is not None and spaeter.saetze[0].verlaesslichkeit == 'einfach'
    assert spaeter.saetze[0].hinweis == 'nur eine Quelle, von 2026'
    # Antworten von vor dem zweiten Tor (ohne `pruefung`) bleiben lesbar.
    alt = {k: v for k, v in daten.items() if k != 'pruefung'}
    for satz in alt['saetze']:
        satz.pop('pruefmodell'), satz.pop('verlaesslichkeit')
    frueher = satzantwort.wiederherstellen(alt, episodes, claims)
    assert frueher is not None and frueher.pruefung['zustand'] == 'kein_modell'


def test_ein_alter_einzelner_beleg_bekommt_den_nebensatz(raum):
    episodes, claims, _ = raum
    rueckmeldung(episodes, tage=700)
    gespeichert = fragen(raum, spm.tor('an', ideal()))
    text, _, _ = wma.render(gespeichert, episodes, claims)
    assert f'{RICHTIG} [1] (nur eine Quelle, von 2024)' in text
    struktur = wma.satz_struktur(gespeichert, episodes, claims)
    assert (struktur['saetze'][0]['verlaesslichkeit'], struktur['saetze'][0]['hinweis']) == (
        'einfach', 'nur eine Quelle, von 2024')


def test_nur_ueber_die_kopfzeile_gestuetzt_ist_duenn(raum):
    episodes, claims, _ = raum
    mail(episodes, 'Programm Horizont', [('Die Laufzeit beträgt bis zu 18 Monate.', 'fact')], tage=10)
    satz = 'Das Programm Horizont läuft bis zu 18 Monate.'
    gespeichert = fragen(raum, spm.tor('an', Pruefer()), saetze=lambda n: {'status': 'antwort', 'saetze': [
        {'text': satz, 'belege': [n['belege'][0]['nr']]}]}, frage='Wie lange ist die Laufzeit beim Programm Horizont?')
    assert gespeichert['satzantwort']['status'] == 'saetze', gespeichert['satzantwort']
    struktur = wma.satz_struktur(gespeichert, episodes, claims)
    assert struktur['saetze'][0]['text'] == satz
    assert (struktur['saetze'][0]['verlaesslichkeit'], struktur['saetze'][0]['hinweis']) == (
        'duenn', 'nur über Betreff oder Absender belegt')


def test_auch_der_vom_programm_ergaenzte_wandel_geht_durch_das_tor(raum):
    from tests.test_satzantwort import wandel
    episodes, claims, akten = raum
    wandel(episodes)

    def nur_neu(nutzer):
        neu = next(b['nr'] for b in nutzer['belege'] if 'Verlängerung' in b['quelle'])
        alt = next(b['nr'] for b in nutzer['belege'] if 'Ausschreibung' in b['quelle'])
        return {'status': 'antwort', 'saetze': [
            {'text': 'Die Laufzeit beträgt bis zu 18 Monate.', 'belege': [alt]},
            {'text': 'Die neue Einreichfrist ist der 12. November 2026.', 'belege': [neu]}]}

    akten.bezuege.aktualisieren()
    pruefer = Pruefer({'Die Frist gilt jetzt': '{"urteil":"nein"}'})
    gespeichert = wma.prepare('Bis wann ist die Einreichfrist?', episodes, claims, Skript(nur_neu), saetze=True,
                              pruefung=spm.tor('an', pruefer))
    gefragt = [spm.satz_der_anfrage(a) for a in pruefer.anfragen]
    assert any(s and s.startswith('Die Frist gilt jetzt') for s in gefragt), gefragt
    assert gespeichert['satzantwort']['status'] == 'zitate', 'Ein Wandel, den das Tor nicht bestätigt, gilt nicht'
