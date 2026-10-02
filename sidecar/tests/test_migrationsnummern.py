"""Docstrings nennen die Migrationsnummer, unter der die Funktion wirklich aufgerufen wird."""
import importlib
import inspect
import re

from icarus_memory import episodes


def test_docstring_nennt_die_nummer_der_migrationsliste():
    pruefungen = 0
    for nummer in range(1, 40):
        migration = getattr(episodes, f'_migrate_v{nummer}', None)
        if migration is None:
            continue
        quelltext = inspect.getsource(migration)
        # `from . import a, b` im Rumpf, danach `a.funktion(connection)`.
        importiert = {}
        for zeile in re.findall(r'from \. import ([\w, ]+)', quelltext):
            importiert.update({name.strip(): name.strip() for name in zeile.split(',')})
        for modul, funktion in re.findall(r'\b(\w+)\.(\w+)\(connection\)', quelltext):
            if modul not in importiert:
                continue
            aufgerufen = getattr(importlib.import_module(f'icarus_memory.{modul}'), funktion)
            genannt = re.search(r'Migration (\d+)', inspect.getdoc(aufgerufen) or '')
            if genannt:
                pruefungen += 1
                assert int(genannt[1]) == nummer, f'{modul}.{funktion} nennt Migration {genannt[1]}, läuft aber als {nummer}'
    assert pruefungen >= 2, 'die Prüfung hat nichts gefunden'
