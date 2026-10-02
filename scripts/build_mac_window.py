#!/usr/bin/env python3
"""Build a native window for an existing local Kingfisher Docker installation.

Copies configuration paths only, never secrets; never replaces an existing app.
Requires macOS Command Line Tools. Building does not launch Docker or the app.
"""
import argparse
import json
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse


def run(*args):
    subprocess.run(args, check=True, capture_output=True, text=True)


def clear_generated_metadata(bundle):
    """Remove only signing-incompatible metadata from this generated artifact."""
    # File Provider can recreate metadata on the root while traversing children;
    # clean that root last, immediately before signature verification.
    for path in (*bundle.rglob('*'), bundle):
        attributes = subprocess.run(['/usr/bin/xattr', str(path)], check=True,
                                    capture_output=True, text=True).stdout.splitlines()
        for name in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
            if name in attributes:
                run('/usr/bin/xattr', '-d', name, str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    env = args.env_file.expanduser().resolve()
    output = args.output.expanduser().absolute()
    if output.exists():
        parser.error('Ziel existiert bereits; vorhandene App wird nicht ersetzt.')
    if output.suffix != '.app':
        parser.error('Ziel muss auf .app enden.')
    parsed = urlparse(args.url)
    try:
        port = parsed.port
    except ValueError:
        parser.error('Ungültiger lokaler Port.')
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment or port == 0):
        parser.error('Kingfisher benötigt eine lokale HTTP-Adresse auf 127.0.0.1.')
    source = repo/'macos/KingfisherApp.swift'
    shared = sorted((repo/'macos/Shared').glob('*.swift'))
    logo = repo/'design-source/01_Brand/Approved/kingfisher-logo-dark-approved-v1.png'
    if not source.is_file() or not shared or not (repo/'scripts/start_mac_app.py').is_file() or not env.is_file() or not logo.is_file():
        parser.error('Repository, private Konfiguration oder freigegebenes Logo fehlen.')
    if not args.container.strip() or args.container.startswith('-'):
        parser.error('Ein vorhandener Docker-Container muss angegeben werden.')
    with tempfile.TemporaryDirectory(prefix='kingfisher-window-') as temporary:
        root = Path(temporary)
        bundle = root/'Kingfisher.app'
        contents = bundle/'Contents'
        resources = contents/'Resources'
        executable = contents/'MacOS/Kingfisher'
        resources.mkdir(parents=True)
        executable.parent.mkdir()
        run('/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-O', '-target',
            f'{platform.machine()}-apple-macosx11.3',
            '-framework', 'AppKit', '-framework', 'WebKit', *map(str, shared), str(source), '-o', str(executable))
        # Explicitly retain executable permission through copytree/copy2.
        executable.chmod(0o755)
        configuration = {'repo': str(repo), 'envFile': str(env), 'container': args.container,
                         'url': args.url.rstrip('/')}
        (resources/'WindowConfiguration.json').write_text(json.dumps(configuration, ensure_ascii=False)+'\n')
        iconset = root/'Kingfisher.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
                run('/usr/bin/sips', '-z', str(size*scale), str(size*scale), str(logo), '--out', str(iconset/name))
        run('/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o', str(resources/'Kingfisher.icns'))
        info = dict(CFBundleName='Kingfisher', CFBundleDisplayName='Kingfisher',
                    CFBundleIdentifier='local.kingfisher.window', CFBundleExecutable='Kingfisher',
                    CFBundlePackageType='APPL', CFBundleIconFile='Kingfisher',
                    CFBundleShortVersionString='1.0', CFBundleVersion='1',
                    LSMinimumSystemVersion='11.3', NSHighResolutionCapable=True,
                    NSHumanReadableCopyright='Kingfisher — lokale App',
                    NSAppTransportSecurity={'NSAllowsLocalNetworking': True,
                                            'NSAllowsArbitraryLoadsInWebContent': True})
        with (contents/'Info.plist').open('wb') as file:
            plistlib.dump(info, file)
        # Resource metadata from macOS image tools must not invalidate signing.
        clear_generated_metadata(bundle)
        run('/usr/bin/codesign', '--force', '--sign', '-', str(bundle))
        run('/usr/bin/codesign', '--verify', '--strict', str(bundle))
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, output, copy_function=shutil.copy2)
        clear_generated_metadata(output)
        run('/usr/bin/codesign', '--verify', '--strict', str(output))
    print(str(output))


if __name__ == '__main__':
    main()
