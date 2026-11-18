"""Offline local-state backup, integrity verification and non-destructive restore.

Only use while the API, freshness worker and indexing jobs are STOPPED.
PostgreSQL is NOT backed up here: use pg_dump/pg_restore separately.
A backup includes sensitive account/session data: restrict, encrypt and secure it.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
MAX_UNCOMPRESSED = 20 * 1024 ** 3  # guard accidental zip bombs
SLOT = re.compile(r'^[a-z][a-z0-9_-]{0,39}$')


def _digest(stream):
    h = hashlib.sha256()
    size = 0
    for part in iter(lambda: stream.read(1024 * 1024), b''):
        size += len(part)
        h.update(part)
    return h.hexdigest(), size


def _safe_name(name):
    if not isinstance(name, str) or '\\' in name or name.startswith('/') or '\0' in name:
        raise ValueError('Unsafe archive path')
    parts = PurePosixPath(name).parts
    if len(parts) < 3 or parts[0] != 'state' or not SLOT.fullmatch(parts[1]) or any(p in ('.', '..') for p in parts):
        raise ValueError('Unsafe archive path')
    # PurePosixPath normalizes some invalid paths; verify original exactly.
    if PurePosixPath(name).as_posix() != name or '//' in name:
        raise ValueError('Unsafe archive path')
    return parts


def backup(sources, output):
    """Back up named existing *directories*; never follow symlinks."""
    output = Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'Backup already exists: {output}')
    records = []
    for slot, source in sorted(sources.items()):
        if not SLOT.fullmatch(slot):
            raise ValueError('Invalid local-state slot')
        source = Path(source)
        if source.is_symlink():
            raise ValueError('Refusing symlink state directory')
        if not source.exists():
            continue
        if not source.is_dir():
            raise ValueError('Local-state source must be a directory')
        for directory, dirs, files in os.walk(source, followlinks=False):
            for name in dirs + files:
                if (Path(directory) / name).is_symlink():
                    raise ValueError('Refusing symlink in local state')
            for name in sorted(files):
                file = Path(directory) / name
                if not file.is_file():
                    raise ValueError('Not a regular state file')
                rel = file.relative_to(source)
                item = 'state/' + slot + '/' + rel.as_posix()
                _safe_name(item)
                with file.open('rb') as handle:
                    digest, size = _digest(handle)
                records.append((item, file, digest, size))
    if not records:
        raise ValueError('No existing local-state files to back up')
    if sum(item[3] for item in records) > MAX_UNCOMPRESSED:
        raise ValueError('Local state exceeds backup safety limit')
    if any(file.resolve() == output for _, file, _, _ in records):
        raise ValueError('Backup cannot overwrite source data')
    manifest = {'schema': SCHEMA, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'files': [{'path': name, 'sha256': sha, 'size': size} for name, _, sha, size in records]}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for name, file, _, _ in records:
                    archive.write(file, name)
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        verify(output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {'archive': str(output), 'files': len(records), 'bytes': sum(x[3] for x in records)}


def verify(archive_path):
    with zipfile.ZipFile(archive_path, 'r') as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('Missing manifest or duplicate archive files')
        for info in archive.infolist():
            if info.filename != 'manifest.json':
                _safe_name(info.filename)
            if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError('Archive contains link or directory entry')
        if archive.getinfo('manifest.json').file_size > 1024 * 1024:
            raise ValueError('Manifest is too large')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('files'), list):
            raise ValueError('Unsupported backup manifest schema')
        expected = {item['path']: item for item in manifest['files']}
        if set(names) != set(expected) | {'manifest.json'} or len(expected) != len(manifest['files']):
            raise ValueError('Manifest entries do not match archive entries')
        total = 0
        for name, entry in expected.items():
            _safe_name(name)
            info = archive.getinfo(name)
            total += info.file_size
            if total > MAX_UNCOMPRESSED or info.file_size != entry['size']:
                raise ValueError('Backup checksum metadata size mismatch or unsafe total')
            with archive.open(name) as stream:
                digest, size = _digest(stream)
            if digest != entry['sha256'] or size != entry['size']:
                raise ValueError('SHA-256 checksum mismatch for ' + name)
        return {'valid': True, 'files': len(expected), 'bytes': total, 'created_utc': manifest.get('created_utc')}


def restore(archive_path, destination):
    """Restore only into a NEW directory; use rename for atomic visibility."""
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'Restore destination must not exist: {destination}')
    result = verify(archive_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.repolens-restore-', dir=destination.parent))
    try:
        with zipfile.ZipFile(archive_path, 'r') as archive:
            for name in archive.namelist():
                if name == 'manifest.json':
                    continue
                _safe_name(name)
                target = stage.joinpath(*PurePosixPath(name).parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(name) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                target.chmod(0o600)
        stage.rename(destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {'destination': str(destination), **result}


def local_sources(root=ROOT, environ=None):
    env = os.environ if environ is None else environ
    root = Path(root)
    def location(key, default):
        p = Path(env.get(key) or default).expanduser()
        return p if p.is_absolute() else root / p
    sources = {
        'auth': location('REPOLENS_AUTH_DIR', root / '.repolens_auth'),
        'chroma': location('REPOLENS_CHROMA_PATH', root / '.repolens_chroma'),
        'embedding-cache': location('REPOLENS_EMBED_CACHE_DIR', root / '.repolens_cache'),
        'reports': location('REPOLENS_REPORT_DIR', root / 'reports'),
        'gallery-review': root / '.repolens_gallery',
    }
    if env.get('REPOLENS_INDEX_JOBS_DB'):
        p = location('REPOLENS_INDEX_JOBS_DB', '')
        if p.parent != sources['auth']:
            sources['jobs'] = p.parent
    return sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument('--backup', type=Path, metavar='NEW_ZIP')
    command.add_argument('--verify', type=Path, metavar='ZIP')
    command.add_argument('--restore', type=Path, metavar='ZIP')
    parser.add_argument('--destination', type=Path, help='NEW empty output directory for --restore')
    args = parser.parse_args(argv)
    if args.restore and not args.destination:
        parser.error('--restore requires --destination')
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    if args.backup:
        result = backup(local_sources(), args.backup)
    elif args.verify:
        result = verify(args.verify)
    else:
        result = restore(args.restore, args.destination)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
