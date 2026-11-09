"""`hermes icarus pruefen`: ein Satz, ob Hermes das Gedächtnis von Kingfisher erreicht.

Erscheint nur, solange `memory.provider` auf `icarus` steht. Ohne Unterbefehl wird ebenfalls
geprüft — es gibt nur diesen einen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .icarus_tuer import (
    TOKEN_NAME,
    Tuer,
    TuerFehler,
    einstellungen,
    finde_verbindung,
    nicht_gefunden,
    urllib_transport,
)


def icarus_command(args: Any) -> int:
    try:
        from hermes_constants import get_hermes_home
        home: Path | None = Path(get_hermes_home())
    except Exception:  # noqa: BLE001 - ohne Profil gelten die Vorgaben
        home = None
    try:
        from agent.secret_scope import get_secret
        token = get_secret(TOKEN_NAME) or None
    except Exception:  # noqa: BLE001
        token = None
    werte = einstellungen(home)
    zuhause = Path.home()
    tuer = Tuer(lambda: finde_verbindung(werte, token, zuhause), urllib_transport(8.0),
                nicht_gefunden(zuhause))
    try:
        print(tuer.pruefen())
    except TuerFehler as fehler:
        print(fehler)
        return 1
    return 0


def register_cli(subparser: Any) -> None:
    befehle = subparser.add_subparsers(dest="icarus_befehl")
    befehle.add_parser("pruefen", help="Prüfen, ob Hermes das Kingfisher-Gedächtnis erreicht")
    subparser.set_defaults(func=icarus_command)
