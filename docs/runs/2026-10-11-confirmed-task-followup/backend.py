import os, socket, ipaddress
from pathlib import Path
root=Path(__file__).parent
os.environ['ICARUS_DATA_DIR']=str(root/'data-run3')
os.environ['KINGFISHER_UPDATE_URL']=''
os.environ.pop('ICARUS_SIDECAR_TOKEN',None)
from icarus_memory.secrets import KNOWN, PASSPHRASE_ENV, Keychain
for name in (*KNOWN,PASSPHRASE_ENV,'ICARUS_PROVIDER','ICARUS_MODEL','ICARUS_BASE_URL'):
    os.environ.pop(name,None)
Keychain._detect=lambda self:'none'
original_connect=socket.socket.connect
def loopback_only(self,address):
    if not isinstance(address,tuple) or not ipaddress.ip_address(address[0]).is_loopback:
        raise OSError('Synthetic check blocks outgoing connections')
    return original_connect(self,address)
socket.socket.connect=loopback_only
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
app=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic-file-flow'))
assert app.state.agent.provider is None
assert not app.state.settings.schedule.enabled
app.state.hintergrund.pausieren(True)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18764,log_level='warning')
