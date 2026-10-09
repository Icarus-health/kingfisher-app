"""Beteiligte einer Quelle: Name, Adresse und Rolle.

Eine Mail hat einen Absender, Empfänger (An) und Mitleser (Cc). Bisher blieb
nur der Absender übrig; wem der Nutzer selbst geschrieben hat, kam nirgends
vor. Dieses Modul beschreibt die Beteiligten so, wie sie in den Metadaten der
Episode stehen — und nichts weiter. Wer damit gemeint ist, entscheidet
`identitaet.py`.

Jeder Eintrag ist ein einfaches Wörterbuch:

    {"name": "Anna Keller", "adresse": "anna@x.example", "rolle": "von", "ich": False}

`rolle` ist `von`, `an`, `cc` oder `bcc`. `ich` heißt: Die Adresse gehört einem
eigenen Konto des Nutzers. Eine eigene Adresse ist kein fremder Mensch und darf
in keiner Personenliste als Kontakt erscheinen.

Die Textform („Anna Keller <anna@x.example>“) steht weiter in
`Episode.participants`. Damit bleiben Suche, Anzeige und ältere Auswertungen
unverändert lesbar; die Wörterbücher tragen zusätzlich die Rolle.
"""

from __future__ import annotations

import re
import unicodedata
from email.errors import HeaderParseError
from email.header import decode_header
from email.utils import formataddr, getaddresses
from typing import Any, Iterable

from .episodes import mail_address

ROLLEN = ("von", "an", "cc", "bcc")

_SPITZE = re.compile(r"\s*<[^<>]*>\s*$")


def anzeigename(wert: Any, *, kopfzeile: bool = False) -> str:
    """Der Name vor der Adresse: „Keller, Anna“ aus „Keller, Anna <a@x>“.

    Ohne Namen (nur eine Adresse) bleibt es leer, statt die Adresse als Namen
    auszugeben. Nur ausdrücklich als Mailkopf bekannte Namen werden nach
    RFC 2047 dekodiert; Namen und Textstellen anderer Quellen bleiben wörtlich.
    """
    text = _SPITZE.sub("", str(wert or "")).strip().strip('"').strip()
    if kopfzeile:
        try:
            dekodiert = "".join(teil.decode(kodierung or "ascii", errors="strict")
                               if isinstance(teil, bytes) else teil
                               for teil, kodierung in decode_header(text))
            # Defekte oder steuernde Kopfdaten bleiben sichtbar, statt einen
            # Ersatznamen oder zusätzliche Kopfzeilen daraus zu erzeugen.
            if not any(unicodedata.category(zeichen) in {"Cc", "Cf", "Cs"} for zeichen in dekodiert):
                text = dekodiert.strip()
        except (LookupError, UnicodeError, ValueError, HeaderParseError):
            pass
        # Bei schon unkodierten Unicode-Köpfen ist die Rohfassung kein sicherer
        # Ersatz. Die Adresse bleibt der Anker, ein steuernder Name entfällt.
        if any(unicodedata.category(zeichen) in {"Cc", "Cf", "Cs"} for zeichen in text):
            return ""
    return "" if "@" in text else text


def kontakt(wert: Any, rolle: str, *, eigene: Iterable[str] = ()) -> dict[str, Any] | None:
    """Ein Beteiligter aus einer Textangabe, oder nichts, wenn sie leer ist."""
    if rolle not in ROLLEN:
        raise ValueError(f"Unbekannte Rolle: {rolle}")
    text = str(wert or "").strip()
    if not text:
        return None
    adresse = mail_address(text)
    name = anzeigename(text, kopfzeile=True)
    if not name and not adresse:
        return None
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    return {"name": name, "adresse": adresse, "rolle": rolle,
            "ich": bool(adresse and adresse in selbst)}


def text_form(eintrag: dict[str, Any]) -> str:
    """„Anna Keller <anna@x.example>“, wie `participants` es führt."""
    adresse, name = eintrag.get("adresse") or "", eintrag.get("name") or ""
    if adresse and name:
        return formataddr((name, adresse))
    return adresse or name


def aus_kopfzeilen(werte: Iterable[str], rolle: str, *, eigene: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Alle Beteiligten einer Kopfzeile (`To`, `Cc`, `Bcc`).

    `getaddresses` trennt an den Kommas außerhalb von Anführungszeichen; ein
    Name „Keller, Anna“ bleibt deshalb ein Name, solange der Absender ihn
    korrekt zitiert hat.
    """
    gefunden = []
    for name, adresse in getaddresses(list(werte)):
        eintrag = kontakt(formataddr((name, adresse)) if name else adresse, rolle, eigene=eigene)
        if eintrag:
            gefunden.append(eintrag)
    return gefunden


def fuer_mail(absender: str, empfaenger: Iterable[dict[str, Any]], *,
              eigene: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Absender zuerst, danach An, Cc und Bcc; jeder Mensch höchstens einmal je Rolle.

    Bcc steht nur da, wo der Kopf mitgeliefert wurde. Das ist bei der eigenen
    Kopie in „Gesendet“ der Fall; bei empfangenen Mails fehlt er, weil der
    Absender ihn entfernt hat. Ist bekannt, welche Adressen dem Nutzer gehören,
    zählt Bcc zusätzlich nur bei einer Mail, deren Absender er selbst ist.
    """
    eigene = [a for a in eigene if a]
    ergebnis: list[dict[str, Any]] = []
    von = kontakt(absender, "von", eigene=eigene)
    if von:
        ergebnis.append(von)
    von_ich = bool(von and von["ich"])
    gesehen = {(e["adresse"] or e["name"].casefold(), e["rolle"]) for e in ergebnis}
    for roh in empfaenger or ():
        rolle = roh.get("rolle")
        if rolle not in ("an", "cc", "bcc"):
            continue
        if rolle == "bcc" and eigene and not von_ich:
            continue
        eintrag = kontakt(text_form(roh) or roh.get("adresse") or roh.get("name"), rolle, eigene=eigene)
        if not eintrag:
            continue
        schluessel = (eintrag["adresse"] or eintrag["name"].casefold(), rolle)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ergebnis.append(eintrag)
    return ergebnis


def teilnehmer_texte(kontakte: Iterable[dict[str, Any]], *, absender_text: str = "") -> list[str]:
    """Die Textform aller Beteiligten für `Episode.participants`, ohne Doppelte.

    Der Absender behält seine Schreibweise aus der Kopfzeile unverändert
    (`absender_text`); so bleibt `participants[0]` bei Mails, was es war.

    Die eigene Adresse als **Empfänger** fehlt hier: Sie stünde sonst in jeder
    empfangenen Mail, die Wortsuche fände über „Lea“ jede davon, und niemand
    lernte etwas daraus. In `contacts` bleibt sie erhalten (mit `ich`). Als
    Absender einer eigenen Mail steht sie weiter da: Wer schrieb, gehört dazu.
    """
    texte: list[str] = []
    for eintrag in kontakte:
        if eintrag.get("ich") and eintrag["rolle"] != "von":
            continue
        text = absender_text if eintrag["rolle"] == "von" and absender_text else text_form(eintrag)
        if text and text not in texte:
            texte.append(text)
    return texte


def absender_text(participants: list[str], kontakte: list[dict[str, Any]] | None) -> str:
    """Der Absender einer Mail als Text, ob mit oder ohne Rollenangabe gespeichert.

    Ältere Episoden führen genau einen Beteiligten: den Absender. Neuere tragen
    die Rolle. Wer „der eine Beteiligte“ als Absender liest, muss diese Stelle
    fragen, nicht `participants[0]` raten.
    """
    for eintrag in kontakte or ():
        if eintrag.get("rolle") == "von":
            # Möglichst die Schreibweise aus der Kopfzeile, wie sie gespeichert wurde.
            adresse = eintrag.get("adresse") or ""
            for text in participants:
                if adresse and mail_address(text) == adresse:
                    return text
            return text_form(eintrag)
    if not kontakte and len(participants) == 1:
        return participants[0]
    return ""
