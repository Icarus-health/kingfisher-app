"""Optional module config cannot inherit the main application's authority."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'deploy/compose.modules.yaml'
IMAGE = 'sha256:' + 'a' * 64


def config(tmp_path, compose_file=FILE):
    if shutil.which('docker') is None:
        pytest.skip('Docker Compose unavailable')
    # An empty, explicit environment prevents the machine's real credentials
    # from entering even the config-only command. Nothing is started or pulled.
    environment = {'PATH': os.environ['PATH'], 'HOME': str(tmp_path),
        'DOCKER_HOST': 'unix://' + str(tmp_path / 'no-docker-daemon.sock'),
        'KINGFISHER_MODULE_IMAGE': IMAGE, 'KF_GATEWAY_CONTROL_KEY': 'x' * 43,
        'KINGFISHER_MODULE_RUNTIME': str(tmp_path / 'public-runtime')}
    compose = shutil.which('docker-compose')
    command = [compose] if compose else ['docker', 'compose']
    result = subprocess.run([*command, '-f', str(compose_file),
        'config', '--format', 'json'], env=environment, capture_output=True,
        text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_optional_project_is_separate_and_never_default_started():
    text = FILE.read_text()
    assert 'name: kingfisher-modules\n' in text
    assert 'ports:' not in text
    assert 'kingfisher-data' not in text
    assert 'docker.sock' not in text
    assert 'ICARUS_SIDECAR_TOKEN' not in text
    assert 'ICARUS_SECRETS_PASSPHRASE' not in text
    assert 'depends_on:' not in text
    assert 'compose.modules.yaml' not in (ROOT / 'macos/App/Docker.swift').read_text()


def test_no_cloud_or_worker_authority_in_resolved_config(tmp_path):
    value = config(tmp_path)
    assert set(value['services']) == {'gateway', 'worker'}
    gateway, worker = (value['services'][name] for name in ('gateway', 'worker'))
    assert worker.get('environment', {}) == {}
    assert gateway['environment'] == {'KF_GATEWAY_CONTROL_KEY': 'x' * 43}
    assert worker['entrypoint'] == ['/runtime/bin/node', '/runtime/harness_service.mjs',
                                    '--controlled-local-readonly-v1']
    assert gateway['entrypoint'] == ['python', '/runtime/harness_gateway.py',
                                     '--controlled-local-readonly-v1']
    assert set(worker['networks']) == {'worker'}
    assert set(gateway['networks']) == {'worker', 'control'}
    for name in ('worker', 'control'):
        assert value['networks'][name]['internal'] is True
        assert value['networks'][name]['name'] == 'kingfisher-modules-' + name
    assert gateway['networks']['worker']['aliases'] == ['kingfisher-gateway']
    assert gateway['networks']['control']['aliases'] == ['kingfisher-gateway-control']
    assert worker['networks']['worker']['aliases'] == ['kingfisher-worker']


def test_resolved_runtime_has_only_public_readonly_mount_and_resource_bounds(tmp_path):
    # Older compose-go versions omit a false bool in JSON; newer versions
    # preserve the explicitly disabled OptOut. The source must disable it in
    # both services regardless of serialization. No daemon is contacted.
    assert FILE.read_text().count('create_host_path: false\n') == 2
    value = config(tmp_path)
    for name, memory, cpu, pids in [('worker', 512 * 1024 ** 2, .75, 64),
                                   ('gateway', 96 * 1024 ** 2, .25, 32)]:
        service = value['services'][name]
        assert service['image'] == IMAGE
        assert service['user'] == '1000:1000'
        assert service['read_only'] is True
        assert service.get('privileged', False) is False
        assert service['cap_drop'] == ['ALL']
        assert service['security_opt'] == ['no-new-privileges:true']
        assert int(service['mem_limit']) == memory
        assert float(service['cpus']) == cpu
        assert service['pids_limit'] == pids
        assert service['restart'] == 'no'
        assert service['dns'] == ['127.0.0.1']
        assert service['healthcheck']['disable'] is True
        assert not service.get('ports')
        assert len(service['volumes']) == 1
        mount = dict(service['volumes'][0])
        assert mount.pop('bind') in ({}, {'create_host_path': False})
        assert mount == {'type': 'bind',
            'source': str(tmp_path / 'public-runtime'), 'target': '/runtime',
            'read_only': True}
        assert len(service['tmpfs']) == 2
        assert all('noexec' in entry and 'nosuid' in entry for entry in service['tmpfs'])
        assert any(entry.startswith('/data:') and 'mode=000' in entry for entry in service['tmpfs'])


def test_config_parser_keeps_enabled_host_creation_distinguishable(tmp_path):
    # A parser that drops *both* true and false must not make the safety test
    # vacuous. New OptOut parsers omit true; older bool parsers emit true.
    unsafe = tmp_path / 'unsafe.compose.yaml'
    unsafe.write_text(FILE.read_text().replace('create_host_path: false', 'create_host_path: true'))
    safe = config(tmp_path)
    value = config(tmp_path, unsafe)
    for name, service in value['services'].items():
        unsafe_bind = service['volumes'][0].get('bind', {})
        assert unsafe_bind in ({}, {'create_host_path': True})
        assert unsafe_bind != safe['services'][name]['volumes'][0].get('bind', {})
