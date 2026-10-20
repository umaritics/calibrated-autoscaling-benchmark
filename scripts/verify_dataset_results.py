#!/usr/bin/env python3
"""Verify committed dataset outputs against raw inputs and independent arithmetic."""
import csv
import hashlib
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/dataset_phase'

def main():
    for name in ['dataset_manifest.csv','online_manifest.csv']:
        for row in csv.DictReader((OUT/name).open()):
            path=ROOT/'data'/row['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],path
            with path.open() as f: assert sum(1 for _ in csv.DictReader(f))==int(row['rows']),path
    per=pd.read_csv(OUT/'offline_per_scenario.csv')
    assert len(per)==6000 and per.scenario.nunique()==600
    assert not per.duplicated(['scenario','horizon_steps','model']).any()
    assert (per.loc[per.horizon_steps==1,'test_rows']==672).all()
    assert (per.loc[per.horizon_steps==4,'test_rows']==669).all()
    for row in pd.read_csv(OUT/'offline_summary.csv').itertuples():
        g=per[(per.pattern==row.pattern)&(per.horizon_steps==row.horizon_steps)&(per.model==row.model)]
        assert len(g)==100
        for name in ['mae','rmse','mape_nonzero','wape']:
            assert math.isclose(g[name].mean(),getattr(row,name),rel_tol=1e-12)
    # Independent persistence calculation from raw values, every scenario/horizon.
    for row in per[per.model=='persistence'].itertuples():
        train_path=next((ROOT/'data/phpa').rglob(row.scenario+'_train.csv'))
        test_path=train_path.with_name(row.scenario+'_test.csv')
        with train_path.open() as f: train=[float(r['pod_count']) for r in csv.DictReader(f)]
        with test_path.open() as f: test=[float(r['pod_count']) for r in csv.DictReader(f)]
        h=row.horizon_steps
        actual=test[h-1:]; predicted=([train[-1]]+test)[:len(actual)]
        mae=sum(abs(a-b) for a,b in zip(actual,predicted))/len(actual)
        assert math.isclose(mae,row.mae,rel_tol=1e-12),row.scenario
    for row in pd.read_csv(OUT/'online_trace_metrics.csv').itertuples():
        path=next((ROOT/'data').glob(f'**/patterns/{row.pattern}/{row.model}.csv'))
        with path.open() as f: raw=list(csv.DictReader(f))
        integral=sum((float(b['elapsed_seconds'])-float(a['elapsed_seconds']))*(float(a['ready_replicas'])+float(b['ready_replicas']))/2 for a,b in zip(raw,raw[1:]))
        assert math.isclose(integral,row.pod_seconds,rel_tol=1e-12)
    early=pd.read_csv(OUT/'online_early_detection_audit.csv')
    assert len(early)==36 and np.allclose(early.difference_s,0,atol=1e-9)
    print('Verified manifests, 6,000 model results, all aggregate metrics, 1,200 independent persistence errors, 42 integrals, and 36 timing matches.')

if __name__=='__main__': main()
