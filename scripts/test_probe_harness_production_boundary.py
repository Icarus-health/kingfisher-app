"""A failed/missing receipt must never claim production isolation passed."""
from copy import deepcopy
import pytest
from probe_harness_production_boundary import boundary_checks


def receipt():
    base=dict(synthetic_only=True,personal_store_opened=False,paid_calls=0,
        injected_model_only=True,live_semantic_verified=False,cleanup_verified=True,sampled_max_mac_pressure=1,
        worker_isolation={'configured':True,'negative':True},
        topology_verified=True,no_initial_worker_key=True,parent_proc_test=True,
        ui_bootstrap_baseline=True,
        negatives={'main_ip':'ENETUNREACH','main_dns':'ENOTFOUND',
          'gateway_root':{'status':404,'cookie':False},
          'gateway_api':{'status':404,'cookie':False},
          'gateway_main_port':{'status':404,'cookie':False},
          'controller_without_key':{'status':401,'cookie':False}},
        cases=[])
    base['cases'].append(dict(case='baseline',status=200,model_calls=2,
        checks=dict(complete=True,scope=True,actual_search=True,automatic_skills=True,originals_unchanged=True)))
    for case in ('cancel','source_revoked'):
        base['cases'].append(dict(case=case,status=502,model_calls=1,
            coordination={'ui_seconds':.1},checks=dict(result_withheld=True,interrupted=True,
              ui_responsive=True,capability_revoked=True,original_bodies_unchanged=True)))
    return base


def test_complete_receipt_passes():
    assert all(boundary_checks(receipt()).values())


def controlled_receipt():
    report=receipt();report['runtime_mode']='controlled-local-readonly-v1'
    report['controlled_health']=[dict(status='ok',mode='controlled-local-readonly-v1',
        model='kingfisher-qwen3.5:9b-8k',syntheticOnly=False,osIsolationVerified=False,instance='a'*64)
        for _ in range(4)]
    return report


def test_controlled_mode_receipt_still_requires_artificial_inference_and_current_pair():
    assert all(boundary_checks(controlled_receipt()).values())
    report=controlled_receipt();report['controlled_health'][1]['instance']='b'*64
    assert not all(boundary_checks(report).values())


@pytest.mark.parametrize('change',[
    lambda r:r.update(runtime_mode='other'),
    lambda r:r.pop('controlled_health'),
    lambda r:r['controlled_health'].pop(),
    lambda r:r['controlled_health'][0].update(syntheticOnly=True),
    lambda r:r['controlled_health'][0].update(osIsolationVerified=True),
    lambda r:r['controlled_health'][0].update(model='cloud'),
    lambda r:r['controlled_health'][0].update(status='awaiting_controller'),
    lambda r:r['controlled_health'][0].update(instance='not-a-generation'),
    lambda r:r['controlled_health'][0].update(extra='unexpected'),
    lambda r:r.update(live_semantic_verified=True),
    lambda r:r.update(injected_model_only=False),
    lambda r:r.update(synthetic_only=False),
])
def test_unverified_controlled_mode_receipt_fails(change):
    report=controlled_receipt();change(report)
    assert not all(boundary_checks(report).values())


def test_explicit_dns_refusal_is_still_a_denial_not_an_address():
    report=receipt();report['negatives']['main_dns']='ESERVFAIL'
    assert all(boundary_checks(report).values())


@pytest.mark.parametrize('key',['synthetic_only','cleanup_verified','topology_verified',
    'no_initial_worker_key','parent_proc_test','ui_bootstrap_baseline','sampled_max_mac_pressure'])
def test_missing_positive_gate_fails(key):
    report=receipt();del report[key]
    assert not all(boundary_checks(report).values())


@pytest.mark.parametrize('change',[
    lambda r:r.update(cleanup_pending=['owned-resource']),
    lambda r:r.update(personal_store_opened=True),
    lambda r:r.update(paid_calls=1),
    lambda r:r.update(live_semantic_verified=True),
    lambda r:r['worker_isolation'].update(negative=False),
    lambda r:r['negatives'].update(main_ip='connected'),
    lambda r:r['negatives'].update(main_dns=['172.1.2.3']),
    lambda r:r['negatives']['gateway_root'].update(cookie=True),
    lambda r:r['negatives']['gateway_api'].update(status=200),
    lambda r:r['negatives']['controller_without_key'].update(status=200),
    lambda r:r['cases'][0]['checks'].update(scope=False),
    lambda r:r['cases'][1]['checks'].update(result_withheld=False),
    lambda r:r['cases'][2]['checks'].update(capability_revoked=False),
    lambda r:r['cases'][1]['coordination'].update(ui_seconds=10),
    lambda r:r['cases'][1].update(status=200),
    lambda r:r['cases'].pop(),
    lambda r:r.update(parent_proc_test='true'),
    lambda r:r.update(sampled_max_mac_pressure=4),
    lambda r:r.update(sampled_max_mac_pressure='1'),
])
def test_negative_receipts_fail(change):
    report=deepcopy(receipt());change(report)
    assert not all(boundary_checks(report).values())
