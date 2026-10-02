"""Einordnung je Abschnitt: jede Quelle wird eingeordnet, lange in Häppchen, und die Belege zeigen auf die richtige Stelle.

Zusicherungen (Sabotageproben in `docs/35-belegte-antworten.md`, Abschnitt „Lange Quellen in Abschnitten“):

1. Eine Quelle über 12.000 Zeichen wird eingeordnet (die alte Grenze ist weg); darüber, an der Obergrenze, nicht, und
   das Logbuch vermerkt es einmal je Fassung, statt sie still zu übergehen.
2. Der Arbeitsgang gibt einer Quelle nie alle Abschnitte in einem Paket: höchstens `ABSCHNITTE_JE_PAKET` Modellaufrufe,
   der Rest folgt im nächsten Paket, und in den Bestand wird erst mit dem letzten Abschnitt geschrieben.
3. Die Belege (`ref`) zeigen auf die Stelle im Volltext; `pruef_text` und das Fenster des Prüfmodells enthalten sie.
4. Fehler, Modellwechsel und Änderung der Quelle werfen den Zwischenstand weg; geschrieben wird nie Halbes.
5. Kurze Quellen gehen unverändert in einem Aufruf durch (keine Abschnittsangabe in der Anfrage).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory import abschnitte as ab
from icarus_memory import logbuch, satzantwort, satzpruefung_modell as spm
from icarus_memory.claims import ClaimStore
from icarus_memory.providers import ProviderError
from icarus_memory.working_memory_store import MAX_SOURCE_CHARS, WorkingMemoryStore
from icarus_memory.working_memory_worker import ABSCHNITTE_JE_PAKET, Zwischenstand, run
from tests.test_working_memory_worker import FakeLocalProvider

AT = datetime(2026, 9, 23, tzinfo=timezone.utc)
SATZ = 'Die Frist für den Quasarantrag endet am 17. November 2026.'
FUELL = 'Wir besprechen den Ablauf, die Unterlagen und den Zeitplan für die kommenden Wochen in Ruhe. '


def transkript(absaetze: int = 60, *, tief: int | None = None, satz: str = SATZ) -> str:
    """Ein Transkript aus Absätzen mit Sprecherzeilen; der Satz steht im Absatz `tief` (Vorgabe: Mitte)."""
    tief = absaetze // 2 if tief is None else tief
    teile = []
    for n in range(absaetze):
        zeilen = [f'{"Anna" if (n + i) % 2 else "Bert"}: ' + (satz if (n, i) == (tief, 1) else FUELL * 3) for i in range(3)]
        teile.append('\n'.join(zeilen))
    return '\n\n'.join(teile)


def quelle(episodes, body, *, tags=('transkript',), titel='Mitschrift', at=AT):
    episode, angelegt = episodes.record(EpisodeKind.DOCUMENT, titel, body, Provenance(SourceType.CHAT, source_ref=f'chat:{titel}'),
                                        at=at, tags=list(tags))
    assert angelegt
    return episode


class Zaehler(FakeLocalProvider):
    """Lokaler Anbieter: `request` für Blöcke mit „Quasarantrag“, sonst `fact`; merkt sich jede Anfrage."""

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[1]['content'])
        self.calls.append(payload)
        if self.on_call:
            self.on_call(payload)
        items = [{'block_id': b['block_id'], 'kind': 'request' if 'Quasarantrag' in b['text'] else 'fact'}
                 for b in payload['blocks']]
        return type('Reply', (), {'text': json.dumps({'items': items}), 'tool_calls': []})()


@pytest.fixture
def raum(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield episodes, WorkingMemoryStore(episodes), SimpleNamespace(lock=threading.Lock(), stand=Zwischenstand())
    episodes.close()


def lauf(raum, anbieter, **kwargs):
    episodes, _, hilfe = raum
    return run(episodes, anbieter, hilfe.lock, stand=hilfe.stand, **kwargs)


# -- 1. Die alte Grenze ist weg, die Obergrenze gilt ------------------------------------------------------------------


def test_ein_transkript_ueber_12000_zeichen_wird_eingeordnet_und_kann_beleg_werden(raum):
    episodes, store, _ = raum
    body = transkript(40)
    assert 12_000 < len(body) < 60_000
    episode = quelle(episodes, body)
    anbieter = Zaehler()
    for _ in range(40):
        lauf(raum, anbieter)
        if store.source_state(episode.id) == 'complete':
            break
    assert store.source_state(episode.id) == 'complete'
    refs = store.search('Quasarantrag')['refs']
    assert [r['episode_id'] for r in refs] == [episode.id]
    assert refs[0]['kind'] == 'request'


def test_eine_quelle_ueber_der_obergrenze_bleibt_zurueckgestellt_und_das_logbuch_sagt_es_einmal(raum, tmp_path):
    episodes, store, _ = raum
    buch = logbuch.Logbuch(tmp_path / 'logbuch.sqlite3')
    logbuch.verbinde(buch)
    try:
        zu_gross = quelle(episodes, 'x ' * (MAX_SOURCE_CHARS // 2 + 1), tags=())
        anbieter = Zaehler()
        assert lauf(raum, anbieter).ok
        assert anbieter.calls == [] and store.source_state(zu_gross.id) == 'deferred'
        lauf(raum, anbieter)
        lauf(raum, anbieter)
        z = buch.seit(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2100, 1, 1, tzinfo=timezone.utc))
        assert z.zu_lang == 1, 'Einmal je Fassung der Quelle, nicht bei jedem Durchlauf'
        assert any('zu lang zum Einordnen' in zeile for zeile in logbuch.drei_zeilen(z))
    finally:
        logbuch.verbinde(None)
        buch.close()


def test_direkt_an_der_obergrenze_wird_noch_eingeordnet(raum):
    episodes, store, _ = raum
    body = ('Zeile mit Inhalt und Zahl 12345 zum Füllen. ' * 6 + '\n\n') * 2000
    body = body[:MAX_SOURCE_CHARS].rstrip()
    episode = quelle(episodes, body, tags=())
    assert store.pending(limit=5, episode_ids=[episode.id]), 'Eine Quelle an der Obergrenze ist noch einzuordnen'


# -- 2. Häppchen ----------------------------------------------------------------------------------------------------


def test_ein_paket_gibt_einer_langen_quelle_nie_alle_abschnitte(raum):
    episodes, store, hilfe = raum
    body = transkript(115)  # rund 100.000 Zeichen
    assert len(body) > 90_000
    episode = quelle(episodes, body)
    plan = ab.bilden(body, 'transkript')
    assert len(plan) > 3 * ABSCHNITTE_JE_PAKET
    anbieter = Zaehler()
    pakete = 0
    while store.source_state(episode.id) != 'complete' and pakete < 100:
        vorher = len(anbieter.calls)
        lauf(raum, anbieter)
        pakete += 1
        assert len(anbieter.calls) - vorher <= ABSCHNITTE_JE_PAKET, 'Ein Paket ruft höchstens so oft das Modell'
        if store.source_state(episode.id) != 'complete':
            assert not store.search('Quasarantrag')['refs'], 'Halbes wird nie in den Bestand geschrieben'
    assert pakete >= len(plan) // ABSCHNITTE_JE_PAKET
    assert len(anbieter.calls) == len(plan), 'Jeder Abschnitt genau einmal'
    assert store.source_state(episode.id) == 'complete'
    assert hilfe.stand.offene() == []


def test_die_abschnittsanfragen_tragen_nummer_und_zahl_kurze_quellen_nicht(raum):
    episodes, store, _ = raum
    kurz = quelle(episodes, 'Bitte den Plan prüfen.', tags=(), titel='Kurz')
    anbieter = Zaehler()
    lauf(raum, anbieter)
    assert len(anbieter.calls) == 1 and 'abschnitt' not in anbieter.calls[0]
    lang = quelle(episodes, transkript(40), titel='Lang')
    for _ in range(10):
        lauf(raum, anbieter)
    angaben = [c['abschnitt'] for c in anbieter.calls[1:]]
    assert [a['nr'] for a in angaben] == list(range(1, len(angaben) + 1)) and {a['von'] for a in angaben} == {len(angaben)}
    assert store.source_state(lang.id) == 'complete'


def test_eine_angefangene_quelle_kommt_im_naechsten_paket_zuerst_dran(raum):
    episodes, store, hilfe = raum
    lang = quelle(episodes, transkript(200), titel='Lang')
    kurz = quelle(episodes, 'Bitte den Plan prüfen.', tags=(), titel='Kurz')
    anbieter = Zaehler()
    lauf(raum, anbieter, abschnitte_je_lauf=2, source_ids=[lang.id, kurz.id])
    assert hilfe.stand.offene() == [lang.id] or set(hilfe.stand.offene()) == {lang.id, kurz.id}
    assert [c['abschnitt']['nr'] for c in anbieter.calls] == [1, 2]
    lauf(raum, anbieter, abschnitte_je_lauf=2)  # ohne Angabe der Quellen: die angefangene geht weiter
    assert [c['abschnitt']['nr'] for c in anbieter.calls] == [1, 2, 3, 4]


def test_die_ueberlappung_wird_zweimal_gesehen_aber_nur_einmal_gespeichert(raum):
    episodes, store, _ = raum
    body = transkript(60)
    episode = quelle(episodes, body)
    plan = ab.bilden(body, 'transkript')
    anbieter = Zaehler()
    for _ in range(30):
        lauf(raum, anbieter)
    gesehen = sum(len(c['blocks']) for c in anbieter.calls)
    einheiten = {e for a in plan for e in a.einheiten}
    assert gesehen == len(einheiten) + len(plan) - 1, 'Je Naht eine Einheit doppelt'
    with episodes._lock:
        zeilen = episodes._conn.execute('SELECT start,end FROM working_memory_items WHERE episode_id=?', (episode.id,)).fetchall()
    assert len(zeilen) == len(einheiten) == len({(z[0], z[1]) for z in zeilen})


# -- 3. Die Belege zeigen auf die Stelle im Volltext ----------------------------------------------------------------


def eine_einordnung(raum, body):
    episodes, store, _ = raum
    episode = quelle(episodes, body)
    for _ in range(60):
        lauf(raum, Zaehler())
        if store.source_state(episode.id) == 'complete':
            return episode
    raise AssertionError('nicht eingeordnet')


def beleg_zu(raum, tmp_path, ref):
    episodes, store, _ = raum
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    try:
        return satzantwort._beleg_aus(ref, 'Quelle', 1, store, claims, (), satzantwort.kennzeichnung.LEER, None, ())
    finally:
        claims.close()


def test_der_beleg_zeigt_auf_die_stelle_tief_im_volltext(raum, tmp_path):
    episodes, store, _ = raum
    body = transkript(120, tief=100)
    assert body.index(SATZ) > 25_000
    episode = eine_einordnung(raum, body)
    [ref] = store.search('Quasarantrag')['refs']
    assert SATZ in body[ref['start']:ref['end']], 'Der Verweis zeigt im Volltext auf den Absatz'
    assert ref['start'] <= body.index(SATZ) < ref['end']
    beleg = beleg_zu(raum, tmp_path, ref)
    assert beleg.episode_id == episode.id and SATZ in beleg.pruef_text and SATZ in beleg.text


def test_das_fenster_des_pruefmodells_um_die_fundstelle_enthaelt_den_satz(raum, tmp_path):
    episodes, store, _ = raum
    body = transkript(120, tief=100)
    eine_einordnung(raum, body)
    [ref] = store.search('Quasarantrag')['refs']
    beleg = beleg_zu(raum, tmp_path, ref)
    assert len(beleg.pruef_text) > spm.MAX_BELEG_ZEICHEN or len(body) > spm.MAX_BELEG_ZEICHEN
    angezeigt = spm.belegtext([beleg])
    assert SATZ in angezeigt and len(angezeigt) < len(body) / 3, 'Ein Fenster um die Fundstelle, nicht die ganze Quelle'


def test_das_fenster_liegt_auch_am_anfang_und_am_ende_der_quelle_richtig(raum, tmp_path):
    episodes, store, _ = raum
    for tief in (0, 119):
        body = transkript(120, tief=tief, satz=SATZ.replace('Quasarantrag', f'Quasarantrag{tief}'))
        episode = eine_einordnung(raum, body)
        [ref] = store.search(f'Quasarantrag{tief}')['refs']
        assert ref['episode_id'] == episode.id
        assert f'Quasarantrag{tief}' in spm.belegtext([beleg_zu(raum, tmp_path, ref)])


# -- 4. Fehler, Modellwechsel, Änderung ----------------------------------------------------------------------------------


def test_ein_fehler_im_dritten_abschnitt_wirft_den_zwischenstand_weg_und_schreibt_nichts(raum):
    episodes, store, hilfe = raum
    episode = quelle(episodes, transkript(120))

    class Bricht(Zaehler):
        def complete_json(self, messages, *, max_tokens, schema):
            if len(self.calls) == 2:
                raise ProviderError('offline')
            return super().complete_json(messages, max_tokens=max_tokens, schema=schema)

    anbieter = Bricht()
    ergebnis = lauf(raum, anbieter)
    assert not ergebnis.ok and len(anbieter.calls) == 2
    assert hilfe.stand.offene() == [] and store.source_state(episode.id) == 'failed'
    assert not store.search('Quasarantrag')['refs']


def test_der_zwischenstand_gilt_nur_fuer_dieselbe_fassung_und_dasselbe_modell():
    stand = Zwischenstand()
    stand.ablegen('e1', 'fp1', 'modell-a', [[{'start': 0, 'end': 5, 'kind': 'fact'}]])
    assert stand.holen('e1', 'fp1', 'modell-a') and not stand.holen('e1', 'fp2', 'modell-a') and not stand.holen('e1', 'fp1', 'modell-b')
    stand.verwerfen('e1')
    assert stand.offene() == []


def test_der_zwischenstand_ist_begrenzt_und_haelt_keinen_text():
    stand = Zwischenstand(maximum=3)
    for n in range(10):
        stand.ablegen(f'e{n}', 'fp', 'm', [[{'start': 0, 'end': 5, 'kind': 'fact'}]])
    assert stand.offene() == ['e7', 'e8', 'e9']
    assert set(stand.holen('e9', 'fp', 'm')[0][0]) == {'start', 'end', 'kind'}


# -- Über die Steuerung des Hintergrunds --------------------------------------------------------------------------------


def test_die_steuerung_gibt_die_lange_quelle_nur_einmal_aus_die_abschnitte_laufen_trotzdem_zu_ende(raum):
    """Die Steuerung lässt eine ausgegebene Quelle eine Stunde ruhen; der Arbeitsgang macht sie in Häppchen fertig."""
    from icarus_memory import hintergrund
    episodes, store, hilfe = raum
    steuerung = hintergrund.Steuerung(None, lambda: episodes)
    lang = quelle(episodes, transkript(115))
    plan = ab.bilden(episodes.get(lang.id).body, 'transkript')
    anbieter = Zaehler()
    pakete, ausgegeben = 0, []
    while store.source_state(lang.id) != 'complete' and pakete < 100:
        ids = steuerung.naechste_quellen(5)
        ausgegeben += ids
        vorher = len(anbieter.calls)
        lauf(raum, anbieter, source_ids=ids)
        assert len(anbieter.calls) - vorher <= ABSCHNITTE_JE_PAKET
        pakete += 1
    assert ausgegeben == [lang.id], 'Die Steuerung hat die Quelle einmal ausgegeben'
    assert pakete > 1 and len(anbieter.calls) == len(plan)
    assert store.source_state(lang.id) == 'complete'



# -- Die Suche: eine lange Quelle verdrängt die kurzen nicht ----------------------------------------------------------


def test_eine_lange_quelle_mit_vielen_treffern_verdraengt_die_kurzen_aus_der_wortsuche_nicht(raum):
    episodes, store, _ = raum
    kurze = [quelle(episodes, f'Bitte den Quasarantrag {n} prüfen.', tags=(), titel=f'Kurz {n}') for n in range(6)]
    absaetze = '\n\n'.join(f'Anna: Der Quasarantrag Nummer {n} liegt bei der Stiftung. ' + FUELL * 2 for n in range(70))
    lang = quelle(episodes, absaetze, titel='Lang')
    anbieter = Zaehler()
    for _ in range(60):
        lauf(raum, anbieter, limit=10)
        if store.progress()['remaining'] == 0:
            break
    assert store.progress()['remaining'] == 0
    ohne = store.search('Quasarantrag', limit=64)['refs']
    mit = store.search('Quasarantrag', limit=64, je_quelle=1)['refs']
    assert [r['episode_id'] for r in mit].count(lang.id) == 1
    assert {k.id for k in kurze} <= {r['episode_id'] for r in mit}
    assert len({r['episode_id'] for r in mit}) == 7
    assert len(ohne) > len(mit), 'Ohne Grenze belegt die lange Quelle mit ihren Abschnitten den Platz'
    with pytest.raises(ValueError):
        store.search('Quasarantrag', je_quelle=0)


def test_bei_gleicher_trefferzahl_geht_die_kuerzere_quelle_der_langen_vor(raum):
    episodes, store, _ = raum
    kurz = quelle(episodes, 'Bitte den Quasarantrag prüfen.', tags=(), titel='Kurz', at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    lang_body = '\n\n'.join(f'Anna: Der Quasarantrag Nummer {n} liegt bei der Stiftung. ' + FUELL * 2 for n in range(40))
    lang = quelle(episodes, lang_body, titel='Lang', at=datetime(2026, 9, 20, tzinfo=timezone.utc))  # neuer als die kurze
    anbieter = Zaehler()
    for _ in range(40):
        lauf(raum, anbieter, limit=10)
        if store.progress()['remaining'] == 0:
            break
    folge = [r['episode_id'] for r in store.search('Quasarantrag', limit=64, je_quelle=1)['refs']]
    assert folge == [kurz.id, lang.id], 'Gleiche Trefferzahl: erst die kurze Quelle, obwohl die lange neuer ist'


def test_ein_mehrzeiliger_beitrag_wird_nicht_mitten_im_beitrag_geteilt():
    zeilen = []
    for n in range(60):
        zeilen.append(f'{["Anna Kraus", "Bert Weiß"][n % 2]}: Beginn des Beitrags {n} mit etwas Text dazu.')
        zeilen += [f'fortgesetzt in Zeile {k} des Beitrags {n}, ohne neuen Sprecher und mit Füllwörtern.' for k in range(8)]
    body = '\n'.join(zeilen)
    starts = [body[s:e] for abschnitt in ab.bilden(body, 'transkript') for s, e in abschnitt.einheiten]
    assert len(starts) > 10
    assert all(t.startswith(('Anna Kraus:', 'Bert Weiß:')) for t in starts), 'Ein Schnitt liegt nur vor einem Sprecherwechsel'


def test_der_kandidatenpool_der_wortsuche_behaelt_die_kurzen_quellen_neben_einer_langen_mit_vielen_treffern(raum, monkeypatch):
    from icarus_memory import source_candidates
    episodes, store, _ = raum
    kurze = [quelle(episodes, f'Bitte den Quasarantrag {n} prüfen.', tags=(), titel=f'Kurz {n}') for n in range(10)]
    # Jeder Absatz trifft beide Suchwörter (zwei Treffer), die kurzen nur eines: Die lange Quelle steht in der Suche vorn.
    absaetze = '\n\n'.join(f'Anna: Der Quasarantrag Nummer {n} liegt bei der Stiftung. ' + FUELL * 2 for n in range(70))
    lang = quelle(episodes, absaetze, titel='Lang')
    anbieter = Zaehler()
    for _ in range(80):
        lauf(raum, anbieter, limit=10)
        if store.progress()['remaining'] == 0:
            break
    aufrufe = []
    echte_suche = WorkingMemoryStore.search

    def suche(self, *args, **kwargs):
        aufrufe.append(kwargs)
        return echte_suche(self, *args, **kwargs)

    monkeypatch.setattr(WorkingMemoryStore, 'search', suche)
    gefunden = source_candidates.zusammenfuehren(store, 'Quasarantrag Stiftung', limit=16)
    assert aufrufe and all(a.get('je_quelle') == source_candidates.MAX_PRO_QUELLE for a in aufrufe), \
        'Der Pool der Wortsuche zählt je Quelle einen Verweis (der Volltextindex rettet die kurzen sonst nur zufällig)'
    ids = {r['episode_id'] for r in gefunden.refs}
    assert lang.id in ids and {k.id for k in kurze} <= ids, 'Kein Platz geht an Abschnitte einer einzigen Quelle'
