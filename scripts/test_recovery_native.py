"""Host protocol tests; every Docker and HTTP boundary is synthetic."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types

import pytest

IMAGE = 'sha256:' + 'a' * 64


def load():
    spec = importlib.util.spec_from_file_location('recovery_native', Path(__file__).with_name('recovery_native.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def host(tmp_path, monkeypatch):
    module = load()
    root = tmp_path.resolve()
    docker = root / 'docker'; docker.write_text('# synthetic executable'); docker.chmod(0o700)
    source = root / 'original'; (source / 'data').mkdir(parents=True)
    (source / 'settings.env').write_text('OLD_PRIVATE_SENTINEL')
    bundle = root / 'bundle.kf'; bundle.write_text('encrypted synthetic fixture')
    output = root / 'new'; output.mkdir()
    calls = []; containers = {}; faults = {}; image_env = ['PATH=/usr/local/bin:/usr/bin:/bin', 'LANG=C.UTF-8']
    raw_calls = []
    socketpath = root / 'docker.sock'; socketpath.touch()
    is_socket = Path.is_socket
    monkeypatch.setattr(Path, 'is_socket', lambda path: True if path == socketpath else is_socket(path))
    endpoint = 'unix://' + str(socketpath)

    def run(command, **kwargs):
        raw_calls.append(command)
        args = command[1:]
        if args[:2] == ['--host', endpoint]: args = args[2:]
        normalized = [command[0], *args]
        calls.append((normalized, kwargs))
        assert kwargs.get('shell', False) is False
        assert kwargs['timeout'] <= 180
        assert 'HTTPS_PROXY' not in kwargs['env']
        if args[:2] == ['context', 'inspect']:
            return subprocess.CompletedProcess(command, 0, json.dumps(faults.get('endpoint', endpoint)), '')
        assert command[1:3] == ['--host', endpoint]
        if args[:2] == ['image', 'inspect']:
            return subprocess.CompletedProcess(command, 0, json.dumps([{'Id': IMAGE, 'Config': {'Env': image_env, 'Volumes': {'/data': {}}}}]), '')
        if args[0] == 'run':
            if faults.get('timeout') == ('probe' if 'CAPABILITY' in command[-1] else 'worker'):
                owner = next(value.split('=', 1)[1] for index, value in enumerate(args) if index and args[index - 1] == '--label' and value.startswith('org.kingfisher.recovery.owner='))
                name = args[args.index('--name') + 1]
                containers[name] = {'Id': 'c' * 64, 'Name': '/' + name, 'Image': IMAGE,
                    'Config': {'Labels': {'org.kingfisher.recovery.owner': owner, 'org.kingfisher.recovery.version': '1'}}}
                Path(args[args.index('--cidfile') + 1]).write_text('c' * 64)
                raise subprocess.TimeoutExpired(command, 1, output='PASSWORD_SENTINEL')
            if 'CAPABILITY' in command[-1]:
                return subprocess.CompletedProcess(command, 0, json.dumps({'capability': faults.get('capability', 1)}), '')
            payload = json.loads(kwargs['input'])
            if faults.get('worker'):
                raise subprocess.CalledProcessError(1, command, output='PASSWORD_SENTINEL', stderr='OLD_PRIVATE_SENTINEL')
            if payload['operation'] in ('extract', 'prepare'):
                folder = Path(payload['target']); (folder / 'data').mkdir(parents=True)
                answer = {'ok': True, 'folder': str(folder)}
            else:
                answer = {'ok': True, 'report': {'report_fingerprint': 'b' * 64, 'restored': {'files': []}, 'unresolved': ['current_authority_unverified']}}
            return subprocess.CompletedProcess(command, 0, json.dumps(answer), '')
        if args[0] == 'create':
            name = args[args.index('--name') + 1]
            owner = next(value.split('=', 1)[1] for index, value in enumerate(args) if index and args[index - 1] == '--label' and value.startswith('org.kingfisher.recovery.owner='))
            mount = args[args.index('--mount') + 1]
            folder = mount.split('source=', 1)[1].split(',', 1)[0]
            container = {'Id': 'c' * 64, 'Name': '/' + name, 'Image': IMAGE,
                'Config': {'Labels': {'org.kingfisher.recovery.owner': owner, 'org.kingfisher.recovery.version': '1'},
                    'User': f'{os.getuid()}:{os.getgid()}', 'Env': list(image_env), 'Entrypoint': ['python'],
                    'Cmd': ['-m', 'icarus_memory.recovery_workspace_cli', 'serve', '--container', '--folder', folder, '--port', '8890']},
                'HostConfig': {'Privileged': False, 'NetworkMode': 'bridge', 'ReadonlyRootfs': True,
                    'CapAdd': None, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                    'LogConfig': {'Type': 'none'}, 'PortBindings': {'8890/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '49173'}]},
                    'Tmpfs': {'/tmp': 'rw,noexec,nosuid,size=64m', '/data': 'ro,noexec,nosuid,size=1m'}},
                'Mounts': [{'Type': 'bind', 'Source': folder, 'Destination': folder, 'RW': True}],
                'NetworkSettings': {'Ports': {'8890/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '49173'}]}},
                'State': {'Running': False}}
            containers[name] = container
            if '--cidfile' in args:
                Path(args[args.index('--cidfile') + 1]).write_text(container['Id'])
            if faults.get('create-timeout'):
                raise subprocess.TimeoutExpired(command, 1)
            return subprocess.CompletedProcess(command, 0, container['Id'] + '\n', '')
        if args[0] == 'inspect':
            if faults.get('inspect-once'):
                faults['inspect-once'] = False
                raise subprocess.TimeoutExpired(command, 1)
            value = next((c for name, c in containers.items() if args[-1] in (name, c['Id'])), None)
            if value is None: raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0, json.dumps([value]), '')
        if args[0] == 'start':
            if faults.get('start'): raise subprocess.CalledProcessError(1, command, stderr='private details')
            value = next(c for name, c in containers.items() if args[-1] in (name, c['Id']))
            value['State']['Running'] = True
            return subprocess.CompletedProcess(command, 0, args[-1], '')
        if args[0] == 'rm':
            assert args[-1] == 'c' * 64
            containers.clear()
            return subprocess.CompletedProcess(command, 0, '', '')
        raise AssertionError(command)

    monkeypatch.setenv('HTTPS_PROXY', 'https://must-not-inherit.invalid')
    monkeypatch.setattr(module.subprocess, 'run', run)
    monkeypatch.setattr(module, '_wait_ready', lambda url: None)
    monkeypatch.setattr(module, '_choose_port', lambda: 49173, raising=False)
    return locals()


def request(host, operation, **fields):
    return {'operation': operation, 'docker': str(host['docker']), 'image': IMAGE, **fields}


def invoke(host, payload):
    output = io.StringIO()
    result = host['module'].main(io.StringIO(json.dumps(payload)), output)
    return result, json.loads(output.getvalue())


def test_extract_password_only_on_stdin_offline_and_no_original_settings_read(host):
    payload = request(host, 'extract', bundle=str(host['bundle']), target=str(host['output'] / 'restored'), password='PASSWORD_SENTINEL')
    code, result = invoke(host, payload)
    assert code == 0 and result == {'ok': True, 'folder': payload['target']}
    command, options = next((c, k) for c, k in host['calls'] if k.get('input') and 'PASSWORD_SENTINEL' in k['input'])
    assert 'PASSWORD_SENTINEL' not in json.dumps(command) and 'PASSWORD_SENTINEL' not in json.dumps(result)
    assert '--pull=never' in command and command[command.index('--network') + 1] == 'none'
    assert command[command.index('--user') + 1] == f'{os.getuid()}:{os.getgid()}'
    assert any(str(host['bundle']) in arg and 'readonly' in arg for arg in command)
    assert (host['source'] / 'settings.env').read_text() == 'OLD_PRIVATE_SENTINEL'


def test_inspect_and_prepare_use_bundle_data_without_source_write_mount(host):
    code, result = invoke(host, request(host, 'inspect', folder=str(host['source'])))
    assert code == 0 and result['report']['unresolved'] == ['current_authority_unverified']
    code, result = invoke(host, request(host, 'prepare', folder=str(host['source']), target=str(host['output'] / 'working'), fingerprint='b' * 64, selection='restored', acknowledge_unknown=True))
    assert code == 0 and result['folder'] == str(host['output'] / 'working')
    commands = [c for c, k in host['calls'] if k.get('input')]
    assert all(any(f'source={host["source"] / "data"}' in arg and 'readonly' in arg for arg in c) for c in commands)


@pytest.mark.parametrize('mutation', [
    {'image': 'latest'}, {'image': 'sha256:' + 'A' * 64}, {'operation': 'delete'},
    {'password': 123}, {'extra': 'unknown'}, {'target': '/tmp/../'},
])
def test_closed_input_rejects_before_docker(host, mutation):
    payload = request(host, 'extract', bundle=str(host['bundle']), target=str(host['output'] / 'restored'), password='PASSWORD_SENTINEL')
    code, result = invoke(host, payload | mutation)
    assert code != 0 and result['ok'] is False and set(result) == {'ok', 'error'}
    assert not host['calls']


def test_oversized_duplicate_and_argument_input_are_rejected(host):
    for text in ('{' + ' ' * 65536, '{"operation":"inspect","operation":"open"}'):
        output = io.StringIO()
        assert host['module'].main(io.StringIO(text), output) != 0
        assert json.loads(output.getvalue())['ok'] is False
    assert not host['calls']


def test_missing_capability_does_not_touch_target(host):
    host['faults']['capability'] = 0
    code, result = invoke(host, request(host, 'extract', bundle=str(host['bundle']), target=str(host['output'] / 'restored'), password='PASSWORD_SENTINEL'))
    assert code != 0 and result['ok'] is False
    assert not (host['output'] / 'restored').exists()
    assert not any(options.get('input') for _, options in host['calls'])


def test_worker_errors_never_disclose_private_output_or_delete_data(host):
    host['faults']['worker'] = True
    code, result = invoke(host, request(host, 'extract', bundle=str(host['bundle']), target=str(host['output'] / 'restored'), password='PASSWORD_SENTINEL'))
    assert code != 0 and 'SENTINEL' not in json.dumps(result)
    assert not any(command[1] == 'rm' for command, _ in host['calls'])
    assert host['bundle'].exists()


def test_new_open_and_reopen_validate_container_without_disclosing_secrets(host):
    folder = host['source']
    code, result = invoke(host, request(host, 'open', folder=str(folder)))
    assert code == 0 and result['url'] == 'http://127.0.0.1:49173'
    receipt = folder / 'recovery-app.json'
    state = json.loads(receipt.read_text())
    assert result == {'ok': True, 'url': 'http://127.0.0.1:49173', 'instance_id': state['owner'], 'image': IMAGE}
    assert set(state) == {'version', 'owner', 'container', 'image', 'port'}
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600 and state['port'] == 49173
    assert 'OLD_PRIVATE_SENTINEL' not in receipt.read_text()
    before = len([c for c, _ in host['calls'] if c[1] == 'create'])
    assert invoke(host, request(host, 'open', folder=str(folder)))[0] == 0
    assert len([c for c, _ in host['calls'] if c[1] == 'create']) == before


@pytest.mark.parametrize('fault', ['image', 'owner', 'mount', 'port', 'command', 'user', 'env', 'privileged', 'extra-port'])
def test_reopening_foreign_or_mutated_container_never_starts_or_removes_it(host, fault):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    container = next(iter(host['containers'].values())); container['State']['Running'] = False
    if fault == 'image': container['Image'] = 'sha256:' + 'f' * 64
    elif fault == 'owner': container['Config']['Labels']['org.kingfisher.recovery.owner'] = 'foreign'
    elif fault == 'mount': container['Mounts'][0]['Source'] = '/private/other'
    elif fault == 'port': container['NetworkSettings']['Ports']['8890/tcp'][0]['HostIp'] = '0.0.0.0'
    elif fault == 'command': container['Config']['Cmd'] = ['other-service']
    elif fault == 'user': container['Config']['User'] = '0'
    elif fault == 'env': container['Config']['Env'] += ['MISTRAL_API_KEY=old']
    elif fault == 'privileged': container['HostConfig']['Privileged'] = True
    else: container['HostConfig']['PortBindings']['9999/tcp'] = [{'HostIp': '0.0.0.0', 'HostPort': '9999'}]
    host['calls'].clear()
    code, result = invoke(host, request(host, 'open', folder=str(host['source'])))
    assert code != 0 and result['ok'] is False
    assert not any(c[1] in ('start', 'rm', 'create') for c, _ in host['calls'])


def test_failed_new_start_removes_only_own_new_container_and_keeps_data(host):
    host['faults']['start'] = True
    code, result = invoke(host, request(host, 'open', folder=str(host['source'])))
    assert code != 0 and result['ok'] is False
    assert not host['containers'] and host['source'].is_dir()
    assert not (host['source'] / 'recovery-app.json').exists()
    assert (host['source'] / 'settings.env').read_text() == 'OLD_PRIVATE_SENTINEL'


def test_symlink_existing_and_overlapping_targets_are_rejected(host):
    alias = host['root'] / 'alias'; alias.symlink_to(host['source'], target_is_directory=True)
    for target in (host['source'], host['source'] / 'nested', alias / 'nested'):
        code, _ = invoke(host, request(host, 'prepare', folder=str(host['source']), target=str(target), fingerprint='b' * 64, selection='restored', acknowledge_unknown=True))
        assert code != 0
    assert not host['calls']


def test_concurrent_operation_fails_closed_without_docker(host):
    with host['module']._locked(host['source']):
        assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] != 0
    assert not host['calls']


def test_inspection_never_adds_files_to_the_historical_folder(host):
    before = sorted(p.name for p in host['source'].iterdir())
    assert invoke(host, request(host, 'inspect', folder=str(host['source'])))[0] == 0
    assert sorted(p.name for p in host['source'].iterdir()) == before


def test_image_volume_is_masked_and_loopback_port_reserved_in_container_config(host):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    command = next(c for c, _ in host['calls'] if c[1] == 'create')
    assert '/data:ro,noexec,nosuid,size=1m' in command
    assert command[command.index('--publish') + 1] == '127.0.0.1:49173:8890'


@pytest.mark.parametrize('fault', ['unknown-key', 'public', 'symlink'])
def test_invalid_private_receipt_never_touches_existing_container(host, fault):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    receipt = host['source'] / 'recovery-app.json'
    if fault == 'unknown-key':
        state = json.loads(receipt.read_text()); state['token'] = 'private'; receipt.write_text(json.dumps(state))
    elif fault == 'public': receipt.chmod(0o644)
    else:
        other = host['source'] / 'other.json'; receipt.rename(other); receipt.symlink_to(other)
    host['calls'].clear()
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] != 0
    assert not any(c[1] in ('start', 'rm', 'create') for c, _ in host['calls'])


@pytest.mark.parametrize('phase', ['probe', 'worker', 'create', 'inspect'])
def test_timeouts_remove_only_the_demonstrably_created_container(host, phase):
    if phase in ('probe', 'worker'): host['faults']['timeout'] = phase
    elif phase == 'create': host['faults']['create-timeout'] = True
    else: host['faults']['inspect-once'] = True
    payload = request(host, 'extract', bundle=str(host['bundle']), target=str(host['output'] / 'restored'), password='PASSWORD_SENTINEL') if phase in ('probe', 'worker') else request(host, 'open', folder=str(host['source']))
    code, result = invoke(host, payload)
    assert code != 0 and result['ok'] is False and 'SENTINEL' not in json.dumps(result)
    assert not host['containers']
    assert any(command[1] == 'rm' for command, _ in host['calls'])
    assert host['source'].is_dir() and host['bundle'].is_file()


@pytest.mark.parametrize('current_image', ['sha256:' + 'f' * 64, ''])
def test_reopen_keeps_original_image_after_main_app_update_or_removal(host, current_image):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    host['calls'].clear()
    code, result = invoke(host, request(host, 'open', folder=str(host['source'])) | {'image': current_image})
    assert code == 0 and result['image'] == IMAGE
    assert next(c[-1] for c, _ in host['calls'] if c[1:3] == ['image', 'inspect']) == IMAGE
    assert not any(c[1] == 'create' for c, _ in host['calls'])


def test_missing_receipt_needs_explicit_pinned_image(host):
    assert invoke(host, request(host, 'open', folder=str(host['source'])) | {'image': ''})[0] != 0
    assert not host['calls']


def test_stopped_owned_container_reopens_only_after_all_checks(host):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    value = next(iter(host['containers'].values()))
    value['State']['Running'] = False
    value['NetworkSettings']['Ports'] = None
    run = host['module'].subprocess.run
    def restart(command, **kwargs):
        result = run(command, **kwargs)
        if 'start' in command[1:]:
            value['NetworkSettings']['Ports'] = {'8890/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '49173'}]}
        return result
    host['monkeypatch'].setattr(host['module'].subprocess, 'run', restart)
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0


@pytest.mark.parametrize('normal_api', [True, False])
def test_readiness_requires_cookie_authenticated_normal_api_not_inspection_html(monkeypatch, normal_api):
    from urllib.error import HTTPError
    module = load(); requests = []; handlers = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Opener:
        def open(self, url, timeout):
            requests.append(url)
            if not normal_api and url.endswith('/api/v1/system'):
                raise HTTPError(url, 403, 'inspection fixture', {}, None)
            return Response()
    def opener(*parts): handlers.extend(parts); return Opener()
    monkeypatch.setattr(module, 'build_opener', opener)
    times = iter([0, 1, 30]); monkeypatch.setattr(module.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    if normal_api: module._wait_ready('http://127.0.0.1:49173')
    else:
        with pytest.raises(ValueError): module._wait_ready('http://127.0.0.1:49173')
    assert requests == ['http://127.0.0.1:49173/', 'http://127.0.0.1:49173/api/v1/system']
    assert any(type(handler).__name__ == 'HTTPCookieProcessor' for handler in handlers)
    redirect = next(handler for handler in handlers if hasattr(handler, 'redirect_request'))
    assert redirect.redirect_request(None, None, 302, 'redirect', {}, 'http://elsewhere.invalid') is None


def test_private_state_becomes_visible_only_when_completely_written(host, monkeypatch):
    statefile = host['source'] / 'recovery-app.json'
    dump = host['module'].json.dump
    def write(value, stream):
        assert not statefile.exists()
        dump(value, stream)
    monkeypatch.setattr(host['module'].json, 'dump', write)
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    assert json.loads(statefile.read_text())['image'] == IMAGE
    assert not list(host['source'].glob('.recovery-app-*.tmp'))


@pytest.mark.parametrize('operation', ['extract', 'inspect', 'prepare'])
def test_worker_executes_existing_api_with_exact_selected_data_directory(monkeypatch, tmp_path, operation):
    module = load(); folder = tmp_path.resolve() / 'historical'; target = tmp_path.resolve() / 'working'
    payload = {'operation': operation, 'folder': str(folder), 'target': str(target),
        'bundle': str(tmp_path.resolve() / 'bundle.kf'), 'password': 'SYNTHETIC_PASSWORD',
        'fingerprint': 'b' * 64, 'selection': '20261104T120000Z', 'acknowledge_unknown': True}
    called = []
    package = types.ModuleType('icarus_memory'); package.__path__ = []
    monkeypatch.setitem(sys.modules, 'icarus_memory', package)
    def restore(bundle, destination, password): called.append((bundle, destination, password)); return destination
    def inspect(source): called.append((source,)); return {'report_fingerprint': 'b' * 64}
    def prepare(source, destination, **options): called.append((source, destination, options)); return destination
    for name, functions in [('recovery_bundle', {'restore_bundle': restore}), ('recovery_preflight', {'preflight': inspect}), ('recovery_workspace', {'prepare_working_copy': prepare})]:
        fake = types.ModuleType('icarus_memory.' + name)
        for key, function in functions.items(): setattr(fake, key, function)
        monkeypatch.setitem(sys.modules, 'icarus_memory.' + name, fake)
    output = io.StringIO(); monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload))); monkeypatch.setattr(sys, 'stdout', output)
    exec(module.WORKER, {})
    result = json.loads(output.getvalue())
    assert result['ok'] is True and 'SYNTHETIC_PASSWORD' not in output.getvalue()
    if operation == 'extract': assert called == [(Path(payload['bundle']), target, 'SYNTHETIC_PASSWORD')]
    elif operation == 'inspect': assert called == [(folder / 'data',)]
    else:
        assert called == [(folder / 'data', target, {'fingerprint': 'b' * 64, 'selection': '20261104T120000Z', 'acknowledge_unknown': True})]


@pytest.mark.parametrize('endpoint', ['tcp://127.0.0.1:2375', 'ssh://elsewhere.invalid', 'unix:///does/not/exist', 'unix://relative'])
def test_remote_or_non_socket_docker_endpoint_cannot_receive_work(host, endpoint):
    host['faults']['endpoint'] = endpoint
    code, result = invoke(host, request(host, 'inspect', folder=str(host['source'])))
    assert code != 0 and result['ok'] is False
    assert [c[1:3] for c, _ in host['calls']] == [['context', 'inspect']]


def test_every_docker_operation_is_bound_to_the_verified_local_socket(host):
    assert invoke(host, request(host, 'open', folder=str(host['source'])))[0] == 0
    assert host['raw_calls'][0][1:3] == ['context', 'inspect']
    assert all(command[1:3] == ['--host', host['endpoint']] for command in host['raw_calls'][1:])
