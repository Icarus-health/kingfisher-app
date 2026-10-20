"""Zeitzonen aus iCalendar-Dateien (`TZID`).

Die meisten Kalender schreiben IANA-Namen (`Europe/Berlin`); die kennt `zoneinfo`
(mit dem Paket `tzdata` auch ohne Zeitzonendatenbank des Betriebssystems).
Outlook und Exchange schreiben dagegen Windows-Namen (`W. Europe Standard Time`).
Für die häufigsten steht unten eine kleine Zuordnung.

Beleg der Zuordnung: Unicode CLDR, `common/supplemental/windowsZones.xml`, je
Windows-Zone der Eintrag für das Gebiet „001“ (die Hauptzone). Abgeglichen mit
der daraus erzeugten Tabelle `tzlocal/windows_tz.py` (tzlocal 5.3.1). Einige
Ziele sind ältere IANA-Namen (`Asia/Calcutta`, `Europe/Kiev`), so wie CLDR sie
führt; `tzdata` kennt sie als Verweise.

Ein Name, der weder IANA noch in der Tabelle ist (etwa „Customized Time Zone“
oder „(UTC+01:00) Amsterdam, Berlin, …“), gilt als unbekannt: `zone` gibt dann
None zurück, und der Aufrufer wendet seine Rückfallregel an. Geraten wird nicht.
"""
from __future__ import annotations

from datetime import tzinfo
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

WINDOWS_ZONEN: dict[str, str] = {
    # Europa
    "W. Europe Standard Time": "Europe/Berlin",
    "Romance Standard Time": "Europe/Paris",
    "Central Europe Standard Time": "Europe/Budapest",
    "Central European Standard Time": "Europe/Warsaw",
    "GMT Standard Time": "Europe/London",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "E. Europe Standard Time": "Europe/Chisinau",
    "FLE Standard Time": "Europe/Kiev",
    "GTB Standard Time": "Europe/Bucharest",
    "Kaliningrad Standard Time": "Europe/Kaliningrad",
    "Belarus Standard Time": "Europe/Minsk",
    "Russian Standard Time": "Europe/Moscow",
    "Turkey Standard Time": "Europe/Istanbul",
    "Azores Standard Time": "Atlantic/Azores",
    "UTC": "Etc/UTC",
    # Amerika
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix",
    "Pacific Standard Time": "America/Los_Angeles",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Atlantic Standard Time": "America/Halifax",
    "Newfoundland Standard Time": "America/St_Johns",
    "Canada Central Standard Time": "America/Regina",
    "Central Standard Time (Mexico)": "America/Mexico_City",
    "SA Pacific Standard Time": "America/Bogota",
    "Pacific SA Standard Time": "America/Santiago",
    "Argentina Standard Time": "America/Buenos_Aires",
    "E. South America Standard Time": "America/Sao_Paulo",
    # Afrika, Asien, Ozeanien
    "South Africa Standard Time": "Africa/Johannesburg",
    "Egypt Standard Time": "Africa/Cairo",
    "Morocco Standard Time": "Africa/Casablanca",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "Israel Standard Time": "Asia/Jerusalem",
    "Arab Standard Time": "Asia/Riyadh",
    "Arabian Standard Time": "Asia/Dubai",
    "Iran Standard Time": "Asia/Tehran",
    "Pakistan Standard Time": "Asia/Karachi",
    "India Standard Time": "Asia/Calcutta",
    "SE Asia Standard Time": "Asia/Bangkok",
    "Singapore Standard Time": "Asia/Singapore",
    "China Standard Time": "Asia/Shanghai",
    "Taipei Standard Time": "Asia/Taipei",
    "Korea Standard Time": "Asia/Seoul",
    "Tokyo Standard Time": "Asia/Tokyo",
    "W. Australia Standard Time": "Australia/Perth",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "E. Australia Standard Time": "Australia/Brisbane",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "New Zealand Standard Time": "Pacific/Auckland",
}
"""Windows-Name → IANA-Name (CLDR `windowsZones.xml`, Gebiet „001“)."""


@lru_cache(maxsize=1)
def _iana_namen() -> frozenset[str]:
    """Die IANA-Namen, die als Zone eines Termins gelten.

    Aus der Liste des Pakets `tzdata` (auch ältere Namen wie `Europe/Kiev`,
    `US/Eastern`), ohne `Factory`. Nicht dazu gehören Dateien der
    Zeitzonendatenbank des Rechners wie `localtime` oder `posixrules` und die
    Unterbäume `posix/` und `right/` (mit Schaltsekunden): `ZoneInfo` nähme sie
    an, aber sie beschreiben den Rechner, nicht den Termin.
    """
    try:
        namen = set(files("tzdata").joinpath("zones").read_text(encoding="utf-8").split())
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        namen = {name for name in available_timezones() if not name.startswith(("posix/", "right/"))}
    return frozenset(namen - {"Factory", "localtime", "posixrules"})


def _zoneinfo(name: str) -> tzinfo | None:
    if name not in _iana_namen():
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def zone(tzid: str | None) -> tzinfo | None:
    """Die Zeitzone zu einem `TZID`-Wert, oder None, wenn der Name unbekannt ist.

    libical und ältere Mozilla-Kalender stellen dem IANA-Namen ihren
    Herausgeber voran: `/freeassociation.sourceforge.net/Europe/Berlin`,
    `/mozilla.org/20070129_1/Europe/Berlin`. Bei einem Namen, der mit „/“
    beginnt, gelten deshalb auch seine letzten drei oder zwei Pfadteile als
    IANA-Name (`Europe/Berlin`, `America/Argentina/Buenos_Aires`). Steht keiner
    darin, bleibt die Zone unbekannt; ein einzelner Teil wie `localtime` aus
    `/etc/localtime` wäre die Zone des Rechners, nicht die des Termins.
    """
    name = (tzid or "").strip().strip('"').strip()
    if not name:
        return None
    gefunden = _zoneinfo(WINDOWS_ZONEN.get(name, name))
    if gefunden is None and name.startswith("/"):
        teile = [teil for teil in name.split("/") if teil]
        for anzahl in (3, 2):
            if len(teile) > anzahl and (gefunden := _zoneinfo("/".join(teile[-anzahl:]))) is not None:
                break
    return gefunden


__all__ = ["WINDOWS_ZONEN", "zone"]
