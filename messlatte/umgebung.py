"""Umgebungsvariablen: gekapselt gesetzt, danach genau wiederhergestellt.

Die Messlatte darf weder echte Zugangsdaten des Rechners in die Messinstanz
lassen (ein Mail-Passwort, ein Anbieterschlüssel aus der Umgebung) noch etwas
davon verändert zurücklassen. Deshalb gilt für die Dauer des Blocks:

* alle `ICARUS_*`- und `KINGFISHER_*`-Variablen sowie die Schlüsselvariablen der
  Anbieter sind entfernt,
* nur die hier ausdrücklich genannten sind gesetzt,
* am Ende steht die Umgebung so da wie vorher, auch nach einem Fehler.

Schlüssel, die die Messlatte selbst braucht (etwa für ein Cloud-Modell), liest
der Aufrufer **vorher** aus der echten Umgebung und reicht sie als Wert weiter.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Mapping

# Was aus dem Rechner nie in die Messinstanz gelangen darf.
GESPERRT_PRAEFIXE = ('ICARUS_', 'KINGFISHER_')
GESPERRT_NAMEN = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'LLM_API_KEY')


@contextmanager
def isolierte_umgebung(setzen: Mapping[str, str]) -> Iterator[None]:
    vorher = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(GESPERRT_PRAEFIXE) or name in GESPERRT_NAMEN:
                del os.environ[name]
        os.environ.update(setzen)
        yield
    finally:
        os.environ.clear()
        os.environ.update(vorher)
