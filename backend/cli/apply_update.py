"""Preview/apply source updates to an existing installation, preserving local data."""
import argparse,shutil,time
from pathlib import Path
EXCLUDED={'.env','.venv','venv','node_modules','.git','.repolens_auth','.repolens_chroma','.repolens_cache','.repolens_gallery','.repolens_logs','__pycache__','.pytest_cache','.repolens_backups','test-results','playwright-report'}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('target');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    source=Path(__file__).resolve().parents[2];target=Path(args.target).expanduser().resolve()
    if source==target or source in target.parents or target in source.parents:raise SystemExit('Source and target must be separate, non-nested project folders')
    legacy = (target/'api.py').is_file() and (target/'main.py').is_file()
    packaged = (target/'backend/api/api.py').is_file() and (target/'backend/cli/main.py').is_file()
    if not (legacy or packaged):raise SystemExit('Target does not look like an existing RepoLens project')
    files=[]
    for path in source.rglob('*'):
        rel=path.relative_to(source)
        if path.is_symlink() or not path.is_file() or any(x in EXCLUDED for x in rel.parts):continue
        if rel.parts[0]=='reports' or path.suffix in {'.pyc','.db','.sqlite3','.key'} or path.name.startswith('.env') and path.name!='.env.example':continue
        destination=target/rel
        if destination.is_symlink() or not destination.resolve().is_relative_to(target):raise SystemExit('Refusing to follow a destination symlink outside the project')
        files.append((path,rel))
    print(f'{len(files)} source/assets files will be copied to {target}')
    print('Existing credentials, environments, indexes, accounts and root reports are preserved.')
    if not args.apply:print('Preview only. Add --apply to copy files.');return
    backup=target/'.repolens_backups'/str(time.time_ns())
    for path,rel in files:
        destination=target/rel
        if destination.exists():
            old=backup/rel;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,old)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,destination)
    print('Update applied. Replaced-file backup:',backup)
if __name__=='__main__':main()
