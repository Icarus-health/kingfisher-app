"""Es gibt genau eine Liste der privaten Mailanbieter (`identitaet.py`).

Gruppierung der Gegenpartei (`bedeutungen`) und Kennung der Organisation
(`bezuege`) fragen dieselbe Funktion. Zwei Listen liefen auseinander: Eine
Adresse galt einmal als Firma, einmal als Privatperson.
"""
import ast
import re
from pathlib import Path

import pytest

from icarus_memory import bedeutungen, bezuege, identitaet
from icarus_memory.identitaet import domaenenname, ist_privater_anbieter

PAKET = Path(identitaet.__file__).parent

# Namen, von denen drei dicht beieinander eine Anbieterliste verraten.
ANBIETER_NAMEN = ('gmail', 'googlemail', 'gmx', 'hotmail', 'outlook', 'icloud', 'yahoo', 't-online', 'posteo',
                  'protonmail', 'freenet')
# Der Mailassistent (`providers_mail.py`) kennt Anbieter, um Server einzutragen: anderer Zweck, je Anbieter ein Eintrag.
AUSGENOMMEN = {'identitaet.py', 'providers_mail.py'}


@pytest.mark.parametrize('adresse, erwartet', [
    ('anna@gmail.com', True),
    ('anna@GMX.de', True),
    ('anna@mail.gmx.net', True),          # Subdomäne
    ('anna@yahoo.de', True),              # Länderendung
    ('anna@yahoo.co.uk', True),           # zweite Ebene
    ('gmx.at', True),                     # eine Domäne statt einer Adresse
    ('mail.gmx.net', True),
    ('anna@t-online.de', True),
    ('anna@pm.me', True),
    ('anna@1und1.de', True),
    ('anna@winter-catering.example', False),
    ('anna@mail.klinik.example', False),
    ('anna@firma.co.uk', False),
    ('anna@gmxfirma.de', False),          # nur der ganze Name zählt
    ('anna@web.firma.de', False),         # `web` als Subdomäne einer Firma
    ('ohne-at', False),
    ('', False),
])
def test_ist_privater_anbieter(adresse, erwartet):
    assert ist_privater_anbieter(adresse) is erwartet


def test_domaenenname():
    assert domaenenname('x@mail.winter-catering.example') == 'winter-catering'
    assert domaenenname('x@firma.co.uk') == 'firma'
    assert domaenenname('keine-domaene') == ''


def test_beide_nutzer_folgen_der_einen_liste(monkeypatch):
    """Ändert man die Liste an der einen Stelle, folgen Organisation und Gegenpartei."""
    assert bezuege.org_aus_adresse('x@beispielpost.example') == 'beispielpost'
    partei = {'participants': ['Max <max@beispielpost.example>']}
    assert bedeutungen._partei(partei, [])[0] == 'd:beispielpost.example'

    monkeypatch.setattr(identitaet, 'PRIVATE_ANBIETER', identitaet.PRIVATE_ANBIETER | {'beispielpost'})
    assert bezuege.org_aus_adresse('x@beispielpost.example') == ''
    assert bedeutungen._partei(partei, [])[0] == 'a:max@beispielpost.example'


def _anbieter_in(text: str) -> set[str]:
    woerter = re.split(r'[\s,;]+', text.casefold())
    return {n for n in ANBIETER_NAMEN for w in woerter if w == n or w.startswith(n + '.')}


def _ist_anbieterliste(knoten: ast.AST) -> bool:
    """Ein Zeichenkettenliteral (oder eine Sammlung davon) mit mindestens drei privaten Anbietern."""
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
        return len(_anbieter_in(knoten.value)) >= 3
    if isinstance(knoten, (ast.Set, ast.List, ast.Tuple)):
        texte = [e.value for e in knoten.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return len(_anbieter_in(' '.join(texte))) >= 3
    return False


def test_keine_zweite_anbieterliste_im_paket():
    funde = []
    for datei in sorted(PAKET.rglob('*.py')):
        if datei.name in AUSGENOMMEN:
            continue
        baum = ast.parse(datei.read_text(encoding='utf-8'))
        doku = {id(k.body[0].value) for k in ast.walk(baum)
                if isinstance(k, (ast.Module, ast.FunctionDef, ast.ClassDef)) and k.body
                and isinstance(k.body[0], ast.Expr)}
        for knoten in ast.walk(baum):
            if id(knoten) not in doku and _ist_anbieterliste(knoten):
                funde.append(f'{datei.relative_to(PAKET)}:{knoten.lineno}')
    assert not funde, ('Eigene Liste privater Anbieter gefunden; `identitaet.ist_privater_anbieter` '
                       f'nutzen: {funde}')


def test_sperre_erkennt_eine_kopie():
    """Die Sperre selbst: Die alte Kopie aus `bedeutungen` und die aus `bezuege` hätte sie gefunden."""
    alt_voll = ast.parse("X = frozenset('gmail.com gmx.de web.de yahoo.de'.split())").body[0].value.args[0].func.value
    alt_name = ast.parse("X = frozenset({'gmail', 'gmx', 'yahoo'})").body[0].value.args[0]
    harmlos = ast.parse("X = ('gmail', 'firma')").body[0].value
    assert _ist_anbieterliste(alt_voll) and _ist_anbieterliste(alt_name) and not _ist_anbieterliste(harmlos)
