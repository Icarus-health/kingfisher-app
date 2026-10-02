"""Die Postfachprobe ist reproduzierbar, netzfrei und überschreibt nichts."""
import json
import subprocess
import sys
from pathlib import Path

import probe_working_memory_scale as probe

SCRIPT = Path(probe.__file__)


def test_mailbox_is_reproducible_and_needles_are_unique():
    first, second = probe.mailbox(120, 20, 7), probe.mailbox(120, 20, 7)
    assert first == second and len(first) == 120
    needles = [item for item in first if item['needle']]
    assert len(needles) == 20
    facts = [item['fact'] for item in first]
    # Keine Nadel-Angabe kommt ein zweites Mal vor; Ablenker teilen nur Teile.
    assert all(facts.count(item['fact']) == 1 for item in needles)


def test_small_run_finds_needles_without_model_or_network():
    report = probe.run(120, needles=20, seed=7)
    assert report['synthetic_only'] and not report['network_used'] and not report['model_called']
    assert report['eingeordnet'] == 120
    assert report['ergebnis']['fragen'] == 20
    assert report['ergebnis'][f'nadel_in_top_{probe.MAX_REFS}'] == 20
    assert report['ergebnis']['nadel_beim_modell'] == 20


def test_existing_output_is_never_overwritten(tmp_path):
    target = tmp_path / 'bericht.json'
    target.write_text('{}', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), '--sizes', '50', '--needles', '5',
                             '--output', str(target)], capture_output=True, text=True)
    assert result.returncode != 0 and 'existiert bereits' in result.stderr
    assert json.loads(target.read_text(encoding='utf-8')) == {}
