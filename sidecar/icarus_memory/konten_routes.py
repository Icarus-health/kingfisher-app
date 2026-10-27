"""Konten und Bereiche unter Einstellungen → Zugänge (Paket K, docs/66-automatik.md).

* `GET  /api/v1/konten`: je Postfach und Kalender Name, Adresse, Bereich (bestätigt) oder Vorschlag mit Grund und der
  Stand in einem Satz („Zuletzt gelesen vor 4 Min.“ oder der Fehler mit dem Weg); dazu alle Bereiche, die Bereiche in
  Gebrauch (für die Filter in Kalender und Aufgaben) und die ausgeblendeten Kalender.
* `PUT  /api/v1/konten/name` `{id, name}`: umbenennen; ein Name gilt je Art nur einmal.
* `PUT  /api/v1/konten/bereich` `{zuordnung: {id: bereich | null}}`: bestätigen, ändern oder lösen (auch mehrere auf
  einmal, so „Alle Vorschläge übernehmen“ und dessen Rückgängig).
* `POST /api/v1/bereiche` `{name}`: einen eigenen Bereich anlegen (gleichnamig: der vorhandene).
* `PUT  /api/v1/kalender/ausgeblendet` `{ids}`: die ausgeblendeten Kalender der Kalenderseite, gespeichert.

Alles hier ist umkehrbar und bleibt auf dem Rechner; deshalb gibt es keine Rückfrage, die Oberfläche bietet danach
„Rückgängig“ an (docs/16-gestaltung.md). Die Ableitung selbst steht in `bereiche.py`.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import bereiche, config, identitaet

_MAC = "mac-calendar"
MAX_NAME = 120

#: Wann ein Kalender zuletzt gelesen wurde (Kalenderseite, Heute, Abgleich) und was dabei schiefging; nur im Speicher.
_gelesen: dict[int, dict[str, dict[str, Any]]] = {}
_sperre = threading.Lock()


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=300)
    name: str = Field(max_length=200)


class BereichIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zuordnung: dict[str, str | None] = Field(min_length=1, max_length=200)


class NeuerBereichIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=200)


class AusgeblendetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(max_length=200)


# -- Zeit und Stand ---------------------------------------------------------------------------------------------------


def vor(zeit: datetime | None, jetzt: datetime | None = None) -> str:
    """„gerade eben“, „vor 4 Min.“, „vor 3 Std.“, „gestern um 14:43“, „am 3. Oktober um 14:43“."""
    if zeit is None:
        return ""
    from .mail_stand import zeit_text
    from .model import user_timezone
    jetzt = jetzt or datetime.now(timezone.utc)
    zeit = zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)
    sekunden = (jetzt - zeit).total_seconds()
    if sekunden < 60:
        return "gerade eben"
    if sekunden < 3600:
        return f"vor {int(sekunden // 60)} Min."
    zone = user_timezone() or timezone.utc
    tag, heute = zeit.astimezone(zone).date(), jetzt.astimezone(zone).date()
    if tag == heute:
        return f"vor {int(sekunden // 3600)} Std."
    if tag == heute - timedelta(days=1):
        return f"gestern um {zeit.astimezone(zone):%H:%M}"
    return zeit_text(zeit, jetzt)


def _satz(text: str) -> str:
    """Ein Punkt am Ende, aber nie zwei („vor 4 Min.“)."""
    return text if text.endswith(".") else text + "."


def _ohne_namen(satz: str, name: str) -> str:
    """Der Satz von `mail_stand` ohne „Postfach <Name>“ vorne: In der Zeile steht der Name schon."""
    kopf = f"Postfach {name}"
    # Die Zeile steht schon unter Zugänge; der Verweis dorthin entfällt („Melde dich neu an.“).
    satz = satz.replace(f" von {kopf} ", " ").replace(" unter Einstellungen → Zugänge", "")
    if satz.startswith(kopf + ": "):
        satz = satz[len(kopf) + 2:]
    elif satz.startswith(kopf + " "):
        satz = satz[len(kopf) + 1:]
    return satz[:1].upper() + satz[1:]


def kurzer_mailstand(aussage: dict[str, Any] | None, name: str, jetzt: datetime | None = None) -> dict[str, Any] | None:
    """Die eine Aussage eines Postfachs (`mail_stand.stand`) als kurzer Satz für die Zeile unter Zugänge.

    `art`: `gut` (gelesen, leer), `laeuft` (liest, wartet, pausiert, noch nicht abgerufen) oder `fehler`.
    """
    if not aussage:
        return None
    from .mail_stand import _zeit
    zustand = aussage.get("zustand")
    zuletzt = _zeit(aussage.get("zuletzt"))
    verweis = aussage.get("verweis")
    if zustand in {"aktuell", "leer"} and zuletzt is not None:
        satz = _satz(f"Zuletzt gelesen {vor(zuletzt, jetzt)}" if zustand == "aktuell"
                     else f"Leer, zuletzt nachgesehen {vor(zuletzt, jetzt)}")
        return {"satz": satz, "art": "gut", "verweis": None}
    if zustand == "nicht_abgerufen":
        return {"satz": "Noch nicht gelesen. Kingfisher liest es beim nächsten Abruf von selbst.", "art": "laeuft",
                "verweis": None}
    art = "fehler" if zustand in {"fehler", "gescheitert"} else "gut" if zustand in {"aktuell", "leer"} else "laeuft"
    return {"satz": _ohne_namen(str(aussage.get("satz") or ""), name), "art": art, "verweis": verweis}


def kalender_gelesen(app: Any, kalender: Any, *, jetzt: datetime | None = None) -> None:
    """Merkt nach einem Abruf je Kalenderquelle die Zeit oder den Fehler (`CalendarCollection.last_errors`)."""
    quellen = getattr(kalender, "sources", None)
    if not isinstance(quellen, list):
        return
    jetzt = jetzt or datetime.now(timezone.utc)
    fehler = dict(getattr(kalender, "last_errors", {}) or {})
    with _sperre:
        eintraege = _gelesen.setdefault(id(app), {})
        for quelle in quellen:
            kennung = getattr(quelle, "id", "")
            if not kennung or kennung == _MAC:
                continue
            vorher = eintraege.get(kennung) or {}
            eintraege[kennung] = ({**vorher, "fehler": str(fehler[kennung]), "fehler_am": jetzt}
                                  if kennung in fehler else {"zeit": jetzt})


def nach_kalenderabruf(app: Any, kalender: Any, ergebnis: dict[str, Any]) -> None:
    """Einhängepunkt in `server._calendar_overview`: Stand merken und jedem Termin seinen Bereich geben."""
    try:
        kalender_gelesen(app, kalender)
        bereiche.termine_anreichern(app.state.settings, ergebnis.get("items") or [])
    except Exception:  # noqa: BLE001 - Beiwerk; die Termine selbst bleiben
        import logging
        logging.getLogger(__name__).exception("Bereich oder Stand der Termine nicht bestimmbar")


def _kalenderstand(app: Any, eintrag: Any, geheimnis: bool, jetzt: datetime) -> dict[str, Any]:
    with _sperre:
        gemerkt = dict((_gelesen.get(id(app)) or {}).get(eintrag.id) or {})
    letzter = getattr(app.state, "calendar_memory_letzter", None) or {}
    abgleich = (letzter.get("quellen") or {}).get(eintrag.id)
    from .mail_stand import _zeit
    abgleich_zeit = _zeit(letzter.get("abgeglichen_am")) if abgleich else None
    if eintrag.kind in {"caldav", "google", "microsoft"} and not geheimnis:
        return {"satz": "Der Zugang fehlt. Verbinde den Kalender über „Kalender hinzufügen“ neu.", "art": "fehler",
                "verweis": None}
    zeit = max(filter(None, (gemerkt.get("zeit"), abgleich_zeit if abgleich and not abgleich.get("fehler") else None)),
               default=None)
    fehler_am = gemerkt.get("fehler_am")
    if gemerkt.get("fehler") and (zeit is None or fehler_am >= zeit):
        return {"satz": "Konnte zuletzt nicht gelesen werden. Kingfisher versucht es von selbst wieder"
                        + (_satz(f"; zuletzt gelesen {vor(zeit, jetzt)}") if zeit else "."), "art": "fehler", "verweis": None}
    if abgleich and abgleich.get("fehler") and zeit is None:
        return {"satz": "Konnte beim letzten Abgleich nicht gelesen werden. Kingfisher versucht es von selbst wieder.",
                "art": "fehler", "verweis": None}
    if zeit is not None:
        return {"satz": _satz(f"Zuletzt gelesen {vor(zeit, jetzt)}"), "art": "gut", "verweis": None}
    return {"satz": "Wird beim nächsten Abgleich gelesen.", "art": "laeuft", "verweis": None}


def _mac_kalender(app: Any) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    mac = getattr(app.state, "mac_calendar", None)
    if mac is None:
        return [], None
    try:
        zustand = mac.read()
    except Exception:  # noqa: BLE001 - ohne Mac-Zustand keine Mac-Kalender
        return [], None
    if not zustand.get("enabled"):
        return [], zustand
    gewaehlt = set(zustand.get("selected") or [])
    return [k for k in zustand.get("calendars") or [] if isinstance(k, dict) and k.get("id") in gewaehlt], zustand


def _macstand(zustand: dict[str, Any], jetzt: datetime) -> dict[str, Any]:
    from .mail_stand import _zeit
    if zustand.get("error"):
        return {"satz": str(zustand["error"]), "art": "fehler", "verweis": None}
    zeit = _zeit(zustand.get("synced_at"))
    if zeit is not None:
        return {"satz": _satz(f"Zuletzt gelesen {vor(zeit, jetzt)}"), "art": "gut", "verweis": None}
    return {"satz": "Wartet auf die Kingfisher-App am Mac.", "art": "laeuft", "verweis": None}


# -- Namen ------------------------------------------------------------------------------------------------------------


def _adresse(eintrag: Any) -> str:
    return (getattr(eintrag, "sender", "") or getattr(eintrag, "user", "") or "").strip()


def doppeltes_postfach(settings: Any, user: str, imap_host: str) -> Any | None:
    """Das schon verbundene Postfach mit derselben Anmeldung beim selben Server, sonst None."""
    user, host = user.strip().casefold(), imap_host.strip().casefold()
    return next((e for e in settings.mail_accounts
                 if e.user.strip().casefold() == user and e.imap_host.strip().casefold() == host), None)


def doppelt_satz(eintrag: Any) -> str:
    return f"Dieses Postfach ist schon verbunden: {eintrag.label}. Kingfisher liest es bereits."


def eindeutiger_name(vorhandene: list[str], wunsch: str, adresse: str) -> str:
    """Der Wunschname, wenn er frei ist; sonst die Adresse; sonst die Adresse mit Zahl (zwei Gmail-Konten)."""
    belegt = {n.strip().casefold() for n in vorhandene}
    for name in (wunsch.strip(), adresse.strip()):
        if name and name.casefold() not in belegt:
            return name[:MAX_NAME]
    basis, n = (adresse.strip() or wunsch.strip() or "Postfach"), 2
    while f"{basis} ({n})".casefold() in belegt:
        n += 1
    return f"{basis} ({n})"[:MAX_NAME]


def namen_eindeutig_machen(settings: Any) -> bool:
    """Zwei Postfächer mit demselben Namen (früher hieß jedes Gmail-Konto „Gmail / Google Workspace“) heißen nach
    ihrer Adresse. Nur der Anzeigename ändert sich; gibt zurück, ob etwas geändert wurde."""
    geaendert = False
    zaehlung: dict[str, int] = {}
    for eintrag in settings.mail_accounts:
        zaehlung[eintrag.label.strip().casefold()] = zaehlung.get(eintrag.label.strip().casefold(), 0) + 1
    doppelt = {name for name, anzahl in zaehlung.items() if anzahl > 1}
    for eintrag in settings.mail_accounts:
        if eintrag.label.strip().casefold() not in doppelt:
            continue
        andere = [e.label for e in settings.mail_accounts if e is not eintrag and e.label.strip().casefold() not in doppelt]
        neu = eindeutiger_name(andere, "", _adresse(eintrag))
        if neu and neu != eintrag.label:
            eintrag.label = neu
            geaendert = True
    return geaendert


# -- Übersicht --------------------------------------------------------------------------------------------------------


def uebersicht(app: Any, *, jetzt: datetime | None = None) -> dict[str, Any]:
    from .server import _integration_secret
    settings = app.state.settings
    jetzt = jetzt or datetime.now(timezone.utc)
    zuordnung = bereiche.bereich_je_konto(settings)
    try:
        from . import mail_stand
        staende = {s["account_id"]: s for s in mail_stand.stand(app)}
    except Exception:  # noqa: BLE001 - ohne Stand bleibt die Liste
        staende = {}
    postfaecher = []
    #: Was in einem unbestätigten Postfach eines privaten Anbieters steht, je Adresse; auch für seinen Kalender.
    inhalte: dict[str, bereiche.Inhalt] = {}
    for e in settings.mail_accounts:
        bestaetigt = zuordnung.get(e.id)
        vorschlag = None
        if not bestaetigt:
            inhalt = None
            if identitaet.ist_privater_anbieter(_adresse(e)):
                inhalt = inhalte[_adresse(e).casefold()] = bereiche.inhalt_des_postfachs(app, e.id)
            vorschlag = bereiche.vorschlag_postfach(_adresse(e), inhalt)
        postfaecher.append({"id": e.id, "name": e.label, "adresse": _adresse(e), "bereich": bestaetigt,
                            "vorschlag": vorschlag.to_dict() if vorschlag else None,
                            "stand": kurzer_mailstand(staende.get(e.id), e.label, jetzt) if e.configured else None})
    kalender = []
    for e in settings.calendar_sources:
        bestaetigt = zuordnung.get(e.id)
        vorschlag = None
        if not bestaetigt:
            konto = next((p for p in settings.mail_accounts
                          if e.user and p.user.strip().casefold() == e.user.strip().casefold()), None)
            vorschlag = bereiche.vorschlag_kalender(
                e.label, adresse=e.user if "@" in (e.user or "") else "",
                konto=(konto.label, zuordnung.get(konto.id, "")) if konto is not None else None,
                inhalt=inhalte.get((e.user or "").strip().casefold()))
        geheimnis = bool(_integration_secret(app, "calendar", e.id))
        if e.kind == "microsoft":
            from .microsoft_routes import zugang_da
            geheimnis = zugang_da(app, e.user)
        kalender.append({"id": e.id, "name": e.label, "art": e.kind, "adresse": e.user if "@" in (e.user or "") else "",
                         "umbenennbar": True, "bereich": bestaetigt,
                         "vorschlag": vorschlag.to_dict() if vorschlag else None,
                         "stand": _kalenderstand(app, e, geheimnis, jetzt) if e.configured else None})
    mac_liste, mac_zustand = _mac_kalender(app)
    for k in mac_liste:
        kennung = f"{_MAC}:{k['id']}"
        bestaetigt = zuordnung.get(kennung)
        vorschlag = None if bestaetigt else bereiche.vorschlag_kalender(str(k.get("name") or ""))
        kalender.append({"id": kennung, "name": str(k.get("name") or "Mac-Kalender"), "art": "mac", "adresse": "",
                         "umbenennbar": False, "bereich": bestaetigt,
                         "vorschlag": vorschlag.to_dict() if vorschlag else None,
                         "stand": _macstand(mac_zustand or {}, jetzt)})
    kennungen = [p["id"] for p in postfaecher] + [k["id"] for k in kalender]
    return {"bereiche": bereiche.bereiche(settings), "in_gebrauch": bereiche.in_gebrauch(settings, kennungen),
            "postfaecher": postfaecher, "kalender": kalender,
            "ausgeblendet": bereiche.ausgeblendete_kalender(settings)}


# -- Routen -----------------------------------------------------------------------------------------------------------


def register(app: Any, guard: Any, data_dir: Callable[[], Any], neu_bauen: Callable[[], Any]) -> None:
    settings = app.state.settings
    if namen_eindeutig_machen(settings):
        try:
            config.save(data_dir(), settings)
        except OSError:
            pass

    def speichern(aenderung: Callable[[config.Settings], Any], *, bauen: bool = False) -> Any:
        settings = app.state.settings
        vorher = settings.to_dict()
        with app.state.conversation_lock:
            try:
                ergebnis = aenderung(settings)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            try:
                config.save(data_dir(), settings)
            except OSError:
                app.state.settings = config.Settings.from_dict(vorher)
                raise HTTPException(500, "Die Änderung konnte nicht gespeichert werden.") from None
        if bauen:
            neu_bauen()
        return ergebnis

    def bekannte_kennungen(settings: config.Settings) -> set[str]:
        kennungen = {e.id for e in settings.mail_accounts} | {e.id for e in settings.calendar_sources}
        return kennungen | {f"{_MAC}:{k['id']}" for k in _mac_kalender(app)[0]}

    @app.get("/api/v1/konten", dependencies=guard)
    def konten() -> dict[str, Any]:
        return uebersicht(app)

    @app.put("/api/v1/konten/name", dependencies=guard)
    def umbenennen(body: NameIn) -> dict[str, Any]:
        name = " ".join(body.name.split())
        if not name:
            raise HTTPException(422, "Bitte gib einen Namen ein.")
        if len(name) > MAX_NAME:
            raise HTTPException(422, f"Der Name ist zu lang; höchstens {MAX_NAME} Zeichen.")
        if body.id.startswith(_MAC + ":"):
            raise HTTPException(409, "Den Namen eines Mac-Kalenders legst du im Kalender des Macs fest.")

        def aendern(settings: config.Settings) -> str:
            for liste, art in ((settings.mail_accounts, "Postfach"), (settings.calendar_sources, "Kalender")):
                eintrag = next((e for e in liste if e.id == body.id), None)
                if eintrag is None:
                    continue
                if any(e is not eintrag and e.label.strip().casefold() == name.casefold() for e in liste):
                    raise HTTPException(409, "Diesen Namen trägt schon ein anderes Postfach." if art == "Postfach"
                                        else "Diesen Namen trägt schon ein anderer Kalender.")
                vorher, eintrag.label = eintrag.label, name
                return vorher
            raise HTTPException(404, "Diesen Zugang gibt es nicht.")
        vorher = speichern(aendern, bauen=True)
        return {**uebersicht(app), "vorher": vorher}

    @app.put("/api/v1/konten/bereich", dependencies=guard)
    def bereich_setzen(body: BereichIn) -> dict[str, Any]:
        bekannt = bekannte_kennungen(app.state.settings)
        fremd = [k for k in body.zuordnung if k not in bekannt]
        if fremd:
            raise HTTPException(404, "Diesen Zugang gibt es nicht.")

        def aendern(settings: config.Settings) -> dict[str, str | None]:
            gueltig = {b["id"] for b in bereiche.bereiche(settings)}
            if any(b is not None and b not in gueltig for b in body.zuordnung.values()):
                raise ValueError("Diesen Bereich gibt es nicht.")
            return {k: bereiche.setze_bereich(settings, k, b) for k, b in body.zuordnung.items()}
        vorher = speichern(aendern)
        return {**uebersicht(app), "vorher": vorher}

    @app.post("/api/v1/bereiche", dependencies=guard, status_code=201)
    def bereich_anlegen(body: NeuerBereichIn) -> dict[str, Any]:
        kennung = speichern(lambda settings: bereiche.neuer_bereich(settings, body.name))
        return {**uebersicht(app), "neu": kennung}

    @app.put("/api/v1/kalender/ausgeblendet", dependencies=guard)
    def ausblenden(body: AusgeblendetIn) -> dict[str, Any]:
        ids = speichern(lambda settings: bereiche.setze_ausgeblendet(settings, body.ids))
        return {"ausgeblendet": ids}


__all__ = ["doppelt_satz", "doppeltes_postfach", "eindeutiger_name", "kalender_gelesen", "kurzer_mailstand",
           "nach_kalenderabruf", "namen_eindeutig_machen", "register", "uebersicht", "vor"]
