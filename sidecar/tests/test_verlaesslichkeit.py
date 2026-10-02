"""Verlässlichkeit je Satz: gut, einfach, dünn aus Regeln (Zahl und Alter der Belege, Kennzeichnung, Prüfmodell)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from icarus_memory.verlaesslichkeit import DUENN, EINFACH, GUT, einstufen

JETZT = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)


def b(kennung, tage, kennzeichen=()):
    return SimpleNamespace(episode_id=kennung, zeit=None if tage is None else JETZT - timedelta(days=tage),
                           kennzeichen=kennzeichen)


def test_zwei_belege_oder_ein_junger_mit_ja_des_pruefmodells_sind_gut_und_still():
    assert einstufen([b('a', 400), b('b', 500)], JETZT, pruefmodell_ja=True, nur_kopf=False).stufe == GUT
    jung = einstufen([b('a', 89)], JETZT, pruefmodell_ja=True, nur_kopf=False)
    assert (jung.stufe, jung.hinweis) == (GUT, '')


def test_ein_alter_beleg_ist_einfach_und_sagt_es():
    alt = einstufen([b('a', 90)], JETZT, pruefmodell_ja=True, nur_kopf=False)
    assert (alt.stufe, alt.hinweis) == (EINFACH, 'nur eine Quelle, von 2026')
    aelter = einstufen([b('a', 700)], JETZT, pruefmodell_ja=True, nur_kopf=False)
    assert aelter.hinweis == 'nur eine Quelle, von 2024'
    ohne_datum = einstufen([b('a', None)], JETZT, pruefmodell_ja=True, nur_kopf=False)
    assert (ohne_datum.stufe, ohne_datum.hinweis) == (EINFACH, 'nur eine Quelle')


def test_derselbe_beleg_zweimal_ist_eine_quelle():
    assert einstufen([b('a', 400), b('a', 400)], JETZT, pruefmodell_ja=True, nur_kopf=False).stufe == EINFACH


def test_ohne_pruefmodell_hoechstens_einfach_ohne_nebensatz():
    """Dass das Prüfmodell nicht lief, betrifft die ganze Antwort und steht einmal darunter, nicht hinter jedem Satz."""
    stufe = einstufen([b('a', 5), b('b', 6)], JETZT, pruefmodell_ja=False, nur_kopf=False)
    assert (stufe.stufe, stufe.hinweis) == (EINFACH, '')


def test_gekennzeichnet_oder_nur_ueber_die_kopfzeile_ist_duenn_und_geht_vor():
    marke = (SimpleNamespace(art='andere_person'),)
    duenn = einstufen([b('a', 5, marke), b('b', 6)], JETZT, pruefmodell_ja=True, nur_kopf=False)
    assert (duenn.stufe, duenn.hinweis) == (DUENN, 'gestützt auf eine gekennzeichnete Quelle')
    kopf = einstufen([b('a', 5), b('b', 6)], JETZT, pruefmodell_ja=True, nur_kopf=True)
    assert (kopf.stufe, kopf.hinweis) == (DUENN, 'nur über Betreff oder Absender belegt')
