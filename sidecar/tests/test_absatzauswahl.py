"""Zweistufige Auswahl (`absatzauswahl.py`): aus langen Quellen nur die passenden Absätze in den Kontext.

Zusicherungen (Sabotageproben in `docs/35-belegte-antworten.md`, Abschnitt „Zweistufige Auswahl“):

1. Kurze Quellen (bis `GANZ_BIS`) bleiben ganz; lange bekommen Kopf, passende Absätze und den Vermerk mit den Zahlen.
2. Die Fenster decken den Text, überlappen nicht und sind höchstens 600 Zeichen lang.
3. Passend heißt: Wörter der Frage samt Wortformen und Wortteilen; seltene Wörter der Quelle zählen mehr; Zitat,
   Signatur und Haftungsausschluss zählen weniger.
4. Ein Beleg ohne passenden Absatz bekommt Kopf und ersten Absatz, nie nichts.
5. Die Fundstelle steht nicht doppelt im Kontext (nur ein Verweis), außer in den Belegen der Satzformulierung.
6. Die Stellen der Akte (überholte Angabe, Frist) kommen dazu, wenn sie fehlen.
7. Zeilen des Kontexts tragen den Volltext; alles, was Text prüft, liest ihn, nie den Ausschnitt.
8. Die Kandidaten bleiben 16, das Budget bleibt bei 32.000 Zeichen und zählt Ausschnitt, Stellen und Hinweise der Akte.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType, absatzauswahl, working_memory_answers as wma
from icarus_memory.absatzauswahl import (FENSTER_MAX, GANZ_BIS, LUECKE, Suchwoerter, Zeile, auszug, bewerten, ergaenzen,
                                         fenster, kuerzung, volltext_zeilen)
from icarus_memory.working_memory_store import WorkingMemoryStore

AT = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)
FRAGE = Suchwoerter.aus('Wann ist die Einreichfrist der Stiftung?')

FUELL = ('Wir melden uns, sobald es Neuigkeiten gibt, und hoffen, dass die Abstimmung in den kommenden Wochen gut '
         'verläuft. Bis dahin bleibt alles wie besprochen, und ich schicke Ihnen gern weitere Unterlagen. ')


def absatz(text: str, laenge: int = 500) -> str:
    """Ein Absatz von etwa `laenge` Zeichen, der mit `text` beginnt."""
    rest = max(laenge - len(text), 0)
    return (text + ' ' + (FUELL * 4)[:rest]).strip()


def mail_text() -> str:
    """Eine lange Mail: Gruß, eine tragende Stelle in der Mitte, Signatur, Haftungsausschluss, zitierte Vor-Mail."""
    return '\n\n'.join([
        'Von: Förderteam <team@stiftung.example>\nAdresse: Musterweg 1, Mainz',
        absatz('Guten Tag Frau Hartmann, vielen Dank für Ihre Anfrage zum Bürobedarf.', 450),
        absatz('Die Einreichfrist der Stiftung endet am 12. November 2026 um 12 Uhr.', 480),
        absatz('Zum Catering in der Kantine gibt es noch keine Neuigkeiten, wir melden uns.', 500),
        '-- \nDr. Alex Beispiel\nStiftung Zukunft\nTel. 0611 555-0100',
        'Diese E-Mail ist vertraulich und ausschließlich für den Adressaten bestimmt. Bei Irrtum bitte löschen. ' * 3,
        'Am 01.03.2025 schrieb Petra Keller:\n' + '\n'.join(f'> Zeile {i}: die Einreichfrist der Stiftung war damals unklar.'
                                                        for i in range(12)),
    ])


# -- 1. Kurz bleibt ganz, lang bekommt Vermerk ------------------------------------------------------------------------


def test_kurze_quellen_bleiben_ganz_und_ohne_vermerk():
    text = 'Die Einreichfrist endet am 12. November.\n\n' + absatz('Weiteres', 700)
    assert len(text) <= GANZ_BIS
    ergebnis = auszug(text, FRAGE)
    assert ergebnis.text == text and not ergebnis.gekuerzt and 'gekürzt' not in ergebnis.text


def test_lange_mail_zeigt_die_tragende_stelle_und_nennt_was_fehlt():
    text = mail_text()
    assert len(text) > 2500
    ergebnis = auszug(text, FRAGE)
    assert '12. November 2026 um 12 Uhr' in ergebnis.text, 'die tragende Stelle steht im Auszug'
    assert ergebnis.gekuerzt and len(ergebnis.text) < len(text) * 0.6
    treffer = re.search(r'… \[gekürzt, (\d+) von (\d+) Absätzen\]$', ergebnis.text)
    assert treffer and (int(treffer[1]), int(treffer[2])) == (ergebnis.gezeigt, ergebnis.gesamt)
    assert ergebnis.gezeigt < ergebnis.gesamt and ergebnis.gesamt == len(fenster(text))


def test_signatur_haftungsausschluss_und_zitat_kommen_nicht_vor_der_tragenden_stelle():
    ergebnis = auszug(mail_text(), FRAGE, max_fenster=1)
    assert 'vertraulich' not in ergebnis.text and '> Zeile' not in ergebnis.text and 'Tel. 0611' not in ergebnis.text


def test_getrennte_stellen_sind_mit_luecke_markiert():
    text = '\n\n'.join([absatz('Erster Absatz zur Einreichfrist der Stiftung.', 500), absatz('Dazwischen nichts Wichtiges.', 550),
                        absatz('Dritter Absatz, die Einreichfrist der Stiftung gilt.', 500)] + [absatz('Füller', 550)] * 3)
    ergebnis = auszug(text, FRAGE, max_fenster=2)
    assert LUECKE in ergebnis.text.split('… [gekürzt')[0]


# -- 2. Fenster ---------------------------------------------------------------------------------------------


def test_fenster_decken_den_text_ueberlappen_nicht_und_bleiben_klein():
    text = mail_text()
    liste = fenster(text)
    assert all(ende - start <= FENSTER_MAX for start, ende in liste)
    assert all(a[1] <= b[0] for a, b in zip(liste, liste[1:])), 'keine Überlappung, Reihenfolge des Textes'
    belegt = ''.join(text[s:e] for s, e in liste)
    assert re.sub(r'\s+', '', belegt) == re.sub(r'\s+', '', text), 'nichts geht verloren, nichts kommt dazu'


def test_ein_langer_absatz_ohne_leerzeile_wird_an_zeilen_und_saetzen_geteilt():
    text = '\n'.join(f'> Zeile {i}: die Einreichfrist war damals unklar, wir fragen nach.' for i in range(60))
    liste = fenster(text)
    assert len(liste) >= 6 and all(ende - start <= FENSTER_MAX for start, ende in liste)
    assert all(text[s:e].startswith('> Zeile') for s, e in liste), 'an Zeilengrenzen'


def test_kleine_absaetze_werden_zusammengefasst():
    text = '\n\n'.join(['Danke.', 'Gruß', 'Anna', absatz('Ein ordentlicher Absatz', 590)])
    liste = fenster(text)
    assert len(liste) == 2 and text[liste[0][0]:liste[0][1]] == 'Danke.\n\nGruß\n\nAnna'

    # Eine Signatur oder ein Zitat verschwindet nicht im Fenster des Fließtextes davor.
    gemischt = '\n\n'.join([absatz('Fließtext', 200), '-- \nDr. Alex Beispiel', '> zitiert\n> noch eine Zeile'])
    assert len(fenster(gemischt)) == 3


# -- 3. Bewertung -----------------------------------------------------------------------------------------------


def test_wortformen_und_wortteile_zaehlen_wie_in_der_suche():
    text = absatz('Wir haben die Rechnungen geprüft.', 400) + '\n\n' + absatz('Sonst nichts Besonderes.', 400)
    liste = fenster(text)
    punkte = bewerten(text, liste, Suchwoerter.aus('Wo ist die Rechnung?'))
    assert punkte[0] > 0 and punkte[1] == 0, 'Wortform „Rechnungen“ trifft „Rechnung“'
    text = absatz('Die Stiftungsförderung läuft bis Dezember.', 400) + '\n\n' + absatz('Sonst nichts Besonderes.', 400)
    assert bewerten(text, fenster(text), Suchwoerter.aus('Förderung'))[0] > 0, 'Wortteil „förderung“'


def test_seltene_woerter_der_quelle_zaehlen_mehr_als_haeufige():
    haeufig = absatz('Der Vertrag, der Vertrag, ein Vertrag mit allem.', 300)
    selten = absatz('Die Kündigungsfrist steht im Vertrag.', 300)
    text = '\n\n'.join([haeufig, haeufig.replace('Vertrag', 'Vertrag'), selten, absatz('Füller', 400)])
    punkte = bewerten(text, fenster(text), Suchwoerter.aus('Kündigungsfrist im Vertrag'))
    assert punkte.index(max(punkte)) == 2


def test_ein_seltenes_wort_schlaegt_zwei_haeufige_die_ueberall_stehen():
    haeufig = [absatz('Der Vertrag und das Angebot.', 300) for _ in range(4)]
    text = '\n\n'.join([*haeufig, absatz('Die Kündigungsfrist steht fest.', 300)])
    punkte = bewerten(text, fenster(text), Suchwoerter.aus('Vertrag Angebot Kündigungsfrist'))
    assert punkte.index(max(punkte)) == 4, punkte


def test_zitat_und_signatur_zaehlen_weniger_als_fliesstext():
    zitat = '\n'.join(f'> die Einreichfrist der Stiftung, Zeile {i}' for i in range(8))
    text = '\n\n'.join([zitat, absatz('Die Einreichfrist der Stiftung ist wichtig.', 350)])
    liste = fenster(text)
    punkte = bewerten(text, liste, FRAGE)
    assert punkte[1] > punkte[0] > 0


def test_ohne_suchwoerter_zaehlt_nur_der_anfang():
    text = mail_text()
    leer = Suchwoerter.aus('')
    assert leer.leer() and bewerten(text, fenster(text), leer) == [0.0] * len(fenster(text))
    ergebnis = auszug(text, leer)
    assert ergebnis.text and 'Von: Förderteam' in ergebnis.text and 'Guten Tag Frau Hartmann' in ergebnis.text


# -- 4. Nie leer -------------------------------------------------------------------------------------------------------


def test_ohne_passenden_absatz_bleiben_kopf_und_erster_absatz():
    ergebnis = auszug(mail_text(), Suchwoerter.aus('Wann kommt der Klempner wegen der Heizung?'))
    assert ergebnis.text.startswith('Von: Förderteam <team@stiftung.example>\nAdresse: Musterweg 1, Mainz')
    assert 'Guten Tag Frau Hartmann' in ergebnis.text and 'Einreichfrist' not in ergebnis.text
    assert ergebnis.gekuerzt and '… [gekürzt, ' in ergebnis.text


def test_ein_text_ohne_kopf_und_ohne_treffer_ist_nie_leer():
    text = '\n\n'.join(absatz(f'Absatz {i} ohne Bezug', 500) for i in range(8))
    ergebnis = auszug(text, FRAGE)
    assert ergebnis.text.strip() and ergebnis.text.startswith('Absatz 0 ohne Bezug')


def test_kopfzeilen_des_textes_stehen_immer_vorn():
    # Die Frage nennt nichts aus den Kopfzeilen (dort steht „stiftung“): Sie stehen trotzdem vorn.
    ergebnis = auszug(mail_text(), Suchwoerter.aus('Einreichfrist'))
    assert 'endet am 12. November 2026' in ergebnis.text
    assert ergebnis.text.startswith('Von: Förderteam <team@stiftung.example>\nAdresse: Musterweg 1, Mainz')


# -- 5. Fundstelle -------------------------------------------------------------------------------------------------


def test_die_fundstelle_steht_nur_als_verweis_im_kontext_und_vorn_in_der_satzformulierung():
    text = mail_text()
    ref = next(f for f in fenster(text) if 'endet am 12. November' in text[f[0]:f[1]])
    im_kontext = auszug(text, FRAGE, ref=ref)
    assert 'endet am 12. November 2026' not in im_kontext.text and absatzauswahl.FUNDSTELLE in im_kontext.text
    beleg = auszug(text, FRAGE, ref=ref, ref_zeigen=True)
    assert 'endet am 12. November 2026' in beleg.text and absatzauswahl.FUNDSTELLE not in beleg.text


# -- 6. Stellen der Akte --------------------------------------------------------------------------------------------


def test_die_stelle_der_akte_kommt_dazu_auch_ohne_wortbezug_zur_frage():
    text = mail_text()
    frage = Suchwoerter.aus('Wie geht es dem Catering in der Kantine?')
    ohne = auszug(text, frage, max_fenster=1)
    start = text.index('Die Einreichfrist der Stiftung endet')
    assert '12. November 2026' not in ohne.text
    mit = ergaenzen(text, ohne, [(start, start + 480, '12. November 2026')])
    assert '12. November 2026' in mit.text and mit.gezeigt == ohne.gezeigt + 1
    assert ergaenzen(text, mit, [(start, start + 480, '12. November 2026')]) == mit, 'nichts doppelt'
    ganz = auszug('kurz', frage)
    assert ergaenzen('kurz', ganz, [(0, 4, '')]) is ganz


# -- 7. Zeile und Volltext ----------------------------------------------------------------------------------------


def test_eine_zeile_traegt_den_volltext_und_serialisiert_nur_das_woerterbuch():
    zeile = Zeile({'id': 'S1', 'context': 'Auszug'})
    zeile.volltext, zeile.auszug = 'Volltext der Quelle', auszug('Kurz', FRAGE)
    assert json.loads(json.dumps(zeile)) == {'id': 'S1', 'context': 'Auszug'}
    assert volltext_zeilen([zeile, {'id': 'K1', 'context': 'x'}]) == [{'id': 'S1', 'context': 'Volltext der Quelle'},
                                                                        {'id': 'K1', 'context': 'x'}]
    assert zeile['context'] == 'Auszug', 'das Original bleibt'


def test_die_zaehlung_der_kuerzung_nennt_nur_gekuerzte_quellen():
    lang, kurz = Zeile({'id': 'S1'}), Zeile({'id': 'S2'})
    lang.auszug, kurz.auszug = auszug(mail_text(), FRAGE), auszug('kurz', FRAGE)
    zaehlung = kuerzung([lang, kurz, {'id': 'K1'}])
    assert zaehlung == {'gekuerzt': 1, 'absaetze_gezeigt': lang.auszug.gezeigt, 'absaetze_gesamt': lang.auszug.gesamt}


def test_die_auswahl_ist_deterministisch():
    text = mail_text()
    assert auszug(text, FRAGE) == auszug(text, FRAGE)


# -- 8. Anbindung an die Suche ---------------------------------------------------------------------------------------


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield store
    store.close()


class Claims:
    def source_is_unclaimed(self, episode_id):
        return True


def put(episodes, titel, text, tage=0):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.DOCUMENT, source_ref=f'test:{titel}'),
                                 occurred_at=AT + timedelta(days=tage), at=AT)
    return episode


def einordnen(episodes):
    """Jeder Absatz ein Abschnitt, wie die Einordnung ihn anlegt."""
    from icarus_memory.working_memory_analysis import _blocks
    speicher = WorkingMemoryStore(episodes)
    for snapshot in speicher.pending(limit=200):
        bloecke = [{'start': s, 'end': e, 'kind': 'fact'} for s, e in _blocks(snapshot.episode.body)]
        assert speicher.commit(snapshot, bloecke, model='test')


def test_akte_und_hinweise_zaehlen_zum_budget(episodes, claims, monkeypatch):
    """Die Stellen der Akte und die Hinweise auf Überholtes kosten Zeichen: Was nicht mehr passt, fällt hinten weg."""
    from icarus_memory import akten_kontext
    from icarus_memory.akten_kontext import Kontext, Ueberholt
    quellen = [put(episodes, f'Mail {n}', mail_text().replace('Beispiel', f'Beispiel{n}'), tage=n) for n in range(6)]
    einordnen(episodes)
    frage = 'Wann ist die Einreichfrist der Stiftung?'
    _, ohne, _, _ = wma._candidates(frage, episodes, Claims())
    genau = sum(len(json.dumps(z, ensure_ascii=False)) for z in ohne)
    hinweis = Ueberholt(quellen[0].id, 'frist', 'alt', '15. Oktober 2026', 'x', 'neu', '12. November 2026', 's', {}, {})
    kontext = Kontext(ueberholt={q.id: (hinweis,) for q in quellen})
    monkeypatch.setattr(akten_kontext, 'aufbauen', lambda *a, **k: kontext)
    monkeypatch.setattr(wma, 'MAX_CONTEXT', genau)
    statistik = {}
    refs, zeilen, _, _ = wma._candidates(frage, episodes, Claims(), stats=statistik)
    assert len(refs) < len(ohne) and statistik['abgeschnitten'], 'Die Hinweise haben Platz gekostet'
    hinweise = len(json.dumps({'ueberholt': akten_kontext.hinweis_fuer_modell(kontext, quellen[0].id, {}, {})}, ensure_ascii=False))
    assert sum(len(json.dumps(z, ensure_ascii=False)) for z in zeilen) + hinweise * len(zeilen) <= genau


def test_kandidaten_und_budget_sind_gemessen_festgelegt():
    assert wma.MAX_REFS == 16 and wma.MAX_CONTEXT == 32000


def test_die_zeilen_der_kandidaten_tragen_den_auszug_und_behalten_den_volltext(episodes):
    quelle = put(episodes, 'Stiftung: Frist', mail_text())
    einordnen(episodes)
    statistik = {}
    refs, zeilen, _, _ = wma._candidates('Wann ist die Einreichfrist der Stiftung?', episodes, Claims(), stats=statistik)
    assert [r['episode_id'] for r in refs] == [quelle.id]
    zeile = zeilen[0]
    assert isinstance(zeile, Zeile) and zeile.volltext == episodes.get(quelle.id).body
    assert len(zeile['context']) < len(zeile.volltext) * 0.6 and '… [gekürzt, ' in zeile['context']
    assert 'Dr. Alex Beispiel' not in zeile['context'] and zeile['text'] and 'Einreichfrist' in zeile['text']
    assert statistik['kuerzung'] == {'gekuerzt': 1, 'absaetze_gezeigt': zeile.auszug.gezeigt,
                                     'absaetze_gesamt': zeile.auszug.gesamt}
    assert statistik['abgeschnitten'] == []


def test_das_budget_zaehlt_den_ausschnitt_nicht_den_volltext(episodes, monkeypatch):
    for nummer in range(10):
        put(episodes, f'Mail {nummer}', mail_text().replace('Beispiel', f'Beispiel{nummer}'), tage=nummer)
    einordnen(episodes)
    statistik = {}
    monkeypatch.setattr(wma, 'MAX_CONTEXT', 12_000)
    refs, zeilen, begrenzt, _ = wma._candidates('Wann ist die Einreichfrist der Stiftung?', episodes, Claims(), stats=statistik)
    ganze_zeile = len(json.dumps(dict(zeilen[0], context=zeilen[0].volltext), ensure_ascii=False))
    assert len(refs) > 12_000 // ganze_zeile, 'Mit Ausschnitten passen mehr Quellen ins Budget, als ganze Mails passten'
    assert sum(len(json.dumps(z, ensure_ascii=False)) for z in zeilen) <= 12_000
    assert begrenzt and len(refs) + len(statistik['abgeschnitten']) == 10, 'Was das Budget verdrängt, steht in der Zählung'


@pytest.fixture
def claims(tmp_path):
    from icarus_memory.claims import ClaimStore
    speicher = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield speicher
    speicher.close()


class Modell:
    """Ein lokales Modell, das wählt, was der Test vorgibt, und merkt, was es sah."""

    is_local = True
    name, model = 'skript', 'skript'

    def __init__(self, ids=('S1',)):
        self.ids, self.gesehen = list(ids), {}

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.providers import Reply
        self.gesehen.update(quellen=json.loads(messages[-1]['content'])['sources'], anweisung=messages[0]['content'])
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': self.ids}))


def test_prepare_zeigt_dem_modell_den_auszug_und_prueft_am_volltext(episodes, claims, monkeypatch):
    quelle = put(episodes, 'Stiftung: Frist', mail_text())
    einordnen(episodes)
    gepruefte = {}

    def spion(name, original):
        def innen(*args, **kwargs):
            zeilen = next(a for a in args if isinstance(a, list) and a and isinstance(a[0], dict) and 'id' in a[0])
            gepruefte[name] = zeilen
            return original(*args, **kwargs)
        return innen

    monkeypatch.setattr(wma, 'adjust_selection', spion('identitaet', wma.adjust_selection))
    monkeypatch.setattr(wma.working_memory_projects, 'adjust', spion('projekt', wma.working_memory_projects.adjust))
    monkeypatch.setattr(wma.working_memory_focus, 'adjust', spion('fokus', wma.working_memory_focus.adjust))
    modell = Modell()
    antwort = wma.prepare('Wann ist die Einreichfrist der Stiftung?', episodes, claims, modell)
    assert antwort['status'] == 'reports' and antwort['refs']
    zeile = modell.gesehen['quellen'][0]
    assert '… [gekürzt, ' in zeile['context'] and 'Dr. Alex Beispiel' not in zeile['context']
    assert 'gekürzt' in modell.gesehen['anweisung'], 'Die Anweisung sagt, was der Vermerk bedeutet'
    voll = episodes.get(quelle.id).body
    assert set(gepruefte) == {'identitaet', 'projekt', 'fokus'}
    assert all(z[0]['context'] == voll for z in gepruefte.values()), 'Prüfungen lesen den Volltext, nie den Ausschnitt'
    assert antwort['search']['kuerzung']['gekuerzt'] == 1 and antwort['search']['abgeschnitten'] == []
    assert antwort['basis'] == antwort['refs'], 'Verweise und Kandidaten bleiben unverändert'
