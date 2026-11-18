"""Run freshness checks independently of the web server. Schedule --once every 5 min."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from backend.database.product_store import configured_engine
from backend.services.freshness import run_due
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--once',action='store_true');args=p.parse_args()
    db=configured_engine()
    while True:
        result=run_due(db);print(json.dumps({'time':int(time.time()),**result}),flush=True)
        if args.once:break
        time.sleep(300)
