import subprocess

import pytest

from icarus_memory import secrets


@pytest.mark.parametrize(
    "backend,not_found",
    [
        ("macos", "The specified item could not be found in the keychain."),
        ("secret-tool", "No such secret was found."),
    ],
)
def test_delete_ignores_only_explicit_not_found(backend, not_found, monkeypatch):
    keychain = secrets.Keychain()
    keychain._backend = backend
    monkeypatch.setattr(
        secrets,
        "_run",
        lambda command, stdin=None: subprocess.CompletedProcess(command, 1, "", not_found),
    )

    keychain.delete("MISTRAL_API_KEY")


@pytest.mark.parametrize("backend", ["macos", "secret-tool"])
def test_delete_surfaces_permission_failures(backend, monkeypatch):
    keychain = secrets.Keychain()
    keychain._backend = backend
    monkeypatch.setattr(
        secrets,
        "_run",
        lambda command, stdin=None: subprocess.CompletedProcess(command, 1, "", "Permission denied"),
    )

    with pytest.raises(secrets.KeychainError, match="Permission denied"):
        keychain.delete("MISTRAL_API_KEY")


def test_windows_delete_ignores_missing_file_but_surfaces_denial(monkeypatch):
    keychain = secrets.Keychain()
    keychain._backend = "windows"
    monkeypatch.setattr(keychain, "_windows_path", lambda name: "synthetic-secret-path")
    monkeypatch.setattr(secrets.Path, "unlink", lambda *args, **kwargs: None)
    keychain.delete("MISTRAL_API_KEY")
    monkeypatch.setattr(
        secrets.Path,
        "unlink",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )
    with pytest.raises(secrets.KeychainError, match="denied"):
        keychain.delete("MISTRAL_API_KEY")


def test_windows_set_passes_secret_as_stdin_not_powershell_source(monkeypatch, tmp_path):
    keychain = secrets.Keychain()
    keychain._backend = "windows"
    monkeypatch.setattr(keychain, "_windows_path", lambda name: str(tmp_path / "synthetic'path" / "key.dpapi"))
    calls = []
    monkeypatch.setattr(
        secrets,
        "_run",
        lambda command, stdin=None: calls.append((command, stdin))
        or subprocess.CompletedProcess(command, 0, "", ""),
    )
    secret = "synthetic'; Start-Process calc; 'credential"

    keychain.set("MISTRAL_API_KEY", secret)

    assert len(calls) == 1
    command, stdin = calls[0]
    assert stdin == secret
    assert secret not in " ".join(command)
