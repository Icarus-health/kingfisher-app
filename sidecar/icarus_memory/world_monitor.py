"""Consent-bound monitoring of explicitly registered public web sources."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .source_versions import invalidate_with_corrections
from .episodes import EpisodeKind
from .model import Provenance, SourceType
from .source_versions import track_source
from .world_sources import _validate_url, fetch_public_text


class WorldMonitor:
    """Coordinate source refreshes without holding the settings lock on I/O."""

    def __init__(self, settings, episodes, claims, save: Callable, lock, fetch=None):
        self.settings = settings
        self.episodes = episodes
        self.claims = claims
        self.save = save
        self.lock = lock
        self.fetch = fetch or fetch_public_text

    def _persist(self) -> None:
        self.save(self.settings)

    def _find(self, source_id: str) -> dict[str, Any] | None:
        return next((item for item in self.settings.world_sources if item.get("id") == source_id), None)

    def add(self, url: str, label: str, topics: list[str]) -> dict[str, Any]:
        canonical = _validate_url(url)
        if not isinstance(label, str) or not (label := label.strip()) or len(label) > 200:
            raise ValueError("Das Label ist leer oder zu lang.")
        if not isinstance(topics, list) or any(not isinstance(topic, str) or not topic.strip() for topic in topics):
            raise ValueError("Themen müssen nichtleere Texte sein.")
        clean_topics = list(dict.fromkeys(topic.strip() for topic in topics))
        with self.lock:
            if any(item.get("url") == canonical for item in self.settings.world_sources):
                raise ValueError("Diese Quelle ist bereits registriert.")
            source = {
                "id": str(uuid.uuid4()), "url": canonical, "label": label,
                "topics": clean_topics, "enabled": True, "episode_id": None,
                "last_success": None, "error": None, "truncated": False,
            }
            self.settings.world_sources.append(source)
            self._persist()
            return dict(source)

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            result = []
            now = datetime.now(timezone.utc)
            for source in self.settings.world_sources:
                if not isinstance(source, dict):
                    continue
                ignored = False
                if source.get("episode_id"):
                    try:
                        ignored = getattr(self.episodes.get(source["episode_id"]), "state", None).value == "ignored"
                    except (AttributeError, KeyError, TypeError):
                        ignored = False
                if not source.get("enabled", True):
                    status = "disabled"
                elif ignored:
                    status = "ignored"
                elif source.get("error") or self._is_stale(source.get("last_success"), now):
                    status = "stale"
                elif source.get("last_success"):
                    status = "ok"
                else:
                    status = "pending"
                result.append({
                    "id": source.get("id"), "url": source.get("url"),
                    "label": source.get("label", ""), "topics": list(source.get("topics", [])),
                    "enabled": bool(source.get("enabled", True)),
                    "episode_id": source.get("episode_id"),
                    "last_success": source.get("last_success"),
                    "error": "Quelle konnte zuletzt nicht aktualisiert werden." if source.get("error") else None,
                    "truncated": bool(source.get("truncated", False)), "status": status,
                })
            return result

    @staticmethod
    def _is_stale(value: str | None, now: datetime) -> bool:
        if not value:
            return False
        try:
            captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if captured.tzinfo is None:
                return True
            return not timedelta(0) <= now - captured.astimezone(timezone.utc) <= timedelta(hours=24)
        except (TypeError, ValueError, AttributeError):
            return True

    @staticmethod
    def _captured_at(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    def refresh(self, source_id: str, *, permitted=lambda: True) -> dict[str, Any]:
        with self.lock:
            source = self._find(source_id)
            if source is None:
                raise KeyError(source_id)
            if not source.get("enabled", True):
                raise ValueError("Quelle ist deaktiviert.")
            requested_url = source.get("url")
            expected_episode_id = source.get("episode_id")
            expected_last_success = source.get("last_success")
        try:
            fetched = self.fetch(requested_url)
        except Exception:
            with self.lock:
                source = self._find(source_id)
                if (source is not None and source.get("enabled", True)
                        and source.get("url") == requested_url
                        and source.get("episode_id") == expected_episode_id
                        and source.get("last_success") == expected_last_success):
                    source["error"] = "refresh_failed"
                    self._persist()
            raise ValueError("Quelle konnte nicht aktualisiert werden.")

        with self.lock:
            source = self._find(source_id)
            if (source is None or not source.get("enabled", True) or source.get("url") != requested_url
                    or source.get("episode_id") != expected_episode_id
                    or source.get("last_success") != expected_last_success or not permitted()):
                raise ValueError("Quelle wurde während der Aktualisierung geändert oder deaktiviert.")
            captured = fetched.get("captured_at")
            provenance = Provenance(
                source_type=SourceType.WEB, source_ref=requested_url,
                captured_at=self._captured_at(captured), verbatim=fetched["text"],
            )
            episode, _created = self.episodes.record(
                EpisodeKind.DOCUMENT, source.get("label", requested_url), fetched["text"], provenance,
                tags=list(source.get("topics", [])), source_key=f"world:{source_id}",
            )
            track_source(self.episodes, self.claims, f"world:{source_id}", episode)
            source.update({
                "episode_id": episode.id, "last_success": captured,
                "error": None, "truncated": bool(fetched.get("truncated", False)),
            })
            self._persist()
            return dict(source)

    def disable(self, source_id: str) -> None:
        with self.lock:
            source = self._find(source_id)
            if source is None:
                raise KeyError(source_id)
            episode_id = source.get("episode_id") or self.episodes.source_head(f"world:{source_id}")
            if episode_id:
                invalidate_with_corrections(self.episodes, self.claims, episode_id)
                self.episodes.ignore(episode_id)
            source["enabled"] = False
            self._persist()


__all__ = ["WorldMonitor"]
