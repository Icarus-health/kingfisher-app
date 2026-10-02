"""Abschnitte langer Quellen: deterministisch, Überlappung, Zeichenbereiche, Zusammenführung, Obergrenze.

Zusicherungen (Sabotageproben in `docs/35-belegte-antworten.md`, Abschnitt „Lange Quellen in Abschnitten“):

1. Die Abschnittsbildung ist deterministisch und verliert keinen Text: Jedes Zeichen außer Leerraum liegt in einer Einheit.
2. Ein Abschnitt hat 3.000 bis etwa 6.000 Zeichen, höchstens 24 Einheiten; der nächste beginnt mit der letzten Einheit
   des vorigen (eine Einheit Überlappung).
3. Die Zeichenbereiche sind Stellen im Volltext: `start`/`ende` eines Abschnitts sind Anfang der ersten und Ende der
   letzten Einheit, und der Text dort ist der Text der Quelle.
4. Ein Transkript wird an Sprecherwechseln, eine Mail an Zitatgrenzen geteilt, nie mitten in einem Beitrag oder Zitat.
5. Zusammenführen: Die Überlappung liefert keine Dublette; die erste Einordnung gilt; `irrelevant` fällt weg.
6. Über der Obergrenze: `ZuLang`, kein Modellaufruf.
"""
from __future__ import annotations

import random

import pytest

from icarus_memory import abschnitte as ab
from icarus_memory.working_memory_analysis import MAX_BLOCKS, _blocks
from icarus_memory.working_memory_store import MAX_SOURCE_CHARS

WOERTER = ('Haus', 'Frist', 'Bitte', 'Mainz', 'Plan', 'Antrag', 'Klinik', 'Termin', 'Liste', 'Angebot')


def text_aus(seed: int, absaetze: int, *, sprecher: bool = False, trenner: str = '\n\n') -> str:
    zufall = random.Random(seed)
    teile = []
    for nummer in range(absaetze):
        woerter = ' '.join(zufall.choice(WOERTER) for _ in range(zufall.randint(30, 200)))
        teile.append(f'{"AB"[nummer % 2]}: {woerter}' if sprecher else f'Absatz {nummer}: {woerter}')
    return trenner.join(teile)


def nicht_leer_abgedeckt(body: str, plan) -> bool:
    abgedeckt = bytearray(len(body))
    for abschnitt in plan:
        for start, ende in abschnitt.einheiten:
            abgedeckt[start:ende] = b'\x01' * (ende - start)
    return all(abgedeckt[i] or body[i].isspace() for i in range(len(body)))


# -- 1. Deterministisch, nichts geht verloren -------------------------------------------------------------------------


@pytest.mark.parametrize('art', ['transkript', 'mail', 'text'])
def test_die_abschnitte_sind_deterministisch_und_verlieren_keinen_text(art):
    body = text_aus(1, 90)
    erster, zweiter = ab.bilden(body, art), ab.bilden(body, art)
    assert erster == zweiter and len(erster) > 5
    assert nicht_leer_abgedeckt(body, erster)


def test_eine_kurze_quelle_bleibt_ein_abschnitt_mit_den_absaetzen_des_arbeitsgedaechtnisses():
    body = 'Bitte morgen prüfen.\n\nWenn es klappt,\n\ndann melde ich mich.\n\nAlter Verlauf: erledigt.'
    [abschnitt] = ab.bilden(body)
    assert list(abschnitt.einheiten) == _blocks(body)
    assert (abschnitt.nr, abschnitt.ueberlappung) == (1, 0)
    assert ab.bilden('  \n ') == [] and ab.bilden('') == []


def test_der_text_einer_quelle_bis_zum_abschnittsmass_wird_nicht_anders_geteilt_als_frueher():
    body = text_aus(2, 20)[:ab.ZIEL_MAX - 1]
    assert len(ab.bilden(body)) == 1 and list(ab.bilden(body)[0].einheiten) == _blocks(body)


# -- 2. Größe und Überlappung ---------------------------------------------------------------------------------------


def test_ein_abschnitt_hat_drei_bis_sechstausend_zeichen_und_hoechstens_24_einheiten():
    plan = ab.bilden(text_aus(3, 150), 'text')
    assert len(plan) > 10
    for abschnitt in plan[:-1]:
        summe = sum(ende - start for start, ende in abschnitt.einheiten)
        assert ab.ZIEL_MIN <= summe < ab.ZIEL_MAX, (abschnitt.nr, summe)
        assert len(abschnitt.einheiten) <= MAX_BLOCKS
    assert all(abschnitt.zeichen <= ab.ZIEL_MAX + 600 for abschnitt in plan), 'mit Zwischenräumen der Leerzeilen'


def test_der_naechste_abschnitt_beginnt_mit_der_letzten_einheit_des_vorigen():
    plan = ab.bilden(text_aus(4, 100), 'text')
    assert plan[0].ueberlappung == 0
    for vorher, nachher in zip(plan, plan[1:]):
        assert nachher.einheiten[0] == vorher.einheiten[-1]
        assert nachher.ueberlappung == 1
        assert len(nachher.einheiten) >= 2, 'Jeder Abschnitt bringt mindestens eine neue Einheit'
    assert [a.nr for a in plan] == list(range(1, len(plan) + 1))


def test_viele_winzige_absaetze_schliessen_den_abschnitt_nach_24_einheiten():
    body = '\n\n'.join(f'Zeile {n}' for n in range(200))
    plan = ab.bilden(body)
    assert len(plan) > 8
    assert all(len(a.einheiten) <= MAX_BLOCKS for a in plan)
    assert nicht_leer_abgedeckt(body, plan)


# -- 3. Zeichenbereiche im Volltext -----------------------------------------------------------------------------------


def test_die_zeichenbereiche_sind_stellen_im_volltext():
    body = text_aus(5, 80)
    for abschnitt in ab.bilden(body, 'text'):
        assert (abschnitt.start, abschnitt.ende) == (abschnitt.einheiten[0][0], abschnitt.einheiten[-1][1])
        for start, ende in abschnitt.einheiten:
            assert abschnitt.start <= start < ende <= abschnitt.ende
            assert body[start:ende] == body[start:ende].strip() and body[start:ende]
        assert body[abschnitt.start:abschnitt.ende].startswith('Absatz')


def test_ein_absatz_ohne_leerzeile_wird_geteilt_und_behaelt_seine_stellen():
    body = 'x ' * 4000  # ein Absatz von 8.000 Zeichen ohne Zeilenende
    plan = ab.bilden(body, 'text')
    einheiten = [e for a in plan for e in a.einheiten]
    assert len(plan) > 1 and all(ende - start <= ab.EINHEIT_MAX for start, ende in einheiten)
    assert all(body[start:ende].strip() for start, ende in einheiten)


# -- 4. Sprecherwechsel, Zitatgrenzen ----------------------------------------------------------------------------------


def test_ein_transkript_ohne_leerzeilen_wird_an_sprecherwechseln_geteilt():
    zufall = random.Random(6)
    zeilen = [f'{["Anna Kraus", "Bert Weiß"][n % 2]}: ' + ' '.join(zufall.choice(WOERTER) for _ in range(zufall.randint(8, 50)))
              for n in range(700)]
    body = '\n'.join(zeilen)
    plan = ab.bilden(body, 'transkript')
    assert len(plan) > 10
    einheiten = [e for a in plan for e in a.einheiten]
    assert all(ende - start <= ab.EINHEIT_MAX for start, ende in einheiten)
    for start, ende in einheiten:
        assert body[start:ende].startswith(('Anna Kraus:', 'Bert Weiß:')), 'Jede Einheit beginnt mit einem Sprecherwechsel'
    assert nicht_leer_abgedeckt(body, plan)


def test_ein_beitrag_ueber_der_einheitengrenze_wird_nicht_am_sprecherwechsel_zerrissen_sondern_geteilt():
    body = 'Anna: ' + ' '.join(['Wort'] * 2000)  # ein einziger Beitrag von rund 10.000 Zeichen
    einheiten = ab.einheiten(body, 'transkript')
    assert len(einheiten) > 3 and all(ende - start <= ab.EINHEIT_MAX for start, ende in einheiten)


def test_eine_mail_wird_an_zitatgrenzen_geteilt():
    eigener = '\n'.join(f'Zeile {n}: Der Antrag ist fertig und liegt bereit.' for n in range(60))
    zitat = '\n'.join(f'> Zeile {n}: alles war damals noch offen, wir melden uns.' for n in range(60))
    body = 'Kurze Antwort vorweg.\n\n' + eigener + '\n' + zitat + '\n' + eigener
    assert max(len(eigener), len(zitat)) > 2500 and len(eigener) + len(zitat) > ab.EINHEIT_MAX
    einheiten = ab.einheiten(body, 'mail')
    mischt = [(s, e) for s, e in einheiten
              if any(z.lstrip().startswith('>') for z in body[s:e].splitlines())
              and any(not z.lstrip().startswith('>') for z in body[s:e].splitlines())]
    assert not mischt, 'Zitat und eigener Text stehen nie in einer Einheit'
    assert any(body[s:e].startswith('>') for s, e in einheiten)


def test_die_art_der_quelle_kommt_aus_marke_und_art():
    from types import SimpleNamespace
    assert ab.art_der_quelle(SimpleNamespace(tags=['transkript'], kind='document')) == 'transkript'
    assert ab.art_der_quelle(SimpleNamespace(tags=[], kind='message')) == 'mail'
    assert ab.art_der_quelle(SimpleNamespace(tags=[], kind='document')) == 'text'


# -- 5. Zusammenführen ------------------------------------------------------------------------------------------------


def test_die_ueberlappung_liefert_keine_dublette_und_die_erste_einordnung_gilt():
    erster = [{'start': 0, 'end': 10, 'kind': 'request'}, {'start': 12, 'end': 30, 'kind': 'status'}]
    zweiter = [{'start': 12, 'end': 30, 'kind': 'fact'}, {'start': 32, 'end': 40, 'kind': 'change'}]
    assert ab.zusammenfuehren([erster, zweiter]) == [
        {'start': 0, 'end': 10, 'kind': 'request'}, {'start': 12, 'end': 30, 'kind': 'status'},
        {'start': 32, 'end': 40, 'kind': 'change'}]


def test_irrelevant_faellt_erst_beim_zusammenfuehren_weg():
    erster = [{'start': 0, 'end': 10, 'kind': 'irrelevant'}]
    zweiter = [{'start': 0, 'end': 10, 'kind': 'fact'}, {'start': 12, 'end': 20, 'kind': 'irrelevant'}]
    assert ab.zusammenfuehren([erster, zweiter]) == [], 'Die erste Einordnung (belanglos) gilt auch für die Überlappung'
    assert ab.zusammenfuehren([]) == []


def test_zusammenfuehren_ordnet_nach_stelle():
    liste = ab.zusammenfuehren([[{'start': 50, 'end': 60, 'kind': 'fact'}], [{'start': 5, 'end': 9, 'kind': 'fact'}]])
    assert [e['start'] for e in liste] == [5, 50]


# -- 6. Obergrenze ---------------------------------------------------------------------------------------------------


def test_die_obergrenze_ist_die_des_arbeitsgedaechtnisses_und_liegt_weit_ueber_12000():
    assert ab.OBERGRENZE == MAX_SOURCE_CHARS >= 100_000


def test_eine_quelle_an_der_obergrenze_hat_abschnitte_eine_darueber_nicht():
    an_der_grenze = ('Zeile mit Inhalt und Zahl 12345 zum Füllen. ' * 6 + '\n\n') * 2000
    an_der_grenze = an_der_grenze[:ab.OBERGRENZE]
    plan = ab.bilden(an_der_grenze, 'text')
    assert len(plan) > 40 and nicht_leer_abgedeckt(an_der_grenze, plan)
    with pytest.raises(ab.ZuLang):
        ab.bilden(an_der_grenze + 'x', 'text')
    assert ab.zu_lang(an_der_grenze + 'x') and not ab.zu_lang(an_der_grenze)


def test_zu_viele_einheiten_sind_ebenfalls_zu_lang():
    body = '\n\n'.join('a' for _ in range(ab.MAX_EINHEITEN + 1))
    with pytest.raises(ab.ZuLang):
        ab.bilden(body)
