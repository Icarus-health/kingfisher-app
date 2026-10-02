from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from icarus_memory.mail_sync_status import record_attempt, record_failure, record_success


def _settings():
    return SimpleNamespace(mail_sync_status={})


def test_attempt_creates_utc_status_without_sensitive_values():
    settings = _settings()
    result = record_attempt(settings, "mail-work")
    assert result["consecutive_failures"] == 0
    parsed = datetime.fromisoformat(result["last_attempt"])
    assert parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    assert settings.mail_sync_status["mail-work"] is result
    assert "password" not in str(result).lower()


def test_success_records_bounded_counts_and_resets_failures():
    settings = _settings()
    record_failure(settings, "work", "unavailable")
    result = record_success(settings, "work", {"recorded": 3, "duplicates": 2, "secret": "nope"})
    assert result["consecutive_failures"] == 0
    assert result["last_success"] == result["last_attempt"]
    assert result["last_report"] == {"recorded": 3, "duplicates": 2}
    assert "secret" not in result["last_report"]


def test_failure_keeps_last_success_and_allows_only_safe_codes():
    settings = _settings()
    success = record_success(settings, "work", {"recorded": 1, "duplicates": 0})
    failed = record_failure(settings, "work", "credentials_missing")
    assert failed["consecutive_failures"] == 1
    assert failed["last_success"] == success["last_success"]
    assert failed["last_failure"] == "credentials_missing"
    with pytest.raises(ValueError):
        record_failure(settings, "work", "imap password leaked")


def test_config_roundtrip_keeps_status():
    from icarus_memory.config import Settings
    settings = Settings()
    record_success(settings, 'work', {'recorded': 4, 'duplicates': 0})
    record_failure(settings, 'work')
    assert Settings.from_dict(settings.to_dict()).mail_sync_status == settings.mail_sync_status
