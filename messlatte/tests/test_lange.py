"""Lange Quellen (`--lange-quellen`): Mails auf 3.000, Transkripte auf 30.000 Zeichen, Pflichtaussagen unverändert.

Zusicherungen (Sabotageproben in `docs/35-belegte-antworten.md`, Abschnitt „Zweistufige Auswahl“):

1. Deterministisch: gleicher Startwert, gleiche Quellen; anderer Startwert, anderes Füllmaterial.
2. Länge: Mails erreichen die Zielgröße (knapp darunter), Transkripte ebenso; der Originaltext bleibt wörtlich erhalten
   (Mail: vorn, Transkript: in der Mitte). Kennungen, Zeit und Metadaten bleiben.
3. Die Pflicht- und verbotenen Aussagen stehen nach dem Auffüllen in genau denselben Quellen wie vorher; das Füllmaterial
   nennt keinen vollen Namen und keine Adresse der Welt.
4. Notizen und Termine bleiben unverändert; Rauschen wird wie die Welt aufgefüllt.
5. Jede aufgefüllte Mail bleibt für das Arbeitsgedächtnis auswertbar (höchstens 24 Blöcke, keiner über 4.000 Zeichen).
6. Der ganze Lauf nimmt die langen Quellen auf, der Kopf des Berichts nennt die Option, die Kommandozeile kennt sie.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import MINI_WELT

from icarus_memory.working_memory_analysis import MAX_BLOCK_CHARS, MAX_BLOCKS, _blocks
from messlatte import bericht, lange, rauschen
from messlatte.__main__ import _parser
from messlatte.bewertung import normalisiere
from messlatte.daten import Mail, Notiz, Termin, Transkript
from messlatte.lauf import Optionen, durchfuehren, quellen_des_laufs
from messlatte.welt import lade_welt


@pytest.fixture(scope='module')
def welt():
    return lade_welt(MINI_WELT)


@pytest.fixture(scope='module')
def quellen(welt):
    """Weltquellen plus ein Transkript und Rauschen, damit alle Arten vorkommen."""
    transkript = Transkript(id='lange-001', zeit=welt.stichtag.replace(hour=8), szenario='lange', titel='Abstimmung Angebot',
                            text='Wir haben besprochen, dass das Angebot bis 12. November steht.\n\nDanach Frage zur Abnahme.',
                            teilnehmer=('Lea Hartmann',))
    return (*welt.quellen, transkript, *rauschen.erzeuge(40, [welt], 3))


def texte(q):
    return ' '.join(str(getattr(q, f, '') or '') for f in ('betreff', 'titel', 'text', 'ort', 'notiz'))


# -- 1. Deterministisch ----------------------------------------------------------------------------------------


def test_gleicher_startwert_gleiche_quellen_anderer_startwert_anderes_fuellmaterial(welt, quellen):
    a = lange.aufblasen(quellen, [welt], 1)
    assert a == lange.aufblasen(quellen, [welt], 1)
    b = lange.aufblasen(quellen, [welt], 2)
    assert a != b
    # Die Reihenfolge der Quellen ändert das Füllmaterial einer Quelle nicht (Zufall je Kennung).
    umgekehrt = {q.id: q for q in lange.aufblasen(tuple(reversed(quellen)), [welt], 1)}
    assert all(umgekehrt[q.id] == q for q in a)


# -- 2. Länge und Originaltext --------------------------------------------------------------------------------------


def test_mails_erreichen_die_zielgroesse_und_behalten_ihren_text_vorn(welt, quellen):
    neu = {q.id: q for q in lange.aufblasen(quellen, [welt], 1)}
    mails = [q for q in quellen if isinstance(q, Mail)]
    assert len(mails) > 20
    for alt in mails:
        lang = neu[alt.id]
        assert lange.MAIL_ZEICHEN - 150 <= len(lang.text) <= lange.MAIL_ZEICHEN, (alt.id, len(lang.text))
        assert lang.text.startswith(alt.text.rstrip()), 'Der neue Text der Mail steht oben, wie im Alltag'
        assert replace(lang, text=alt.text) == alt, 'Nur der Text ändert sich'
    assert 'schrieb' in neu[mails[0].id].text and '\n> ' in neu[mails[0].id].text, 'zitierte Vor-Mail'


def test_ein_transkript_steht_in_der_mitte_und_erreicht_die_zielgroesse(welt, quellen):
    alt = next(q for q in quellen if isinstance(q, Transkript) and q.id == 'lange-001')
    lang = next(q for q in lange.aufblasen(quellen, [welt], 1) if q.id == alt.id)
    assert lange.TRANSKRIPT_ZEICHEN - 400 <= len(lang.text) <= lange.TRANSKRIPT_ZEICHEN
    assert alt.text in lang.text, 'Der Originaltext bleibt wörtlich erhalten'
    stelle = lang.text.index(alt.text)
    assert 0.05 * len(lang.text) < stelle < 0.6 * len(lang.text), 'Begrüßung und Small Talk davor'
    assert replace(lang, text=alt.text) == alt


def test_jede_mail_hat_ihr_eigenes_fuellmaterial(welt, quellen):
    neu = [q for q in lange.aufblasen(quellen, [welt], 1) if isinstance(q, Mail)]
    signaturen = {q.text[q.text.index('\n--\n'):][:120] for q in neu if '\n--\n' in q.text}
    assert len(signaturen) > len(neu) // 2, 'Der Zufall hängt an der Kennung, nicht an einem gemeinsamen Startwert'


def test_eine_schon_lange_quelle_bleibt_wie_sie_ist(welt):
    mail = Mail(id='x-1', zeit=welt.stichtag.replace(hour=7), szenario='x', betreff='Lang', text='a ' * 2000)
    assert lange.aufblasen([mail], [welt], 1, mail=3000) == (mail,)


def test_die_zielgroessen_sind_einstellbar(welt, quellen):
    kurz = lange.aufblasen(quellen, [welt], 1, mail=1500, transkript=11_000)
    assert all(1350 <= len(q.text) <= 1500 for q in kurz if isinstance(q, Mail))
    assert all(10_600 <= len(q.text) <= 11_000 for q in kurz if isinstance(q, Transkript))


# -- 3. Pflichtaussagen unverändert --------------------------------------------------------------------------------


def test_pflichtaussagen_und_verbotene_stehen_in_denselben_quellen_wie_vorher(welt, quellen):
    neu = lange.aufblasen(quellen, [welt], 1)
    gesucht = set()
    for frage in welt.fragen:
        gesucht |= {a for gruppe in frage.erwartet.aussagen for a in gruppe} | set(frage.verboten.aussagen)
    gesucht |= {n for p in welt.personen for n in p.namen} | {a for p in welt.personen for a in p.adressen}
    assert len(gesucht) > 10

    def vorkommen(liste):
        return {a: {q.id for q in liste if normalisiere(a) in normalisiere(texte(q))} for a in gesucht if len(a) >= 4}

    # Die Füllung hängt nie etwas an, was vorher nicht stand (sie darf nur nichts hinzufügen); das Original bleibt ganz.
    vorher, nachher = vorkommen(quellen), vorkommen(neu)
    assert vorher == nachher
    assert any(vorher.values()), 'Die Probe ist nicht leer'


def test_ein_satz_mit_dem_vollen_namen_einer_person_wird_nie_gezogen(welt):
    fueller = lange._Fueller([welt], 1)
    # Ein Wortschatz, aus dem nur ein voller Name der Welt entstehen kann: Die Sperrliste muss jeden Satz verwerfen.
    person = next(n for p in welt.personen for n in p.namen if len(n.split()) == 2)
    fueller.vornamen, fueller.nachnamen = [person.split()[0]], [person.split()[1]]
    rng = lange._rng(1, 'x')
    zusatz = ' '.join([fueller.signatur(rng), fueller.zitat(rng, Mail(id='m', zeit=welt.stichtag, szenario='x'), 600),
                       fueller.absatz(rng, lange._SMALLTALK, sprecher=True)])
    assert normalisiere(person) not in normalisiere(zusatz)


def test_ein_satz_mit_einer_gesperrten_aussage_wird_nie_gezogen(welt):
    fueller = lange._Fueller([welt], 1)
    gesperrt = fueller.gesperrt[0]
    fueller.orte = [gesperrt]  # jeder Satz mit {ort} enthielte die gesperrte Aussage
    rng = lange._rng(1, 'y')
    saetze = [fueller.satz(rng, lange._SMALLTALK) for _ in range(300)]
    assert not any(gesperrt in normalisiere(satz) for satz in saetze)
    assert any('{ort}' in v for v in lange._SMALLTALK), 'Die Probe trifft Vorlagen mit Ort'


def test_der_lauf_fuellt_weltquellen_und_rauschen_auf(welt):
    optionen = Optionen(welten=(str(MINI_WELT),), lange_quellen=True, rauschen=30)
    quellen, lauter = quellen_des_laufs(optionen, [welt])
    assert len(lauter) == 30 and all(len(q.text) >= 2850 for q in (*quellen, *lauter) if isinstance(q, Mail))
    kurz_quellen, kurz_lauter = quellen_des_laufs(replace(optionen, lange_quellen=False), [welt])
    assert all(len(q.text) < 1000 for q in (*kurz_quellen, *kurz_lauter) if isinstance(q, Mail))


def test_das_fuellmaterial_nennt_keinen_namen_und_keine_adresse_der_welt(welt, quellen):
    namen = {normalisiere(n) for p in welt.personen for n in p.namen} | {normalisiere(welt.nutzer.name)}
    adressen = {normalisiere(a) for p in welt.personen for a in p.adressen} | {normalisiere(a) for a in welt.nutzer.adressen}
    for alt, lang in zip(quellen, lange.aufblasen(quellen, [welt], 1)):
        if isinstance(alt, (Mail, Transkript)):
            zusatz = normalisiere(lang.text.replace(alt.text.rstrip(), '', 1))
            assert not any(n in zusatz for n in namen if len(n) >= 4), alt.id
            assert not any(a in zusatz for a in adressen), alt.id


# -- 4. Notizen, Termine, Rauschen ---------------------------------------------------------------------------------------------


def test_notizen_und_termine_bleiben_und_rauschen_wird_wie_die_welt_aufgefuellt(welt, quellen):
    neu = lange.aufblasen(quellen, [welt], 1)
    assert [q.id for q in neu] == [q.id for q in quellen], 'Reihenfolge und Kennungen bleiben'
    for alt, lang in zip(quellen, neu):
        if isinstance(alt, (Notiz, Termin)):
            assert alt == lang
    rauschmails = [q for q in neu if isinstance(q, Mail) and q.id.startswith('rauschen-')]
    assert rauschmails and all(len(q.text) >= lange.MAIL_ZEICHEN - 150 for q in rauschmails)


# -- 5. Auswertbar für das Arbeitsgedächtnis -------------------------------------------------------------------------------


def test_jede_aufgefuellte_mail_bleibt_fuer_das_arbeitsgedaechtnis_auswertbar(welt, quellen):
    for q in lange.aufblasen(quellen, [welt], 1):
        if isinstance(q, Mail):
            bloecke = _blocks(q.text)
            assert len(bloecke) <= MAX_BLOCKS, q.id
            assert all(ende - start <= MAX_BLOCK_CHARS for start, ende in bloecke), q.id


# -- 6. Lauf, Kopf, Kommandozeile ------------------------------------------------------------------------------------------


def test_die_kommandozeile_kennt_die_option_mit_den_vorgaben():
    args = _parser().parse_args(['lauf', '--welt', 'x', '--lange-quellen'])
    assert args.lange_quellen and (args.lange_mail_zeichen, args.lange_transkript_zeichen) == (3000, 30_000)
    args = _parser().parse_args(['lauf', '--welt', 'x', '--lange-quellen', '--lange-transkript-zeichen', '11000'])
    assert args.lange_transkript_zeichen == 11_000
    assert not _parser().parse_args(['lauf', '--welt', 'x']).lange_quellen


def test_der_lauf_nimmt_lange_quellen_auf_und_der_kopf_nennt_sie():
    lauf = durchfuehren(Optionen(welten=(str(MINI_WELT),), lange_quellen=True))
    assert lauf.aufnahme.fehlgeschlagen == 0, lauf.aufnahme.nicht_angekommen
    assert lauf.kopf['lange_quellen'] == {'mail': 3000, 'transkript': 30_000}
    text = bericht.markdown(lauf)
    assert 'Lange Quellen' in text and 'Mails auf 3000, Transkripte auf 30000 Zeichen' in text
    z = lauf.abruf_gesamt
    assert z.gekuerzte_quellen > 0 and 0 < z.absaetze_gezeigt < z.absaetze_gesamt, 'Die langen Quellen kommen gekürzt ins Modell'
    assert 'Gekürzte Quellen im Kontext' in text
    # Die Mails sind wirklich lang geworden: Der Kontext ist deutlich größer als mit den kurzen Quellen der Mini-Welt.
    kurz = durchfuehren(Optionen(welten=(str(MINI_WELT),)))
    assert lauf.abruf_gesamt.kontext_zeichen_mittel > 1.5 * kurz.abruf_gesamt.kontext_zeichen_mittel
    assert bericht.markdown(kurz).count('Lange Quellen') == 0
