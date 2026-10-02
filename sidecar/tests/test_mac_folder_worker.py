from pathlib import Path
import importlib.util
import os
import time

spec = importlib.util.spec_from_file_location("mac_folder_worker", Path(__file__).parents[2] / "scripts" / "mac_folder_worker.py")
worker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(worker)


def test_scan_consumes_stable_supported_files_and_observes_unsupported(tmp_path):
    good = tmp_path / "note.txt"
    good.write_text("Hallo", encoding="utf-8")
    old = time.time() - 5
    os.utime(good, (old, old))
    bad = tmp_path / "bild.png"
    bad.write_bytes(b"x")
    os.utime(bad, (old, old))
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.txt").write_text("no", encoding="utf-8")
    received = []
    report = worker.scan(tmp_path, lambda name, data: received.append((name, data)))
    assert report["complete"] is True
    assert set(report["observed"]) == {"bild.png", "note.txt"}
    assert received == [("note.txt", b"Hallo")]


def test_scan_missing_root_is_incomplete_and_does_not_consume(tmp_path):
    received = []
    report = worker.scan(tmp_path / "gone", lambda name, data: received.append(name))
    assert report["complete"] is False
    assert received == []


def test_scan_never_follows_symlink(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(outside)
    report = worker.scan(tmp_path, lambda name, data: None)
    assert "link.txt" not in report["observed"]


def test_root_symlink_is_not_registered(tmp_path):
    import pytest
    (tmp_path / 'actual').mkdir()
    link = tmp_path / 'link'
    link.symlink_to(tmp_path / 'actual', target_is_directory=True)
    with pytest.raises(ValueError):
        worker.root_id(link)


def test_api_refuses_remote_or_redirectable_endpoint():
    import pytest
    for url in ('https://example.com', 'http://127.0.0.1:8891/path', 'http://u:p@127.0.0.1', 'http://127.0.0.1/?q=1'):
        with pytest.raises(ValueError):
            worker.Api(url, 'secret')


def test_permission_revoked_before_read_blocks_consumption(tmp_path):
    import pytest
    file = tmp_path / 'source.txt'
    file.write_text('private')
    os.utime(file, (time.time()-10, time.time()-10))
    received=[]
    def revoked():
        raise worker.StopSync()
    with pytest.raises(worker.StopSync):
        worker.scan(tmp_path, lambda *args: received.append(args), permitted=revoked)
    assert received == []


def test_recent_supported_file_defers_success(tmp_path):
    (tmp_path / 'writing.txt').write_text('not yet stable')
    report = worker.scan(tmp_path, lambda *args: None)
    assert report['complete'] is False
    assert report['errors']


def test_root_replaced_before_walk_does_not_read_replacement(tmp_path, monkeypatch):
    root = tmp_path / 'selected'
    root.mkdir()
    other = tmp_path / 'outside'
    other.mkdir()
    private = other / 'private.txt'
    private.write_text('outside')
    os.utime(private, (time.time()-10, time.time()-10))
    original_walk = os.fwalk
    def replaced(*args, **kwargs):
        root.rename(tmp_path / 'original')
        root.symlink_to(other, target_is_directory=True)
        yield from original_walk(*args, **kwargs)
    monkeypatch.setattr(os, 'fwalk', replaced)
    received = []
    report = worker.scan(root, lambda *args: received.append(args))
    assert received == []
    assert report['complete'] is False


def test_changed_root_identity_blocks_new_directory(tmp_path):
    root = tmp_path / 'selected'
    root.mkdir()
    approved = worker.root_id(root)
    root.rename(tmp_path / 'old')
    root.mkdir()
    file = root / 'outside.txt'
    file.write_text('not approved')
    os.utime(file, (time.time()-10, time.time()-10))
    received = []
    report = worker.scan(root, lambda *args: received.append(args), expected_root_id=approved)
    assert received == [] and report['complete'] is False
