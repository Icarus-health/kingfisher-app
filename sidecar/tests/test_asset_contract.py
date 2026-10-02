"""Ein grüner Build darf fehlende Originalgrafiken und Schriften nicht verdecken."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "asset_check", Path(__file__).resolve().parents[2] / "scripts/check_asset_manifest.py")
asset_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asset_check)


@pytest.fixture
def asset_copy(tmp_path):
    manifest = json.loads(asset_check.MANIFEST.read_text())
    for relative in asset_check.required_files(manifest):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Hier wird Vollständigkeit geprüft, nicht Bildinhalt oder Gestaltung.
        path.write_bytes(b"test-only asset presence fixture")
    return manifest, tmp_path


# Die Bildvorlagen unter 06_Screens wurden vor der Veröffentlichung entfernt; ihr Manifest-Eintrag ist leer.
@pytest.mark.parametrize("category", ["logo", "font", "media"])
def test_missing_approved_file_fails_release_gate(asset_copy, category, capsys):
    manifest, directory = asset_copy
    path = {
        "logo": manifest["brand"]["logoDark"],
        "font": manifest["fonts"]["source"] + "/" + manifest["fonts"]["ui"][0],
        "media": manifest["media"]["source"] + "/" + manifest["media"]["approved"][0],
    }[category]
    (directory / path).unlink()
    with pytest.raises(SystemExit):
        asset_check.check_required_files(manifest, directory)
    assert path in capsys.readouterr().err


def test_complete_copy_passes_but_zero_byte_font_fails(asset_copy):
    manifest, directory = asset_copy
    asset_check.check_required_files(manifest, directory)
    font = directory / manifest["fonts"]["source"] / manifest["fonts"]["ui"][0]
    font.write_bytes(b"")
    with pytest.raises(SystemExit):
        asset_check.check_required_files(manifest, directory)
