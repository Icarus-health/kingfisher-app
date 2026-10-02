"""Die Prüfung auf falsche deutsche Anführungszeichen in Zeichenketten (`scripts/pruefe_anfuehrungszeichen.py`).

Regel aus CLAUDE.md: nie `„…"` in einer Zeichenkette, immer `„…“`. Das Skript wird von `scripts/hooks/pre-push`
gerufen; hier steht, was es findet, was es ausdrücklich nicht findet und dass der Bestand sauber ist.

Im Testtext steht `¦` für ein ASCII-Anführungszeichen; sonst verstieße diese Datei selbst gegen die Regel.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location('pruefe_anfuehrungszeichen', WURZEL / 'scripts' / 'pruefe_anfuehrungszeichen.py')
pruefer = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = pruefer  # dataclass sucht das Modul der Klasse
_SPEC.loader.exec_module(pruefer)


def roh(text):
    return text.replace('¦', '"')


def funde(tmp_path, name, text):
    datei = tmp_path / name
    datei.write_text(roh(text), encoding='utf-8')
    return pruefer.pruefe_datei(datei)


# -- Python -----------------------------------------------------------------------

@pytest.mark.parametrize('zeile', [
    "x = 'Er sagt „ja¦ dazu'",                  # ASCII-Anführungszeichen schließt
    "x = f'Er sagt „{name}¦ dazu'",             # auch im f-String
    "x = ¦Er sagt „ja¦ dazu¦",                  # das ¦ beendet die Zeichenkette zu früh (Syntaxfehler)
    "x = ['a', 'Klick auf „Speichern¦']",
])
def test_python_findet_falsch_geschlossene_zeichenketten(tmp_path, zeile):
    gefunden = funde(tmp_path, 'a.py', 'name = 1\n' + zeile + '\n')
    assert len(gefunden) == 1 and gefunden[0].zeile == 2, gefunden


@pytest.mark.parametrize('zeile', [
    "x = 'Er sagt „ja“ dazu'",
    "x = ¦Er sagt „ja“ dazu¦",
    "x = f'„{name}“ fehlt'",
    "x = s.startswith('Einpacken: „Laptop')",   # gewollter Anfang eines Zitats
    "ok = 'falsch: „' in text",                 # Code hinter der Zeichenkette
    "x = 'Einpacken: „'",                       # Anfang eines Zitats am Zeilenende
    "# x = 'Kommentar mit „Anführung¦ dazu'",
    "x = 'kein deutsches Zeichen ¦ja¦ hier'",
])
def test_python_laesst_richtiges_in_ruhe(tmp_path, zeile):
    assert funde(tmp_path, 'a.py', 'name, text, s = 1, 2, 3\n' + zeile + '\n') == []


def test_python_ignoriert_dokumentation_und_dreifache_anfuehrungszeichen(tmp_path):
    quelltext = ('¦¦¦Modul: „ja¦ sagt man so.¦¦¦\n\n\ndef f():\n    ¦¦¦Er sagt „ja¦ dazu.¦¦¦\n    return 1\n\n\n'
                 'PROMPT = ¦¦¦Schreibe „Arbeitete an X¦, nicht „Du hast¦.¦¦¦\n')
    assert funde(tmp_path, 'a.py', quelltext) == []


def test_python_ignoriert_einzeilige_dokumentation(tmp_path):
    zeilen = ['def f():', "    'Er sagt „ja¦ dazu.'", '    return 1', '']
    assert funde(tmp_path, 'a.py', '\n'.join(zeilen)) == []
    zeilen[1] = "    x = 'Er sagt „ja¦ dazu.'"
    assert len(funde(tmp_path, 'a.py', '\n'.join(zeilen))) == 1


def test_python_meldet_einen_syntaxfehler_statt_still_zu_schweigen(tmp_path):
    gefunden = funde(tmp_path, 'a.py', 'x = (\n')
    assert len(gefunden) == 1 and 'Syntaxfehler' in gefunden[0].text


# -- JavaScript und TypeScript -----------------------------------------------------------

@pytest.mark.parametrize('zeile', [
    'const a = ¦Er sagt „ja¦ dazu¦;',           # das ¦ beendet die Zeichenkette zu früh
    "const a = 'Er sagt „ja¦ dazu';",
    'const a = `Er sagt „${x}¦ dazu`;',
    "const a = [¦ein¦, 'Klick auf „Speichern¦'];",
    '<input aria-label=¦Feld „Name¦ ausfüllen¦ />',
])
def test_javascript_findet_falsch_geschlossene_zeichenketten(tmp_path, zeile):
    gefunden = funde(tmp_path, 'a.tsx', 'const x = 1;\n' + zeile + '\n')
    assert len(gefunden) == 1 and gefunden[0].zeile == 2, gefunden


@pytest.mark.parametrize('zeile', [
    'const a = ¦Er sagt „ja“ dazu¦;',
    "const a = 'Er sagt „ja“ dazu';",
    'const a = `„${x}“ fehlt`;',
    "if (text.startsWith('Einpacken: „Laptop')) run();",
    "const b = 'falsch: „' in text;",
    "const c = 'Einpacken: „'",                 # Anfang eines Zitats am Zeilenende
    "// const a = 'Kommentar mit „Anführung¦ dazu';",
    "/* const a = 'Block mit „Anführung¦ dazu'; */ const c = 1;",
    '<p>„Wetter¦ und mehr</p>',                  # Text zwischen Tags ist keine Zeichenkette
    'const d = text.replace(/¦/g, ¦“¦);',        # ein ¦ in einem regulären Ausdruck beginnt keine Zeichenkette
])
def test_javascript_laesst_richtiges_in_ruhe(tmp_path, zeile):
    assert funde(tmp_path, 'a.tsx', 'const text = 1;\n' + zeile + '\n') == []


def test_javascript_liest_nach_einem_regulaeren_ausdruck_weiter(tmp_path):
    gefunden = funde(tmp_path, 'a.js', "const a = t.replace(/¦/g, '') + 'Er sagt „ja¦ dazu';\n")
    assert len(gefunden) == 1


def test_mehrzeilige_vorlage_wird_nicht_als_zeichenkette_der_zeile_gelesen(tmp_path):
    assert funde(tmp_path, 'a.js', 'const a = `Zeile „eins¦ \nzwei`;\nconst b = 2;\n') == []


# -- Aufruf -----------------------------------------------------------------------------------

def test_aufruf_meldet_fundstelle_und_rueckgabewert(tmp_path, capsys):
    schlecht = tmp_path / 'schlecht.py'
    schlecht.write_text(roh("x = 'Er sagt „ja¦ dazu'\n"), encoding='utf-8')
    gut = tmp_path / 'gut.py'
    gut.write_text("x = 'Er sagt „ja“ dazu'\n", encoding='utf-8')
    assert pruefer.main([str(gut)]) == 0
    assert pruefer.main([str(schlecht)]) == 1
    ausgabe = capsys.readouterr().out
    assert 'schlecht.py:1:' in ausgabe and 'gut.py' not in ausgabe


def test_der_bestand_des_repositorys_ist_sauber():
    gefunden = [f for pfad in pruefer.verfolgte_dateien(WURZEL) for f in pruefer.pruefe_datei(pfad, str(pfad.relative_to(WURZEL)))]
    assert gefunden == [], '\n'.join(map(str, gefunden))
