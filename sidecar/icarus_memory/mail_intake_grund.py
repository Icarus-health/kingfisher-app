"""Warum eine Mail nicht ins Gedächtnis kam: ein Kürzel, ein Satz für alle und eine Angabe für Techniker.

Fremdprobe 3, Befund 2: Die Aufnahme verschluckte jede Ausnahme. Fünf Mails scheiterten, und die Oberfläche zeigte
bis zum Ende „wird gelesen: 0 von 5 Mails“. Jetzt speichert die Aufnahme je gescheiterter Mail ein Kürzel
(`mail_intake_items.grund`) und eine technische Angabe (`…technik`); der Stand des Postfachs (`mail_stand.py`) sagt den
Grund in einem Satz, und die Oberfläche bietet „Erneut versuchen“ an.

Die technische Angabe enthält nur Fehlerklassen und eigene Meldungen von Kingfisher, nie Text vom Server oder aus der
Mail: Eine Serverantwort kann Betreff oder Absender nennen, und der Stand landet in der Oberfläche.
"""
from __future__ import annotations

import imaplib
import sqlite3

from .connectors.mail import MailboxGenerationChanged, MailError

#: Kürzel → Satz für alle. Jeder Satz handelt von „den Mails“ und passt hinter „N Mails kamen nicht ins Gedächtnis.“
SATZ = {
    'postfach_schweigt': 'Das Postfach hat beim Abholen nicht geantwortet.',
    'abgelehnt': 'Das Postfach hat sie nicht herausgegeben.',
    'kennung': 'Das Postfach hat sie nicht so herausgegeben, dass Kingfisher sie sicher zuordnen kann.',
    'nicht_gefunden': 'Sie lagen beim Abholen nicht mehr im Postfach.',
    'unlesbar': 'Ihr Inhalt ließ sich nicht lesen.',
    'speichern': 'Kingfisher konnte sie nicht in sein Gedächtnis schreiben.',
    'unbekannt': 'Der Grund ist unklar; Einzelheiten stehen unter „Für Techniker“.',
}

#: Eigene Meldungen von `connectors/mail.py`, an denen sich der Grund erkennen lässt.
_KENNUNG = ('stabile Nachrichtenkennung', 'Nachrichtenkennung ist veraltet', 'passt nicht zur angefragten Kennung',
            'Ungültige Nachrichtenkennung')


def _klassen(fehler: BaseException) -> str:
    """„MailError ← OSError“: die Kette der Fehlerklassen, ohne Text."""
    kette, gesehen = [], set()
    while fehler is not None and id(fehler) not in gesehen and len(kette) < 4:
        gesehen.add(id(fehler))
        kette.append(type(fehler).__name__)
        fehler = fehler.__cause__ or fehler.__context__
    return ' ← '.join(kette)


def einordnen(fehler: BaseException, *, beim_speichern: bool = False) -> tuple[str, str]:
    """(Kürzel, technische Angabe) für eine Ausnahme der Aufnahme.

    `beim_speichern`: Der Abruf gelang, das Schreiben ins Gedächtnis scheiterte.
    """
    technik = _klassen(fehler)
    # Eigene Meldungen ohne Ursache stammen aus Kingfisher selbst und dürfen mit; Meldungen mit Ursache tragen den Text
    # des Servers („IMAP-Zugriff fehlgeschlagen: …“) und bleiben draußen.
    if isinstance(fehler, MailError) and fehler.__cause__ is None and str(fehler):
        technik += f': {str(fehler)[:160]}'
    if beim_speichern:
        return ('speichern' if isinstance(fehler, (sqlite3.Error, OSError)) else 'unbekannt'), technik
    ursache = fehler.__cause__ if isinstance(fehler, MailError) and fehler.__cause__ is not None else fehler
    if isinstance(ursache, (OSError, imaplib.IMAP4.abort)):  # auch Zeitüberschreitung und TLS
        return 'postfach_schweigt', technik
    if isinstance(ursache, imaplib.IMAP4.error):
        return 'abgelehnt', technik
    eigene = str(fehler) if isinstance(fehler, MailError) else ''
    if isinstance(fehler, MailboxGenerationChanged) or any(teil in eigene for teil in _KENNUNG):
        return 'kennung', technik
    if 'nicht gefunden' in eigene:
        return 'nicht_gefunden', technik
    if isinstance(fehler, (MailError, ValueError, UnicodeError, LookupError)):
        return 'unlesbar', technik
    return 'unbekannt', technik


def haeufigster(je_grund: dict[str, int]) -> str | None:
    """Der Grund, der die meisten Mails betrifft (bei Gleichstand der erste in `SATZ`)."""
    if not je_grund:
        return None
    reihenfolge = list(SATZ)
    return max(je_grund, key=lambda k: (je_grund[k], -reihenfolge.index(k) if k in reihenfolge else -len(reihenfolge)))


__all__ = ['SATZ', 'einordnen', 'haeufigster']
