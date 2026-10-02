"""Vorsichtige, rein beobachtende Erkennung explizit markierter Muster.

Dieses Modul erzeugt Vorschläge, schreibt aber weder Aussagen noch Identitäten.
Eine Gewohnheit darf nur aus einem vom Nutzer ausdrücklich gesetzten
``habit:``-Tag entstehen; der Inhalt und die Herkunft der Episoden bleiben der
Beleg.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterable, Any

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeKind


MAX_EPISODES = 2000
MAX_QUOTE_LENGTH = 280


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Zeitpunkte müssen eine Zeitzone tragen.")
    return value.astimezone(timezone.utc)


def _excerpt(body: Any) -> str:
    text = str(body or "").strip()
    return text[:MAX_QUOTE_LENGTH].strip()


def detect_patterns(
    episodes: Iterable[Any],
    *,
    now: datetime,
    window_days: int = 30,
    min_days: int = 3,
) -> list[dict[str, Any]]:
    """Erzeuge deterministische Pattern-Vorschläge aus rohen Episoden.

    Nur nicht ignorierte, nicht archivierte Roh-Episoden mit einem expliziten
    ``habit:<label>``-Tag werden betrachtet. Zukunft, Zusammenfassungen,
    Dubletten und leere Quellen liefern keinen Beleg. Die Eingabemenge ist
    absichtlich hart begrenzt, damit ein Aufrufer nichts still unterschlägt.
    """
    if not isinstance(window_days, int) or isinstance(window_days, bool) or window_days <= 0:
        raise ValueError("window_days muss eine positive ganze Zahl sein.")
    if not isinstance(min_days, int) or isinstance(min_days, bool) or min_days <= 0:
        raise ValueError("min_days muss eine positive ganze Zahl sein.")
    if min_days > window_days:
        raise ValueError("min_days darf window_days nicht überschreiten.")
    reference = _utc(now)
    raw = list(episodes)
    if len(raw) > MAX_EPISODES:
        raise ValueError(f"Höchstens {MAX_EPISODES} Episoden pro Lauf erlaubt.")
    start = reference - timedelta(days=window_days)

    by_id: dict[str, Any] = {}
    for episode in raw:
        episode_id = str(getattr(episode, "id", "")).strip()
        if not episode_id or episode_id in by_id:
            continue
        if getattr(episode, "kind", None) is EpisodeKind.SUMMARY:
            continue
        if getattr(episode, "state", None) in AUSGEBLENDETE_ZUSTAENDE:
            continue
        tags = getattr(episode, "tags", []) or []
        labels = []
        for tag in tags:
            value = str(tag).strip()
            if value.casefold().startswith("habit:"):
                label = value[6:].strip()
                if label:
                    labels.append(label)
        if not labels:
            continue
        try:
            occurred = _utc(episode.reference_time())
        except (AttributeError, TypeError, ValueError):
            continue
        if occurred < start or occurred > reference:
            continue
        quote = _excerpt(getattr(episode, "body", ""))
        if not quote:
            continue
        by_id[episode_id] = (episode, occurred, quote, labels)

    groups: dict[str, dict[str, Any]] = {}
    for episode, occurred, quote, labels in by_id.values():
        for label in labels:
            key = label.casefold()
            group = groups.setdefault(key, {"label": label, "items": []})
            if label < group["label"]:
                group["label"] = label
            group["items"].append((episode, occurred, quote))

    result: list[dict[str, Any]] = []
    for group in groups.values():
        items = sorted(group["items"], key=lambda item: (item[1], str(item[0].id)))
        days = sorted({item[1].date() for item in items})
        if len(days) < min_days:
            continue
        evidence = [
            {"episode_id": str(episode.id), "digest": str(episode.digest), "quote": quote}
            for episode, _, quote in items
        ]
        fingerprint = "|".join([group["label"], *(
            f"{entry['episode_id']}:{entry['digest']}" for entry in sorted(evidence, key=lambda e: (e["episode_id"], e["digest"]))
        )])
        pattern_id = "pattern-" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
        result.append({
            "id": pattern_id,
            "statement": f"Für {group['label']} liegen an {len(days)} Tagen Beobachtungen vor; mögliche Gewohnheit, bitte prüfen",
            "label": group["label"],
            "evidence": evidence,
            "observed_days": len(days),
            "window_start": start.date().isoformat(),
            "window_end": reference.date().isoformat(),
        })
    return sorted(result, key=lambda item: (item["label"].casefold(), item["id"]))


__all__ = ["detect_patterns", "MAX_EPISODES", "MAX_QUOTE_LENGTH"]
