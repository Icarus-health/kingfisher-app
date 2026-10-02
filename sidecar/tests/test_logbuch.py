"""Logbuch: Chronik, Zusammenfassung, drei Zeilen, leere Fälle, Sicherung, Aufrufe, die nie scheitern. Nur synthetische Daten."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import logbuch
from icarus_memory.logbuch import Logbuch, Zusammenfassung, drei_zeilen, seit_text, zusammenfassen

UTC = timezone.utc
JETZT = datetime(2026, 9, 30, 7, 10, tzinfo=UTC)
GESTERN_ABEND = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)


class Uhr:
    def __init__(self, start: datetime = JETZT) -> None:
        self.jetzt = start.timestamp()

    def __call__(self) -> float:
        return self.jetzt

    def vor(self, **delta) -> None:
        self.jetzt += timedelta(**delta).total_seconds()


@pytest.fixture
def uhr():
    return Uhr(JETZT - timedelta(hours=12))


@pytest.fixture
def buch(tmp_path, uhr):
    b = Logbuch(tmp_path / 'logbuch.sqlite3', uhr=uhr)
    yield b
    b.close()


@pytest.fixture(autouse=True)
def kein_aktives_logbuch():
    logbuch.verbinde(None)
    yield
    logbuch.verbinde(None)


def fuelle(buch: Logbuch, uhr: Uhr) -> None:
    """Der Abend und die Nacht: 41 Mails, zwei neue Akten, ein Widerspruch."""
    buch.vermerke('quellen', sorte='mail', anzahl=25)
    uhr.vor(minutes=5)
    buch.vermerke('quellen', sorte='mail', anzahl=16)
    buch.vermerke('akte_neu', sache='person:a:anna@example.org', name='Anna Keller')
    buch.vermerke('akte_neu', sache='projekt:mainz', name='Mainz')
    buch.vermerke('lint', befunde={'widerspruch': 1})


# -- Die Chronik ------------------------------------------------------------------------------


def test_chronik_haengt_an_und_bleibt_nach_dem_neuoeffnen(tmp_path, uhr):
    pfad = tmp_path / 'logbuch.sqlite3'
    b = Logbuch(pfad, uhr=uhr)
    assert b.vermerke('quellen', sorte='mail', anzahl=3) is True
    uhr.vor(minutes=1)
    assert b.vermerke('export', was='selbstmodell') is True
    b.close()
    b = Logbuch(pfad, uhr=uhr)
    try:
        e = b.ereignisse(0)
        assert [(x.art, x.daten) for x in e] == [('quellen', {'sorte': 'mail', 'anzahl': 3}), ('export', {'was': 'selbstmodell'})]
        assert e[0].zeit < e[1].zeit and e[0].zeit.tzinfo is not None
    finally:
        b.close()


def test_eintraege_lassen_sich_weder_aendern_noch_loeschen(buch):
    buch.vermerke('quellen', sorte='mail', anzahl=3)
    with sqlite3.connect(buch._path) as roh:
        with pytest.raises(sqlite3.DatabaseError, match='anhaengend'):
            roh.execute("UPDATE ereignis SET art = 'export'")
        with pytest.raises(sqlite3.DatabaseError, match='anhaengend'):
            roh.execute('DELETE FROM ereignis')
    assert buch.zaehlen() == 1


def test_kein_rohtext_im_logbuch(buch):
    buch.vermerke('quellen', sorte='mail', anzahl=1, text='Sehr geehrte Frau Keller, ...', body='Inhalt der Mail',
                  betreff='Angebot', absender='anna@example.org', Antwort='Bis zum 31. Oktober.')
    buch.vermerke('akte_neu', sache='projekt:x', name='N' * 500)
    a, b = buch.ereignisse(0)
    assert a.daten == {'sorte': 'mail', 'anzahl': 1}
    assert len(b.daten['name']) <= logbuch.MAX_ZEICHEN
    with sqlite3.connect(buch._path) as roh:
        inhalt = ' '.join(str(z) for z in roh.execute('SELECT * FROM ereignis'))
    for verboten in ('Sehr geehrte', 'Inhalt der Mail', 'Angebot', 'anna@example.org', '31. Oktober'):
        assert verboten not in inhalt


def test_unbekannte_art_wird_nicht_geschrieben(buch):
    assert buch.vermerke('erfunden', x=1) is False
    assert buch.zaehlen() == 0


def test_zeitraum_grenzen(buch, uhr):
    buch.vermerke('export', was='a')
    uhr.vor(hours=1)
    buch.vermerke('export', was='b')
    uhr.vor(hours=1)
    buch.vermerke('export', was='c')
    mitte = datetime.fromtimestamp(uhr.jetzt - 3600, UTC)
    assert [e.daten['was'] for e in buch.ereignisse(mitte)] == ['b', 'c']
    assert [e.daten['was'] for e in buch.ereignisse(mitte, datetime.fromtimestamp(uhr.jetzt, UTC))] == ['b']


# -- Die Zusammenfassung -----------------------------------------------------------------------


def test_zusammenfassung_zaehlt_nur_den_zeitraum(buch, uhr):
    buch.vermerke('quellen', sorte='mail', anzahl=99)   # vor dem Bezugspunkt
    uhr.vor(hours=2)
    bezug = datetime.fromtimestamp(uhr.jetzt, UTC)
    uhr.vor(minutes=1)
    fuelle(buch, uhr)
    z = buch.seit(bezug)
    assert z.quellen == {'mail': 41}
    assert [a['name'] for a in z.akten_neu] == ['Anna Keller', 'Mainz']
    assert z.befunde == {'widerspruch': 1} and z.befunde_quelle == 'ereignisse'


def test_die_drei_zeilen_des_beispiels(buch, uhr):
    bezug = GESTERN_ABEND
    uhr.jetzt = (bezug + timedelta(minutes=30)).timestamp()
    fuelle(buch, uhr)
    uhr.jetzt = JETZT.timestamp()
    zeilen = drei_zeilen(buch.seit(bezug, JETZT))
    assert zeilen == ['Seit gestern Abend: 41 Mails aufgenommen, 2 neue Akten (Anna Keller, Projekt Mainz).',
                      '1 Widerspruch gefunden.']


def test_hoechstens_drei_zeilen_und_leere_kategorien_fehlen(buch, uhr):
    z = Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, quellen={'mail': 1}, vorschlaege_erzeugt=3,
                        fehler=['aufnahme'], exporte=1, rueckmeldungen=2)
    zeilen = drei_zeilen(z)
    assert zeilen == ['Seit gestern Abend: 1 Mail aufgenommen.', '3 neue Vorschläge.',
                      '1 Export angelegt, 2 Rückmeldungen „Stimmt nicht“ notiert. Im Hintergrund ist einmal etwas nicht '
                      'fertig geworden (Quellen aufnehmen). Du musst nichts tun: Kingfisher versucht es von selbst noch einmal.']
    # Nur eine Kategorie: genau eine Zeile, keine leeren.
    assert drei_zeilen(Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, exporte=2)) == ['Seit gestern Abend: 2 Exporte angelegt.']
    assert all(len(drei_zeilen(z)) <= 3 for z in (z,))


def test_nichts_neues(buch):
    assert drei_zeilen(buch.seit(GESTERN_ABEND, JETZT)) == ['Nichts Neues seit gestern Abend.']


def test_am_tag_der_einrichtung_heisst_es_heute(tmp_path):
    """Fremdprobe, Befund 29: „Seit gestern Abend: …“ am Tag, an dem Kingfisher eingerichtet wurde."""
    uhr = Uhr(JETZT - timedelta(hours=1))           # heute früh angelegt, bei der Einrichtung
    buch = Logbuch(tmp_path / 'logbuch.sqlite3', uhr=uhr)
    try:
        assert drei_zeilen(buch.seit(GESTERN_ABEND, JETZT)) == ['Heute noch nichts Neues.']
        buch.vermerke('rueckmeldung')
        z = buch.seit(GESTERN_ABEND, JETZT)
        assert z.seit_beginn and z.seit == JETZT - timedelta(hours=1)
        assert drei_zeilen(z) == ['Heute: 1 Rückmeldung „Stimmt nicht“ notiert.']
        # Am nächsten Tag gilt wieder der gewohnte Bezug: das Logbuch ist dann älter als „gestern Abend“.
        morgen = JETZT + timedelta(days=1)
        uhr.jetzt = morgen.timestamp()
        assert drei_zeilen(buch.seit(morgen - timedelta(hours=12), morgen))[0].startswith('Nichts Neues seit gestern')
    finally:
        buch.close()


def test_einzahl_und_mehrzahl_und_viele_namen():
    akten = [{'sache': f'person:a:p{i}@example.org', 'name': n} for i, n in enumerate(['Anna Keller', 'Bob Weiß', 'Cem Yilmaz', 'Dora Lang', 'Emil Roth'])]
    z = Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, akten_neu=akten, akten_aktualisiert=[{'sache': 'organisation:x', 'name': 'Stiftung'}],
                        befunde={'widerspruch': 2, 'veraltet': 1}, befunde_quelle='ereignisse')
    zeilen = drei_zeilen(z)
    assert zeilen[0] == 'Seit gestern Abend: 5 neue Akten (Anna Keller, Bob Weiß, Cem Yilmaz und 2 weitere), 1 Akte ergänzt.'
    assert zeilen[1] == '2 Widersprüche und 1 veraltete Angabe gefunden.'


def test_akte_die_neu_ist_zaehlt_nicht_zusaetzlich_als_ergaenzt():
    def e(i, art, sache):
        return logbuch.Ereignis(i, JETZT, art, {'sache': sache, 'name': sache})
    z = zusammenfassen([e(1, 'akte_neu', 'projekt:a'), e(2, 'akte_aktualisiert', 'projekt:a'), e(3, 'akte_aktualisiert', 'projekt:b'),
                        e(4, 'akte_aktualisiert', 'projekt:b')], GESTERN_ABEND, JETZT)
    assert [a['sache'] for a in z.akten_neu] == ['projekt:a'] and [a['sache'] for a in z.akten_aktualisiert] == ['projekt:b']


def test_keine_fachwoerter_in_den_zeilen():
    z = Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, quellen={'mail': 2, 'gespraech': 1}, vorschlaege_angenommen=1,
                        vorschlaege_abgelehnt=2, befunde={'etwas_neues': 4}, befunde_quelle='lieferant', modellwechsel=['Antworten formulieren'])
    text = ' '.join(drei_zeilen(z))
    for fach in ('episode', 'claim', 'lint', 'proposal', 'sqlite', 'etwas_neues', '_'):
        assert fach not in text.lower()
    assert '4 Auffälligkeiten noch offen' in text and '1 Modell gewechselt (Antworten formulieren)' in text


@pytest.mark.parametrize('seit,jetzt,erwartet', [
    (datetime(2026, 9, 29, 19, 0, tzinfo=UTC), datetime(2026, 9, 30, 7, 10, tzinfo=UTC), 'gestern Abend'),
    (datetime(2026, 9, 30, 6, 0, tzinfo=UTC), datetime(2026, 9, 30, 9, 0, tzinfo=UTC), 'heute früh'),
    (datetime(2026, 9, 30, 12, 0, tzinfo=UTC), datetime(2026, 9, 30, 16, 0, tzinfo=UTC), 'heute Mittag'),
    (datetime(2026, 9, 30, 6, 0, tzinfo=UTC), datetime(2026, 9, 30, 6, 40, tzinfo=UTC), 'kurzem'),
    (datetime(2026, 9, 28, 10, 0, tzinfo=UTC), datetime(2026, 9, 30, 7, 10, tzinfo=UTC), 'vorgestern'),
    (datetime(2026, 9, 26, 10, 0, tzinfo=UTC), datetime(2026, 9, 30, 7, 10, tzinfo=UTC), 'Samstag'),
    (datetime(2026, 9, 12, 10, 0, tzinfo=UTC), datetime(2026, 9, 30, 7, 10, tzinfo=UTC), 'dem 12. September'),
])
def test_der_bezugspunkt_wird_gesagt_wie_man_ihn_sagt(seit, jetzt, erwartet):
    assert seit_text(seit, jetzt) == erwartet


# -- Die Lieferanten für Befunde -----------------------------------------------------------------


def test_lieferant_zeigt_den_stand_wenn_es_keine_eintraege_gibt(tmp_path, uhr):
    b = Logbuch(tmp_path / 'l.sqlite3', uhr=uhr, befunde_lieferant=lambda: {'widerspruch': 2, 'gesamt': 2})
    try:
        z = b.seit(GESTERN_ABEND, JETZT)
        assert z.befunde == {'widerspruch': 2} and z.befunde_quelle == 'lieferant'
        assert drei_zeilen(z) == ['Seit gestern Abend: 2 Widersprüche noch offen.']
        b.vermerke('lint', befunde={'veraltet': 1})
        uhr.jetzt = JETZT.timestamp()
        z = b.seit(GESTERN_ABEND - timedelta(days=1), JETZT)
        assert z.befunde == {'veraltet': 1} and z.befunde_quelle == 'ereignisse'   # der Eintrag bestimmt, nicht der Stand
    finally:
        b.close()


def test_lieferant_darf_fehlen_oder_scheitern(tmp_path, uhr):
    def kaputt():
        raise RuntimeError('Lint nicht erreichbar')
    for lieferant in (None, kaputt, lambda: None, lambda: 'unsinn', lambda: {'widerspruch': 'viele', 'x': -1}):
        b = Logbuch(tmp_path / f'l{id(lieferant)}.sqlite3', uhr=uhr, befunde_lieferant=lieferant)
        try:
            z = b.seit(GESTERN_ABEND, JETZT)
            assert z.befunde == {} and drei_zeilen(z) == ['Nichts Neues seit gestern Abend.']
        finally:
            b.close()


def test_lieferant_mit_je_art_verschachtelt(tmp_path, uhr):
    b = Logbuch(tmp_path / 'l.sqlite3', uhr=uhr, befunde_lieferant=lambda: {'gesamt': 3, 'je_art': {'widerspruch': 1, 'veraltet': 2}})
    try:
        assert b.seit(GESTERN_ABEND, JETZT).befunde == {'widerspruch': 1, 'veraltet': 2}
    finally:
        b.close()


# -- Seit dem letzten Blick ----------------------------------------------------------------------


def test_ohne_gespeicherten_blick_gelten_24_stunden(buch):
    assert buch.bezugspunkt(JETZT) == JETZT - timedelta(hours=24)


def test_der_letzte_aufruf_ist_der_bezugspunkt_nach_einer_pause(buch):
    abend = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)
    buch.bezugspunkt(abend)
    assert buch.bezugspunkt(JETZT) == abend   # am nächsten Morgen: seit dem Abend


def test_neuladen_leert_die_zeilen_nicht(buch):
    abend = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)
    buch.bezugspunkt(abend)
    erster = buch.bezugspunkt(JETZT)
    for minuten in (1, 2, 61, 120):   # Neuladen und der Takt der Oberfläche
        assert buch.bezugspunkt(JETZT + timedelta(minutes=minuten)) == erster == abend


def test_nach_einer_weiteren_pause_rueckt_der_bezugspunkt_vor(buch):
    abend = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)
    buch.bezugspunkt(abend)
    buch.bezugspunkt(JETZT)
    mittag = JETZT + timedelta(hours=5)
    assert buch.bezugspunkt(mittag) == JETZT


def test_ansehen_ohne_buchen_verschiebt_nichts(buch):
    abend = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)
    buch.bezugspunkt(abend)
    buch.bezugspunkt(JETZT + timedelta(hours=5), buchen=False)
    assert buch.bezugspunkt(JETZT) == abend


def test_bezugspunkt_bleibt_nach_dem_neuoeffnen_erhalten(tmp_path):
    pfad = tmp_path / 'l.sqlite3'
    abend = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)
    b = Logbuch(pfad)
    b.bezugspunkt(abend)
    b.close()
    b = Logbuch(pfad)
    try:
        assert b.bezugspunkt(JETZT) == abend
    finally:
        b.close()


def test_nie_weiter_zurueck_als_dreissig_tage(buch):
    buch.bezugspunkt(JETZT - timedelta(days=90))
    assert buch.bezugspunkt(JETZT) == JETZT - logbuch.MAX_RUECKBLICK


# -- Akten ------------------------------------------------------------------------------------


def sachen(*paare):
    return [{'sache': s, 'name': n, 'letzte': letzte} for s, n, letzte in paare]


def test_akten_der_erste_abgleich_setzt_nur_den_stand_fuer_altes(buch):
    assert buch.akten_abgleichen(sachen(('person:a:x@example.org', 'Xaver', '2026-09-01'), ('projekt:alt', 'Alt', ''))) == 0
    assert buch.zaehlen() == 0
    assert buch.akten_abgleichen(sachen(('person:a:x@example.org', 'Xaver', '2026-09-01'), ('projekt:alt', 'Alt', ''))) == 0


def test_akten_der_erste_abgleich_meldet_was_nach_dem_anlegen_entstand(buch):
    assert buch.akten_abgleichen(sachen(('person:a:x@example.org', 'Xaver', '2026-09-01'),
                                        ('projekt:mainz', 'Mainz', '2026-09-29T20:00:00+00:00'))) == 1
    assert [(e.art, e.daten['name']) for e in buch.ereignisse(0)] == [('akte_neu', 'Mainz')]


def test_akten_neu_und_aktualisiert_genau_einmal(buch):
    buch.akten_abgleichen(sachen(('person:a:x@example.org', 'Xaver', '2026-09-01')))
    heute = sachen(('person:a:x@example.org', 'Xaver', '2026-09-29'), ('projekt:mainz', 'Mainz', '2026-09-29'))
    assert buch.akten_abgleichen(heute) == 2
    assert buch.akten_abgleichen(heute) == 0
    e = {(x.art, x.daten['sache']) for x in buch.ereignisse(0)}
    assert e == {('akte_aktualisiert', 'person:a:x@example.org'), ('akte_neu', 'projekt:mainz')}


def test_akten_nach_leerem_ersten_abgleich_ist_alles_neue_neu(buch):
    assert buch.akten_abgleichen([]) == 0
    assert buch.akten_abgleichen(sachen(('projekt:mainz', 'Mainz', '2026-09-29'))) == 1


def test_akten_ausserhalb_der_stichprobe_bleiben_im_stand(buch):
    buch.akten_abgleichen(sachen(('projekt:a', 'A', '1'), ('projekt:b', 'B', '1')))
    buch.akten_abgleichen(sachen(('projekt:a', 'A', '1')))   # B fehlt nur in dieser Stichprobe
    assert buch.akten_abgleichen(sachen(('projekt:a', 'A', '1'), ('projekt:b', 'B', '1'))) == 0


# -- Tage der Chronik --------------------------------------------------------------------------


def test_tagesgruppen_juengster_zuerst_ohne_leere_tage(buch, uhr):
    uhr.jetzt = datetime(2026, 9, 27, 10, 0, tzinfo=UTC).timestamp()
    buch.vermerke('quellen', sorte='mail', anzahl=3)
    uhr.jetzt = datetime(2026, 9, 29, 20, 0, tzinfo=UTC).timestamp()
    buch.vermerke('quellen', sorte='mail', anzahl=41)
    buch.vermerke('akte_neu', sache='person:a:anna@example.org', name='Anna Keller')
    uhr.jetzt = datetime(2026, 9, 30, 7, 0, tzinfo=UTC).timestamp()
    buch.vermerke('export', was='selbstmodell')
    tage = buch.tage(datetime(2026, 9, 20, tzinfo=UTC), JETZT)
    assert [t['titel'] for t in tage] == ['Heute', 'Gestern', 'Sonntag, 27. September']
    assert tage[0]['eintraege'] == ['1 Export angelegt']
    assert tage[1]['eintraege'] == ['41 Mails aufgenommen', '1 neue Akte (Anna Keller)']


# -- Aufrufe, die nie scheitern -------------------------------------------------------------------


def test_vermerke_ohne_aktives_logbuch_tut_nichts():
    assert logbuch.aktiv() is None
    assert logbuch.vermerke('quellen', sorte='mail', anzahl=1) is False
    z = logbuch.seit(GESTERN_ABEND, JETZT)
    assert z.leer and drei_zeilen(z) == ['Nichts Neues seit gestern Abend.']


def test_vermerke_nach_dem_schliessen_wirft_nicht(tmp_path):
    b = Logbuch(tmp_path / 'l.sqlite3')
    logbuch.verbinde(b)
    b.close()
    assert logbuch.vermerke('export', was='x') is False


def test_vermerke_mit_kaputter_datenbank_und_unbrauchbaren_daten_wirft_nicht(tmp_path, caplog):
    b = Logbuch(tmp_path / 'l.sqlite3')
    logbuch.verbinde(b)
    try:
        class Unsinn:
            def __str__(self):
                raise RuntimeError('nicht darstellbar')
        assert logbuch.vermerke('export', was=Unsinn()) is False
        b._conn.close()   # die Datei ist weg, das Objekt lebt noch
        assert b.vermerke('export', was='x') is False   # auch die Methode wirft nicht
        assert logbuch.vermerke('export', was='x') is False
        assert logbuch.vermerke('quellen', sorte='mail', anzahl=1) is False
        assert b.akten_abgleichen(sachen(('projekt:a', 'A', '1'))) == 0
        assert b.bezugspunkt(JETZT) == JETZT - timedelta(hours=24)
        assert any('Logbuch' in r.message for r in caplog.records)
    finally:
        logbuch.verbinde(None)


def test_die_modulfunktion_faengt_auch_ein_werfendes_logbuch(tmp_path):
    class Werfend:
        def vermerke(self, art, **daten):
            raise RuntimeError('unerwartet')
    logbuch.verbinde(Werfend())
    assert logbuch.vermerke('export', was='x') is False


def test_vorschlaege_funktionieren_auch_wenn_das_logbuch_kaputt_ist(tmp_path):
    from icarus_memory.proposals import ProposalKind, ProposalStore
    b = Logbuch(tmp_path / 'l.sqlite3')
    logbuch.verbinde(b)
    b._conn.close()
    store = ProposalStore(tmp_path / 'p.sqlite3')
    try:
        p, neu = store.propose(ProposalKind.CONFIRMATION, 'Gilt das noch?', 'Synthetischer Anlass', about=['a-1'])
        assert neu and store.accept(p.id).state.value == 'accepted'
        q, _ = store.propose(ProposalKind.CONFIRMATION, 'Und das?', 'Synthetischer Anlass', about=['a-1'])
        assert store.reject(q.id).state.value == 'rejected'
    finally:
        store.close()


def test_vorschlaege_landen_im_logbuch(tmp_path):
    from icarus_memory.proposals import ProposalKind, ProposalStore
    b = Logbuch(tmp_path / 'l.sqlite3')
    logbuch.verbinde(b)
    store = ProposalStore(tmp_path / 'p.sqlite3')
    try:
        p, _ = store.propose(ProposalKind.CONFIRMATION, 'Gilt das noch?', 'Synthetischer Anlass', about=['a-1'])
        q, _ = store.propose(ProposalKind.CONFIRMATION, 'Und das?', 'Synthetischer Anlass', about=['a-1'])
        store.propose(ProposalKind.CONFIRMATION, 'Gilt das noch?', 'Synthetischer Anlass', about=['a-1'])   # dasselbe noch einmal: kein neuer
        store.accept(p.id)
        store.reject(q.id)
        assert [e.art for e in b.ereignisse(0)] == ['vorschlag_erzeugt', 'vorschlag_erzeugt', 'vorschlag_angenommen', 'vorschlag_abgelehnt']
        assert {e.daten['id'] for e in b.ereignisse(0)} == {p.id, q.id}
        assert 'Gilt das noch' not in str([e.daten for e in b.ereignisse(0)])   # keine Texte, nur Kennungen
    finally:
        store.close()
        b.close()


def test_fehler_der_hintergrundarbeit_nur_mit_namen(buch):
    from icarus_memory.scheduler import JobResult
    logbuch.verbinde(buch)
    logbuch.fehler_des_laufs([JobResult('aufnahme', False, 'OSError: Passwort abc123 falsch'), JobResult('lage', True, ''),
                              JobResult('sicherung', False, 'x')])
    assert [e.daten for e in buch.ereignisse(0)] == [{'was': 'aufnahme'}, {'was': 'sicherung'}]
    assert 'abc123' not in str([e.daten for e in buch.ereignisse(0)])
    logbuch.fehler_des_laufs([object(), None])   # Unbrauchbares wirft nicht


# -- Aufnahme ---------------------------------------------------------------------------------


def test_mailaufnahme_vermerkt_nur_neue_mails(tmp_path, buch):
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.mail_intake import Intake
    from tests.test_mail_intake import Reader
    logbuch.verbinde(buch)
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        intake = Intake(ep)
        intake.start('a', ['INBOX'])
        for _ in range(4):
            intake.step('a', Reader(), batch=2)
        gezaehlt = sum(e.daten['anzahl'] for e in buch.ereignisse(0) if e.art == 'quellen' and e.daten['sorte'] == 'mail')
        assert gezaehlt == sum(ep.counts().values()) == 6
        # Dieselben Mails noch einmal abrufen: bekannt, also nichts Neues und kein weiterer Eintrag.
        with ep.transaction():
            ep._conn.execute("UPDATE mail_intake_items SET status='pending'")
        for _ in range(4):
            intake.step('a', Reader(), batch=2)
        assert sum(e.daten['anzahl'] for e in buch.ereignisse(0) if e.art == 'quellen') == 6
        assert 'alice@example.org' not in str([e.daten for e in buch.ereignisse(0)])
    finally:
        ep.close()


def test_ordneraufnahme_zaehlt_dokumente(tmp_path, buch):
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.ingest import ingest_directory
    logbuch.verbinde(buch)
    wurzel = tmp_path / 'vault'
    wurzel.mkdir()
    (wurzel / 'eins.md').write_text('# Eins\n\nEine Notiz über das Projekt Mainz.\n', encoding='utf-8')
    (wurzel / 'zwei.md').write_text('# Zwei\n\nNoch eine Notiz.\n', encoding='utf-8')
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        bericht = ingest_directory(ep, wurzel, roots=[wurzel])
        assert bericht.recorded == 2
        ingest_directory(ep, wurzel, roots=[wurzel])   # zweiter Lauf: nichts Neues, nichts vermerkt
        assert [(e.daten['sorte'], e.daten['anzahl']) for e in buch.ereignisse(0)] == [('dokument', 2)]
    finally:
        ep.close()


def test_sicherung_kennt_die_datei():
    from icarus_memory import backup, update_backup
    assert 'logbuch.sqlite3' in backup.SQLITE_DATA_FILES
    assert update_backup._targets()['logbuch.sqlite3'] is logbuch._MIGRATIONS


def test_fehler_in_alltagssprache_mit_dem_satz_ob_man_etwas_tun_muss():
    """Fremdprobe 2, Befund 15: nicht „gehakt“ und „Verdichtung“, sondern was nicht fertig wurde und ob man etwas tut."""
    z = Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, fehler=['gedaechtnis', 'zusagen', 'verdichtung'],
                        rueckmeldungen=1)
    zeilen = drei_zeilen(z)
    assert zeilen == ['Seit gestern Abend: 1 Rückmeldung „Stimmt nicht“ notiert. Im Hintergrund ist 3-mal etwas nicht '
                      'fertig geworden (Quellen einordnen, Zusagen erkennen und Wissensvorschläge). Du musst nichts tun: '
                      'Kingfisher versucht es von selbst noch einmal.']
    for wort in ('gehakt', 'Verdichtung', 'Einordnung'):
        assert wort not in zeilen[0]
    # Wo ein Mensch helfen kann, steht, wo er nachsieht; ein Postfach heißt „Mails abrufen“, nie seine Kennung.
    satz = drei_zeilen(Zusammenfassung(seit=GESTERN_ABEND, bis=JETZT, fehler=['mail:konto-1', 'mail:konto-1']))[0]
    assert satz == ('Seit gestern Abend: Im Hintergrund ist 2-mal etwas nicht fertig geworden (Mails abrufen). '
                    'Kingfisher versucht es von selbst noch einmal; bleibt es dabei, prüfe dein Postfach unter '
                    'Einstellungen → Zugänge.')
    assert 'konto-1' not in satz and 'nichts tun' not in satz
