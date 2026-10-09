"""The read-capacity probe preserves originals and distinguishes limited empty pages."""
import json
import subprocess
import sys

import pytest
import probe_memory_area_scale as probe


def test_small_corpus_keeps_old_rare_sources_and_withdrawal():
    report = probe.run((64, 128), body_chars=128)
    assert report['synthetic_only'] and not report['network_used'] and not report['models_called']
    assert report['withdrawal_verified']
    assert [r['sources'] for r in report['measurements']] == [64, 128]
    for row in report['measurements']:
        assert row['pages']['health']['returned'] == 25
        assert row['pages']['health']['checked'] == 26
        assert row['pages']['finance']['returned'] == 0
        assert row['pages']['finance']['has_more'] is False
        assert row['pages']['other']['has_more'] is False


def test_empty_bounded_page_does_not_claim_empty_corpus():
    report = probe.run((512,), body_chars=128)
    page = report['measurements'][0]['pages']['other']
    assert page['returned'] == 0 and page['checked'] == 500
    assert page['scan_limited'] and page['has_more']


@pytest.mark.parametrize('sizes, chars', [((63,),128), ((64,64),128), ((128,64),128), ((150001,),128), ((64,),127), ((64,),8193)])
def test_invalid_workloads_are_rejected_before_build(sizes, chars):
    with pytest.raises(ValueError):
        probe.run(sizes, chars)


def test_existing_report_is_never_overwritten(tmp_path):
    target = tmp_path/'report.json'
    target.write_text('{}')
    result = subprocess.run([sys.executable, str(probe.__file__), '--sizes','64','--output',str(target)], capture_output=True, text=True)
    assert result.returncode != 0 and 'existiert bereits' in result.stderr
    assert json.loads(target.read_text()) == {}


def test_cli_retains_completed_checkpoint_and_marks_failure(tmp_path, monkeypatch):
    target=tmp_path/'failed.json'
    def failed_run(*args, progress, **kwargs):
        progress({'status':'running', 'measurements':[{'sources':64}]})
        raise OSError('internal details must not be published')
    monkeypatch.setattr(probe,'run',failed_run)
    monkeypatch.setattr(probe.resource,'setrlimit',lambda *_:None)
    monkeypatch.setattr(sys,'argv',['probe','--sizes','64','--output',str(target)])
    assert probe.main()==1
    result=json.loads(target.read_text())
    assert result['status']=='failed' and result['measurements']==[{'sources':64}]
    assert result['error_class']=='OSError' and 'internal details' not in target.read_text()
