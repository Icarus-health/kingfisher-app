"""Bounded, read-only previews for imported SRT and WebVTT transcripts."""

from __future__ import annotations

from .transcript_import import parse_transcript


_MAX_BYTES = 512 * 1024


def _timecode(milliseconds: int) -> str:
    seconds, millis = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def preview_transcript(text: str, format: str) -> dict:
    """Return a bounded display body and cue count without storing the input."""
    if not isinstance(text, str):
        raise ValueError("Das Transkript muss Text sein.")
    if "\x00" in text:
        raise ValueError("Das Transkript darf kein NUL-Zeichen enthalten.")
    try:
        input_bytes = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Das Transkript enthält ungültige Unicode-Zeichen.") from exc
    if len(input_bytes) > _MAX_BYTES:
        raise ValueError("Das Transkript darf höchstens 512 KiB groß sein.")
    if not text.lstrip("\ufeff").strip():
        raise ValueError("Das Transkript darf nicht leer sein.")

    kind = format.lower() if isinstance(format, str) else ""
    if kind not in {"srt", "vtt"}:
        raise ValueError("Bitte verwenden Sie das Format SRT oder VTT.")
    try:
        segments = parse_transcript(text, kind)
    except ValueError as exc:
        raise ValueError(f"Das Transkript ist ungültig: {exc}.") from exc
    if not segments:
        raise ValueError("Das Transkript enthält keine Segmente.")

    lines = []
    for segment in segments:
        start = _timecode(segment["start_ms"])
        end = _timecode(segment["end_ms"])
        prefix = f"[{start} – {end}]"
        speaker = segment.get("speaker")
        if speaker is not None:
            prefix += f" {speaker}:"
        lines.append(f"{prefix} {segment['text']}")
    body = "\n\n".join(lines)
    if "\x00" in body or not body:
        raise ValueError("Die Vorschau darf nicht leer sein oder NUL-Zeichen enthalten.")
    try:
        output_bytes = body.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Die Vorschau enthält ungültige Unicode-Zeichen.") from exc
    if len(output_bytes) > _MAX_BYTES:
        raise ValueError("Die Vorschau darf höchstens 512 KiB groß sein.")
    return {"body": body, "segment_count": len(segments)}
