"""Empfänger und Cc für Mails nachtragen, die vor der Rollenangabe aufgenommen wurden.

Bis Etappe C3 blieb von einer Mail nur der Absender als Beteiligter übrig. Aus
dem gespeicherten Rohtext lassen sich An und Cc **nicht** rekonstruieren: Der
Text der Episode ist der Nachrichtenkörper, die Kopfzeilen sind nicht
mitgespeichert. Einzige Quelle ist der Server. Dieses Modul holt die Kopfzeilen
für Mails ohne Rollen erneut, in kleinen Paketen, und ergänzt die Beteiligten
in der vorhandenen Episode. Der Text, sein Digest und der Zustand bleiben
unberührt; eine ausgeschlossene Quelle wird nicht angefasst.

`nachtragen` ist ein Paket und wiederholbar: Was ergänzt ist, kommt beim
nächsten Mal nicht mehr vor. `Lauf` ist der Hintergrundtakt darüber: Er gibt in
kleinen Paketen frei, solange ein Konto verbunden und die Aufnahme aktiv ist,
tritt auf die Bremse, wenn die Einordnung im Rückstau liegt (jeder Nachtrag
ändert den Fingerabdruck und ordnet die Mail neu ein), zählt mit, wie viele
Mails noch offen sind, und endet, wenn nichts mehr zu tun ist.
"""

from __future__ import annotations

import time
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Collection

from . import kontakte
from .episodes import EpisodeError, EpisodeStore, sql_nicht_ignoriert

#: Schutz gegen ein Postfach, das ein Paket nach dem anderen schuldig bleibt.
MAX_PAKET = 200
#: Mails je Hintergrundtakt (alle 30 s). Klein: Jede ergänzte Mail wird neu eingeordnet.
PAKET_IM_TAKT = 10
#: Ab so vielen unverarbeiteten Mails im Rückstau der Einordnung ruht der Nachtrag.
#: Die Aufnahme selbst bremst bei 200; der Nachtrag ist nachrangig und bremst früher.
RUECKSTAU_GRENZE = 50
#: Wie lange eine Mail nach einem Abruffehler ruht, bevor sie erneut versucht wird.
PAUSE_NACH_FEHLER = 3600.0

_OFFEN_BEDINGUNG = (
    f"i.account = ? AND i.status IN ('captured','duplicate') AND {sql_nicht_ignoriert('e')} "
    "AND (json_extract(e.document, '$.contacts') IS NULL "
    "     OR json_extract(e.document, '$.contacts') = '[]')")


def offene(episodes: EpisodeStore, account_id: str, *, limit: int,
           ausser: Collection[str] = ()) -> list[dict[str, Any]]:
    """Aufgenommene Mails eines Kontos ohne Rollenangabe, neueste zuerst.

    `ausser` sind Episoden, die dieser Lauf nicht (mehr) versucht. Eine Episode
    kommt nur einmal vor, auch wenn mehrere Postfachordner auf sie zeigen.
    """
    wieviele = max(1, min(limit, MAX_PAKET))
    with episodes._lock:
        rows = episodes._conn.execute(
            "SELECT i.folder, i.generation, i.uid, i.episode_id FROM mail_intake_items i "
            "JOIN episodes e ON e.id = i.episode_id WHERE " + _OFFEN_BEDINGUNG + " "
            "ORDER BY COALESCE(e.occurred_at, e.recorded_at) DESC, i.episode_id LIMIT ?",
            (account_id, wieviele + len(ausser) + 20)).fetchall()
    gesehen: set[str] = set(ausser)
    ergebnis = []
    for r in rows:
        if r[3] in gesehen:
            continue
        gesehen.add(r[3])
        ergebnis.append({"folder": r[0], "generation": r[1], "uid": r[2], "episode_id": r[3]})
        if len(ergebnis) >= wieviele:
            break
    return ergebnis


def anzahl_offen(episodes: EpisodeStore, account_id: str) -> int:
    """Wie viele Mails des Kontos noch ohne Rollenangabe sind (je Episode einmal)."""
    with episodes._lock:
        return episodes._conn.execute(
            "SELECT COUNT(DISTINCT i.episode_id) FROM mail_intake_items i "
            "JOIN episodes e ON e.id = i.episode_id WHERE " + _OFFEN_BEDINGUNG,
            (account_id,)).fetchone()[0]


def rueckstau(episodes: EpisodeStore, account_id: str, *, bis: int) -> int:
    """Wie viele Mails des Kontos auf ihre (Neu-)Einordnung warten, gezählt bis `bis` + 1.

    Wartend heißt: noch nie eingeordnet oder seit der letzten Einordnung
    geändert (Stützgeneration weicht ab). Genau das erzeugt der Nachtrag selbst.
    """
    with episodes._lock:
        return episodes._conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT i.episode_id FROM mail_intake_items i "
            "JOIN episodes e ON e.id = i.episode_id "
            "LEFT JOIN mail_intake_analysis a ON a.episode_id = e.id "
            f"WHERE i.account = ? AND {sql_nicht_ignoriert('e')} AND i.episode_id IS NOT NULL "
            "AND (a.episode_id IS NULL OR a.generation != e.support_generation) LIMIT ?)",
            (account_id, bis + 1)).fetchone()[0]


def _paket(episodes: EpisodeStore, reader: Any, account_id: str, eintraege: list[dict[str, Any]], *,
           permitted: Callable[[], bool], permission_lock: Any) -> list[tuple[str, str]]:
    """Arbeitet die Einträge ab: je Mail (Episode, Ausgang) mit `ergaenzt`, `fehlend` oder `fehler`."""
    tor = permission_lock if permission_lock is not None else nullcontext()
    ausgaenge: list[tuple[str, str]] = []
    for eintrag in eintraege:
        if not permitted():
            break
        kennung = eintrag["episode_id"]
        try:
            message = reader.message_in_folder(eintrag["folder"], f"{eintrag['generation']}.{eintrag['uid']}")
        except Exception:  # noqa: BLE001 - Netz und Server dürfen scheitern; die Mail bleibt offen
            ausgaenge.append((kennung, "fehler"))
            continue
        message = replace(message, account_id=account_id)
        beteiligte = kontakte.fuer_mail(message.sender, message.recipients, eigene=message.own_addresses)
        if not beteiligte:
            ausgaenge.append((kennung, "fehlend"))
            continue
        with tor:
            # Nach dem Abruf neu prüfen: Die Freigabe kann inzwischen zurückgenommen sein.
            if not permitted():
                break
            try:
                episodes.add_contacts(kennung, beteiligte,
                                      kontakte.teilnehmer_texte(beteiligte, absender_text=message.sender))
            except EpisodeError:
                continue  # inzwischen ausgeschlossen: nicht anfassen, nicht zählen
        ausgaenge.append((kennung, "ergaenzt"))
    return ausgaenge


def _zaehlen(ausgaenge: list[tuple[str, str]]) -> dict[str, int]:
    zaehler = {"ergaenzt": 0, "fehlend": 0, "fehler": 0}
    for _, ausgang in ausgaenge:
        zaehler[ausgang] += 1
    return zaehler


def nachtragen(episodes: EpisodeStore, reader: Any, account_id: str, *, limit: int = 50,
               permitted: Callable[[], bool] = lambda: True, permission_lock: Any = None,
               ausser: Collection[str] = ()) -> dict[str, int]:
    """Holt die Kopfzeilen von höchstens `limit` Mails und ergänzt ihre Beteiligten.

    Gibt zurück, wie viele ergänzt wurden, wie viele der Server nicht mehr
    lieferte (`fehlend`) und wie viele Fehler auftraten. Ein Fehler bricht das
    Paket nicht ab; die Mail bleibt offen und kommt beim nächsten Aufruf wieder.
    Geschrieben wird unter `permission_lock` (falls gegeben) und nur, solange
    `permitted()` gilt.
    """
    eintraege = offene(episodes, account_id, limit=limit, ausser=ausser)
    return _zaehlen(_paket(episodes, reader, account_id, eintraege,
                           permitted=permitted, permission_lock=permission_lock))


@dataclass
class _Stand:
    """Was der Lauf über ein Konto weiß; nur im Speicher, ein Neustart zählt neu."""

    offen: int | None = None
    ergaenzt: int = 0
    fehlend: set[str] = field(default_factory=set)
    fehler: dict[str, float] = field(default_factory=dict)
    fertig: bool = False
    gedrosselt: bool = False

    def ausser(self, jetzt: float) -> set[str]:
        """Episoden, die dieser Lauf gerade nicht versucht: ohne Kopfzeilen oder kürzlich gescheitert."""
        self.fehler = {k: bis for k, bis in self.fehler.items() if bis > jetzt}
        return self.fehlend | set(self.fehler)


class Lauf:
    """Der Hintergrundtakt des Nachtrags: kleine Pakete, gedrosselt, mit Fortschritt und Ende.

    Eine Instanz je App. `schritt` gehört in den Takt der Mailaufnahme.
    """

    def __init__(self, *, paket: int = PAKET_IM_TAKT, grenze: int = RUECKSTAU_GRENZE,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self._paket, self._grenze, self._uhr = paket, grenze, uhr
        self._konten: dict[str, _Stand] = {}

    def schritt(self, episodes: EpisodeStore, reader: Any, account_id: str, *,
                permitted: Callable[[], bool], permission_lock: Any = None,
                mit_modell: bool = True) -> dict[str, int] | None:
        """Ein Paket, wenn erlaubt, sonst nichts. Gibt die Zahlen des Pakets zurück, sonst `None`.

        Ohne Modell wird nichts neu eingeordnet, also gibt es auch keinen
        Rückstau, auf den man Rücksicht nehmen müsste.
        """
        stand = self._konten.setdefault(account_id, _Stand())
        if stand.fertig or not permitted():
            return None
        if mit_modell and rueckstau(episodes, account_id, bis=self._grenze) > self._grenze:
            stand.gedrosselt = True
            return None
        stand.gedrosselt = False
        if stand.offen is None:
            stand.offen = anzahl_offen(episodes, account_id)
        eintraege = offene(episodes, account_id, limit=self._paket, ausser=stand.ausser(self._uhr()))
        if not eintraege:
            # Nichts Versuchbares mehr. Ruhen nur noch gescheiterte Mails, kommen sie nach der Pause wieder dran.
            stand.fertig = not stand.fehler
            return None
        sitzung = getattr(reader, "session", None)
        with (sitzung() if sitzung is not None else nullcontext()):
            ausgaenge = _paket(episodes, reader, account_id, eintraege,
                               permitted=permitted, permission_lock=permission_lock)
        for kennung, ausgang in ausgaenge:
            if ausgang == "ergaenzt":
                stand.ergaenzt += 1
            elif ausgang == "fehlend":
                stand.fehlend.add(kennung)
            else:
                stand.fehler[kennung] = self._uhr() + PAUSE_NACH_FEHLER
        return _zaehlen(ausgaenge)

    def status(self, account_id: str) -> dict[str, Any] | None:
        """Für die Anzeige: `None`, solange der Lauf das Konto noch nicht angesehen hat."""
        stand = self._konten.get(account_id)
        if stand is None or stand.offen is None:
            return None
        offen = 0 if stand.fertig else max(0, stand.offen - stand.ergaenzt - len(stand.fehlend))
        return {"offen": offen, "ergaenzt": stand.ergaenzt, "ohne_kopfzeilen": len(stand.fehlend),
                "gedrosselt": stand.gedrosselt, "fertig": stand.fertig}
