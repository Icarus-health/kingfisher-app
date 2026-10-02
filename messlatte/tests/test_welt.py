"""Der Prüfer lehnt kaputte Welten ab und sagt, wo und was."""
from __future__ import annotations

import json

import pytest

from messlatte.daten import Mail, Termin
from messlatte.welt import WeltFehler, lade_welt, lade_welten, pruefe_fragen_lokal

from conftest import finde


def fehler_von(pfad) -> str:
    with pytest.raises(WeltFehler) as info:
        lade_welt(pfad)
    return str(info.value)


def test_mini_welt_ist_gueltig(mini_welt):
    welt = lade_welt(mini_welt)
    assert len(welt.szenarien) == 2
    assert len(welt.quellen) == 15
    assert len(welt.fragen) == 8
    assert {f.erwartet.verhalten for f in welt.fragen} == {'antworten', 'rueckfrage', 'nicht_bekannt'}
    assert any(isinstance(q, Termin) for q in welt.quellen)
    sent = [q for q in welt.quellen if isinstance(q, Mail) and q.ordner == 'Sent']
    assert sent and all(m.von.adresse == 'lea@hartmann-beratung.example' for m in sent)
    assert welt.hinweise == ()


def test_doppelte_quellen_id(welt_kopie):
    welt_kopie('mainz', lambda d: d['quellen'].append(dict(d['quellen'][0])))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'szenarien/mainz.json' in meldung and 'mainz-001' in meldung and 'Doppelte Quellen-ID' in meldung


def test_quellen_id_ohne_szenario_praefix(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001').update(id='x-001'))
    assert 'Szenario-Präfix' in fehler_von(welt_kopie.pfad)


def test_beleg_gibt_es_nicht(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['erwartet'].update(belege=['mainz-999']))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'mainz-01' in meldung and 'mainz-999' in meldung and 'gibt es nicht' in meldung


def test_verbotener_beleg_gibt_es_nicht(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['verboten'].update(belege=['nirgends-1']))
    assert 'verboten.belege' in fehler_von(welt_kopie.pfad)


def test_beleg_zugleich_erwartet_und_verboten(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['verboten'].update(belege=['mainz-003']))
    assert 'zugleich' in fehler_von(welt_kopie.pfad)


def test_zeit_nach_dem_stichtag(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001').update(zeit='2026-10-01T10:00:00+02:00'))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'mainz-001' in meldung and 'nicht vor dem Stichtag' in meldung


def test_termin_darf_nach_dem_stichtag_beginnen(mini_welt):
    # mainz-006 beginnt am 3. Oktober, nach dem Stichtag; nur die Anlage muss davor liegen.
    assert lade_welt(mini_welt)


def test_zeit_ohne_zeitzone(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001').update(zeit='2026-08-20T10:12:00'))
    assert 'Zeitzone' in fehler_von(welt_kopie.pfad)


def test_domain_ohne_example(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001')['von'].update(adresse='s.becker@gmail.com'))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'mainz-001' in meldung and '.example' in meldung


def test_adresse_im_text_ohne_example(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-005').update(text='Schreib an info@firma.de'))
    assert 'info@firma.de' in fehler_von(welt_kopie.pfad)


def test_link_im_text_ohne_example(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-005').update(text='Siehe https://www.echt.de/x'))
    assert 'echt.de' in fehler_von(welt_kopie.pfad)


def test_kategorie_unbekannt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01').update(kategorie='zauberei'))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'kategorie' in meldung and 'zauberei' in meldung


def test_verhalten_unbekannt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['erwartet'].update(verhalten='raten'))
    assert 'verhalten' in fehler_von(welt_kopie.pfad)


def test_schwere_unbekannt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01').update(schwere='hoch'))
    assert 'schwere' in fehler_von(welt_kopie.pfad)


def test_sent_mail_nicht_vom_nutzer(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-002')['von'].update(adresse='x@beispiel.example'))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'mainz-002' in meldung and 'Sent' in meldung and 'vom Nutzer' in meldung


def test_eigene_mail_im_posteingang(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-002').update(ordner='INBOX'))
    assert 'Ordner Sent' in fehler_von(welt_kopie.pfad)


def test_antwort_auf_unbekannte_mail(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-002').update(antwort_auf='mainz-042'))
    assert 'antwort_auf' in fehler_von(welt_kopie.pfad)


def test_antwort_vor_der_urspruenglichen_mail(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-002').update(zeit='2026-08-19T08:40:00+02:00'))
    assert 'später gesendet' in fehler_von(welt_kopie.pfad)


def test_unbekanntes_feld_wird_benannt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001').update(prioritaet='hoch'))
    meldung = fehler_von(welt_kopie.pfad)
    assert 'prioritaet' in meldung and 'mainz-001' in meldung


def test_pflichtfeld_fehlt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['quellen'], 'mainz-001').pop('betreff'))
    assert 'Pflichtfeld „betreff“ fehlt' in fehler_von(welt_kopie.pfad)


def test_rueckfrage_braucht_zwei_bedeutungen(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-02')['erwartet'].update(bedeutungen=[['Klinikum']]))
    assert 'mindestens zwei Bedeutungsgruppen' in fehler_von(welt_kopie.pfad)


def test_nicht_bekannt_erwartet_keine_belege(welt_kopie):
    welt_kopie('rechnung', lambda d: finde(d['fragen'], 'rechnung-03')['erwartet'].update(belege=['rechnung-001']))
    assert 'nicht_bekannt' in fehler_von(welt_kopie.pfad)


def test_antworten_ohne_aussage_und_beleg(welt_kopie):
    def leeren(d):
        finde(d['fragen'], 'mainz-01')['erwartet'].update(aussagen=[], belege=[])
    welt_kopie('mainz', leeren)
    assert 'nicht messbar' in fehler_von(welt_kopie.pfad)


def test_alternativgruppe_leer(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['erwartet'].update(aussagen=[[]]))
    assert 'Gruppe' in fehler_von(welt_kopie.pfad)


def test_kaputtes_json_nennt_zeile(welt_kopie):
    datei = welt_kopie.pfad / 'szenarien' / 'mainz.json'
    datei.write_text(datei.read_text(encoding='utf-8').replace('"art": "notiz",', '"art": "notiz"'), encoding='utf-8')
    meldung = fehler_von(welt_kopie.pfad)
    assert 'mainz.json' in meldung and 'Zeile' in meldung


def test_szenario_id_passt_nicht_zum_dateinamen(welt_kopie):
    welt_kopie('mainz', lambda d: d.update(id='koeln'))
    assert 'Dateinamen' in fehler_von(welt_kopie.pfad)


def test_stichtag_ohne_zeitzone(welt_kopie):
    welt_kopie('welt', lambda d: d.update(stichtag='2026-09-29T07:30:00'))
    assert 'stichtag' in fehler_von(welt_kopie.pfad)


def test_unbekannte_zeitzone(welt_kopie):
    welt_kopie('welt', lambda d: d.update(zeitzone='Mars/Olympus'))
    assert 'Zeitzone' in fehler_von(welt_kopie.pfad)


def test_mehrere_fehler_auf_einmal(welt_kopie):
    def kaputt(d):
        finde(d['quellen'], 'mainz-001').update(zeit='2027-01-01T00:00:00+01:00')
        finde(d['fragen'], 'mainz-01').update(kategorie='x')
    welt_kopie('mainz', kaputt)
    with pytest.raises(WeltFehler) as info:
        lade_welt(welt_kopie.pfad)
    assert len(info.value.meldungen) >= 2


def test_hinweis_wenn_pflichtaussage_in_keinem_beleg_steht(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-01')['erwartet'].update(aussagen=[['31. Dezember']]))
    welt = lade_welt(welt_kopie.pfad)
    assert any('mainz-01' in h and '31. Dezember' in h for h in welt.hinweise)


def test_mehrere_welten_teilen_einen_stichtag_und_eindeutige_ids(mini_welt, welt_kopie):
    with pytest.raises(WeltFehler) as info:
        lade_welten([str(mini_welt), f'holdout={welt_kopie.pfad}'])
    text = str(info.value)
    assert 'gibt es schon' in text and 'holdout' in text


def test_holdout_mit_anderem_stichtag_wird_abgelehnt(mini_welt, tmp_path):
    import shutil
    ziel = tmp_path / 'holdout'
    shutil.copytree(mini_welt, ziel)
    (ziel / 'szenarien' / 'mainz.json').unlink()
    (ziel / 'szenarien' / 'rechnung.json').rename(ziel / 'szenarien' / 'neu.json')
    daten = json.loads((ziel / 'szenarien' / 'neu.json').read_text(encoding='utf-8'))
    daten['id'] = 'neu'
    for eintrag in daten['quellen'] + daten['fragen']:
        eintrag['id'] = eintrag['id'].replace('rechnung-', 'neu-')
    for frage in daten['fragen']:
        frage['erwartet']['belege'] = [b.replace('rechnung-', 'neu-') for b in frage['erwartet'].get('belege', [])]
        frage.get('verboten', {}).update(belege=[b.replace('rechnung-', 'neu-') for b in frage.get('verboten', {}).get('belege', [])])
    for quelle in daten['quellen']:
        if quelle.get('antwort_auf'):
            quelle['antwort_auf'] = quelle['antwort_auf'].replace('rechnung-', 'neu-')
    (ziel / 'szenarien' / 'neu.json').write_text(json.dumps(daten, ensure_ascii=False), encoding='utf-8')
    welt = json.loads((ziel / 'welt.json').read_text(encoding='utf-8'))
    welt['stichtag'] = '2026-10-15T07:30:00+02:00'
    (ziel / 'welt.json').write_text(json.dumps(welt), encoding='utf-8')
    with pytest.raises(WeltFehler) as info:
        lade_welten([str(mini_welt), f'holdout={ziel}'])
    assert 'Stichtag' in str(info.value)


def test_erste_welt_heisst_welt_die_weiteren_tragen_ihren_namen(mini_welt, tmp_path):
    welten = lade_welten([str(mini_welt)])
    assert welten[0].name == 'welt' and {f.herkunft for f in welten[0].fragen} == {'welt'}


def test_lokale_fragen_brauchen_keine_belege():
    fragen = pruefe_fragen_lokal({'fragen': [
        {'id': 'e-1', 'frage': 'Was ist mit Mainz los?', 'erwartet': {'verhalten': 'rueckfrage',
                                                                       'bedeutungen': [['A'], ['B']]}},
        {'id': 'e-2', 'frage': 'Wann ist X?', 'erwartet': {'verhalten': 'antworten', 'aussagen': [['Montag']]}},
    ]})
    assert [f.herkunft for f in fragen] == ['lokal', 'lokal']
    assert fragen[0].kategorie == 'eigene' and fragen[0].schwere == 'normal'


def test_lokale_fragen_doppelte_id_wird_abgelehnt():
    with pytest.raises(WeltFehler):
        pruefe_fragen_lokal([{'id': 'e-1', 'frage': 'a?', 'erwartet': {'verhalten': 'nicht_bekannt'}},
                             {'id': 'e-1', 'frage': 'b?', 'erwartet': {'verhalten': 'nicht_bekannt'}}])
