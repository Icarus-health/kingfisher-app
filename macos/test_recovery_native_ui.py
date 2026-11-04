"""Native recovery selection is tested without launching an app or Docker."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_recovery_selection_and_consent_are_closed(tmp_path):
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    binary = tmp_path / 'recovery-selection'
    result = subprocess.run([compiler, '-module-cache-path', str(tmp_path / 'cache'),
        str(ROOT / 'macos/App/Logic/RecoverySelection.swift'),
        str(ROOT / 'macos/tests/recovery_native/main.swift'), '-o', str(binary)],
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert 'consent and loopback boundaries passed' in result.stdout


def test_helper_uses_stdin_suppresses_private_errors_and_drains_output(tmp_path):
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    helper = tmp_path / 'helper with spaces.py'
    helper.write_text('''import json, os, sys, time
request=json.load(sys.stdin)
assert len(sys.argv)==1
assert 'ANTHROPIC_API_KEY' not in os.environ
mode=request['operation']
if mode=='extract':
    assert request['password']=='synthetic-$(never-execute)'
    print(json.dumps({'ok':True,'folder':request['target']}))
elif mode=='bad-json': print('synthetic-private-value')
elif mode=='private-stderr':
    print('synthetic-private-value',file=sys.stderr)
    sys.exit(1)
elif mode=='oversized': print('x'*(8*1024*1024+1))
elif mode=='chunked':
    value=json.dumps({'ok':True,'large':'x'*(512*1024),'tail':'complete'})
    for offset in range(0,len(value),513):
        sys.stdout.write(value[offset:offset+513]);sys.stdout.flush()
''')
    (tmp_path / 'blocked.py').write_text('import time; time.sleep(10)\n')
    binary = tmp_path / 'recovery-helper'
    result = subprocess.run([compiler, '-module-cache-path', str(tmp_path / 'cache'),
        str(ROOT / 'macos/App/RecoveryHelperClient.swift'),
        str(ROOT / 'macos/tests/recovery_client/main.swift'), '-o', str(binary)],
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    import os
    result = subprocess.run([str(binary), str(helper)], capture_output=True, text=True,
        timeout=30, env={**os.environ, 'ANTHROPIC_API_KEY':'synthetic-private-value'})
    assert result.returncode == 0, result.stderr
    assert 'bounded output passed' in result.stdout
    assert 'synthetic-private-value' not in result.stdout + result.stderr


def test_recovery_is_packaged_separate_and_does_not_attach_main_bridges():
    build = (ROOT / 'macos/build_dmg.sh').read_text()
    delegate = (ROOT / 'macos/App/AppDelegate.swift').read_text()
    controller = (ROOT / 'macos/App/RecoveryWindowController.swift').read_text()
    assert 'scripts/recovery_native.py "$APP/Contents/Resources/recovery-native.py"' in build
    assert 'Sicherung wiederherstellen …' in delegate and 'Arbeitskopie öffnen …' in delegate
    assert 'WKWebsiteDataStore(forIdentifier: identifier)' in controller
    assert 'BridgeHandler(' not in controller
    assert 'NSWorkspace.shared.open(origin)' not in controller
    assert 'NSSecureTextField(' in controller


def test_close_warnings_cover_all_recovery_browsers_and_reload_uses_focus():
    controller = (ROOT / 'macos/App/RecoveryWindowController.swift').read_text()
    delegate = (ROOT / 'macos/App/AppDelegate.swift').read_text()
    assert 'var needsDraftQuitConfirmation: Bool { surface != nil }' in controller
    assert 'if needsDraftQuitConfirmation && !closeConfirmed' in controller
    assert 'transientBrowser' not in controller
    assert 'needsDraftQuitConfirmation' in delegate
    assert 'recoveryQuitConfirmed = false' in delegate
    assert 'NSApp.keyWindow' in delegate
    assert 'RecoveryReloadTarget.resolve' in delegate
    assert 'validateMenuItem' in delegate and 'activeReloadTarget != .none' in delegate
    assert 'recoveryWindows.first { $0.identifier == identifier }?.reloadPage()' in delegate
