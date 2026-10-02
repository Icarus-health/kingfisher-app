import pytest

from icarus_memory.transcript_preview import preview_transcript


def test_srt_preview_formats_milliseconds_and_separates_segments():
    source = (
        "1\n00:01:02,003 --> 00:01:04,500\nErste Zeile\n"
        "\n2\n00:01:05,000 --> 00:01:06,007\nZweite Zeile\n"
    )
    assert preview_transcript(source, "srt") == {
        "body": "[00:01:02.003 – 00:01:04.500] Erste Zeile\n\n"
        "[00:01:05.000 – 00:01:06.007] Zweite Zeile",
        "segment_count": 2,
    }


def test_vtt_preview_keeps_unicode_and_only_explicit_speaker_labels():
    source = (
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n"
        "<v Sprecher>Grüße 👋</v>\n\n00:00:03.000 --> 00:00:04.000\nOhne Zuordnung\n"
    )
    result = preview_transcript(source, "vtt")
    assert result["body"] == (
        "[00:00:01.000 – 00:00:02.000] Sprecher: Grüße 👋\n\n"
        "[00:00:03.000 – 00:00:04.000] Ohne Zuordnung"
    )
    assert result["segment_count"] == 2


@pytest.mark.parametrize("text, kind", [("", "srt"), ("   \n", "vtt"), ("WEBVTT\n", "vtt")])
def test_empty_transcripts_are_rejected_with_german_message(text, kind):
    with pytest.raises(ValueError, match="leer|keine Segmente"):
        preview_transcript(text, kind)


def test_malformed_transcript_is_rejected_with_german_message():
    with pytest.raises(ValueError, match="ungültig"):
        preview_transcript("1\nnot a timestamp\nText", "srt")


@pytest.mark.parametrize("text", ["x" * (512 * 1024 + 1), "\x00"])
def test_input_limits_and_nul_are_rejected(text):
    with pytest.raises(ValueError, match="512 KiB|NUL"):
        preview_transcript(text, "srt")


def test_output_expansion_limit_is_checked_in_utf8_bytes(monkeypatch):
    # Keep the parser input small while exercising the independently bounded output.
    monkeypatch.setattr(
        "icarus_memory.transcript_preview.parse_transcript",
        lambda *_: [{"start_ms": 0, "end_ms": 1000, "speaker": None, "text": "x" * (512 * 1024)}],
    )
    with pytest.raises(ValueError, match="Vorschau.*512 KiB"):
        preview_transcript("1\n00:00:00,000 --> 00:00:01,000\nx", "srt")


def test_only_srt_and_vtt_are_supported():
    with pytest.raises(ValueError, match="SRT oder VTT"):
        preview_transcript("text", "txt")
