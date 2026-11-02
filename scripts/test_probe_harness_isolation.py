import pytest
from probe_harness_isolation import isolation_checks


IMAGE='sha256:'+'a'*64
CONFIG=dict(image_id=IMAGE,uid='1000:1000',read_only=True,public_runtime_only=True,
    no_host_ports=True,only_internal_network=True,network_internal=True,dns=['127.0.0.1'],
    cap_drop=['ALL'],security=['no-new-privileges'],memory=512*1024**2,nano_cpus=750000000,pids=64,
    tmpfs={'/tmp':'rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=700',
           '/data':'rw,noexec,nosuid,size=64k,mode=000'})
NEGATIVE=dict(uid=1000,external_ip='ENETUNREACH',host_service='ENETUNREACH',external_dns='ESERVFAIL',
    gateway=200,root_write='EROFS',data_read='EACCES',capabilities='0000000000000000',no_new_privileges='1')


def test_complete_positive_and_negative_evidence_required():
    assert all(isolation_checks(CONFIG,NEGATIVE,IMAGE).values())
    assert not any(isolation_checks(CONFIG,{},IMAGE).values())


@pytest.mark.parametrize('key,value',[('read_only',False),('public_runtime_only',False),('no_host_ports',False),
    ('only_internal_network',False),('network_internal',False),('dns',['8.8.8.8']),('cap_drop',[]),
    ('security',[]),('memory',0),('nano_cpus',0),('pids',0),('image_id','other'),('uid','0')])
def test_each_configuration_control_is_load_bearing(key,value):
    assert not isolation_checks(CONFIG | {key:value},NEGATIVE,IMAGE)['configured']


@pytest.mark.parametrize('key,value',[('external_ip','connected'),('external_ip','timeout'),
    ('host_service','connected'),('external_dns',['1.2.3.4']),('gateway','unavailable'),
    ('root_write','allowed'),('data_read','allowed'),('capabilities','1'),('capabilities',None),
    ('no_new_privileges','0'),('uid',0)])
def test_negative_probe_gaps_are_not_a_pass(key,value):
    assert not isolation_checks(CONFIG,NEGATIVE | {key:value},IMAGE)['negative']


@pytest.mark.parametrize('tmpfs',[{}, {'/tmp':'rw,exec,suid,size=64m'},
    CONFIG['tmpfs'] | {'/tmp':'rw,noexec,nosuid,size=1g,mode=700'},
    CONFIG['tmpfs'] | {'/data':'rw,exec,suid,size=64k,mode=000'}])
def test_tmpfs_protection_and_size_are_required(tmpfs):
    assert not isolation_checks(CONFIG | dict(tmpfs=tmpfs),NEGATIVE,IMAGE)['configured']


@pytest.mark.parametrize('failure',['container','network','label_mismatch'])
def test_actual_probe_cannot_pass_with_cleanup_pending(tmp_path,monkeypatch,failure):
    import json
    from types import SimpleNamespace
    import probe_harness_isolation as probe
    runtime=tmp_path/'runtime'
    package=runtime/'node_modules/@deepseek-ai/dsh-sdk-client/package.json'
    package.parent.mkdir(parents=True)
    package.write_text('{}')
    for name in ('harness_worker.mjs','harness_run.mjs','harness_service.mjs','package-lock.json'):
        (runtime/name).write_text('public artificial fixture')
    monkeypatch.setattr(probe,'_mac_resource_check',lambda _model:None)
    monkeypatch.setattr(probe.secrets,'token_hex',lambda _count:'fixture-nonce')
    monkeypatch.setattr(probe.shutil,'copytree',lambda *a,**k:None)
    monkeypatch.setattr(probe.shutil,'copy2',lambda *a,**k:None)
    info=dict(Image=IMAGE,Config=dict(User='1000:1000',Labels={'kingfisher.synthetic':
        'other-owner' if failure=='label_mismatch' else 'fixture-nonce'}),
        HostConfig=dict(ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],
            Memory=CONFIG['memory'],NanoCpus=CONFIG['nano_cpus'],PidsLimit=64,Dns=['127.0.0.1'],Tmpfs=CONFIG['tmpfs']),
        Mounts=[dict(Type='bind',Destination='/runtime',Source=str(runtime),RW=False)],
        NetworkSettings=dict(Ports={},Networks={'internal-net':{}}))
    def command(argv,**kw):
        op=argv[1:];code=0;value=''
        if op[:2]==['network','create']:value='internal-id' if '--internal' in op else 'outbound-id'
        elif op[0]=='create':value='gateway-id' if any('kf-gateway-' in a for a in op) else 'worker-id'
        elif op[0]=='port':value='127.0.0.1:32123'
        elif op[0]=='inspect':value=json.dumps([info])
        elif op[:2]==['network','inspect']:value=json.dumps([dict(Name='internal-net',Internal=True)])
        elif op[0]=='exec':value=json.dumps(NEGATIVE)
        elif op[0]=='rm' and failure=='container':code=1
        elif op[:2]==['network','rm'] and failure=='network':code=1
        return SimpleNamespace(returncode=code,stdout=value,stderr='')
    monkeypatch.setattr(probe.subprocess,'run',command)
    class Response:
        status_code=200
        def json(self):return dict(status='passed')
        def raise_for_status(self):pass
    class Client:
        def __init__(self,*a,**k):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def get(self,*a,**k):return Response()
        def post(self,*a,**k):return Response()
    monkeypatch.setattr(probe.httpx,'Client',Client)
    output=tmp_path/'result.json'
    status=probe.main(['--runtime',str(runtime),'--image',IMAGE,'--output',str(output)])
    report=json.loads(output.read_text())
    assert all(report['isolation_checks'].values())  # Fail specifically at final cleanup.
    assert status==1 and report['status']=='failed'
    assert report['cleanup_pending']
