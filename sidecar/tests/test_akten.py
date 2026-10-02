"""Akten (D2): Verlauf, Offen, Fristen, Stand, Beteiligte, Termine; abgeleitet und mit Fingerabdruck."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from icarus_memory import EpisodeKind
from icarus_memory.akten import Akten, gleicher_gegenstand, stamm_menge
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_bezuege import ICH, JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen

STIFTUNG = 'Förderteam <foerderung@stiftung.example>'
SACHE = 'person:a:foerderung@stiftung.example'


def einordnen(episodes, episode, abschnitte):
    """Ordnet die Abschnitte (Text, Art) ein; der Text muss der Reihe nach im Körper stehen."""
    store = WorkingMemoryStore(episodes)
    offen = store.pending(episode_ids=[episode.id])[0]
    items, position = [], 0
    for text, art in abschnitte:
        start = episode.body.index(text, position)
        items.append({'start': start, 'end': start + len(text), 'kind': art})
        position = start + len(text)
    assert store.commit(offen, items, model='test')


def mail(episodes, titel, abschnitte, tage, absender=STIFTUNG, weitere=(), **kwargs):
    text = ' '.join(t for t, _ in abschnitte)
    e = quelle(episodes, titel, text, [absender, *weitere], tage=tage, **kwargs)
    einordnen(episodes, e, abschnitte)
    return e


@pytest.fixture
def akten(welt):
    episodes, workspace, bezuege = welt
    aufgaben = []
    a = Akten(episodes, bezuege, claims=None, aufgaben=lambda sache, ids: list(aufgaben))
    a.aufgaben_liste = aufgaben
    bezuege.aktualisieren()
    return a


def neu_rechnen(akten):
    akten.bezuege.aktualisieren()
    return akten


def zeilen(liste):
    return [e['text'] for e in liste['eintraege']]


# -- Verlauf -----------------------------------------------------------------


def test_verlauf_ist_chronologisch_mit_zeile_aus_ebene_1_sonst_titel(welt, akten):
    episodes, _, bezuege = welt
    mail(episodes, 'Ausschreibung', [('Die Einreichfrist ist der 15. Oktober 2026.', 'fact')], tage=30)
    mail(episodes, 'Verlängerung', [('Die neue Einreichfrist ist der 12. November 2026.', 'change')], tage=10)
    quelle(episodes, 'Nur Titel', 'Kein Auszug vorhanden.', [STIFTUNG], tage=5)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    verlauf = daten['verlauf']
    assert verlauf['gesamt'] == 3
    assert [e['titel'] for e in verlauf['eintraege']] == ['Nur Titel', 'Verlängerung', 'Ausschreibung']
    assert [e['text'] for e in verlauf['eintraege']] == [None, 'Die neue Einreichfrist ist der 12. November 2026.',
                                                          'Die Einreichfrist ist der 15. Oktober 2026.']
    assert verlauf['eintraege'][1]['art'] == 'Änderung' and verlauf['eintraege'][0]['grundlagen'] == ['anker']
    assert daten['name'] == 'Förderteam' and daten['art_text'] == 'Person'
    assert daten['quellen'] == {'gesamt': 3, 'beruecksichtigt': 3, 'archiviert': 0, 'begrenzt': False,
                                'abschnitte_abgeschnitten': False}


def test_verlauf_nennt_die_gesamtzahl_wo_er_kuerzt(welt, akten):
    episodes, _, _ = welt
    for n in range(14):
        mail(episodes, f'Mail {n}', [(f'Angabe Nummer {n} zum Thema.', 'fact')], tage=n + 1)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    assert len(daten['verlauf']['eintraege']) == 10 and daten['verlauf']['gesamt'] == 14
    assert len(neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['verlauf']['eintraege']) == 14


def test_unbekannte_sache_hat_keine_akte(welt, akten):
    assert akten.akte('person:a:niemand@nirgends.example') is None
    assert akten.akte('unsinn') is None


# -- Offen -------------------------------------------------------------------


def test_bitte_ohne_spaetere_erledigung_ist_vermutlich_offen(welt, akten):
    episodes, _, _ = welt
    e = mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten bis Freitag.', 'request')], tage=3)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    offen = daten['offen']
    assert zeilen(offen) == ['Bitte schicken Sie uns die Druckdaten bis Freitag.']
    assert offen['gesamt'] == 1 and offen['vermutlich'] is True
    assert offen['eintraege'][0]['vermutlich'] is True and offen['eintraege'][0]['episode_id'] == e.id
    assert offen['eintraege'][0]['danach_geaendert'] is None
    assert offen['erledigt']['gesamt'] == 0


def test_spaetere_meldung_mit_erledigtwort_erledigt_die_bitte(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten.', 'request')], tage=10)
    spaeter = mail(episodes, 'Erhalten', [('Die Druckdaten sind erhalten, danke.', 'status')], tage=4)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    assert daten['offen']['gesamt'] == 0
    erledigt = daten['offen']['erledigt']['eintraege']
    assert erledigt[0]['text'] == 'Bitte schicken Sie uns die Druckdaten.'
    assert erledigt[0]['grund'] == 'erledigt' and erledigt[0]['durch']['episode_id'] == spaeter.id


def test_absage_beendet_eine_zusage_auch_ueber_das_datum(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Zusage', [('Ich sage zu, der 28. Oktober passt bei mir.', 'commitment')], tage=80,
         absender=f'Lea <{ICH}>', weitere=['Silke <s.vogt@akademie.example>'])
    mail(episodes, 'Absage', [('Leider müssen wir den Workshop am 28. Oktober absagen.', 'change')], tage=10,
         absender='Silke <s.vogt@akademie.example>')
    # Die Zusage steht in der Sache „Akademie“ (Organisation), nicht bei der Person: Der Bezug läuft über die Domäne.
    daten = neu_rechnen(akten).akte('organisation:akademie', jetzt=JETZT)
    assert daten['offen']['gesamt'] == 0
    assert daten['offen']['erledigt']['eintraege'][0]['grund'] == 'absage'


def test_aenderung_ohne_erledigtwort_laesst_den_punkt_offen_mit_hinweis(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten für das Plakat.', 'request')], tage=10)
    mail(episodes, 'Änderung', [('Die Druckdaten für das Plakat ändern sich, Format jetzt A2.', 'change')], tage=4)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    eintrag = daten['offen']['eintraege'][0]
    assert eintrag['text'].startswith('Bitte schicken') and daten['offen']['gesamt'] == 1
    assert eintrag['danach_geaendert']['text'].startswith('Die Druckdaten für das Plakat ändern sich')


def test_fremdes_thema_erledigt_nichts(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten.', 'request')], tage=10)
    mail(episodes, 'Anderes', [('Die Rechnung ist bezahlt.', 'status')], tage=4)
    assert neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['offen']['gesamt'] == 1


def test_erledigte_aufgabe_zur_quelle_erledigt_die_bitte(welt, akten):
    episodes, _, _ = welt
    e = mail(episodes, 'Bitte', [('Bitte schicken Sie uns die Druckdaten.', 'request')], tage=10)
    aufgabe = SimpleNamespace(id='t1', title='Druckdaten schicken', status=SimpleNamespace(value='open'), due=None,
                              wartet_auf=None, created_at=JETZT, provenance=SimpleNamespace(source_ref=f'episode:{e.id}'))
    akten.aufgaben_liste.append(aufgabe)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)
    assert daten['offen']['eintraege'][0]['aufgabe'] == {'id': 't1', 'title': 'Druckdaten schicken'}
    aufgabe.status = SimpleNamespace(value='done')
    daten = akten.akte(SACHE, jetzt=JETZT)
    assert daten['offen']['gesamt'] == 0
    assert daten['offen']['erledigt']['eintraege'][0]['grund'] == 'aufgabe_erledigt'


# -- Fristen -----------------------------------------------------------------


def test_fristen_mit_bezug_auf_die_quelle_kommend_und_verstrichen(welt, akten):
    episodes, _, _ = welt
    # Quelle vom 26.9.2026 (Samstag): „bis Freitag“ ist der 2.10.; JETZT ist der 29.9.
    mail(episodes, 'Bitte', [('Bitte antworten Sie bis Freitag.', 'request')], tage=3)
    # Quelle vom 19.9.: „bis Freitag“ war der 25.9., also verstrichen.
    mail(episodes, 'Alt', [('Rückmeldung bitte bis Freitag.', 'request')], tage=10)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['fristen']
    assert [(f['datum'], f['ausdruck']) for f in daten['kommend']] == [('2026-10-02', 'bis Freitag')]
    assert [(f['datum'], f['ausdruck']) for f in daten['verstrichen']] == [('2026-09-25', 'bis Freitag')]
    assert daten['gesamt'] == {'kommend': 1, 'verstrichen': 1, 'ersetzt': 0}
    assert daten['kommend'][0]['text'] == 'Bitte antworten Sie bis Freitag.' and daten['kommend'][0]['episode_id']


def test_uneindeutige_zeitangabe_bleibt_text_ohne_datum(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Vage', [('Bitte melden Sie sich nächste Woche, spätestens Mitte Oktober.', 'request')], tage=2)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['fristen']
    assert daten['kommend'] == [] and daten['verstrichen'] == []
    assert sorted(e['ausdruck'] for e in daten['ohne_datum']['eintraege']) == ['Mitte Oktober', 'nächste Woche']


def test_verschobene_frist_ersetzt_die_alte_und_nennt_die_neue(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Ausschreibung', [('Bitte reichen Sie den Antrag ein, Einreichfrist ist der 15. Oktober 2026.', 'request')],
         tage=60)
    mail(episodes, 'Verlängerung', [('Die neue Einreichfrist ist der 12. November 2026, 12 Uhr.', 'change')], tage=26)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['fristen']
    assert [f['datum'] for f in daten['kommend']] == ['2026-11-12']
    assert daten['ersetzt'][0]['datum'] == '2026-10-15'
    assert daten['ersetzt'][0]['ersetzt_durch']['datum'] == '2026-11-12'
    assert daten['ersetzt'][0]['ersetzt_durch']['ausdruck'] == '12. November 2026'
    assert daten['gesamt'] == {'kommend': 1, 'verstrichen': 0, 'ersetzt': 1}


def test_verschiedene_gegenstaende_ersetzen_sich_nicht(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'A', [('Der Kostenplan ist bis zum 25.10.2026 fertig zu stellen.', 'request')], tage=50)
    mail(episodes, 'B', [('Die Absichtserklärung kommt bis zum 29.10.2026.', 'commitment')], tage=20)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['fristen']
    assert [f['datum'] for f in daten['kommend']] == ['2026-10-25', '2026-10-29'] and daten['ersetzt'] == []


def test_datum_in_einer_bloszen_angabe_ist_keine_frist(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Info', [('Die Firma wurde am 3.4.1998 gegründet.', 'fact')], tage=2)
    assert neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}


# -- Stand -------------------------------------------------------------------


def test_stand_zeigt_den_neuen_wert_und_nennt_den_alten_nur_als_vorher(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Alt', [('Die Rechnungsanschrift ist Klinikstraße 5 in Geisenheim.', 'status')], tage=200)
    mail(episodes, 'Neu', [('Die Rechnungsanschrift ist ab jetzt Lindenallee 22 in Kassel.', 'change')], tage=20)
    mail(episodes, 'Mittel', [('Die Rechnungsanschrift bleibt Klinikstraße 5 in Geisenheim bis Mai.', 'status')], tage=100)
    stand = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['stand_der_dinge']
    assert stand['aktuell']['text'] == 'Die Rechnungsanschrift ist ab jetzt Lindenallee 22 in Kassel.'
    assert [z['text'] for z in stand['vorher']] == [
        'Die Rechnungsanschrift bleibt Klinikstraße 5 in Geisenheim bis Mai.',
        'Die Rechnungsanschrift ist Klinikstraße 5 in Geisenheim.'] and stand['vorher_gesamt'] == 2
    assert stand['weitere'] == [] and stand['weitere_gesamt'] == 0


def test_stand_trennt_gegenstaende_statt_den_juengsten_alles_verdecken_zu_lassen(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Adresse', [('Meine neue Mailadresse lautet j.krueger@vitalzentrum.example.', 'change')], tage=100)
    mail(episodes, 'Anschrift', [('Die Rechnungsanschrift ist jetzt Lindenallee 22 in Kassel.', 'change')], tage=20)
    stand = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['stand_der_dinge']
    assert 'Lindenallee' in stand['aktuell']['text']
    assert stand['vorher'] == [] and stand['weitere_gesamt'] == 1
    assert 'Mailadresse' in stand['weitere'][0]['aktuell']['text']


def test_ohne_aenderung_gibt_es_keinen_stand(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Info', [('Ein Dokument ohne Änderung.', 'fact')], tage=2)
    stand = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['stand_der_dinge']
    assert stand['aktuell'] is None and stand['weitere_gesamt'] == 0


# -- Beteiligte und Termine --------------------------------------------------


def test_beteiligte_zaehlen_gemeinsame_quellen(welt, akten):
    episodes, _, _ = welt
    for n, empfaenger in enumerate(['Ben <ben@druck.example>', 'Ben <ben@druck.example>', 'Cem <cem@post.example>']):
        text = f'Nachricht {n} an mehrere.'
        e = quelle(episodes, f'M{n}', text, [STIFTUNG, empfaenger], tage=n + 1)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['beteiligte']
    anzahl = {b['sache']: (b['anzahl'], b['name']) for b in daten['eintraege']}
    assert anzahl['person:a:ben@druck.example'] == (2, 'Ben') and anzahl['person:a:cem@post.example'] == (1, 'Cem')
    assert SACHE not in anzahl and daten['gesamt'] == len(daten['eintraege'])


def test_termine_vergangene_und_kommende(welt, akten):
    episodes, _, _ = welt
    for tage, titel in ((30, 'Werkstatt alt'), (-14, 'Werkstatt neu')):
        quelle(episodes, titel, f'Termin: {titel}\nOrt: Online', [STIFTUNG], art=EpisodeKind.EVENT, tage=tage)
    daten = neu_rechnen(akten).akte(SACHE, jetzt=JETZT)['termine']
    assert [t['titel'] for t in daten['kommend']] == ['Werkstatt neu']
    assert [t['titel'] for t in daten['vergangen']] == ['Werkstatt alt']
    assert daten['gesamt'] == {'kommend': 1, 'vergangen': 1} and daten['kommend'][0]['ort'] == 'Online'


# -- Zwischenspeicher --------------------------------------------------------


def test_akte_wird_nur_neu_berechnet_wenn_sich_eine_verknuepfte_quelle_aendert(welt, akten):
    episodes, _, bezuege = welt
    mail(episodes, 'Erste', [('Bitte schicken Sie die Unterlagen.', 'request')], tage=5)
    fremd = quelle(episodes, 'Fremd', 'Anderes von anderer Seite.', ['Ben <ben@druck.example>'], tage=1)
    neu_rechnen(akten)
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is False
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is True
    assert akten.letzte_berechnung['aus_zwischenspeicher'] is True
    # Eine Quelle einer anderen Sache ändert diese Akte nicht.
    episodes.ignore(fremd.id)
    neu_rechnen(akten)
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is True
    # Neue Quelle dieser Sache: neu berechnet.
    mail(episodes, 'Zweite', [('Danke, alles angekommen.', 'status')], tage=1)
    neu_rechnen(akten)
    daten = akten.akte(SACHE, jetzt=JETZT)
    assert daten['aus_zwischenspeicher'] is False and daten['verlauf']['gesamt'] == 2
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is True


def test_entzug_und_neue_einordnung_und_zuordnung_des_nutzers_verwerfen_den_zwischenspeicher(welt, akten):
    episodes, _, bezuege = welt
    e1 = mail(episodes, 'Erste', [('Bitte schicken Sie die Unterlagen.', 'request')], tage=5)
    e2 = mail(episodes, 'Zweite', [('Die Lage ist unverändert.', 'status')], tage=3)
    neu_rechnen(akten)
    assert akten.akte(SACHE, jetzt=JETZT)['verlauf']['gesamt'] == 2
    # Entzug einer Quelle.
    episodes.ignore(e2.id)
    daten = akten.akte(SACHE, jetzt=JETZT)
    assert daten['aus_zwischenspeicher'] is False and daten['verlauf']['gesamt'] == 1
    # Neue Einordnung derselben Quelle (andere Art) rechnet neu.
    store = WorkingMemoryStore(episodes)
    with episodes.transaction():
        episodes._conn.execute('DELETE FROM working_memory_sources WHERE episode_id=?', (e1.id,))
    einordnen(episodes, episodes.get(e1.id), [('Bitte schicken Sie die Unterlagen.', 'commitment')])
    daten = akten.akte(SACHE, jetzt=JETZT)
    assert daten['aus_zwischenspeicher'] is False and daten['offen']['eintraege'][0]['art'] == 'Zusage'
    # Ablehnung durch den Nutzer nimmt die Quelle aus der Akte.
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is True
    bezuege.nutzer_setzen(e1.id, SACHE, 'nicht')
    assert akten.akte(SACHE, jetzt=JETZT) is None


def test_zwischenspeicher_haelt_keine_zitate(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Geheim', [('Bitte schicken Sie den vertraulichen Vertrag bis 12.10.2026.', 'request')], tage=5)
    neu_rechnen(akten)
    akten.akte(SACHE, jetzt=JETZT)
    gespeichert = episodes._conn.execute('SELECT daten FROM akten_cache').fetchone()[0]
    assert 'vertraulichen' not in gespeichert and 'Vertrag' not in gespeichert
    assert 'Geheim' not in episodes._conn.execute('SELECT group_concat(sache) FROM akten_cache').fetchone()[0]


def test_wortvergleich_ist_grob_aber_vorsichtig():
    a = stamm_menge('Bitte die Druckdaten für das Plakat schicken')
    b = stamm_menge('Die Druckdaten für das Plakat ändern sich')
    assert len(a & b) >= 2
    assert not (stamm_menge('Rechnung ist bezahlt') & stamm_menge('Druckdaten Plakat'))
    assert stamm_menge('am 12. Oktober, Freitag') == frozenset()


def test_aenderung_einer_quelle_verwirft_den_zwischenspeicher(welt, akten):
    episodes, _, _ = welt
    e = mail(episodes, 'Erste', [('Bitte schicken Sie die Unterlagen.', 'request')], tage=5)
    neu_rechnen(akten)
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is False
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is True
    episodes.add_contacts(e.id, [{'name': 'Förderteam', 'adresse': 'foerderung@stiftung.example', 'rolle': 'von', 'ich': False},
                                 {'name': 'Ben', 'adresse': 'ben@druck.example', 'rolle': 'an', 'ich': False}],
                          [STIFTUNG, 'Ben <ben@druck.example>'])
    neu_rechnen(akten)
    assert akten.akte(SACHE, jetzt=JETZT)['aus_zwischenspeicher'] is False
