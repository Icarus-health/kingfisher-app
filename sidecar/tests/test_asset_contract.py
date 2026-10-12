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


@pytest.fixture
def frontend_gate(asset_copy, tmp_path, monkeypatch):
    manifest, design = asset_copy
    for name in manifest['icons']['approvedNames']:
        for variant in ('Filled', 'Outline'):
            path = design / '02_Icons/Approved' / variant / f'{name}.svg'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('<svg/>')
    ui = tmp_path / 'frontend'
    ui.mkdir()
    (ui / 'ui.ts').write_text('export const NAV = [["Heute", "house"], ["Gedächtnis", "brain"]] as const;')
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(asset_check, 'UI', ui)
    monkeypatch.setattr(asset_check, 'DESIGN', design)
    monkeypatch.setattr(asset_check, 'MANIFEST', path)
    return ui, design


def test_status_lists_are_not_icon_references(frontend_gate, capsys):
    ui, _ = frontend_gate
    (ui / 'status.ts').write_text('if (["failed", "expired"].includes(status)) retry();\n'
                                 'const states = [["import", "paused"], ["source", "unknown"]];')
    asset_check.main()
    assert 'asset-check: pass' in capsys.readouterr().out


def test_unapproved_navigation_icon_still_fails(frontend_gate, capsys):
    ui, _ = frontend_gate
    (ui / 'ui.ts').write_text('export const NAV = [["Heute", "unapproved-glyph"]] as const;')
    with pytest.raises(SystemExit):
        asset_check.main()
    assert 'unapproved-glyph' in capsys.readouterr().err


@pytest.mark.parametrize('call', ['icon("unapproved-glyph")', "icon('unapproved-glyph')", 'icon(\n "unapproved-glyph", "Outline")'])
def test_unapproved_direct_icon_still_fails(frontend_gate, capsys, call):
    ui, _ = frontend_gate
    (ui / 'screen.tsx').write_text(f'const image = {call};')
    with pytest.raises(SystemExit):
        asset_check.main()
    assert 'unapproved-glyph' in capsys.readouterr().err


def test_missing_icon_variant_still_fails(frontend_gate, capsys):
    _, design = frontend_gate
    (design / '02_Icons/Approved/Outline/house.svg').unlink()
    with pytest.raises(SystemExit):
        asset_check.main()
    assert 'Outline/house.svg' in capsys.readouterr().err


def test_nonliteral_navigation_cannot_silently_skip_icon_validation(frontend_gate, capsys):
    ui, _ = frontend_gate
    (ui / 'ui.ts').write_text('export const NAV = [["Heute", unknownIcon]] as const;')
    with pytest.raises(SystemExit):
        asset_check.main()
    assert 'Navigation' in capsys.readouterr().err


def test_commented_navigation_cannot_hide_unapproved_real_navigation(frontend_gate, capsys):
    ui, _ = frontend_gate
    (ui / 'ui.ts').write_text('// export const NAV = [["Beispiel", "house"]] as const;\n'
                             'export const NAV = [["Heute", "unapproved-glyph"]] as const;')
    with pytest.raises(SystemExit):
        asset_check.main()
    assert 'unapproved-glyph' in capsys.readouterr().err


def test_navigation_example_in_text_is_not_an_actual_declaration(frontend_gate):
    ui, _ = frontend_gate
    (ui / 'ui.ts').write_text('const example = \'export const NAV = [["Beispiel", "unapproved-glyph"]] as const;\';\n'
                             'export const NAV = [["Heute", "house"]] as const;')
    asset_check.main()
