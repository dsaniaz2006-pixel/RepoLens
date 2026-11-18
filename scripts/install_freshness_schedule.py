"""Print or write a macOS LaunchAgent; launchctl loading is an explicit user step."""
import argparse,hashlib,plistlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args()
label='dev.repolens.freshness.'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]
python=ROOT/'.venv/bin/python';logs=ROOT/'.repolens_logs'
agent={'Label':label,'ProgramArguments':[str(python),str(ROOT/'scripts/freshness_worker.py'),'--once'],'WorkingDirectory':str(ROOT),'StartInterval':300,'RunAtLoad':True,'StandardOutPath':str(logs/'freshness.log'),'StandardErrorPath':str(logs/'freshness-error.log')}
if args.write:
    if sys.platform!='darwin':raise SystemExit('--write is supported on macOS; use your service scheduler elsewhere')
    if not python.exists():raise SystemExit('Create/install the project .venv first')
    target=Path.home()/'Library/LaunchAgents'/(label+'.plist');target.parent.mkdir(parents=True,exist_ok=True);logs.mkdir(exist_ok=True)
    target.write_bytes(plistlib.dumps(agent));print(target)
else:print(plistlib.dumps(agent).decode())
