#!/usr/bin/env python3
"""Sequential, balanced controller order; all failures remain in the ledger."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ARMS=['strawman_hpa','holtwinters','calibrated_hpa']
def main():
    out=ROOT/'results/live_trace_phase';plan=[]
    for repeat in range(1,4):
        for dataset in (['nasa','alibaba'] if repeat%2 else ['alibaba','nasa']):
            order=ARMS[repeat-1:]+ARMS[:repeat-1]
            for arm in order:plan.append(dict(dataset=dataset,arm=arm,repeat=repeat,warmup=120,duration=420,category='runs'))
    for arm in ARMS:plan.append(dict(dataset='phpa_seasonal',arm=arm,repeat=1,warmup=120,duration=180,category='exploratory'))
    planpath=out/'run_plan.json'
    if planpath.exists():assert json.loads(planpath.read_text())==plan
    else:planpath.write_text(json.dumps(plan,indent=2)+'\n')
    for i,run in enumerate(plan):
        path=out/run['category']/run['dataset']/f"repeat{run['repeat']}"/run['arm']
        if (path/'COMPLETE').exists():continue
        if path.exists():raise RuntimeError(f'Unfinished existing run requires review: {path}')
        print(f"START {i+1}/{len(plan)} {run}",flush=True)
        cmd=[sys.executable,str(ROOT/'scripts/live/run_trace.py')]
        for key,value in run.items():cmd += ['--'+key,str(value)]
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        with (out/'execution_ledger.jsonl').open('a') as f:f.write(json.dumps(dict(run=run,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,finished_utc=datetime.now(timezone.utc).isoformat()))+'\n')
        if p.returncode:print('FAILED',p.stderr,flush=True);continue
        q=subprocess.run([sys.executable,str(ROOT/'scripts/live/analyze_runs.py')],cwd=ROOT,capture_output=True,text=True)
        print('FINISHED',i+1,p.stdout.strip(),q.stdout[-1500:],q.stderr,flush=True)
        if q.returncode:raise RuntimeError('Analysis failed; inspect before proceeding')
if __name__=='__main__':main()
