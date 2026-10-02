"""Small, dependency-free parsers for common transcript text formats."""

from __future__ import annotations

import re


_MAX_CHARS = 2_000_000
_SRT_TIMESTAMP = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\Z")
_VTT_TIMESTAMP = re.compile(
    r"(?:(\d+):(\d{2}):([0-5]\d)\.(\d{3})|([0-5]\d):([0-5]\d)\.(\d{3}))\Z"
)
_CUE_ARROW = re.compile(r"^(.+?)\s+-->\s+(.+?)(?:\s+[^\r\n]*)?\Z")
_VOICE = re.compile(r"^<v(?:[ \t]+([^>\r\n]*?))?>(.*)\Z", re.DOTALL)


def _timestamp(value: str, kind: str) -> int:
    match = (_SRT_TIMESTAMP if kind == "srt" else _VTT_TIMESTAMP).fullmatch(value)
    if not match:
        raise ValueError(f"malformed {kind} timestamp")
    groups = match.groups()
    if kind == "srt":
        hours, minutes, seconds, millis = (int(part) for part in groups)
    elif groups[0] is not None:
        hours, minutes, seconds, millis = (int(part) for part in groups[:4])
    else:
        hours, minutes, seconds, millis = 0, int(groups[4]), int(groups[5]), int(groups[6])
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"invalid {kind} timestamp bounds")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def _segment(text: str, start_ms: int | None, end_ms: int | None, speaker: str | None = None) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("cue text must not be empty")
    if start_ms is not None and end_ms is not None and end_ms < start_ms:
        raise ValueError("cue interval is reversed")
    return {"text": text, "start_ms": start_ms, "end_ms": end_ms, "speaker": speaker}


def _blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _parse_srt(text: str) -> list[dict]:
    result = []
    for block in _blocks(text.splitlines()):
        if len(block) < 3 or not re.fullmatch(r"\d+", block[0].strip()):
            raise ValueError("malformed SRT cue")
        match = _CUE_ARROW.fullmatch(block[1].strip())
        if not match:
            raise ValueError("malformed SRT cue timestamp line")
        start = _timestamp(match.group(1), "srt")
        end = _timestamp(match.group(2), "srt")
        cue_text = "\n".join(block[2:])
        if any(_CUE_ARROW.fullmatch(line.strip()) for line in block[2:]):
            raise ValueError("malformed SRT cue boundary")
        result.append(_segment(cue_text, start, end))
    return result


def _voice_text(text: str) -> tuple[str, str | None]:
    match = _VOICE.fullmatch(text)
    if not match:
        return text, None
    label = match.group(1)
    speaker = label.strip() if label and label.strip() else None
    body = match.group(2)
    # WebVTT permits the final voice end tag to be omitted for a whole cue.
    # Mixed or malformed spans cannot safely be assigned to a single voice.
    if re.search(r"<v(?=[. \t>])", body):
        return text, None
    if "</v>" in body:
        if body.count("</v>") != 1 or not body.rstrip().endswith("</v>"):
            return text, None
        body = body.rstrip()[:-4]
    return body, speaker


def _parse_vtt(text: str) -> list[dict]:
    blocks = _blocks(text.splitlines())
    if not blocks:
        return []
    if not re.fullmatch(r"WEBVTT(?:[ \t].*)?", blocks[0][0].strip()):
        raise ValueError("VTT must start with WEBVTT")
    if any("-->" in line for line in blocks[0][1:]):
        raise ValueError("malformed VTT header")
    result = []
    for block in blocks[1:]:
        first = block[0].strip()
        if first == "NOTE" or first.startswith("NOTE ") or first in {"STYLE", "REGION"}:
            continue
        timestamp_index = 0
        if "-->" not in block[0]:
            timestamp_index = 1
        if timestamp_index >= len(block):
            raise ValueError("malformed VTT cue")
        match = _CUE_ARROW.fullmatch(block[timestamp_index].strip())
        if not match:
            raise ValueError("malformed VTT cue timestamp line")
        start = _timestamp(match.group(1), "vtt")
        end_value = match.group(2).split()[0]
        end = _timestamp(end_value, "vtt")
        cue_text, speaker = _voice_text("\n".join(block[timestamp_index + 1 :]))
        if "-->" in cue_text:
            raise ValueError("malformed VTT cue boundary")
        result.append(_segment(cue_text, start, end, speaker))
    return result


def parse_transcript(text: str, format: str) -> list[dict]:
    """Parse a bounded transcript into evidence-preserving cue dictionaries."""
    if not isinstance(text, str):
        raise ValueError("transcript must be text")
    if len(text) > _MAX_CHARS:
        raise ValueError("transcript exceeds 2 million characters")
    kind = format.lower() if isinstance(format, str) else ""
    if kind == "txt":
        stripped = text.lstrip("\ufeff").strip()
        return [] if not stripped else [_segment(stripped, None, None)]
    normalized = text.lstrip("\ufeff")
    if kind == "srt":
        if not normalized.strip():
            return []
        return _parse_srt(normalized)
    if kind == "vtt":
        if not normalized.strip():
            return []
        return _parse_vtt(normalized)
    raise ValueError("unsupported transcript format")
