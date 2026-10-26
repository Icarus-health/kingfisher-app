"""Ein Vorschlag für den Namen im Gruß, statt danach zu fragen (V3, 25. Oktober 2026).

Der erste Schritt des Assistenten fragte „Wie heißt du?“, obwohl sich der Name oft finden lässt. Hier steht, woher, in
dieser Reihenfolge:

* `umgebung`: `KINGFISHER_USER_NAME`, von dem gesetzt, der Kingfisher eingerichtet hat (Container, `.kingfisher.env`).
* `postfach`: der Anzeigename im Absender eigener Mails (Kontakt `von` mit `ich`, `kontakte.py`), der häufigste unter
  den jüngsten; sonst der Name im Absender eines Postfachs (`sender`, „Lea Hartmann <lea@…>“).
* `rechner`: der volle Name des Benutzers auf dem Mac. Die Mac-App gibt ihn als `KINGFISHER_VOLLER_NAME`
  (`NSFullUserName()`) an den Container; läuft der Sidecar selbst unter macOS, steht er im Benutzerkonto (`pw_gecos`).

Es ist nur ein Vorschlag. Gespeichert wird der Name erst, wenn der Mensch ihn im Assistenten mit „Weiter“ bestätigt
(`PUT /api/v1/einrichtung`); bis dahin steht er nirgends im Bestand und auch nicht im Gruß. Erfunden wird nichts:
Aus einer Adresse („lea.hartmann@…“) wird kein Name geraten, ein Sammelname („Info“, „Praxis Team“, „root“) gilt
nicht, und der Vorname ist nur das erste Wort eines gefundenen Namens nach Anrede und Titel.
"""
from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from email.utils import parseaddr
from typing import Any, Callable, Iterable, Mapping

QUELLEN = ('umgebung', 'postfach', 'rechner')

#: Wie viele eigene Mails höchstens gelesen werden (die jüngsten); das reicht, und der Stand bleibt schnell.
JUENGSTE_MAILS = 200

#: Wie lange ein Vorschlag aus dem Postfach gilt, bevor er neu gesucht wird. Der Assistent fragt den Stand alle vier
#: Sekunden nach; die Suche läuft trotzdem höchstens einmal je Frist.
FRIST_S = 60.0

#: Wörter, die keinen Menschen bezeichnen, sondern ein Konto, eine Stelle oder ein Sammelpostfach.
_KEIN_MENSCH = frozenset({
    'admin', 'administrator', 'root', 'user', 'benutzer', 'nutzer', 'gast', 'guest', 'system', 'systemadministrator',
    'info', 'kontakt', 'mail', 'post', 'office', 'büro', 'buero', 'team', 'support', 'service', 'noreply', 'no-reply',
    'kingfisher', 'docker', 'familie', 'praxis', 'kanzlei', 'verwaltung', 'sekretariat', 'empfang', 'gmbh', 'ag',
    'kg', 'ev', 'e.v.', 'ug', 'mbh', 'ohg', 'inc', 'ltd', 'shared', 'test', 'demo',
})

#: Anrede und Titel vor dem Namen; sie gehören nicht in den Gruß („Guten Morgen, Dr.“).
_TITEL = re.compile(r"^(herr|frau|hr\.?|fr\.?|dr\.?|prof\.?|dipl\.?-?[\w.]*|mag\.?|ing\.?|med\.?|rer\.?|nat\.?|phil\.?|"
                    r"mba|msc|bsc|m\.?a\.?|b\.?a\.?)$", re.IGNORECASE)

_ANREDE = re.compile(r"^(herr|frau|hr\.?|fr\.?)$", re.IGNORECASE)

#: Ein Wort eines Namens: Buchstaben, dazu Bindestrich und Apostroph im Wort („Anna-Lena“, „O'Neill“).
_WORT = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*\.?")


def bereinigt(roh: Any) -> str:
    """Ein Name, wie er im Gruß stehen kann, oder leer, wenn der Text kein Name eines Menschen ist.

    „Hartmann, Lea“ wird „Lea Hartmann“; was nach „|“, „ – “ oder einer Klammer kommt (Firma, Rolle), fällt weg.
    Eine Adresse, Ziffern, ein Sammelname oder mehr als fünf Wörter ergeben nichts.
    """
    text = ' '.join(str(roh or '').replace(' ', ' ').split()).strip().strip('"\'').strip()
    if not text or '@' in text or len(text) > 80:
        return ''
    text = re.split(r'\s*(?:\||/|\(|\[|<)|\s[-–—]\s', text, maxsplit=1)[0].strip(' ,;:')
    teile = [t.strip() for t in text.split(',')]
    if len(teile) == 2 and all(teile):
        text = f'{teile[1]} {teile[0]}'
    elif len(teile) > 2:
        return ''
    woerter = text.split()
    if not 1 <= len(woerter) <= 5 or not all(_WORT.fullmatch(w) for w in woerter):
        return ''
    if any(w.casefold().strip('.') in _KEIN_MENSCH or w.casefold() in _KEIN_MENSCH for w in woerter):
        return ''
    if not [w for w in woerter if not _TITEL.match(w)]:
        return ''
    return ' '.join(woerter)


def vorname(name: str) -> str:
    """Das erste Wort nach Anrede und Titel: „Lea“ aus „Dr. Lea Hartmann“. Leer, wenn der Name keiner ist."""
    woerter = bereinigt(name).split()
    rest = [w for w in woerter if not _TITEL.match(w)]
    # Nach „Frau“ oder „Herr“ und nach einem Titel vor nur einem Wort folgt der Nachname („Frau Dr. Hartmann“).
    if not rest or any(_ANREDE.match(w) for w in woerter) or (len(rest) < 2 and len(woerter) > 1):
        return ''
    # Eine Initiale („A. Keller“) ist kein Vorname, mit dem man jemanden grüßt.
    return '' if rest[0].endswith('.') or len(rest[0]) < 2 else rest[0]


def aus_umgebung(umgebung: Mapping[str, str]) -> str:
    return bereinigt(umgebung.get('KINGFISHER_USER_NAME', ''))


def aus_rechner(umgebung: Mapping[str, str], *, plattform: str | None = None, im_container: bool | None = None,
                konto: Callable[[], str] | None = None) -> str:
    """Der volle Name des Benutzers auf dem Mac: von der Mac-App gemeldet oder, ohne Container, aus dem Benutzerkonto.

    Unter Linux oder Windows wird das Benutzerkonto nicht gelesen: Dort steht im Feld oft „root“ oder gar nichts, und
    im Container ist es nie der Mensch vor dem Bildschirm.
    """
    gemeldet = bereinigt(umgebung.get('KINGFISHER_VOLLER_NAME', ''))
    if gemeldet:
        return gemeldet
    plattform = sys.platform if plattform is None else plattform
    if im_container is None:
        from .device_profile import _im_container
        im_container = _im_container()
    if plattform != 'darwin' or im_container:
        return ''
    try:
        roh = konto() if konto is not None else _konto_name()
    except Exception:  # noqa: BLE001 - ohne Auskunft eben kein Vorschlag
        return ''
    return bereinigt(str(roh or '').split(',')[0])


def _konto_name() -> str:
    import pwd
    return pwd.getpwuid(os.getuid()).pw_gecos


def aus_postfach(einstellungen: Any, absendernamen: Iterable[str]) -> str:
    """Der häufigste Name im Absender eigener Mails (jüngste zuerst, bei Gleichstand der jüngere), sonst der Name im
    Absender eines verbundenen Postfachs."""
    zaehler: Counter[str] = Counter()
    zuerst: dict[str, int] = {}
    for stelle, roh in enumerate(absendernamen):
        name = bereinigt(roh)
        if name:
            zaehler[name] += 1
            zuerst.setdefault(name, stelle)
    if zaehler:
        return min(zaehler, key=lambda n: (-zaehler[n], zuerst[n]))
    for konto in getattr(einstellungen, 'mail_accounts', None) or []:
        name = bereinigt(parseaddr(str(getattr(konto, 'sender', '') or ''))[0])
        if name:
            return name
    return ''


def vorschlagen(einstellungen: Any, absendernamen: Callable[[], Iterable[str]], *,
                umgebung: Mapping[str, str] | None = None, **rechner: Any) -> dict[str, str] | None:
    """`{name, vorname, quelle}` aus der ersten Quelle, die einen Namen kennt, oder None.

    `absendernamen` wird nur gefragt, wenn die Umgebung keinen Namen setzt (die Suche liest den Bestand).
    """
    umgebung = os.environ if umgebung is None else umgebung
    for quelle in QUELLEN:
        if quelle == 'umgebung':
            name = aus_umgebung(umgebung)
        elif quelle == 'postfach':
            try:
                name = aus_postfach(einstellungen, absendernamen())
            except Exception:  # noqa: BLE001 - ein Fehler im Bestand darf den Assistenten nicht kippen
                name = ''
        else:
            name = aus_rechner(umgebung, **rechner)
        if name and vorname(name):
            return {'name': name, 'vorname': vorname(name), 'quelle': quelle}
    return None


class Merker:
    """Merkt den Vorschlag eine Frist lang, damit das Nachsehen alle vier Sekunden den Bestand nicht jedes Mal liest.

    Ändern sich die Postfächer (ein neues ist verbunden), gilt der gemerkte Vorschlag nicht mehr."""

    def __init__(self, frist: float = FRIST_S, uhr: Callable[[], float] = time.monotonic) -> None:
        self.frist, self.uhr = frist, uhr
        self._schluessel: Any = None
        self._bis = 0.0
        self._wert: dict[str, str] | None = None

    def holen(self, schluessel: Any, berechnen: Callable[[], dict[str, str] | None]) -> dict[str, str] | None:
        jetzt = self.uhr()
        if schluessel != self._schluessel or jetzt >= self._bis:
            self._wert = berechnen()
            self._schluessel, self._bis = schluessel, jetzt + self.frist
        return dict(self._wert) if self._wert else None


__all__ = ['FRIST_S', 'JUENGSTE_MAILS', 'Merker', 'QUELLEN', 'aus_postfach', 'aus_rechner', 'aus_umgebung',
           'bereinigt', 'vorname', 'vorschlagen']
