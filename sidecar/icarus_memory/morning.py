"""Deterministischer Morning-Briefing-Vertrag für Kingfisher."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from .datumstext import iso_versuchen as _time


def _stable_id(kind: str, source: str, ref: str | None, text: str) -> str:
    payload = "|".join((kind, source, ref or "", text)).encode("utf-8")
    return f"attn-{hashlib.sha256(payload).hexdigest()[:14]}"


def _weather_code(code: int) -> str:
    if code == 0:
        return "Klar"
    if code in {1, 2}:
        return "Leicht bewölkt"
    if code == 3:
        return "Bewölkt"
    if code in {45, 48}:
        return "Nebel"
    if code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
        return "Regen"
    if code in {56, 57, 66, 67}:
        return "Gefrierender Regen"
    if code in {71, 73, 75, 77, 85, 86}:
        return "Schnee"
    if code in {95, 96, 99}:
        return "Gewitter"
    return "Wetterdaten verfügbar"


def load_weather() -> tuple[dict[str, Any] | None, str | None]:
    if os.environ.get("KINGFISHER_WEATHER_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return None, None
    location = os.environ.get("KINGFISHER_WEATHER_LOCATION", "").strip()
    latitude = os.environ.get("KINGFISHER_WEATHER_LATITUDE", "").strip()
    longitude = os.environ.get("KINGFISHER_WEATHER_LONGITUDE", "").strip()
    if not location or not latitude or not longitude:
        return None, "Wetter ist aktiviert, aber Ort oder Koordinaten fehlen."
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=4.0,
        )
        response.raise_for_status()
        current = response.json().get("current") or {}
        return {
            "location": location,
            "temperature_c": round(float(current["temperature_2m"])),
            "condition": _weather_code(int(current["weather_code"])),
            "attribution": "Open-Meteo",
            "attribution_url": "https://open-meteo.com/",
        }, None
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None, "Wetter ist gerade nicht erreichbar."


def _fixture_payload() -> dict[str, Any]:
    """Kanonischer Inhalt, der einmalig in die lokale Fixture-DB geschrieben wird."""
    needs = [
        ("Kingfisher Positionierung", "2 Entscheidungen blockieren weitere Arbeit", "Hoch"),
        ("Clara Neumann", "wartet auf deine Rückmeldung", "Hoch"),
        ("Jonas Brenner", "hat Dokument kommentiert", "Mittel"),
    ]
    happening = [
        ("Cowork", "Wettbewerbsanalyse abgeschlossen", "folder"),
        ("Neue E-Mail von Kunde X", "Angebotsfreigabe", "mail"),
        ("Slack #projekt-nordlicht", "7 neue Nachrichten", "message-circle"),
    ]
    later = [
        ("09:00", "Projekt-Update", "Beispiel GmbH"),
        ("11:30", "Termin: Dr. Kranz", "Strategiegespräch"),
        ("15:30", "Projektcall", "Kingfisher Roadmap"),
        ("17:45", "Familienzeit", "Ab hier keine neue Arbeit"),
    ]
    return {
        "generated_at": "2025-05-20T07:32:00+02:00",
        "timezone": "Europe/Berlin",
        "greeting": "Guten Morgen.",
        "relevance_count": 5,
        "needs_you": [
            {
                "id": _stable_id("need", "fixture", str(index), title),
                "kind": "need",
                "title": title,
                "detail": detail,
                "priority": priority,
                "source": "fixture",
                "source_ref": str(index),
                "reason": detail,
                "action": None,
            }
            for index, (title, detail, priority) in enumerate(needs)
        ],
        "happening_now": [
            {
                "id": _stable_id("activity", "fixture", str(index), title),
                "kind": "activity",
                "title": title,
                "detail": detail,
                "icon": icon,
                "source": "fixture",
                "source_ref": str(index),
                "reason": detail,
                "action": None,
            }
            for index, (title, detail, icon) in enumerate(happening)
        ],
        "later_today": [
            {
                "id": _stable_id("calendar", "fixture", str(index), title),
                "time": time,
                "title": title,
                "detail": detail,
                "source": "fixture",
                "source_ref": str(index),
                "reason": "Heute geplant",
                "action": None,
            }
            for index, (time, title, detail) in enumerate(later)
        ],
        "timeline": [
            {"id": "mail", "label": "GESTERN", "icon": "mail", "tone": "navy"},
            {"id": "network", "label": "", "icon": "network", "tone": "navy"},
            {"id": "mail-2", "label": "", "icon": "mail", "tone": "navy"},
            {"id": "now", "label": "JETZT", "icon": "brand", "tone": "navy"},
            {"id": "network-2", "label": "", "icon": "network", "tone": "navy"},
            {"id": "calendar", "label": "", "icon": "calendar-days", "tone": "orange"},
            {"id": "later", "label": "SPÄTER", "icon": "circle-alert", "tone": "orange"},
        ],
        "weather": {"location": "Freiburg", "temperature_c": 12, "condition": "Leicht bewölkt"},
        "partial_failures": [],
        "fixture": True,
    }


def _fixture_path() -> Path:
    configured = os.environ.get("KINGFISHER_FIXTURE_DB")
    if configured:
        return Path(configured)
    data_dir = Path(os.environ.get("ICARUS_DATA_DIR", ".kingfisher-data"))
    return data_dir / "morning-fixture.sqlite3"


def _seed_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _fixture_payload()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS morning_fixture ("
            "section TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in {0, 1}:
            raise sqlite3.DatabaseError("Unbekannte Morning-Fixture-Version")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM morning_fixture")
        for section, value in payload.items():
            connection.execute(
                "INSERT INTO morning_fixture (section, payload) VALUES (?, ?)",
                (section, json.dumps(value, ensure_ascii=False)),
            )
        if version == 0:
            connection.execute("PRAGMA user_version = 1")
        connection.commit()


def fixture(now: datetime) -> dict[str, Any]:
    """Liest den Referenzdatensatz deterministisch aus einer lokalen SQLite-Datei."""
    del now  # Der Screenshot-Vertrag besitzt bewusst eine feste Referenzzeit.
    path = _fixture_path()
    _seed_fixture(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT section, payload FROM morning_fixture ORDER BY section"
        ).fetchall()
    payload = {section: json.loads(value) for section, value in rows}
    expected = set(_fixture_payload())
    if set(payload) != expected:
        raise sqlite3.DatabaseError("Morning-Fixture ist unvollständig")
    return payload


def compose(dashboard: dict[str, Any], *, now: datetime, target: date,
            wetter=None, nutzername: str = "", verlauf: list[str] | None = None) -> dict[str, Any]:
    if os.environ.get("KINGFISHER_FIXTURE", "").lower() == "morning":
        return fixture(now)

    briefing = dashboard.get("briefing") or {}
    attention: dict[str, dict[str, Any]] = {}
    tasks_by_id = {task.get("id"): task for task in dashboard.get("tasks", {}).get("items", [])}
    projects_by_id = {project.get("id"): project for project in dashboard.get("projects", {}).get("items", [])}
    decisions_by_id = {decision.get("id"): decision for decision in dashboard.get("decisions", {}).get("erschuettert", [])}
    candidates_by_id = {item.get("id"): item for item in (dashboard.get("task_candidates", {}) or {}).get("items", []) or []}
    for index, point in enumerate((briefing.get("punkte") or [])[:3]):
        source = str(point.get("quelle") or "unknown")
        ref = point.get("ref")
        text = str(point.get("text") or "")
        item_id = _stable_id("need", source, ref, text)
        attention[item_id] = {
            "id": item_id,
            "kind": "need",
            "title": text,
            "detail": f"Quelle: {source}",
            "priority": "Hoch" if index < 2 else "Mittel",
            "source": source,
            "source_ref": ref,
            "reason": text,
            "action": point.get("aktion"),
        }
        if source in ("aufgabe", "wartet"):
            task = tasks_by_id.get(ref, {})
            # Die kompakte Karte nennt zuerst die Aufgabe. Der vollständige
            # Erklärungssatz bleibt als reason für das ausführliche Briefing.
            attention[item_id]["title"] = str(task.get("title") or text)
            project_id = task.get("project_id")
            project = projects_by_id.get(project_id)
            if project:
                attention[item_id]["detail"] = f"Projekt: {project['name']}"
            attention[item_id]["project_id"] = project_id if project else None
        elif source == "entscheidung":
            decision = decisions_by_id.get(ref, {})
            attention[item_id]["title"] = str(decision.get("satz") or text)
            project_id = decision.get("project_id")
            project = projects_by_id.get(project_id)
            attention[item_id]["detail"] = f"Projekt: {project['name']}" if project else "Entscheidungsgrundlage prüfen"
            attention[item_id]["project_id"] = project_id if project else None
        elif source == "nachbereitung":
            # Kurz genug für die Karte: Die Frage muss sichtbar bleiben.
            termin = next((t for t in (dashboard.get("calendar", {}) or {}).get("nachzubereiten") or []
                           if isinstance(ref, str) and ref.startswith(f"{t.get('uid')}|")), None)
            if termin:
                attention[item_id]["title"] = (termin.get("frage")
                                               or f"Was kam bei „{termin.get('summary') or 'dem Termin'}“ heraus?")
            attention[item_id]["detail"] = "Termin vorbei · kurz festhalten, was vereinbart wurde"
        elif source == "zusage":
            # Ein Vorschlag, keine Aufgabe: Die Karte nennt ihn und seine
            # Herkunft; übernommen wird erst mit dem Klick des Nutzers.
            candidate = candidates_by_id.get(ref, {})
            attention[item_id]["title"] = str(candidate.get("statement") or text)
            sender = candidate.get("sender")
            received = _time(candidate.get("received_at"))
            origin = f"Vorschlag aus einer Mail von {sender}" if sender else "Vorschlag aus einer Quelle"
            if received is not None:
                origin += f" · {received.day}.{received.month}.{received.year}"
            attention[item_id]["detail"] = origin
            attention[item_id]["episode_id"] = candidate.get("episode_id")
            attention[item_id]["priority"] = ''
            attention[item_id]["reason"] = origin + f': „{attention[item_id]["title"]}“. Modellvorschlag, bitte prüfen.'
            attention[item_id]["review_required"] = bool(candidate.get('review_required', True))
            if attention[item_id]["review_required"]:
                attention[item_id]["reason"] = origin + '. Noch ohne zusätzliche Aufgabenprüfung. Bitte zuerst das Original prüfen.'
                attention[item_id]["action"] = 'Prüfen'

    # Eine offene Klärung ist kein Fakt und niemals Modellkontext. Sie ist
    # allerdings eine echte, zeitnahe Entscheidung für den Menschen. Der
    # Morning-Screen verwendet dafür dieselbe bestehende Aufmerksamkeitszeile,
    # ohne einen neuen Review-Screen vorwegzunehmen. Details bleiben bis zur
    # späteren, genehmigten Kläransicht im lokalen API-Bestand.
    for clarification in (dashboard.get("knowledge", {}).get("clarifications") or []):
        reference = str(clarification.get("id") or "")
        if not reference:
            continue
        item_id = _stable_id("clarification", "knowledge", reference, "Gedächtnis klären")
        attention[item_id] = {
            "id": item_id,
            "kind": "need",
            "title": "Gedächtnis klären",
            "detail": "Widersprüchliche Angaben warten auf deine Einordnung",
            "priority": "Hoch",
            "source": "knowledge",
            "source_ref": reference,
            "reason": "Offene Klärung",
            "action": None,
        }

    happening: list[dict[str, Any]] = []
    for mail in (dashboard.get("mail", {}).get("items") or []):
        if not mail.get("unread"):
            continue
        title = str(mail.get("subject") or "Neue E-Mail")
        happening.append({
            "id": _stable_id("activity", "mail", mail.get("uid"), title),
            "kind": "activity", "title": title,
            "detail": str(mail.get("from") or "Ungelesene Nachricht"),
            "icon": "mail", "source": "mail", "source_ref": mail.get("uid"),
            "occurred_at": mail.get("date"), "recorded_at": mail.get("recorded_at"),
            "reason": "Ungelesene Nachricht", "action": None,
        })
        if len(happening) == 3:
            break
    # A new report is an activity, not an accepted task or an inferred deadline.
    from .working_memory_answers import KINDS
    from .episodes import ist_eigene_quelle
    for report in (dashboard.get("working_memory", {}).get("items") or []):
        if len(happening) >= 3:
            break
        # Eigene Gesprächszeilen und selbst hochgeladene Dateien sind keine Nachrichten (Fremdprobe 2, Befund 22).
        if ist_eigene_quelle(report.get("source_type"), report.get("source_ref")):
            continue
        title = report['title'] or 'Gesprächsquelle'
        happening.append({
            'id': _stable_id('activity', 'working_memory', report['episode_id'], title),
            'kind': 'activity', 'title': title,
            'detail': 'Quelle berichtet · ' + ', '.join(KINDS[kind] for kind in report['kinds']),
            'icon': 'brain', 'source': 'working_memory', 'source_ref': report['episode_id'],
            'occurred_at': report.get('occurred_at'), 'recorded_at': report.get('recorded_at'),
            'reason': 'In den letzten 24 Stunden aufgenommen; keine bestätigte Aussage', 'action': None,
        })
    # Nur, was von anderen kam: die eigenen Zeilen im Gespräch und eben hochgeladene Dateien zählen nicht (Befund 22).
    episoden = dashboard.get("episodes", {}) or {}
    von_aussen = episoden.get("neu_von_aussen", episoden.get("pending"))
    if len(happening) < 3 and von_aussen:
        count = int(von_aussen)
        happening.append({
            "id": _stable_id("activity", "episodes", None, str(count)),
            "kind": "activity", "title": "Neue Hinweise",
            "detail": f"{count} {'Quelle' if count == 1 else 'Quellen'} aufgenommen", "icon": "brain",
            "source": "episodes", "source_ref": None,
            "reason": "Ungesichtetes Material", "action": None,
        })
    if len(happening) < 3 and dashboard.get("proposals", {}).get("pending"):
        count = int(dashboard["proposals"]["pending"])
        happening.append({
            "id": _stable_id("activity", "proposals", None, str(count)),
            "kind": "activity", "title": "Gedächtnisvorschläge",
            "detail": f"{count} warten auf Bestätigung", "icon": "file-text",
            "source": "proposals", "source_ref": None,
            "reason": "Offene Bestätigung", "action": None,
        })

    later: list[dict[str, Any]] = []
    for event in dashboard.get("calendar", {}).get("items") or []:
        start = _time(event.get("start"))
        if start is None:
            continue
        local_start = start.astimezone(now.tzinfo) if start.tzinfo else start
        if local_start.date() != target:
            continue
        title = str(event.get("title") or event.get("summary") or "Termin")
        later.append({
            "id": _stable_id("calendar", "calendar", event.get("uid"), title),
            "time": local_start.strftime("%H:%M"), "title": title,
            "detail": str(event.get("location") or ""), "source": "calendar",
            "source_ref": event.get("uid"), "reason": "Heute geplant", "action": None,
        })
    later.sort(key=lambda item: item["time"])
    later = later[:4]

    failures = []
    for name in ("tasks", "calendar", "mail"):
        error = (dashboard.get(name, {}) or {}).get("error")
        if not error:
            continue
        message = str(error)
        if name == "calendar" and message.startswith("Noch kein Kalender"):
            message = "Kalender ist nicht verbunden."
        elif name == "mail" and message.startswith("Noch kein Postfach"):
            message = "Postfach ist nicht verbunden."
        else:
            message = message.replace("Icarus", "Kingfisher")
        failures.append({"section": name, "message": message})
    # Fehlende Lesebereiche sind kein leerer, erfolgreich geprüfter Bestand.
    for name, label in (("projects", "Projekte"), ("decisions", "Entscheidungen"),
                        ("goals", "Ziele"), ("episodes", "Quellen"),
                        ("proposals", "Vorschläge"), ("knowledge", "Wissensprüfung"),
                        ("memory", "Gedächtnis"), ("working_memory", "Automatische Quellenberichte"),
                        ("task_candidates", "Aufgabenvorschläge")):
        if (dashboard.get(name) or {}).get("error"):
            failures.append({"section": name, "message": f"{label}: gerade nicht verfügbar. Bitte erneut laden."})
    if dashboard.get("briefing_error"):
        failures.append({"section": "briefing", "message": "Die Priorisierung ist gerade nicht verfügbar. Bitte erneut laden."})
    # `wetter`: das Wetter aus der Einstellung „Wetter im Briefing“ (`wetter.py`); ohne sie die alte Umgebungsprüfung.
    weather, weather_error = (wetter(), None) if wetter is not None else load_weather()
    if weather_error:
        failures.append({"section": "weather", "message": weather_error})

    # Ohne gesetzten Namen grüßt das Briefing neutral („Guten Morgen.“).
    # Der Name aus dem Erststart-Assistenten gilt, wenn die Umgebung keinen setzt (Umgebung schlägt Datei).
    user = os.environ.get("KINGFISHER_USER_NAME", "").strip() or nutzername.strip()
    greeting = "Guten Morgen" if now.hour < 12 else "Guten Tag"
    return {
        "generated_at": now.isoformat(),
        "timezone": str(now.tzinfo),
        "greeting": f"{greeting}, {user}." if user else f"{greeting}.",
        # Die drei Zeilen des Logbuchs („Seit gestern Abend: …“), ganz oben im Briefing (`logbuch.py`).
        "verlauf": list(verlauf or []),
        "relevance_count": len(attention),
        "historical_task_reviews": int((dashboard.get("task_candidates") or {}).get("review_pending") or 0),
        "needs_you": list(attention.values())[:3],
        "happening_now": happening[:3],
        "working_memory_more": bool(dashboard.get('working_memory', {}).get('truncated') or
            sum(not ist_eigene_quelle(r.get('source_type'), r.get('source_ref'))
                for r in dashboard.get('working_memory', {}).get('items') or []) >
            sum(item['source'] == 'working_memory' for item in happening[:3])),
        "later_today": later,
        "timeline": [
            {"id": "yesterday", "label": "GESTERN", "icon": "mail", "tone": "navy"},
            {"id": "now", "label": "JETZT", "icon": "brand", "tone": "navy"},
            {"id": "later", "label": "SPÄTER", "icon": "circle-alert", "tone": "orange"},
        ],
        "weather": weather,
        "partial_failures": failures,
        # Ohne Posteingang zusammengestellt (`post=false`): Die Oberfläche sagt, dass die Post noch kommt (Befund 22).
        "post_ausstehend": bool((dashboard.get("mail") or {}).get("ausstehend")),
        "fixture": False,
    }


__all__ = ["compose", "fixture", "load_weather"]
