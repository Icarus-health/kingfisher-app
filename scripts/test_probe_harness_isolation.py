import pytest
from probe_harness_isolation import isolation_checks


IMAGE='sha256:'+'a'*64
CONFIG=dict(image_id=IMAGE,uid='1000:1000',read_only=True,public_runtime_only=True,
    no_host_ports=True,only_internal_network=True,network_internal=True,dns=['127.0.0.1'],
    cap_drop=['ALL'],security=['no-new-privileges'],memory=512*1024**2,nano_cpus=750000000,pids=64)
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
