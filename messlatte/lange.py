"""Lange Quellen: dieselbe Welt, aber Mails und Transkripte in der Länge des Alltags.

Die Quellen der Welt sind kurz (Mails im Mittel unter 300, Transkripte unter 900 Zeichen). Echte Mails haben 2 bis 4 KB,
Transkripte 20 bis 100 KB: Signaturblock, Haftungsausschluss, zitierte Vor-Mail, Small Talk. Dann ist das Zeichenbudget
des Kontexts nach zehn Quellen voll, und was das Modell sieht, sind ganze Mails samt Zitat. Diese Stufe füllt jede
Mail auf `MAIL_ZEICHEN` und jedes Transkript auf `TRANSKRIPT_ZEICHEN` Zeichen auf, **ohne die Pflichtaussagen zu ändern**:

* Der Originaltext bleibt wörtlich erhalten. Bei einer Mail steht er vorn (neuer Text oben, dann Signatur, Haftungsausschluss
  und die zitierte Vor-Mail), bei einem Transkript in der Mitte (Begrüßung und Small Talk davor, Abschweifungen danach).
* Das Füllmaterial entsteht aus dem Wortschatz des Rauschens (`rauschen.py`: gleiche Orte, Themen, Vornamen in
  belanglosen Sätzen) und wird wie dort gegen alle Pflicht- und verbotenen Aussagen, vollen Personennamen und Adressen der
  Welt geprüft; ein Satz mit einem Treffer wird neu gezogen. Die Mengen der Quellen, in denen eine Pflicht- oder verbotene
  Aussage steht, bleiben damit unverändert (Test).
* Deterministisch: gleicher `seed`, gleiche Quellen. Der Zufall je Quelle hängt an Startwert und Kennung, nicht an der
  Reihenfolge; Rauschen und Weltquellen werden gleich behandelt.

Notizen und Termine bleiben, wie sie sind (Notizen sind im Alltag kurz, Termine tragen keinen Fließtext).

**Grenzen:** Das Füllmaterial ist gleichförmiger als echte Post. Es sagt, ob Auswahl und Budget mit langen Quellen
zurechtkommen, nicht, wie gut sie mit den Eigenheiten echter Mails umgehen (dafür `python -m messlatte lokal`).
"""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Sequence

from . import rauschen
from .bewertung import normalisiere
from .daten import Mail, Quelle, Transkript, Welt

MAIL_ZEICHEN = 3_000
TRANSKRIPT_ZEICHEN = 30_000
#: Ein Absatz des Füllmaterials ist höchstens so lang (das Arbeitsgedächtnis wertet Blöcke bis 4.000 Zeichen aus).
MAX_ABSATZ = 1_400

_DISCLAIMER = ('Diese E-Mail und ihre Anhänge sind vertraulich und ausschließlich für den genannten Empfänger bestimmt. '
               'Wenn Sie nicht der richtige Adressat sind, informieren Sie uns bitte umgehend und löschen Sie die Nachricht. '
               'Jede unbefugte Weitergabe ist untersagt.')
_ZITAT_ZEILEN = [
    'Hallo {vorname},', 'hast du diese Woche Zeit für ein kurzes Telefonat zum Thema {thema}?',
    'Ich bin flexibel und in {ort} unterwegs.', 'Anbei noch die Unterlagen vom letzten Mal, falls du sie brauchst.',
    'Beim Thema {thema} bin ich mir noch nicht sicher, wir sollten das gemeinsam anschauen.',
    'Melde dich einfach, wenn es bei dir passt.', 'Danke und viele Grüße', 'Kurze Rückfrage zu {thema}:',
    'Die Abstimmung mit {organisation} läuft, ich halte dich auf dem Laufenden.',
    'Es gibt noch keine neuen Nachrichten, ich schreibe, sobald sich etwas tut.', 'Schöne Grüße aus {ort}',
    'Das Protokoll schicke ich dir morgen, heute komme ich nicht mehr dazu.', 'Bis bald',
    'Hast du eigentlich schon etwas von {organisation} gehört?', 'Ich wollte nur kurz nachfragen, ob alles angekommen ist.',
]
_SMALLTALK = [
    'Guten Morgen zusammen, hört man mich gut?', 'Ja, ich höre Sie. Bei mir ruckelt das Bild ein bisschen.',
    'Wie war die Anreise? In {ort} war heute früh ziemlich viel Verkehr.', 'Alles gut, ich bin mit der Bahn gekommen.',
    'Wir warten noch kurz, dann sind alle da. Möchte jemand einen Kaffee?', 'Gern, mit Milch bitte.',
    'Das Wetter ist gerade wirklich umschlagend, bei uns hat es heute Nacht geregnet.',
    'Kurz zur Technik: Ich teile gleich den Bildschirm, sagen Sie bitte, wenn etwas nicht zu sehen ist.',
    'Ich habe noch eine Frage zum Thema {thema}, aber die hat Zeit bis später.',
    'Bei {organisation} ist übrigens gerade viel los, das kennen Sie sicher.', 'Ja, die Woche ist voll.',
    'Dann fangen wir an. Zuerst kurz die Runde: Wer ist heute dabei?', 'Kurze Pause, ich hole nur schnell meine Unterlagen.',
    'Wir kommen auf {thema} noch einmal zurück, das ist heute aber nicht der Schwerpunkt.',
    'Vielen Dank für Ihre Zeit, ich melde mich, sobald ich mehr weiß.', 'Gern, bis zum nächsten Mal.',
    'Hat jemand die Folien vom letzten Termin noch? Ich finde sie gerade nicht.',
    'Die Leitung ist heute nicht die beste, falls es hakt, rufe ich kurz an.',
    'Noch etwas Organisatorisches: Der Raum in {ort} ist nächste Woche anders belegt.',
]
_SPRECHER = ('A', 'B', 'C', 'D')


def _sauber(gesperrt: Sequence[str], *texte: str) -> bool:
    gesamt = normalisiere(' '.join(texte))
    return not any(g in gesamt for g in gesperrt)


class _Fueller:
    """Erzeugt sauberes Füllmaterial aus dem Wortschatz des Rauschens, je Quelle mit eigenem Zufall."""

    def __init__(self, welten: Sequence[Welt], seed: int):
        self.seed = seed
        self.vornamen, self.nachnamen, self.orte = rauschen.woerter(welten)
        self.gesperrt = rauschen.sperrliste(welten)

    def _slots(self, rng: random.Random) -> dict:
        return {'vorname': rng.choice(self.vornamen), 'nachname': rng.choice(self.nachnamen), 'ort': rng.choice(self.orte),
                'thema': rng.choice(rauschen.THEMEN), 'organisation': rng.choice(rauschen.ORGANISATIONEN)}

    def satz(self, rng: random.Random, vorlagen: Sequence[str]) -> str:
        """Ein Satz aus einer Vorlage; ein Treffer auf eine gesperrte Aussage oder einen vollen Namen zieht neu."""
        for _ in range(30):
            slots = self._slots(rng)
            satz = rng.choice(vorlagen).format(**slots)
            if _sauber(self.gesperrt, satz, f"{slots['vorname']} {slots['nachname']}"):
                return satz
        return 'Dazu später mehr.'

    def signatur(self, rng: random.Random) -> str:
        for _ in range(30):
            slots = self._slots(rng)
            zeilen = ['--', f"{slots['vorname']} {slots['nachname']}", f"{slots['organisation']} {slots['ort']} GmbH",
                      f'Tel. +49 {rng.randint(100, 999)} {rng.randint(1000000, 9999999)}',
                      f"www.{slots['organisation'].lower()}-{slots['ort'].lower()}.example",
                      f"Sitz: {slots['ort']}, Amtsgericht {slots['ort']}, HRB {rng.randint(10000, 99999)}"]
            if _sauber(self.gesperrt, *zeilen):
                return '\n'.join(zeilen)
        return '--\nAlltag GmbH'

    def zitat(self, rng: random.Random, mail: Mail, ziel: int) -> str:
        """Die zitierte Vor-Mail: Kopfzeile und `>`-Zeilen, ein Block ohne Leerzeile, auf `ziel` Zeichen gekürzt."""
        slots = self._slots(rng)
        kopf = (f"Am {rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{mail.zeit.year - 1} um "
                f"{rng.randint(7, 18):02d}:{rng.choice(('00', '15', '30', '45'))} schrieb "
                f"{slots['vorname']} {slots['nachname']}:")
        if not _sauber(self.gesperrt, kopf):
            kopf = 'Am 01.01. schrieb eine Kollegin:'
        zeilen, tiefe = [kopf], '>'
        while sum(len(z) + 1 for z in zeilen) < ziel:
            zeile = self.satz(rng, _ZITAT_ZEILEN)
            if rng.random() < 0.08:
                tiefe = '>>' if tiefe == '>' else '>'
            zeilen.append(f'{tiefe} {zeile}')
        return '\n'.join(zeilen)

    def absatz(self, rng: random.Random, vorlagen: Sequence[str], sprecher: bool) -> str:
        teile = []
        while sum(len(t) + 1 for t in teile) < rng.randint(350, MAX_ABSATZ):
            zeile = self.satz(rng, vorlagen)
            teile.append(f'{rng.choice(_SPRECHER)}: {zeile}' if sprecher else zeile)
        return '\n'.join(teile)


def _rng(seed: int, kennung: str) -> random.Random:
    return random.Random(f'{seed}:{kennung}')  # String-Startwerte sind in Python stabil (kein Hash-Zufall)


def _kuerzen(text: str, grenze: int) -> str:
    """Höchstens `grenze` Zeichen, am letzten Zeilenende davor abgeschnitten."""
    if len(text) <= grenze:
        return text
    kopf = text[:grenze]
    schnitt = kopf.rfind('\n')
    return kopf[:schnitt] if schnitt > grenze // 2 else kopf


def lange_mail(mail: Mail, fueller: _Fueller, ziel: int, seed: int) -> Mail:
    """Der Text der Mail bleibt vorn; dahinter Signatur, Haftungsausschluss und die zitierte Vor-Mail bis `ziel` Zeichen."""
    if len(mail.text) >= ziel:
        return mail
    rng = _rng(seed, mail.id)
    teile = [mail.text.rstrip(), fueller.signatur(rng), _DISCLAIMER]
    kopf = '\n\n'.join(teile)
    rest = ziel - len(kopf) - 2
    if rest > 120:
        kopf += '\n\n' + _kuerzen(fueller.zitat(rng, mail, rest), rest)
    return replace(mail, text=_kuerzen(kopf, ziel))


def langes_transkript(transkript: Transkript, fueller: _Fueller, ziel: int, seed: int) -> Transkript:
    """Der Text des Transkripts steht in der Mitte: davor Begrüßung und Small Talk, danach Abschweifungen."""
    if len(transkript.text) >= ziel:
        return transkript
    rng = _rng(seed, transkript.id)
    fehlt = ziel - len(transkript.text) - 4
    davor_ziel = int(fehlt * rng.uniform(0.15, 0.35))
    davor, danach = [], []
    while sum(len(t) + 2 for t in davor) < davor_ziel:
        davor.append(fueller.absatz(rng, _SMALLTALK, sprecher=True))
    while sum(len(t) + 2 for t in danach) < fehlt - sum(len(t) + 2 for t in davor):
        danach.append(fueller.absatz(rng, _SMALLTALK, sprecher=True))
    text = '\n\n'.join([*davor, transkript.text.strip(), *danach])
    if len(text) > ziel:
        # Überschuss am Ende abschneiden: Das Original steht weiter vorn und bleibt ganz.
        text = _kuerzen(text, ziel)
    return replace(transkript, text=text)


def aufblasen(quellen: Sequence[Quelle], welten: Sequence[Welt], seed: int = 1, *, mail: int = MAIL_ZEICHEN,
              transkript: int = TRANSKRIPT_ZEICHEN) -> tuple[Quelle, ...]:
    """Mails auf `mail`, Transkripte auf `transkript` Zeichen bringen; alles andere bleibt. Reihenfolge und Kennungen bleiben."""
    fueller = _Fueller(welten, seed)
    ergebnis: list[Quelle] = []
    for quelle in quellen:
        if isinstance(quelle, Mail):
            ergebnis.append(lange_mail(quelle, fueller, mail, seed))
        elif isinstance(quelle, Transkript):
            ergebnis.append(langes_transkript(quelle, fueller, transkript, seed))
        else:
            ergebnis.append(quelle)
    return tuple(ergebnis)
