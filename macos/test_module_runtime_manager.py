"""Compile/run native manager contracts with injected synthetic boundaries only."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def manager_binary(tmp_path_factory):
    if sys.platform != 'darwin' or not shutil.which('swiftc'):
        pytest.skip('Native manager contract requires macOS Swift')
    build = tmp_path_factory.mktemp('module-runtime-manager-build')
    sources = ['macos/App/Logic/ModuleRuntimeContract.swift', 'macos/App/Logic/EnvFile.swift',
        'macos/App/Logic/Installation.swift', 'macos/App/Logic/Release.swift',
        'macos/App/Logic/ModuleIsolation.swift', 'macos/App/ModuleRuntimeCache.swift',
        'macos/App/Paths.swift', 'macos/App/ModuleRuntimeManager.swift',
        'macos/tests/module_runtime_manager/main.swift']
    binary = build / 'manager-contract'
    result = subprocess.run(['swiftc','-module-cache-path',str(build/'modules'),
        *[str(ROOT/name) for name in sources],'-o',str(binary)],capture_output=True,text=True,timeout=120)
    (build/'compile.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, result.stderr
    return binary


@pytest.mark.parametrize('scenario', [
    'backend-cache-drain-retry','recipe-cache-drain-retry',
    'recipe-cache-rollback','recipe-cache-cancel-retry','prepared-reconcile','prepared-stale-active-fallback',
    'env-backslash','env-trailing-slash','env-quotes','env-dollar','env-unicode-tab',
    'rollback-env-drift','rollback-mode-drift','rollback-key-drift','rollback-old-authority',
    'fresh-cache-drain-retry','fresh-cache-cancel-retry',
    'shutdown-absent-no-work','shutdown-partial','host-network','oversized-tmpfs','reused-control-key','cancel-before-main','cancel-after-probe','backend-update-cache',
    'dto-strict','topology','foreign-image','private-mount','external-network','ports',
    'root-user','caps','writable-root','dns','resources','bad-tmpfs','worker-authority',
    'gateway-authority','wrong-mode','foreign-alias','network-members','negative-receipt',
    'initial-idle','setup','cache-reuse','unknown-cache','self-signed-cache','cache-ready-not-ready',
    'cancelled','probe-failure','pair-failure','generation-race','foreign-existing','repeat',
    'shutdown','shutdown-busy','shutdown-unknown','shutdown-404','shutdown-404-enabled',
    'reconcile-absent','reconcile-approved','reconcile-changed-recipe','status-no-adopt',
    'image-race','restore-env','preserve-env','admission',
])
def test_manager_boundary(manager_binary, tmp_path, scenario):
    result = subprocess.run([str(manager_binary),scenario,str(tmp_path)],
        env={'PATH':'/usr/bin:/bin','HOME':str(tmp_path),'TMPDIR':str(tmp_path)},
        capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert json.loads(result.stdout) == {'passed':scenario}


def test_preserved_values_roundtrip_through_offline_compose_parser(manager_binary, tmp_path):
    compose = Path('/opt/homebrew/lib/docker/cli-plugins/docker-compose')
    if not compose.is_file():
        pytest.skip('Config-only Compose parser is not installed')
    isolated = tmp_path / 'isolated'
    isolated.mkdir()
    config = tmp_path / 'compose.yaml'
    config.write_text('services:\n  fixture:\n    image: synthetic/offline:never-run\n    environment:\n      VALUE: ${KINGFISHER_VOLLER_NAME}\n')
    fixtures = json.loads(subprocess.check_output([str(manager_binary),'dotenv-roundtrip',str(tmp_path)],text=True,
        env={'PATH':'/usr/bin:/bin','HOME':str(isolated),'TMPDIR':str(isolated)}))
    assert len(fixtures) >= 22  # Every setup and rollback uses the same codec.
    for index, fixture in enumerate(fixtures):
        env_file = tmp_path / f'{index}.env'
        env_file.write_text(fixture['env'])
        command = [str(compose),'-f',str(config),'--env-file',str(env_file),'config']
        clean_env = {'PATH':'/usr/bin:/bin','HOME':str(isolated),'TMPDIR':str(isolated),
                     'DOCKER_CONFIG':str(isolated),'DOCKER_HOST':'unix://' + str(isolated/'nonexistent.sock')}
        result = subprocess.run(command + ['--environment'],env=clean_env,cwd=isolated,capture_output=True,text=True,timeout=10)
        assert result.returncode == 0, result.stderr
        resolved = dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
        assert resolved['KINGFISHER_VOLLER_NAME'] == fixture['original']
        result = subprocess.run(command + ['--format','json'],env=clean_env,cwd=isolated,capture_output=True,text=True,timeout=10)
        assert result.returncode == 0, result.stderr
        # Compose's reusable config output doubles literal dollars again. The
        # resolver above exposes the actual literal value before that printing.
        assert json.loads(result.stdout)['services']['fixture']['environment']['VALUE'] == fixture['original'].replace('$','$$')


@pytest.mark.parametrize('probe_case', ['redirect','writable-home','broker-redirect'])
def test_fixed_probe_refuses_false_positive_boundary_receipts(manager_binary, tmp_path, monkeypatch, capsys, probe_case):
    # Export the compiled fixed program, then execute only against synthetic OS,
    # process, filesystem, DNS and HTTP boundaries. No actual probe runs on host.
    import builtins
    import errno
    import io
    import os
    import socket
    import urllib.error
    import urllib.request
    from types import SimpleNamespace
    from urllib.parse import urlsplit
    scripts = json.loads(subprocess.check_output([str(manager_binary),'probe-scripts',str(tmp_path)],text=True))
    follows = []
    def opened(path, mode='r', *args, **kwargs):
        if path == '/proc/self/status':
            return io.StringIO('CapEff:\t00000000\nNoNewPrivs:\t1\n')
        if str(path).startswith('/home/kingfisher/.kf-isolation-'):
            if probe_case == 'writable-home':
                return io.BytesIO()
            raise OSError(errno.EROFS,'read-only')
        if str(path).startswith('/kf-isolation-'):
            raise PermissionError(errno.EACCES,'root directory permissions')
        if str(path).startswith('/tmp/kf-isolation-'):
            return io.BytesIO()
        raise AssertionError('unexpected filesystem access')
    def denied(*_args, **_kwargs):
        raise OSError(errno.ENETUNREACH,'unreachable')
    def dns(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME,'not found')
    def data_denied(*_args, **_kwargs):
        raise PermissionError(errno.EACCES,'denied')
    def noexec(*_args, **_kwargs):
        raise PermissionError(errno.EACCES,'noexec')
    class Opener:
        def __init__(self, handlers):
            self.handlers = handlers
        def open(self, request, timeout):
            url = urlsplit(request.full_url)
            broker = url.port == 8892
            redirect = (probe_case == 'redirect' and url.path == '/') or (probe_case == 'broker-redirect' and broker)
            if redirect:
                handler = next((h for h in self.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)), urllib.request.HTTPRedirectHandler())
                target = handler.redirect_request(request,None,302,'Found',{},'http://outside.invalid/')
                if target is not None:
                    follows.append(target.full_url)
                    raise urllib.error.HTTPError(request.full_url,401 if broker else 404,'',{},None)
                raise urllib.error.HTTPError(request.full_url,302,'',{},None)
            if url.path == '/health':
                return SimpleNamespace(status=200,headers={})
            raise urllib.error.HTTPError(request.full_url,401 if broker or url.port == 8891 else 404,'',{},None)
    with monkeypatch.context() as patch:
        patch.setattr(builtins,'open',opened)
        patch.setattr(os,'getuid',lambda:1000)
        patch.setattr(os,'environ',{'ICARUS_SIDECAR_TOKEN':'SENTINEL'} if probe_case == 'broker-redirect' else {})
        patch.setattr(os,'stat',lambda *_a, **_kw:SimpleNamespace(st_uid=1000))
        patch.setattr(os,'chmod',lambda *_a:None)
        patch.setattr(os,'unlink',lambda *_a:None)
        patch.setattr(os,'listdir',data_denied)
        patch.setattr(os,'open',data_denied)
        patch.setattr(os,'close',lambda *_a:None)
        patch.setattr(socket,'getaddrinfo',dns)
        patch.setattr(socket,'create_connection',denied)
        patch.setattr(subprocess,'run',noexec)
        patch.setattr(urllib.request,'build_opener',lambda *handlers:Opener(handlers))
        patch.setattr(sys,'argv',['probe','172.21.0.2','172.20.0.1'])
        exec(scripts['broker' if probe_case == 'broker-redirect' else 'sandbox'],{})
    receipt = json.loads(capsys.readouterr().out)
    if probe_case == 'writable-home':
        assert receipt['root_read_only'] is False
    elif probe_case == 'redirect':
        assert not follows and receipt['ui_denied'] is False
    else:
        assert not follows and not any(receipt.values())
