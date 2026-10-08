"""Änderungen einer erneut gelesenen Datei sperren den früheren Beleg.

Aufrufer serialisieren Aufnahme und Wissensänderungen mit derselben Sperre.
Die Originalepisode bleibt erhalten; neue Inhalte sind weiterhin Rohmaterial.
"""
import hashlib
import json


def invalidate_with_corrections(episodes, claims, episode_id, *, at=None):
    """Auch Ableitungen aus Anhängen und gebundenen Berichtigungen sperren.

    Ein Berichtigungshead ist eine bestehende, indizierte Quellenbeziehung.
    Der gemeinsame Snapshot-Abruf erlaubt höchstens acht Ebenen; weitere
    Ebenen können ohnehin keine gültigen Wissensbelege sein.
    """
    seen = set()
    pending = [(episode_id, 0)]
    while pending:
        current, depth = pending.pop()
        if not current or current in seen or depth >= 8:
            continue
        seen.add(current)
        if at is None:
            claims.invalidate_source(current)
        else:
            claims.invalidate_source(current, at=at)
        pending.append((episodes.source_head('source-correction:' + current), depth + 1))
        pending.extend((child, depth + 1) for child in episodes._mail_attachment_descendants(current))


def source_key(root, reference):
    return hashlib.sha256(json.dumps([str(root.resolve()), reference], ensure_ascii=False).encode()).hexdigest()


def track_document(episodes, claims, root, reference, episode):
    return track_source(episodes, claims, source_key(root, reference), episode)


def track_source(episodes, claims, key, episode):
    previous = episodes.source_head(key)
    if previous == episode.id:
        return False
    if previous is not None:
        # Erst Wissen sperren. Bei Abbruch bleibt der alte Zeiger stehen,
        # damit ein erneuter Lauf den unvollständigen Wechsel wiederholt.
        if claims is None:
            raise ValueError("Für Quellenänderungen muss der Wissensspeicher verfügbar sein.")
        invalidate_with_corrections(episodes, claims, previous)
        episodes.ignore(previous)
    episodes.advance_source_head(key, previous, episode.id)
    return previous is not None


def exclude_missing_documents(episodes, claims, root, adapter, observed_files=None):
    """Nur nach vollständiger Aufnahme: bestätigte Abwesenheit sperrt Belege.

    Nicht erreichbare Ordner, Teilläufe und Lesefehler sind kein Löschbeweis.
    Der Aufrufer muss diese Fälle vor dem Aufruf ausschließen.
    """
    from pathlib import Path
    from .episodes import EpisodeState
    prefix = {"markdown": "vault:", "obsidian": "vault:", "notion": "notion:", "dateien": "datei:", "transkripte": "transkript:"}[adapter]
    root_before = root.stat()
    missing = []
    for key, episode in episodes.source_heads():
        reference = episode.provenance.source_ref or ""
        if not reference.startswith(prefix):
            continue
        if episode.state is EpisodeState.IGNORED:
            correction_id = episodes.source_head('source-correction:' + episode.id)
            correction = episodes.support_snapshot(correction_id) if correction_id else None
            if correction is None or not correction.correction_valid:
                continue
        if source_key(root, reference) != key:
            continue
        relative = reference[len(prefix):]
        if adapter == "notion":
            filename, separator, row = relative.rpartition("#")
            if separator and filename.lower().endswith(".csv") and row.isdigit():
                relative = filename
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            continue
        candidate = root / path
        if not candidate.resolve().is_relative_to(root.resolve()):
            continue
        try:
            candidate.stat()
            if observed_files is not None and relative in observed_files and reference not in observed_files[relative]:
                missing.append(episode.id)
        except FileNotFoundError:
            missing.append(episode.id)
        # PermissionError und andere I/O-Fehler werden zum fehlgeschlagenen
        # Lauf, niemals zu einer angenommenen Löschung.
    root_after = root.stat()
    if (root_before.st_dev, root_before.st_ino) != (root_after.st_dev, root_after.st_ino):
        raise OSError("Der Quellenordner wurde während der Prüfung geändert.")
    for episode_id in missing:
        invalidate_with_corrections(episodes, claims, episode_id)
        episodes.ignore(episode_id)
    return len(missing)
