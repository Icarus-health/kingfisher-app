#!/usr/bin/env python3
"""Prüft Zeichenketten im Code auf deutsche Anführungszeichen, die falsch schließen.

Die Regel steht in CLAUDE.md: Nie `„…"` in einer Zeichenkette, immer `„…“`. Das schließende ASCII-`"` beendet
eine mit `"` begrenzte Zeichenkette, und je nachdem, was danach steht, ist der Fehler ein Syntaxfehler oder,
schlimmer, keiner.

Gemeldet wird, wenn eine Zeichenkette in Code

* ein `„` öffnet und mit ASCII-`"` schließt (`'Er sagt „ja" dazu'`), oder
* ein `„` öffnet und gar nicht schließt, und hinter der Zeichenkette geht ein Wort weiter (`"Er sagt „ja" dazu"`:
  Die Zeichenkette endet hinter „ja, der Rest ist Code oder ein Syntaxfehler). Ein Anfang wie `startswith('Wort: „')`
  ist gewollt und bleibt unbeanstandet.

Geprüft werden `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs` und `.swift` (Swift mit denselben Regeln wie JavaScript). Nicht geprüft werden Kommentare, Dokumentation
(Docstrings) und mehrzeilige Zeichenketten mit dreifachen Anführungszeichen (Fließtext, kein Code) sowie
Text zwischen JSX-Tags. Ohne Dateiangaben werden alle von Git verfolgten Dateien geprüft.

    python scripts/pruefe_anfuehrungszeichen.py [DATEI ...]      Rückgabe 1, wenn etwas gefunden wurde
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ENDUNGEN = ('.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.swift')
AUF, ZU = '„', '“'
# `„` gefolgt von Text ohne `“`, dann ASCII-`"` (mit oder ohne davor stehendem Rückstrich).
FALSCH_GESCHLOSSEN = re.compile(r'„[^“"\n]*\\?"')
# Wörter, die hinter einer Zeichenkette Code sind und keinen Fließtext fortsetzen (`'Text: „' in zeile`).
SCHLUESSELWOERTER = frozenset({'in', 'and', 'or', 'if', 'else', 'not', 'is', 'for', 'as', 'of', 'instanceof', 'satisfies'})
# Wörter, vor denen ein `/` einen Ausdruck beginnt (kein Teilen): dann ist es ein regulärer Ausdruck.
_VOR_REGEX = set('(,=:[!&|?{};+-*%<>~^') | {''}


@dataclass(frozen=True)
class Fund:
    datei: str
    zeile: int
    text: str

    def __str__(self) -> str:
        return f'{self.datei}:{self.zeile}: {self.text}'


def _verdaechtig(inhalt: str, danach: str) -> str | None:
    """Warum diese Zeichenkette falsch mit deutschen Anführungszeichen umgeht, sonst None.

    ``danach`` ist der Text hinter der Zeichenkette in derselben Zeile.
    """
    if AUF not in inhalt:
        return None
    if FALSCH_GESCHLOSSEN.search(inhalt):
        return 'Mit „ geöffnet und mit einem ASCII-Anführungszeichen geschlossen; richtig ist „…“'
    rest = danach.lstrip()
    weiter = rest[:1]
    wort = re.match(r'\w+', rest)
    if (inhalt.rfind(AUF) > inhalt.rfind(ZU) and weiter and (weiter.isalnum() or weiter in '"\'`')
            and not (wort and wort.group() in SCHLUESSELWOERTER)):
        return 'Mit „ geöffnet und nicht mit “ geschlossen, dahinter geht es weiter (beendet ein " die Zeichenkette zu früh?)'
    return None


def _kurz(inhalt: str) -> str:
    inhalt = ' '.join(inhalt.split())
    return inhalt if len(inhalt) <= 70 else inhalt[:67] + '…'


# -- Python -----------------------------------------------------------------------

def _python(datei: str, quelltext: str) -> list[Fund]:
    try:
        baum = ast.parse(quelltext)
    except SyntaxError as fehler:
        return [Fund(datei, fehler.lineno or 1, f'Syntaxfehler: {fehler.msg}')]
    dokumentation = {id(k.body[0].value) for k in ast.walk(baum)
                     if isinstance(k, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and k.body
                     and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant)}
    funde = []
    zeilen = quelltext.splitlines()
    verschachtelt = {id(teil) for k in ast.walk(baum) if isinstance(k, ast.JoinedStr) for teil in ast.walk(k) if teil is not k}
    for knoten in ast.walk(baum):
        if id(knoten) in dokumentation or id(knoten) in verschachtelt:
            continue
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            inhalt = knoten.value
        elif isinstance(knoten, ast.JoinedStr):  # f-String: Ausdrücke durch einen Platzhalter ersetzen
            inhalt = ''.join(t.value if isinstance(t, ast.Constant) else '\x00' for t in knoten.values)
        else:
            continue
        grund = _verdaechtig(inhalt, _danach(zeilen, knoten))
        if grund and not _dreifach(quelltext, knoten):  # das Suchen im Quelltext ist teuer: nur für Verdächtige
            funde.append(Fund(datei, knoten.lineno, f'{grund}: {_kurz(inhalt)}'))
    return sorted(funde, key=lambda f: f.zeile)


def _danach(zeilen: list[str], knoten: ast.AST) -> str:
    """Der Rest der Zeile hinter dem Ende der Zeichenkette."""
    if knoten.end_lineno is None or knoten.end_lineno > len(zeilen):
        return ''
    return zeilen[knoten.end_lineno - 1].encode('utf-8')[knoten.end_col_offset:].decode('utf-8', 'ignore')


def _dreifach(quelltext: str, knoten: ast.AST) -> bool:
    """Ob die Zeichenkette mit dreifachen Anführungszeichen beginnt (Fließtext, etwa ein Prompt)."""
    segment = ast.get_source_segment(quelltext, knoten) or ''
    return segment.lstrip('rRbBuUfF')[:3] in ('"""', "'''")


# -- JavaScript und TypeScript -------------------------------------------------------

def _javascript(datei: str, quelltext: str) -> list[Fund]:
    """Zeichenketten aus dem Quelltext lesen (Kommentare und reguläre Ausdrücke überspringen) und prüfen."""
    funde = []
    n, i, zeile = len(quelltext), 0, 1
    letztes = ''  # letztes Zeichen außerhalb von Leerraum: entscheidet, ob ein `/` ein regulärer Ausdruck beginnt
    while i < n:
        c = quelltext[i]
        if c == '\n':
            zeile += 1
        elif c == '/' and quelltext.startswith('//', i):
            i = quelltext.find('\n', i)
            i = n if i < 0 else i
            continue
        elif c == '/' and quelltext.startswith('/*', i):
            ende = quelltext.find('*/', i + 2)
            ende = n if ende < 0 else ende + 2
            zeile += quelltext.count('\n', i, ende)
            i = ende
            continue
        elif c in '"\'`':
            start, anfang_zeile = i + 1, zeile
            i += 1
            while i < n and quelltext[i] != c:
                if quelltext[i] == '\\':
                    i += 1
                elif quelltext[i] == '\n':
                    zeile += 1
                    if c != '`':  # nicht abgeschlossene Zeichenkette: bis Zeilenende gelesen, weiter
                        break
                i += 1
            inhalt = quelltext[start:i]
            ende_zeile = quelltext.find('\n', i)
            danach = quelltext[i + 1:n if ende_zeile < 0 else ende_zeile]
            grund = _verdaechtig(inhalt, danach) if c != '`' or '\n' not in inhalt else None
            if grund:
                funde.append(Fund(datei, anfang_zeile, f'{grund}: {_kurz(inhalt)}'))
            letztes = c
            i += 1
            continue
        elif c == '/' and letztes in _VOR_REGEX:  # regulärer Ausdruck
            i += 1
            in_klasse = False
            while i < n and quelltext[i] != '\n':
                if quelltext[i] == '\\':
                    i += 1
                elif quelltext[i] == '[':
                    in_klasse = True
                elif quelltext[i] == ']':
                    in_klasse = False
                elif quelltext[i] == '/' and not in_klasse:
                    break
                i += 1
            letztes = '/'
            i += 1
            continue
        if not c.isspace():
            letztes = c
        i += 1
    return funde


PRUEFER = {'.py': _python, '.ts': _javascript, '.tsx': _javascript, '.js': _javascript, '.jsx': _javascript,
           '.mjs': _javascript, '.swift': _javascript}


def pruefe_datei(pfad: Path, anzeige: str | None = None) -> list[Fund]:
    try:
        text = pfad.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return []
    return PRUEFER[pfad.suffix](anzeige or str(pfad), text)


def verfolgte_dateien(wurzel: Path) -> list[Path]:
    """Alle von Git verfolgten Dateien mit einer geprüften Endung (vorhandene, ohne Abhängigkeiten und Bauergebnisse)."""
    ausgabe = subprocess.run(['git', 'ls-files', '-z'], cwd=wurzel, capture_output=True, text=True, check=True).stdout
    pfade = [wurzel / p for p in ausgabe.split('\0') if p.endswith(ENDUNGEN)]
    return [p for p in pfade if p.is_file() and 'node_modules' not in p.parts]


def main(argumente: list[str]) -> int:
    wurzel = Path(__file__).resolve().parents[1]
    pfade = [Path(a) for a in argumente] or verfolgte_dateien(wurzel)
    funde = []
    for pfad in pfade:
        if pfad.suffix in PRUEFER:
            try:
                anzeige = str(pfad.resolve().relative_to(wurzel))
            except ValueError:
                anzeige = str(pfad)
            funde += pruefe_datei(pfad, anzeige)
    for fund in funde:
        print(fund)
    if funde:
        print(f'{len(funde)} Zeichenkette(n) mit falschen deutschen Anführungszeichen (Regel in CLAUDE.md: immer „…“).')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
