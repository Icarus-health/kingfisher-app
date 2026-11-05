#!/usr/bin/env python3
"""Private JSON-only native recovery bridge. Never reads host settings/secrets."""
from contextlib import contextmanager
import fcntl
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, build_opener
import uuid

LIMIT = 65536
OUTPUT_LIMIT = 4 * 1024 * 1024
OWNER_LABEL = 'org.kingfisher.recovery.owner'
VERSION_LABEL = 'org.kingfisher.recovery.version'
ERROR = 'Nicht abgeschlossen. Lokale App-Version, Docker, Auswahl und getrennten Zielordner prüfen.'
PROBE = "import json; from icarus_memory.recovery_workspace import CAPABILITY; print(json.dumps({'capability': CAPABILITY if type(CAPABILITY) is int else None}))"
WORKER = r'''
import json, sys
from pathlib import Path
try:
    request = json.load(sys.stdin)
    operation = request['operation']
    if operation == 'extract':
        from icarus_memory.recovery_bundle import restore_bundle
        folder = restore_bundle(Path(request['bundle']), Path(request['target']), request['password'])
        result = {'ok': True, 'folder': str(folder)}
    elif operation == 'inspect':
        from icarus_memory.recovery_preflight import preflight
        result = {'ok': True, 'report': preflight(Path(request['folder']) / 'data')}
    elif operation == 'prepare':
        from icarus_memory.recovery_workspace import prepare_working_copy
        folder = prepare_working_copy(Path(request['folder']) / 'data', Path(request['target']),
            fingerprint=request['fingerprint'], selection=request['selection'],
            acknowledge_unknown=request['acknowledge_unknown'])
        result = {'ok': True, 'folder': str(folder)}
    else:
        raise ValueError()
    print(json.dumps(result, ensure_ascii=False))
except Exception:
    print(json.dumps({'ok': False, 'error': 'Daten konnten nicht geprüft oder vorbereitet werden.'}))
    sys.exit(1)
'''


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _json(text):
    if len(text) > OUTPUT_LIMIT:
        raise ValueError()
    return json.loads(text, object_pairs_hook=_unique)


def _path(value):
    if (not isinstance(value, str) or not value or not Path(value).is_absolute()
            or any(c in value for c in ('\x00', '\n', '\r', ','))
            or '..' in Path(value).parts):
        raise ValueError()
    path = Path(value)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError()
    return path


def _validate(request):
    if not isinstance(request, dict):
        raise ValueError()
    extras = {'extract': {'bundle', 'target', 'password'}, 'inspect': {'folder'},
        'prepare': {'folder', 'target', 'fingerprint', 'selection', 'acknowledge_unknown'}, 'open': {'folder'}}
    operation = request.get('operation')
    if not isinstance(operation, str) or operation not in extras or set(request) != {'operation', 'docker', 'image'} | extras[operation]:
        raise ValueError()
    if (not isinstance(request['image'], str)
            or not re.fullmatch('sha256:[a-f0-9]{64}', request['image'])
            and not (operation == 'open' and request['image'] == '')):
        raise ValueError()
    docker = request['docker']
    if not isinstance(docker, str) or not Path(docker).is_absolute() or not Path(docker).is_file() or not os.access(docker, os.X_OK):
        raise ValueError()
    # Docker Desktop's executable may itself be a symlink. Resolve that binary,
    # but do not resolve user-data aliases into silently different selections.
    request = dict(request, docker=str(Path(docker).resolve()))
    if operation == 'extract':
        source = _path(request['bundle'])
        if not source.is_file() or not isinstance(request['password'], str) or not 1 <= len(request['password']) <= 4096:
            raise ValueError()
    else:
        source = _path(request['folder'])
        if not source.is_dir() or not _path(str(source / 'data')).is_dir():
            raise ValueError()
    if operation in ('extract', 'prepare'):
        target = _path(request['target'])
        if (target.exists() or not target.parent.is_dir() or source == target
                or source in target.parents or target.parent == source or target.parent in source.parents):
            raise ValueError()
    if operation == 'prepare':
        if (request['acknowledge_unknown'] is not True
                or not isinstance(request['fingerprint'], str) or not re.fullmatch('[a-f0-9]{64}', request['fingerprint'])
                or not isinstance(request['selection'], str)
                or request['selection'] != 'restored' and not re.fullmatch(r'\d{8}T\d{6}Z', request['selection'])):
            raise ValueError()
    return request


@contextmanager
def _locked(folder):
    # Do not unlink lock files: a second process may already be waiting on this inode.
    folder = _path(str(folder))
    path = folder.parent / ('.' + folder.name + '.recovery-native.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError()
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def _run(docker, args, *, payload=None, timeout=120):
    environment = {key: value for key, value in os.environ.items()
                   if key in {'PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'TZ'} or re.fullmatch(r'LC_[A-Z0-9_]+', key)}
    executable = [docker[0], '--host', docker[1]] if isinstance(docker, tuple) else [docker]
    result = subprocess.run([*executable, *args], input=None if payload is None else json.dumps(payload),
        text=True, capture_output=True, check=True, timeout=timeout, env=environment)
    if len(result.stdout) > OUTPUT_LIMIT:
        raise ValueError()
    return result.stdout


def _local_docker(docker):
    # Context inspection reads CLI metadata only; it does not contact its daemon.
    # Pin the resulting local socket explicitly for every subsequent operation.
    endpoint = _json(_run(docker, ['context', 'inspect', '--format', '{{json .Endpoints.docker.Host}}'], timeout=15))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise ValueError()
    socket_path = Path(endpoint[7:])
    if not socket_path.is_absolute():
        raise ValueError()
    socket_path = socket_path.resolve(strict=True)
    if not socket_path.is_socket():
        raise ValueError()
    return (docker, 'unix://' + str(socket_path))


def _sandbox():
    return ['--pull=never', '--user', f'{os.getuid()}:{os.getgid()}', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--tmpfs', '/data:ro,noexec,nosuid,size=1m']


def _cleanup_created(request, cidfile, owner, name):
    """CID file proves this invocation created it; labels bind the inspected ID."""
    try:
        fd = os.open(cidfile, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'r') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return
            identifier = stream.read(129).strip()
        if not re.fullmatch('[a-f0-9]{64}', identifier):
            return
        value = _inspect(request['docker'], identifier)
        labels = value.get('Config', {}).get('Labels', {})
        if (value.get('Id') == identifier and value.get('Name') == '/' + name
                and value.get('Image') == request['image'] and labels.get(OWNER_LABEL) == owner
                and labels.get(VERSION_LABEL) == '1'):
            _run(request['docker'], ['rm', '-f', identifier], timeout=30)
    except Exception:
        # No guessed name-based deletion when Docker cannot prove ownership.
        pass


@contextmanager
def _creation(request, owner, name, *, always_cleanup=False):
    with tempfile.TemporaryDirectory(prefix='kingfisher-recovery-worker-') as temporary:
        cidfile = Path(temporary).resolve() / 'created.cid'
        try:
            yield str(cidfile)
        except BaseException:
            _cleanup_created(request, cidfile, owner, name)
            raise
        else:
            if always_cleanup:
                _cleanup_created(request, cidfile, owner, name)


def _ephemeral(request, script, *, mounts=(), payload=None, timeout=30):
    owner = uuid.uuid4().hex
    name = 'kingfisher-recovery-worker-' + owner
    with _creation(request, owner, name, always_cleanup=True) as cidfile:
        return _run(request['docker'], ['run', '--rm', '-i', '--network', 'none', *_sandbox(),
            '--name', name, '--cidfile', cidfile, '--label', OWNER_LABEL + '=' + owner,
            '--label', VERSION_LABEL + '=1', *mounts, '--entrypoint', 'python', request['image'], '-c', script],
            payload=payload, timeout=timeout)


def _image(request):
    result = _json(_run(request['docker'], ['image', 'inspect', request['image']], timeout=30))
    if not isinstance(result, list) or len(result) != 1 or result[0].get('Id') != request['image']:
        raise ValueError()
    configuration = result[0].get('Config', {})
    # The app image declares /data. Mask it with an empty readonly tmpfs rather
    # than creating an anonymous persistent volume beside the working copy.
    if set(configuration.get('Volumes') or {}) - {'/data'}:
        raise ValueError()
    answer = _json(_ephemeral(request, PROBE))
    if answer != {'capability': 1} or type(answer.get('capability')) is not int:
        raise ValueError()
    environment = configuration.get('Env') or []
    if not isinstance(environment, list) or not all(isinstance(value, str) for value in environment):
        raise ValueError()
    return environment


def _mount(path, *, readonly=False):
    return ['--mount', f'type=bind,source={path},target={path}' + (',readonly' if readonly else '')]


def _worker(request):
    operation = request['operation']
    payload = {key: value for key, value in request.items() if key not in {'docker', 'image'}}
    source = Path(request['bundle']) if operation == 'extract' else Path(request['folder']) / 'data'
    mounts = _mount(source, readonly=True)
    if operation in ('extract', 'prepare'):
        mounts += _mount(Path(request['target']).parent)
    result = _json(_ephemeral(request, WORKER, mounts=mounts, payload=payload, timeout=180))
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise ValueError()
    if operation == 'inspect':
        if set(result) != {'ok', 'report'} or not isinstance(result['report'], dict):
            raise ValueError()
    elif set(result) != {'ok', 'folder'} or result['folder'] != request['target'] or not _path(result['folder']).is_dir():
        raise ValueError()
    return result


def _state(folder):
    path = _path(str(folder / 'recovery-app.json'))
    if not path.exists():
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
            raise ValueError()
        value = _json(stream.read(8193))
    if (not isinstance(value, dict) or set(value) != {'version', 'owner', 'container', 'image', 'port'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['owner'], str) or not re.fullmatch('[a-f0-9]{32}', value['owner'])
            or value['container'] != 'kingfisher-recovery-' + value['owner']
            or not isinstance(value['image'], str) or not re.fullmatch('sha256:[a-f0-9]{64}', value['image'])
            or type(value['port']) is not int or not 1024 <= value['port'] <= 65535):
        raise ValueError()
    return value


def _command(folder):
    return ['-m', 'icarus_memory.recovery_workspace_cli', 'serve', '--container', '--folder', str(folder), '--port', '8890']


def _inspect(docker, name):
    result = _json(_run(docker, ['inspect', name], timeout=30))
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise ValueError()
    return result[0]


def _validate_container(value, folder, state, image_env, *, assigned=True):
    config = value['Config']; host = value['HostConfig']
    if (value['Name'] != '/' + state['container'] or value['Image'] != state['image']
            or config.get('Labels', {}).get(OWNER_LABEL) != state['owner'] or config.get('Labels', {}).get(VERSION_LABEL) != '1'
            or config.get('User') != f'{os.getuid()}:{os.getgid()}' or config.get('Env') != image_env
            or config.get('Entrypoint') != ['python'] or config.get('Cmd') != _command(folder)
            or host.get('Privileged') is not False or host.get('NetworkMode') != 'bridge'
            or host.get('ReadonlyRootfs') is not True or host.get('CapAdd') or host.get('CapDrop') != ['ALL']
            or host.get('SecurityOpt') != ['no-new-privileges'] or host.get('LogConfig', {}).get('Type') != 'none'):
        raise ValueError()
    tmpfs = {'/tmp': 'rw,noexec,nosuid,size=64m', '/data': 'ro,noexec,nosuid,size=1m'}
    if host.get('Tmpfs') != tmpfs:
        raise ValueError()
    mounts = value['Mounts']
    binds = [mount for mount in mounts if mount.get('Type') != 'tmpfs']
    if len(binds) != 1 or any(binds[0].get(k) != v for k, v in {'Type': 'bind', 'Source': str(folder), 'Destination': str(folder), 'RW': True}.items()):
        raise ValueError()
    if any(mount.get('Type') == 'tmpfs' and mount.get('Destination') not in tmpfs for mount in mounts):
        raise ValueError()
    bindings = host.get('PortBindings')
    if not isinstance(bindings, dict) or set(bindings) != {'8890/tcp'} or len(bindings['8890/tcp']) != 1 or bindings['8890/tcp'][0].get('HostIp') != '127.0.0.1':
        raise ValueError()
    if bindings['8890/tcp'][0].get('HostPort') != str(state['port']):
        raise ValueError()
    if not re.fullmatch('[a-f0-9]{64}', value.get('Id', '')):
        raise ValueError()
    if not assigned:
        return None
    ports = value['NetworkSettings']['Ports']
    if not isinstance(ports, dict) or set(ports) != {'8890/tcp'} or len(ports['8890/tcp']) != 1:
        raise ValueError()
    mapping = ports['8890/tcp'][0]
    port = int(mapping['HostPort'])
    if mapping.get('HostIp') != '127.0.0.1' or not 1024 <= port <= 65535 or state.get('port', port) != port:
        raise ValueError()
    return port


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _wait_ready(url):
    # Separate in-memory cookies for this readiness check only. Neither the
    # HttpOnly cookie nor an API response is logged, persisted or returned.
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()), _NoRedirect())
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            with opener.open(url + '/', timeout=1) as response:
                if response.status == 200:
                    with opener.open(url + '/api/v1/system', timeout=1) as system:
                        if system.status == 200:
                            return
        except OSError:
            pass
        time.sleep(.25)
    raise ValueError()


def _choose_port():
    # Release before Docker binds. A competing bind makes Docker fail safely;
    # the private receipt is written only after successful verified startup.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def _save_state(folder, state):
    path = folder / 'recovery-app.json'
    temporary = folder / ('.recovery-app-' + uuid.uuid4().hex + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic publication without replacing a receipt created concurrently.
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def _open(request, image_env):
    folder = Path(request['folder']); docker = request['docker']
    state = _state(folder)
    if state is not None:
        if state['image'] != request['image']:
            raise ValueError()
        value = _inspect(docker, state['container'])
        _validate_container(value, folder, state, image_env, assigned=False)
        # Stopped Docker containers can have no NetworkSettings ports yet.
        # The exact recorded host binding was checked above before starting.
        if value['NetworkSettings'].get('Ports'):
            _validate_container(value, folder, state, image_env)
        if not value['State']['Running']:
            _run(docker, ['start', value['Id']], timeout=45)
        value = _inspect(docker, state['container'])
        port = _validate_container(value, folder, state, image_env)
        if value['State']['Running'] is not True:
            raise ValueError()
        url = f'http://127.0.0.1:{port}'
        _wait_ready(url)
        return {'ok': True, 'url': url, 'instance_id': state['owner'], 'image': state['image']}
    owner = uuid.uuid4().hex
    state = {'version': 1, 'owner': owner, 'container': 'kingfisher-recovery-' + owner,
             'image': request['image'], 'port': _choose_port()}
    with _creation(request, owner, state['container']) as cidfile:
        identifier = _run(docker, ['create', *_sandbox(), '--network', 'bridge', '--name', state['container'],
            '--cidfile', cidfile,
            '--label', OWNER_LABEL + '=' + owner, '--label', VERSION_LABEL + '=1',
            *_mount(folder), '--publish', f'127.0.0.1:{state["port"]}:8890', '--entrypoint', 'python', request['image'], *_command(folder)], timeout=45).strip()
        if not re.fullmatch('[a-f0-9]{64}', identifier):
            raise ValueError()
        value = _inspect(docker, identifier)
        _validate_container(value, folder, state, image_env, assigned=False)
        if value['Id'] != identifier:
            raise ValueError()
        _run(docker, ['start', identifier], timeout=45)
        value = _inspect(docker, identifier)
        state['port'] = _validate_container(value, folder, state, image_env)
        if value['State']['Running'] is not True:
            raise ValueError()
        url = f'http://127.0.0.1:{state["port"]}'
        _wait_ready(url)
        _save_state(folder, state)
        return {'ok': True, 'url': url, 'instance_id': owner, 'image': state['image']}


def main(stdin=None, stdout=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        raw = stdin.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError()
        request = _validate(_json(raw))
        lock = request.get('target') or request['folder']
        with _locked(Path(lock)):
            if request['operation'] == 'open':
                state = _state(Path(request['folder']))
                if state is not None:
                    request['image'] = state['image']
                elif not request['image']:
                    raise ValueError()
            request['docker'] = _local_docker(request['docker'])
            image_env = _image(request)
            result = _open(request, image_env) if request['operation'] == 'open' else _worker(request)
        print(json.dumps(result, ensure_ascii=False), file=stdout)
        return 0
    except Exception:
        print(json.dumps({'ok': False, 'error': ERROR}, ensure_ascii=False), file=stdout)
        return 1


if __name__ == '__main__':
    if len(sys.argv) != 1:
        print(json.dumps({'ok': False, 'error': ERROR}, ensure_ascii=False))
        raise SystemExit(1)
    raise SystemExit(main())
