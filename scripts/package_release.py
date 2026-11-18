"""Create a source release without local credentials, account data or dependencies."""
import argparse,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','venv','node_modules','__MACOSX','__pycache__','.pytest_cache','.ruff_cache','.mypy_cache','test-results','playwright-report','output','upload','uploads','data','backup','backups','private','storage','.repolens_auth','.repolens_chroma','.repolens_cache','.repolens_gallery','checkpoints','.github-secrets'}
PRIVATE_SUFFIXES={'.pyc','.pyo','.db','.sqlite','.sqlite3','.key','.pem','.log','.zip','.p12','.pfx','.bak','.sql','.seed','.crt'}

def included(relative):
    p=Path(relative)
    if p.parts[0]=='reports':return False
    # Cached live evidence and model snapshots may contain source/user content.
    if p.parts[0]=='evaluation' and ('checkpoints' in p.parts or p.name=='query-embeddings.json.gz'):return False
    if any(part in EXCLUDED or part.startswith(('.repolens','._')) for part in p.parts):return False
    if p.name in {'.DS_Store','dashboard-reference.png','.npmrc','.pypirc','.netrc','credentials.json','service-account.json','secret.json','secrets.json','token.json'}:return False
    if p.name.lower().endswith(('.sql.gz','.db.gz','.sqlite.gz','.sqlite3.gz','.backup.zip')):return False
    if p.name.startswith('.env') and p.name!='.env.example':return False
    return p.suffix.lower() not in PRIVATE_SUFFIXES

def package(root,destination):
    root=Path(root).resolve();destination=Path(destination).resolve()
    if destination.is_relative_to(root):raise ValueError('Write the release outside the source folder')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            relative=path.relative_to(root)
            if path.is_symlink() or not path.is_file() or not included(relative):continue
            # Prevent copying content through a symlinked parent.
            if any((root/parent).is_symlink() for parent in relative.parents):continue
            archive.write(path,Path('RepoLens')/relative)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:raise ValueError('Archive validation failed')
        return len(archive.namelist())

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    count=package(ROOT,args.output)
    print(f'Created {count} source/assets files: {args.output.resolve()}')

if __name__=='__main__':main()
