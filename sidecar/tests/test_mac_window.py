"""Native wrapper boundaries; no Docker, user app, or live data is touched."""
from pathlib import Path
import subprocess
import sys
import pytest

REPO = Path(__file__).parents[2]


def test_builder_rejects_remote_origin_before_building(tmp_path):
    result = subprocess.run([sys.executable, str(REPO/'scripts/build_mac_window.py'),
                             '--env-file', str(tmp_path/'private.env'), '--container', 'pilot',
                             '--url', 'https://example.com', '--output', str(tmp_path/'Kingfisher.app')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert '127.0.0.1' in result.stderr
    assert not (tmp_path/'Kingfisher.app').exists()


def test_builder_preserves_existing_app(tmp_path):
    output = tmp_path/'Kingfisher.app'
    output.mkdir()
    marker = output/'keep'
    marker.write_text('existing')
    result = subprocess.run([sys.executable, str(REPO/'scripts/build_mac_window.py'),
                             '--env-file', str(tmp_path/'private.env'), '--container', 'pilot',
                             '--output', str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'existiert' in result.stderr
    assert marker.read_text() == 'existing'


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS Swift/AppKit required')
def test_actual_swift_navigation_and_download_policy(tmp_path):
    harness = tmp_path/'main.swift'
    harness.write_text('''import Foundation
let origin = URL(string: "http://127.0.0.1:8891")!
let cases: [(String, Bool, Bool, String)] = [
    ("http://127.0.0.1:8891/today", false, false, "local"),
    ("http://127.0.0.1:8891/api/backup", false, true, "local"),
    ("http://127.0.0.1:8892/today", false, false, "blocked"),
    ("http://localhost:8891/today", false, false, "blocked"),
    ("http://user@127.0.0.1:8891/today", false, false, "blocked"),
    ("https://accounts.google.com/auth", true, false, "external"),
    ("https://example.com/frame", false, false, "blocked"),
    ("http://example.com/", true, false, "blocked"),
    ("file:///etc/passwd", true, false, "blocked"),
    ("blob:http://127.0.0.1:8891/uuid", false, true, "download"),
    ("blob:https://example.com/uuid", false, true, "blocked"),
    ("blob:http://127.0.0.1:8891/uuid", true, false, "blocked"),
]
for (raw, top, download, expected) in cases {
    let result = navigationDisposition(URL(string: raw)!, origin: origin, topLevel: top, download: download)
    if result.rawValue != expected { fatalError("\\(raw): \\(result) != \\(expected)") }
}
let folder = URL(fileURLWithPath: CommandLine.arguments[1])
let destination = folder.appendingPathComponent("backup.zip")
let staged = folder.appendingPathComponent("staged.download")
try Data("old backup".utf8).write(to: destination)
try Data("new backup".utf8).write(to: staged)
try finishDownload(staged: staged, destination: destination)
guard try String(contentsOf: destination, encoding: .utf8) == "new backup" else { fatalError("replacement failed") }
guard !FileManager.default.fileExists(atPath: staged.path) else { fatalError("staging file leaked") }
do {
    try finishDownload(staged: staged, destination: destination)
    fatalError("missing download should fail")
} catch {
    guard try String(contentsOf: destination, encoding: .utf8) == "new backup" else { fatalError("existing backup lost on failure") }
}
let fresh = folder.appendingPathComponent("fresh.zip")
try Data("fresh backup".utf8).write(to: staged)
try finishDownload(staged: staged, destination: fresh)
guard try String(contentsOf: fresh, encoding: .utf8) == "fresh backup" else { fatalError("first save failed") }
print("policy passed")
''')
    executable = tmp_path/'policy'
    result = subprocess.run(['/usr/bin/xcrun', 'swiftc',
                             str(REPO/'macos/Shared/Navigation.swift'), str(harness), '-o', str(executable)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(executable), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'policy passed'


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS extended attributes required')
def test_build_metadata_cleanup_preserves_quarantine(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_mac_window', REPO/'scripts/build_mac_window.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    bundle = tmp_path/'Generated.app'
    bundle.mkdir()
    resource = bundle/'resource'
    resource.write_text('data')
    subprocess.run(['/usr/bin/xattr', '-wx', 'com.apple.FinderInfo', '00'*32, str(bundle)], check=True)
    subprocess.run(['/usr/bin/xattr', '-w', 'com.apple.ResourceFork', 'generated resource metadata', str(resource)], check=True)
    subprocess.run(['/usr/bin/xattr', '-w', 'com.apple.quarantine', '0081;12345678;Test;00000000-0000-0000-0000-000000000000', str(bundle)], check=True)
    builder.clear_generated_metadata(bundle)
    assert 'com.apple.FinderInfo' not in subprocess.check_output(['/usr/bin/xattr', str(bundle)], text=True).splitlines()
    assert 'com.apple.ResourceFork' not in subprocess.check_output(['/usr/bin/xattr', str(resource)], text=True).splitlines()
    assert subprocess.check_output(['/usr/bin/xattr', '-p', 'com.apple.quarantine', str(bundle)], text=True).startswith('0081;')
    assert resource.read_text() == 'data'
