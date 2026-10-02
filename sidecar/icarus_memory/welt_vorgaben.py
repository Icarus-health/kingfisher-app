"""Vorgegebene Nachrichtenquellen zum Anklicken (M3, `docs/47-einstellungen.md`).

Niemand soll eine Feed-Adresse tippen müssen. Diese Liste ist die Auswahl, die die Oberfläche zeigt; ein Klick fügt
die Quelle hinzu (`welt_briefing_routes`), ein zweiter entfernt sie. Erst beim Hinzufügen wird die Adresse abgerufen,
und zwar von `WeltDienst.feed_hinzufuegen`, das sie wie jede eigene Adresse prüft (öffentlich, https, einmal zur Probe
lesen). Ein Feed, der nicht mehr antwortet, wird nicht eingetragen; der Grund steht in einem Satz.

**Stand der Liste: `STAND`. Keine der Adressen wurde abgerufen.** Sie wurden von Hand aus dem Wissen über die Anbieter
zusammengestellt, weil der Container, in dem diese Liste entstand, das Netz nicht erreicht. `ABGERUFEN` sagt das
ausdrücklich; ein Test prüft nur die Form (https, öffentlicher Name, eindeutig), nicht die Erreichbarkeit. Wer die
Liste erneuert, ruft jede Adresse einmal ab, trägt dann das Datum ein und setzt `ABGERUFEN` auf das Datum des Abrufs.

Nicht aufgenommen: der dpa-Ticker. Die Agentur bietet ihren Ticker nicht als öffentlichen Feed an (Kunden erhalten ihn
über Zugangsdaten); eine Adresse dafür wäre geraten.
"""
from __future__ import annotations

from typing import Final, TypedDict

STAND: Final = '2026-09-30'
"""Tag, an dem die Liste zusammengestellt wurde."""

ABGERUFEN: Final[str | None] = None
"""Tag, an dem alle Adressen zuletzt abgerufen und als Feed erkannt wurden. `None`: noch nie."""


class Vorgabe(TypedDict):
    id: str
    label: str
    url: str
    beschreibung: str


VORGABEN: Final[list[Vorgabe]] = [
    {'id': 'tagesschau', 'label': 'tagesschau',
     'url': 'https://www.tagesschau.de/index~rss2.xml', 'beschreibung': 'Nachrichten der ARD'},
    {'id': 'deutschlandfunk', 'label': 'Deutschlandfunk',
     'url': 'https://www.deutschlandfunk.de/nachrichten-100.rss', 'beschreibung': 'Nachrichten im Radio'},
    {'id': 'heise', 'label': 'heise online',
     'url': 'https://www.heise.de/rss/heise-atom.xml', 'beschreibung': 'Technik und Netz'},
    {'id': 'zeit', 'label': 'ZEIT ONLINE',
     'url': 'https://newsfeed.zeit.de/index', 'beschreibung': 'Politik, Wirtschaft, Gesellschaft'},
]
"""Die Auswahl in der Reihenfolge, in der die Oberfläche sie zeigt."""


def mit_zustand(feeds: list[dict]) -> list[dict]:
    """Die Vorgaben, je mit `gewaehlt` und der Kennung des Feeds (`feed_id`), falls der Nutzer sie schon hinzugefügt hat.

    So kann die Oberfläche mit einem Knopf je Quelle hinzufügen und wieder entfernen.
    """
    nach_adresse = {f.get('url'): f for f in feeds}
    ergebnis = []
    for vorgabe in VORGABEN:
        feed = nach_adresse.get(vorgabe['url'])
        ergebnis.append({**vorgabe, 'gewaehlt': feed is not None, 'feed_id': feed.get('id') if feed else None})
    return ergebnis
