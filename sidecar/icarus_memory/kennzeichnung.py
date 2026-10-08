"""Namensvettern und Zeiträume im Antwortkontext kennzeichnen (Nachtrag zu E2).

Seit C3 weiß Kingfisher, dass zwei Menschen gleichen Namens verschieden sind („Alex Winter“ beim
Catering und im Institut), und die Suche liest Zeiträume der Frage. Im Kontext des Modells stand das
aber nicht dran: Die Mail des anderen Alex Winter oder die Mail von vor drei Monaten stand gleichrangig
neben den passenden. Dieses Modul sagt es ausdrücklich, ohne Modell und ohne etwas zu entfernen:

* `andere_person`: Die Frage meint eindeutig eine Person (ein Wort der Frage, das nur zu einer der
  gleichnamigen passt, siehe `personenfrage.gemeinte_unter_namensvettern`), und die Quelle gehört
  einem anderen Menschen gleichen Namens (Adresse des anderen). Ist die Person **nicht** eindeutig,
  bleibt es bei der Rückfrage (E1); hier entsteht keine neue.
* `ausserhalb_zeitraum`: Die Frage nennt einen Zeitraum („letzte Woche“, „im Frühjahr“, „im Juli 2026“),
  und die Quelle liegt davor oder danach. Ein Termin gilt nach seinem Beginn, eine Mail nach ihrem
  eigenen Datum (`occurred_at`). Eine Quelle ohne eigenes Datum ist nie „außerhalb“.

Gekennzeichnete Quellen stehen im Kontext hinter den passenden (wie Überholtes, `akten_kontext`), das Modell
bekommt einen Satz dazu, und die Satzprüfung (`satzantwort.pruefe_satz`) lässt einen Satz, der sich nur auf
solche Quellen stützt, nur durch, wenn er es ausdrücklich sagt („ein anderer Alex Winter“, „außerhalb des
Zeitraums“).

Der Rahmen (wer gemeint ist, welcher Zeitraum) wird mit der Antwort gespeichert und beim Anzeigen
daraus gerechnet, nicht neu erraten: Die Antwort von gestern meint denselben Zeitraum wie gestern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .identitaet import nennungen

ANDERE_PERSON = 'andere_person'
AUSSERHALB = 'ausserhalb_zeitraum'
ARTEN = (ANDERE_PERSON, AUSSERHALB)
RAHMEN_VERSION = 1
#: Höchstens so viele gleichnamige Personen und Namensvettern je Name im gespeicherten Rahmen.
MAX_ANDERE = 6
MAX_NAMEN = 4


@dataclass(frozen=True)
class Gemeint:
    """Ein Name der Frage, der mehreren Menschen gehört, und wer davon gemeint ist."""

    name: str
    adresse: str
    andere: tuple[str, ...]
    """Adressen der Namensvettern."""

    def als_dict(self) -> dict[str, Any]:
        return {'name': self.name, 'adresse': self.adresse, 'andere': list(self.andere)}

    @classmethod
    def aus_dict(cls, roh: Any) -> 'Gemeint | None':
        if (not isinstance(roh, dict) or set(roh) != {'name', 'adresse', 'andere'} or not isinstance(roh['name'], str)
                or not isinstance(roh['adresse'], str) or not roh['adresse'] or not isinstance(roh['andere'], list)
                or not roh['andere'] or len(roh['andere']) > MAX_ANDERE
                or any(not isinstance(a, str) or not a for a in roh['andere'])):
            return None
        return cls(roh['name'], roh['adresse'], tuple(roh['andere']))


@dataclass(frozen=True)
class Zeitraum:
    """Der Zeitraum der Frage [von, bis) mit seiner Beschriftung („der letzten Woche“)."""

    von: datetime
    bis: datetime
    beschriftung: str

    def als_dict(self) -> dict[str, Any]:
        return {'von': self.von.isoformat(), 'bis': self.bis.isoformat(), 'beschriftung': self.beschriftung}

    @classmethod
    def aus_dict(cls, roh: Any) -> 'Zeitraum | None':
        if (not isinstance(roh, dict) or set(roh) != {'von', 'bis', 'beschriftung'}
                or any(not isinstance(roh[k], str) for k in roh)):
            return None
        try:
            von, bis = datetime.fromisoformat(roh['von']), datetime.fromisoformat(roh['bis'])
        except ValueError:
            return None
        if von.tzinfo is None or bis.tzinfo is None or not von < bis:
            return None
        return cls(von, bis, roh['beschriftung'][:60])


@dataclass(frozen=True)
class Rahmen:
    """Was die Frage festlegt: gemeinte Personen unter Namensvettern und ein Zeitraum, je optional."""

    personen: tuple[Gemeint, ...] = ()
    zeitraum: Zeitraum | None = None

    def leer(self) -> bool:
        return not self.personen and self.zeitraum is None

    def als_dict(self) -> dict[str, Any]:
        return {'version': RAHMEN_VERSION, 'personen': [p.als_dict() for p in self.personen],
                'zeitraum': self.zeitraum.als_dict() if self.zeitraum else None}

    @classmethod
    def aus_dict(cls, roh: Any) -> 'Rahmen | None':
        """Ein gespeicherter Rahmen; None, wenn irgendetwas nicht stimmt (dann gilt die Antwort als veraltet)."""
        if (not isinstance(roh, dict) or set(roh) != {'version', 'personen', 'zeitraum'}
                or roh['version'] != RAHMEN_VERSION or not isinstance(roh['personen'], list)
                or len(roh['personen']) > MAX_NAMEN):
            return None
        personen = [Gemeint.aus_dict(p) for p in roh['personen']]
        zeitraum = Zeitraum.aus_dict(roh['zeitraum']) if roh['zeitraum'] is not None else None
        if any(p is None for p in personen) or (roh['zeitraum'] is not None and zeitraum is None):
            return None
        return cls(tuple(personen), zeitraum)  # type: ignore[arg-type]


LEER = Rahmen()


@dataclass(frozen=True)
class Kennzeichen:
    """Eine Kennzeichnung einer Quelle: die Art und, was sie begründet."""

    art: str
    wert: str
    """Bei `andere_person` die Adresse des anderen, bei `ausserhalb_zeitraum` das Datum der Quelle (ISO)."""
    name: str = ''
    """Bei `andere_person` der gemeinsame Name, bei `ausserhalb_zeitraum` der Zeitraum der Frage."""
    gemeint: str = ''
    """Bei `andere_person` die Adresse der gemeinten Person."""

    def fuer_modell(self) -> dict[str, str]:
        """Das Feld in der Zeile des Kontexts (`andere_person` oder `ausserhalb_zeitraum`)."""
        if self.art == ANDERE_PERSON:
            return {'name': self.name, 'adresse_dieser_person': self.wert, 'gemeinte_adresse': self.gemeint}
        return {'datum_der_quelle': self.wert, 'gefragter_zeitraum': self.name}

    def text(self) -> str:
        """Für die Anzeige (Zitatmodus, Belegliste)."""
        if self.art == ANDERE_PERSON:
            return f'Andere Person gleichen Namens ({self.name}, {self.wert})'
        return f'Außerhalb des gefragten Zeitraums ({self.name}): Quelle vom {_datum(self.wert)}'


def _datum(iso: str) -> str:
    return f'{iso[8:10]}.{iso[5:7]}.{iso[0:4]}'


def rahmen_der_frage(gemeinte, zeitraum: Zeitraum | None) -> Rahmen:
    """Der Rahmen aus `personenfrage.gemeinte_unter_namensvettern` und dem Zeitraum der Frage."""
    personen = [Gemeint(erwaehnung.begriff, gemeint.adresse, tuple(a.adresse for a in andere)[:MAX_ANDERE])
                for erwaehnung, gemeint, andere in gemeinte][:MAX_NAMEN]
    return Rahmen(tuple(personen), zeitraum)


def kennzeichen(episode: Any, rahmen: Rahmen) -> tuple[Kennzeichen, ...]:
    """Die Kennzeichnungen einer Quelle im Rahmen der Frage; leer, wenn sie zur Frage passt.

    Eine Quelle gehört einem Namensvetter, wenn sie dessen Adresse trägt und nicht die der gemeinten Person
    (trägt sie beide, ist sie nicht eindeutig fremd). Nur Adressen zählen: Ein bloßer Name ohne Adresse
    beweist nichts, geraten wird nie.
    """
    if rahmen.leer():
        return ()
    marken: list[Kennzeichen] = []
    if rahmen.personen:
        adressen = {n.adresse for n in nennungen(episode) if n.adresse}
        for person in rahmen.personen:
            fremd = [a for a in person.andere if a in adressen]
            if fremd and person.adresse not in adressen:
                marken.append(Kennzeichen(ANDERE_PERSON, fremd[0], person.name, person.adresse))
    if rahmen.zeitraum is not None:
        moment = episode.occurred_at
        if moment is not None and not rahmen.zeitraum.von <= moment < rahmen.zeitraum.bis:
            marken.append(Kennzeichen(AUSSERHALB, moment.date().isoformat(), rahmen.zeitraum.beschriftung))
    return tuple(marken)


def hinweise_fuer_modell(marken: tuple[Kennzeichen, ...]) -> dict[str, Any]:
    """Die Felder für die Zeile einer Quelle im Kontext: `andere_person` und `ausserhalb_zeitraum`, sofern zutreffend."""
    felder: dict[str, Any] = {}
    for marke in marken:
        felder.setdefault(marke.art, []).append(marke.fuer_modell())
    return {art: liste[0] if art == AUSSERHALB else liste for art, liste in felder.items()}


# -- Satzprüfung ---------------------------------------------------------------------------

_NENNT_ZEITRAUM = re.compile(
    r'au(?:ß|ss)erhalb|nicht\s+(?:mehr\s+)?(?:im|in)\s+(?:dem\s+)?(?:gefragten\s+)?zeitraum|'
    r'vor\s+dem\s+(?:gefragten\s+)?zeitraum|nach\s+dem\s+(?:gefragten\s+)?zeitraum', re.I)
_NENNT_VETTER = re.compile(r'namensvetter|gleichnamig|nicht\s+(?:derselbe|dieselbe|der\s+gleiche|die\s+gleiche)\b|'
                           r'ander(?:e|er|en|em|es)\s+(?:person|mensch)', re.I)


def benennt(satz: str, marke: Kennzeichen) -> bool:
    """Sagt der Satz ausdrücklich, dass die Quelle zu einer anderen Person gehört oder außerhalb des Zeitraums liegt?

    Für „andere Person“ zählt „ein anderer Alex Winter“ (das Wort „anderer“ vor dem Namen), „Namensvetter“,
    „gleichnamig“ oder „nicht derselbe“; für den Zeitraum „außerhalb des Zeitraums“ und Verwandtes.
    """
    if marke.art == AUSSERHALB:
        return bool(_NENNT_ZEITRAUM.search(satz))
    if _NENNT_VETTER.search(satz):
        return True
    return bool(marke.name and re.search(r'ander\w*\s+' + re.escape(marke.name), satz, re.I))


__all__ = ['ANDERE_PERSON', 'ARTEN', 'AUSSERHALB', 'Gemeint', 'Kennzeichen', 'LEER', 'Rahmen', 'Zeitraum', 'benennt',
           'hinweise_fuer_modell', 'kennzeichen', 'rahmen_der_frage']
