#!/usr/bin/env python3
"""Build a local Finder/Dock launcher for an existing Kingfisher Docker setup.

Uses macOS tools only. Does not copy secrets, install Docker or replace an app.
"""
import argparse
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import tempfile


def run(*args):
    subprocess.run(args, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--output', type=Path, default=Path.home() / 'Applications/Kingfisher.app')
    args = parser.parse_args()
    repo = args.repo.resolve()
    env = args.env_file.resolve()
    output = args.output.expanduser().absolute()
    if output.exists():
        parser.error('Ziel existiert bereits; vorhandene App wird nicht ersetzt.')
    if output.suffix != '.app':
        parser.error('Ziel muss auf .app enden.')
    launcher = repo / 'scripts/start_mac_app.py'
    logo = repo / 'design-source/01_Brand/Approved/kingfisher-logo-dark-approved-v1.png'
    if not launcher.is_file() or not env.is_file() or not logo.is_file():
        parser.error('Repository, private Konfiguration oder freigegebenes Logo fehlen.')
    # Quote arguments as shell data, then quote the whole shell string as AppleScript data.
    command = 'export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; ' + shlex.join([
        '/usr/bin/python3', str(launcher), '--container', args.container,
        '--env-file', str(env), '--url', args.url])
    source = '''on run
    try
        with timeout of 360 seconds
            do shell script COMMAND
        end timeout
    on error
        display dialog "Kingfisher konnte nicht gestartet werden. Bitte prüfe, ob die Docker-Laufzeit und der Kingfisher-Projektordner noch vorhanden sind." buttons {"OK"} default button "OK" with title "Kingfisher" with icon caution
    end try
end run
'''.replace('COMMAND', json.dumps(command, ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix='kingfisher-launcher-') as temporary:
        root = Path(temporary)
        script = root / 'launcher.applescript'
        script.write_text(source)
        bundle = root / 'Kingfisher.app'
        run('/usr/bin/osacompile', '-o', str(bundle), str(script))
        iconset = root / 'Kingfisher.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
                run('/usr/bin/sips', '-z', str(size * scale), str(size * scale), str(logo), '--out', str(iconset / name))
        resources = bundle / 'Contents/Resources'
        run('/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'Kingfisher.icns'))
        info_path = bundle / 'Contents/Info.plist'
        with info_path.open('rb') as file:
            info = plistlib.load(file)
        info.update(CFBundleName='Kingfisher', CFBundleDisplayName='Kingfisher',
                    CFBundleIdentifier='local.kingfisher.launcher', CFBundleIconFile='Kingfisher',
                    CFBundleShortVersionString='1.0', CFBundleVersion='1',
                    NSHumanReadableCopyright='Kingfisher — lokaler Docker-Starter')
        with info_path.open('wb') as file:
            plistlib.dump(info, file)
        run('/usr/bin/codesign', '--force', '--sign', '-', str(bundle))
        run('/usr/bin/codesign', '--verify', '--strict', str(bundle))
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, output)
    print(str(output))


if __name__ == '__main__':
    main()
