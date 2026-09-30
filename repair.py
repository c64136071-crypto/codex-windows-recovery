"""Verify and mirror Codex MSIX plugin resources without touching user config."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


CLI_FILES = (
    'codex.exe', 'codex-code-mode-host.exe', 'codex-command-runner.exe',
    'codex-windows-sandbox-setup.exe',
)
CUA_CHECKS = ('manifest.json', 'bin/node.exe', 'bin/node_repl.exe')
MARKETPLACE = Path('openai-bundled/.agents/plugins/marketplace.json')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').digest()


def files(root):
    if not root.is_dir():
        return {}
    return {path.relative_to(root): path for path in root.rglob('*') if path.is_file()}


def check_plugins(source, mirror, deep=False):
    manifest = source / MARKETPLACE
    if not manifest.is_file():
        raise RuntimeError('Packaged plugin marketplace is missing.')
    json.loads(manifest.read_text(encoding='utf-8-sig'))
    original, copied = files(source), files(mirror)
    if original.keys() != copied.keys():
        return False
    if any(path.stat().st_size != copied[name].stat().st_size for name, path in original.items()):
        return False
    selected = original if deep else {MARKETPLACE: manifest}
    return all(digest(path) == digest(copied[name]) for name, path in selected.items())


def check_runtime(resources, mirror, deep=False):
    for name in CLI_FILES:
        source, target = resources / name, mirror / name
        if not source.is_file() or not target.is_file() or source.stat().st_size != target.stat().st_size:
            return False
        if deep and digest(source) != digest(target):
            return False
    cua = mirror / 'cua_node'
    if not cua.is_junction() or not (cua / 'bin/node_modules').is_dir():
        return False
    for name in CUA_CHECKS:
        source, target = resources / 'cua_node' / name, cua / name
        if not source.is_file() or not target.is_file() or source.stat().st_size != target.stat().st_size:
            return False
        if deep and digest(source) != digest(target):
            return False
    if deep:
        original, copied = files(resources / 'cua_node'), files(cua)
        if original.keys() != copied.keys():
            return False
        return all(digest(path) == digest(copied[name]) for name, path in original.items())
    return True


def copy_verified(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.codex-recovery-tmp')
    try:
        with source.open('rb') as reader, temporary.open('wb') as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
        if digest(source) != digest(temporary):
            raise RuntimeError(f'Copy verification failed: {source}')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def sync_plugins(source, mirror):
    manifest = source / MARKETPLACE
    if not manifest.is_file():
        raise RuntimeError('Packaged plugin marketplace is missing; nothing changed.')
    json.loads(manifest.read_text(encoding='utf-8-sig'))
    original = files(source)
    if source.resolve() == mirror.resolve() or source.resolve().is_relative_to(mirror.resolve()) or mirror.resolve().is_relative_to(source.resolve()):
        raise RuntimeError('Source and mirror must be separate directory trees.')
    if mirror.is_symlink() or mirror.is_junction():
        raise RuntimeError('Plugin mirror root must not be a link.')
    # Validate every destination before any write or obsolete-file deletion.
    for name, path in original.items():
        target = mirror / name
        if (path.is_symlink() or target.is_symlink()
                or not path.resolve().is_relative_to(source.resolve())
                or not target.resolve().is_relative_to(mirror.resolve())):
            raise RuntimeError(f'Unsafe plugin path: {name}')
        if path.name in ('plugin.json', 'marketplace.json'):
            json.loads(path.read_text(encoding='utf-8-sig'))
    for name, path in files(mirror).items():
        if path.is_symlink() or not path.resolve().is_relative_to(mirror.resolve()):
            raise RuntimeError(f'Unsafe mirror file: {name}')
    for name, path in original.items():
        target = mirror / name
        if target.is_file() and target.stat().st_size == path.stat().st_size and digest(target) == digest(path):
            continue
        copy_verified(path, target)
    for name, path in files(mirror).items():
        if name not in original:
            if path.is_symlink() or not path.resolve().is_relative_to(mirror.resolve()):
                raise RuntimeError(f'Unsafe obsolete mirror path: {name}')
            path.unlink()
    if not check_plugins(source, mirror, deep=True):
        raise RuntimeError('Plugin mirror did not pass full verification.')


def runtime_id(source, names):
    identity = hashlib.sha256()
    for name in names:
        identity.update(name.encode() + b'\0' + digest(source / name).hex().encode() + b'\0')
    return identity.hexdigest()[:16]


def prepare_cache(source, cache, names, whole_tree=False):
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / runtime_id(source, names)
    if target.exists():
        if all((target / name).is_file() and digest(target / name) == digest(source / name)
               for name in names) and (not whole_tree or (target / 'bin/node_modules').is_dir()):
            return target
        raise RuntimeError(f'Incomplete existing cache left untouched: {target}')
    with tempfile.TemporaryDirectory(prefix='.stage-', dir=cache) as temporary:
        stage = Path(temporary)
        paths = files(source).values() if whole_tree else (source / name for name in names)
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                raise RuntimeError(f'Unsafe runtime file: {path}')
            copy_verified(path, stage / path.relative_to(source))
        if whole_tree and not (stage / 'bin/node_modules').is_dir():
            raise RuntimeError('Packaged CUA node_modules is missing.')
        stage.rename(target)
    return target


def link_runtime(resources, mirror, local_app_data):
    if os.name != 'nt':
        raise RuntimeError('Runtime junctions require Windows.')
    import _winapi

    cache = local_app_data / 'OpenAI' / 'Codex'
    cli = prepare_cache(resources, cache / 'bin', CLI_FILES)
    cua = prepare_cache(resources / 'cua_node', cache / 'runtimes' / 'cua_node', CUA_CHECKS, True)
    mirror.mkdir(parents=True, exist_ok=True)
    for name in CLI_FILES:
        target = mirror / name
        if target.exists() and os.path.samefile(target, cli / name):
            continue
        temporary = mirror / (name + '.codex-recovery-link')
        try:
            os.link(cli / name, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    target = mirror / 'cua_node'
    if target.is_junction() and target.resolve() == cua.resolve():
        return
    if os.path.lexists(target):
        if not target.is_junction():
            raise RuntimeError(f'Refusing to replace non-junction path: {target}')
        os.rmdir(target)
    _winapi.CreateJunction(str(cua), str(target))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('quick-check', 'doctor', 'repair'))
    parser.add_argument('--resources', type=Path, required=True, help='Current package app/resources directory')
    parser.add_argument('--home', type=Path, default=Path.home() / '.codex')
    parser.add_argument('--local-app-data', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '')))
    args = parser.parse_args(argv)
    mirror = args.home / 'plugin-resources'
    if args.action == 'repair':
        if not args.local_app_data.is_dir():
            raise RuntimeError('LOCALAPPDATA is unavailable.')
        sync_plugins(args.resources / 'plugins', mirror / 'plugins')
        link_runtime(args.resources, mirror, args.local_app_data)
    deep = args.action != 'quick-check'
    healthy = check_plugins(args.resources / 'plugins', mirror / 'plugins', deep)
    healthy = check_runtime(args.resources, mirror, deep) and healthy
    print('healthy' if healthy else 'repair required')
    return 0 if healthy else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f'error: {error}', file=sys.stderr)
        sys.exit(2)
