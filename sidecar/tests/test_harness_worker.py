import json
import os
import sys
from pathlib import Path

import pytest

from icarus_memory.harness_broker import BridgeError
from icarus_memory.harness_worker import run_synthetic_worker


def fake_node(tmp_path, body):
    path = tmp_path / 'fake-node'
    path.write_text('#!'+sys.executable+'\n'+body)
    path.chmod(0o700)
    return path


def run(node, tmp_path, **kw):
    return run_synthetic_worker(node=node,runtime=tmp_path,origin='http://127.0.0.1:12345',
        token='a'*43,request='Künstliche Frage',scratch=tmp_path,**kw)


def test_child_environment_is_replaced_and_configuration_is_only_stdin(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','not-a-real-secret')
    monkeypatch.setenv('ICARUS_TOKEN','not-a-real-master-token')
    node = fake_node(tmp_path,"""import json,os,sys
c=json.load(sys.stdin)
assert 'ANTHROPIC_API_KEY' not in os.environ and 'ICARUS_TOKEN' not in os.environ
assert not any('a'*43 in value for value in sys.argv)
assert c['syntheticOnly'] is True
print(json.dumps(dict(status='complete',syntheticOnly=True,text='artificial')))
""")
    assert run(node,tmp_path)['text'] == 'artificial'


def test_timeout_stops_entire_owned_process_group(tmp_path):
    node = fake_node(tmp_path,"""import json,subprocess,sys,time
c=json.load(sys.stdin)
child="from pathlib import Path;import time; p=Path("+repr(c['scratch'])+")/'heartbeat'; i=0\\nwhile True:\\n i+=1; p.write_text(str(i)); time.sleep(.03)"
subprocess.Popen([sys.executable,'-c',child])
time.sleep(30)
""")
    with pytest.raises(BridgeError,match='Zeitüberschreitung'): run(node,tmp_path,timeout=.3)
    import time
    heartbeat = tmp_path/'heartbeat'
    before = heartbeat.read_text()
    time.sleep(.15)
    assert heartbeat.read_text() == before


def test_excessive_child_output_is_bounded(tmp_path):
    node = fake_node(tmp_path,"import sys\nsys.stdin.read()\nprint('x'*100000)\n")
    with pytest.raises(BridgeError,match='Ausgabegrenze'): run(node,tmp_path)


def test_failure_does_not_return_child_stderr(tmp_path):
    node = fake_node(tmp_path,"import sys\nsys.stdin.read()\nprint('secret',file=sys.stderr)\nprint('{}')\nsys.exit(1)\n")
    with pytest.raises(BridgeError) as error: run(node,tmp_path)
    assert 'secret' not in str(error.value)
