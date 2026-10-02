import pytest

from icarus_memory.transcript_import import parse_transcript


def test_plain_text_is_one_stripped_segment_and_empty_is_empty():
    assert parse_transcript("\ufeff  Hello\nworld  ", "txt") == [
        {"text": "Hello\nworld", "start_ms": None, "end_ms": None, "speaker": None}
    ]
    assert parse_transcript(" \r\n", "txt") == []


def test_srt_preserves_multiline_text_and_crlf_timestamps():
    source = "1\r\n00:01:02,003 --> 00:01:04,500\r\nHello\r\nsecond line\r\n\r\n"
    assert parse_transcript(source, "srt") == [
        {"text": "Hello\nsecond line", "start_ms": 62003, "end_ms": 64500, "speaker": None}
    ]


def test_vtt_supports_short_timestamps_and_voice_labels():
    source = "\ufeffWEBVTT\n\n00:02.500 --> 00:04.000\n<v Moderator>Hello</v>\n"
    assert parse_transcript(source, "vtt") == [
        {"text": "Hello", "start_ms": 2500, "end_ms": 4000, "speaker": "Moderator"}
    ]


def test_vtt_preserves_multiple_consecutive_cues_with_optional_ids_and_settings():
    source = (
        "WEBVTT\n\n"
        "01\n"
        "00:00:01.000 --> 00:00:02.500 line:10%\n"
        "first\n\n"
        "02\n"
        "00:00:03.000 --> 00:00:04.500 align:middle\n"
        "second\n"
    )
    assert parse_transcript(source, "vtt") == [
        {"text": "first", "start_ms": 1000, "end_ms": 2500, "speaker": None},
        {"text": "second", "start_ms": 3000, "end_ms": 4500, "speaker": None},
    ]


def test_unicode_and_crlf_are_preserved_in_vtt():
    source = "WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000 line:50%\r\n<v Sprecher>Grüße 👋 München, Café!</v>\r\n"
    assert parse_transcript(source, "vtt") == [
        {"text": "Grüße 👋 München, Café!", "start_ms": 1000, "end_ms": 2000, "speaker": "Sprecher"}
    ]


def test_vtt_metadata_blocks_are_ignored_and_html_stays_literal():
    source = "WEBVTT\n\nNOTE\nproducer metadata\n\nSTYLE\n::cue { color: red }\n\n00:00:01.000 --> 00:00:02.000\n<b>literal</b>\n"
    assert parse_transcript(source, "vtt")[0]["text"] == "<b>literal</b>"


def test_empty_vtt_and_header_without_blank_line_are_handled_strictly():
    assert parse_transcript("", "vtt") == []
    with pytest.raises(ValueError):
        parse_transcript("WEBVTT\n00:00:01.000 --> 00:00:02.000\ntext", "vtt")


def test_multiple_vtt_voice_tags_are_not_misattributed():
    source = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v A>one</v> <v B>two</v>\n"
    cue = parse_transcript(source, "vtt")[0]
    assert cue["speaker"] is None
    assert cue["text"] == "<v A>one</v> <v B>two</v>"


def test_voice_label_does_not_cover_text_after_closing_tag():
    source = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v A>one</v> unlabelled\n"
    cue = parse_transcript(source, "vtt")[0]
    assert cue["speaker"] is None
    assert cue["text"] == "<v A>one</v> unlabelled"


def test_whole_cue_voice_may_omit_end_tag():
    source = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v A>only open\n"
    cue = parse_transcript(source, "vtt")[0]
    assert cue["speaker"] == "A"
    assert cue["text"] == "only open"


@pytest.mark.parametrize(
    "source, kind",
    [
        ("1\n00:61:00,000 --> 00:62:00,000\ntext", "srt"),
        ("1\n00:00:02,000 --> 00:00:01,000\ntext", "srt"),
        ("WEBVTT\n\n00:00:02.000 --> 00:00:01.000\ntext", "vtt"),
        ("WEBVTT\n\n00:00:01.000 --> nope\ntext", "vtt"),
        ("1\n00:00:01,000 --> 00:00:02,000\n", "srt"),
        ("WEBVTTgarbage\n\n00:00:01.000 --> 00:00:02.000\ntext", "vtt"),
        ("WEBVTT\n\n00:00:60.000 --> 00:01:02.000\ntext", "vtt"),
        ("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n", "vtt"),
    ],
)
def test_malformed_or_invalid_cues_are_rejected(source, kind):
    with pytest.raises(ValueError):
        parse_transcript(source, kind)


def test_unsupported_and_oversized_formats_are_rejected():
    with pytest.raises(ValueError):
        parse_transcript("text", "macwhisper-json")
    with pytest.raises(ValueError):
        parse_transcript("x" * 2_000_001, "txt")


@pytest.mark.parametrize("kind,source", [
    ("srt", "1\n00:00:01,000 --> 00:00:02,000\nFirst\n2\n00:00:03,000 --> 00:00:04,000\nSecond"),
    ("vtt", "WEBVTT\n\n00:01.000 --> 00:02.000\nFirst\n00:03.000 --> 00:04.000\nSecond"),
])
def test_missing_cue_separator_is_not_silently_merged(kind, source):
    with pytest.raises(ValueError):
        parse_transcript(source, kind)
