"""Release und Download-Seite (scripts/release_seite.py, .github/workflows/release.yml, site/index.html; docs/53).

Die wichtigste Zusage: Das Manifest, das der Workflow veröffentlicht, ist genau eines, das der Sidecar annimmt.
Sonst sähe niemand je ein Update-Angebot, und kein Test im Sidecar fiele auf.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from icarus_memory.fassung import manifest_pruefen, semver

WURZEL = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('release_seite', WURZEL / 'scripts' / 'release_seite.py')
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)
WORKFLOW = WURZEL / '.github' / 'workflows' / 'release.yml'


def test_manifest_der_aktuellen_fassung_nimmt_der_sidecar_an(tmp_path):
    fassung = (WURZEL / 'VERSION').read_text(encoding='utf-8').strip()
    daten = release.bauen(fassung, 'Icarus-health/kingfisher-app', tmp_path, datum='2026-10-02')
    geschrieben = json.loads((tmp_path / 'latest.json').read_text(encoding='utf-8'))
    assert geschrieben == daten
    assert manifest_pruefen(geschrieben) == geschrieben
    assert geschrieben['dmg'] == f'https://github.com/Icarus-health/kingfisher-app/releases/download/v{fassung}/Kingfisher.dmg'
    assert geschrieben['image'] == f'ghcr.io/icarus-health/kingfisher-app:{fassung}'
    for datei in ('index.html', 'kingfisher.png', 'Inter-Regular.ttf', 'Inter-SemiBold.ttf', '.nojekyll'):
        assert (tmp_path / datei).is_file(), datei


def test_jede_notiz_hat_neuerungen_und_eine_gueltige_app_fassung():
    notizen = sorted((WURZEL / 'docs' / 'fassungen').glob('*.md'))
    assert notizen, 'docs/fassungen/ ist leer'
    for notiz in notizen:
        assert semver(notiz.stem) is not None, notiz.name
        text = notiz.read_text(encoding='utf-8')
        assert manifest_pruefen(release.manifest(notiz.stem, 'o/r', '2026-10-02', text)) is not None, notiz.name


def test_tag_muss_version_sein():
    fassung = (WURZEL / 'VERSION').read_text(encoding='utf-8').strip()
    assert release.pruefen(f'v{fassung}') == fassung
    for falsch in (fassung, f'v{fassung}-rc1', 'v0.0.0', f'V{fassung}'):
        with pytest.raises(release.Fehler, match='passt nicht zu VERSION'):
            release.pruefen(falsch)


def test_ohne_notiz_kein_release(tmp_path):
    (tmp_path / 'VERSION').write_text('2.0.0\n')
    with pytest.raises(release.Fehler, match='docs/fassungen/2.0.0.md'):
        release.pruefen('v2.0.0', wurzel=tmp_path)


def test_hinweise_eine_zeile_je_spiegelstrich():
    text = '# Titel\n\nEinleitung.\n\n- Erstens.\n* Zweitens, mit\n  Fortsetzung.\n\nApp mindestens: 1.1.0\n'
    assert release.hinweise(text) == ['Erstens.', 'Zweitens, mit Fortsetzung.']
    assert release.manifest('1.2.0', 'o/r', '2026-10-02', text)['app_mindestens'] == '1.1.0'
    assert release.manifest('1.2.0', 'o/r', '2026-10-02', '- Eins.\n')['app_mindestens'] == '1.0.0'
    with pytest.raises(release.Fehler):
        release.manifest('1.2.0', 'o/r', '2026-10-02', 'Kein Spiegelstrich.\n')
    with pytest.raises(release.Fehler):
        release.manifest('1.2.0', 'o/r; rm', '2026-10-02', '- Eins.\n')


def test_seite_ohne_platzhalter_ohne_skripte_ohne_fremde_quellen(tmp_path):
    release.bauen('1.0.0', 'Icarus-health/kingfisher-app', tmp_path, datum='2026-10-02')
    html = (tmp_path / 'index.html').read_text(encoding='utf-8')
    assert '{{' not in html and '<script' not in html.lower()
    assert 'href="https://github.com/Icarus-health/kingfisher-app/releases/latest/download/Kingfisher.dmg"' in html
    assert 'Fassung 1.0.0 vom 2. Oktober 2026' in html
    # Was die Seite selbst lädt (src=, url(), <link href>), liegt neben ihr.
    geladen = re.findall(r'src="([^"]+)"', html) + re.findall(r'url\("([^"]+)"\)', html) + re.findall(r'<link[^>]+href="([^"]+)"', html)
    assert geladen and all(not re.match(r'^[a-z]+:|^//', ziel) for ziel in geladen), geladen
    for satz in ('Docker Desktop installieren und einmal öffnen', '„Dennoch öffnen“', 'rechten Maustaste',
                 'Ollama installieren', 'Neue Fassungen kommen von selbst'):
        assert satz in html, satz


def test_seite_nie_mit_geraden_anfuehrungszeichen_im_text():
    vorlage = (WURZEL / 'site' / 'index.html').read_text(encoding='utf-8')
    assert '„' in vorlage and not re.search(r'„[^“"<]*"', vorlage)


def test_workflow_reihenfolge_und_rechte():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'tags: ["v*"]' in text and 'workflow_dispatch:' in text
    assert 'scripts/release_seite.py pruefen --tag' in text
    # Von Hand gestartet, legt der Lauf einen fehlenden Tag erst nach der Prüfung von VERSION an.
    anlegen = text.index('Tag anlegen, falls er fehlt')
    assert text.index('release_seite.py pruefen --tag', anlegen) < text.index('git tag "$TAG"', anlegen)
    assert 'platforms: linux/amd64,linux/arm64' in text
    assert '${{ env.IMAGE }}:${{ needs.fassung.outputs.fassung }}' in text and '${{ env.IMAGE }}:latest' in text
    assert 'KINGFISHER_FASSUNG=${{ needs.fassung.outputs.fassung }}' in text
    assert 'uses: ./.github/workflows/mac-app.yml' in text and 'fassung: ${{ needs.fassung.outputs.fassung }}' in text
    assert 'name: Kingfisher.dmg' in text
    # latest.json erst nach Bild, App und Release.
    assert 'needs: [fassung, bild, mac]' in text and 'needs: [fassung, release]' in text
    assert re.search(r'^permissions:\n  contents: read$', text, re.M), 'oben nur Lesen; Schreibrechte je Job'
    for recht in ('packages: write', 'contents: write', 'pages: write', 'id-token: write'):
        assert recht in text, recht
    assert 'actions/deploy-pages@' in text and 'name: github-pages' in text
    container = (WURZEL / '.github' / 'workflows' / 'container.yml').read_text(encoding='utf-8')
    assert 'tags: ["v*"]' not in container and 'value=latest' not in container, ':latest gehört dem Release'
