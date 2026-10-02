import importlib.util
from pathlib import Path
import wave
import pytest


def module():
 path=Path(__file__).resolve().parents[2]/'scripts/mac_audio_worker.py'
 spec=importlib.util.spec_from_file_location('audio_worker',path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_synthesis_keeps_text_out_of_command_and_cleans_files(monkeypatch):
 m=module();files=[]
 def run(args,**kwargs):
  assert 'secret synthetic mail' not in args and kwargs['timeout']==120
  text=Path(args[args.index('-f')+1]);files.append(text)
  assert text.read_text()=='secret synthetic mail'
  target=args[args.index('-o')+1]
  with wave.open(target,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\x00\x00'*2205)
 monkeypatch.setattr(m.subprocess,'run',run)
 assert m.synthesize('secret synthetic mail','Anna').startswith(b'RIFF')
 assert not files[0].exists()


def test_worker_bounds_text_and_local_destination():
 m=module()
 for text in ['', 'x'*8001, 'x\x00y']:
  with pytest.raises(ValueError):m.synthesize(text,'Anna')
 for url in ['https://example.org','http://127.0.0.1.evil','http://user@127.0.0.1','http://127.0.0.1/path']:
  with pytest.raises(ValueError):m.validate_url(url)
 assert m.validate_url('http://127.0.0.1:8891')=='http://127.0.0.1:8891'
