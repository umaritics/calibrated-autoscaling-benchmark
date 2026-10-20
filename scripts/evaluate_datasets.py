#!/usr/bin/env python3
"""Full D1 rolling-origin forecast evaluation and D2 trace audit; no cluster needed."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['persistence', 'moving_average_6', 'hw_period_6', 'hw_train_selected', 'gbdt']
PERIODS = [6, 12, 24, 48, 96]


def errors(y, p):
    e = np.abs(y-p)
    nonzero = y != 0
    return dict(mae=float(e.mean()), rmse=float(np.sqrt(np.mean((y-p)**2))),
                mape_nonzero=float(100*np.mean(e[nonzero]/np.abs(y[nonzero]))) if nonzero.any() else np.nan,
                wape=float(100*e.sum()/np.abs(y).sum()) if np.abs(y).sum() else np.nan,
                zero_targets=int((~nonzero).sum()))


def hw_forecasts(y, period, horizon):
    """At origin t, predict y[t+h-1] BEFORE consuming y[t]."""
    out = np.full(len(y), np.nan)
    level = float(np.mean(y[:period]))
    trend = float((np.mean(y[period:2*period])-level)/period)
    season = y[:period].astype(float)-level
    # Initialization sees two seasons; forecasts start only after these seasons.
    for t in range(period, len(y)):
        if t >= 2*period:
            out[t] = max(0., level+horizon*trend+season[(t+horizon-1) % period])
        old = level
        level = .9*(y[t]-season[t % period])+.1*(level+trend)
        trend = .2*(level-old)+.8*trend
        season[t % period] = .3*(y[t]-level)+.7*season[t % period]
    return out


def lag_features(y, origins):
    return np.column_stack([y[origins-k] for k in range(1, 25)])


def evaluate(train, test, horizon):
    y = np.r_[train, test]
    n = len(train)
    # Forecast origins start after all training observations are available.
    origins = np.arange(n, len(y)-horizon+1)
    val_start = int(n*.8)
    val_origins = np.arange(val_start, n-horizon+1)
    validation_y = y[val_origins+horizon-1]
    all_hw = {m: hw_forecasts(y, m, horizon) for m in PERIODS}
    best_period = min(PERIODS, key=lambda m: np.mean(np.abs(validation_y-all_hw[m][val_origins])))
    preds = {'persistence': y[origins-1],
             'moving_average_6': np.mean(np.column_stack([y[origins-k] for k in range(1, 7)]), axis=1),
             'hw_period_6': all_hw[6][origins], 'hw_train_selected': all_hw[best_period][origins]}
    # Fit direct h-step targets from training only; no test refitting.
    fit_origins = np.arange(24, n-horizon+1)
    model = HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=15,
                                         learning_rate=.1, early_stopping=False, random_state=0)
    model.fit(lag_features(y, fit_origins), y[fit_origins+horizon-1])
    preds['gbdt'] = np.maximum(0., model.predict(lag_features(y, origins)))
    return preds, best_period


def table(df):
    # Keep report generation free of optional tabulate dependency.
    return '| ' + ' | '.join(map(str, df.columns)) + ' |\n|' + '|'.join(['---']*len(df.columns)) + '|\n' + '\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in df.itertuples(index=False, name=None))


def online(data, out):
    records, early = [], []
    manifest = []
    for path in sorted(data.glob('workloads-predictional-scaling-patterns/**/*.csv')):
        manifest.append(dict(path=str(path.relative_to(data)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size, rows=len(pd.read_csv(path))))
    pd.DataFrame(manifest).to_csv(out/'online_manifest.csv', index=False)
    for path in sorted(data.glob('workloads-predictional-scaling-patterns/**/patterns/*/*.csv')):
        df = pd.read_csv(path)
        t = df.elapsed_seconds.to_numpy(float)
        assert np.isfinite(t).all() and np.all(np.diff(t)>0), path
        r = df.ready_replicas.to_numpy(float)
        def first_increase(column):
            ix = np.flatnonzero(np.diff(df[column].to_numpy(float))>0)+1
            return float(t[ix[0]]) if len(ix) else np.nan
        records.append(dict(pattern=path.parent.name, model=path.stem, rows=len(df),
                            duration_s=t[-1]-t[0], pod_seconds=np.trapezoid(r,t),
                            time_mean_ready=np.trapezoid(r,t)/(t[-1]-t[0]),
                            hot_fraction=float((df.cpu_millicores_avg>160).mean()),
                            ready_gt_current_rows=int((df.ready_replicas>df.current_replicas).sum()),
                            first_desired_increase_s=first_increase('desired_replicas'),
                            first_ready_increase_s=first_increase('ready_replicas')))
    df = pd.DataFrame(records)
    assert len(df)==42
    df.to_csv(out/'online_trace_metrics.csv', index=False)
    for path in sorted(data.glob('**/early_detection_summary.csv')):
        pattern = path.parent.parent.name
        base = df[(df.pattern==pattern)&(df.model=='baseline_hpa')].iloc[0]
        for row in pd.read_csv(path).itertuples():
            model = df[(df.pattern==pattern)&(df.model=='phpa_'+row.model)].iloc[0]
            computed = base.first_desired_increase_s-model.first_desired_increase_s
            early.append(dict(pattern=pattern, model=row.model, released_early_s=row.early_detection_time_seconds,
                              first_desired_advantage_s=computed, difference_s=computed-row.early_detection_time_seconds,
                              first_ready_advantage_s=base.first_ready_increase_s-model.first_ready_increase_s))
    ed = pd.DataFrame(early)
    assert len(ed)==36
    ed.to_csv(out/'online_early_detection_audit.csv', index=False)
    hw = ed[ed.model=='holtwinters'].drop(columns='model').round(3)
    text = '# Authors’ online traces: independent audit\n\n'
    text += 'These are the authors’ released runs, not new cluster experiments. All 42 traces and 36 early-detection entries are included. No tuned-HPA trace or repeated trials exists in this release. The separate `online_summary.csv` describes static-load scenarios and is inventoried but not pooled with pattern runs.\n\n'
    text += '## Holt–Winters timing comparison\n\n'+table(hw)+'\n\n'
    text += f'Across all 36 entries, {int(np.isclose(ed.difference_s, 0, atol=1e-9).sum())} match our first-desired-increase calculation within 1e-9 seconds. This verifies arithmetic on released traces, not an independent live replication.\n\n'
    text += 'Released early detection is copied from the supplied summary. Our alternative definition is the HPA time of the first observed increase in desired replicas minus the PHPA time of its first increase. Ready-replica timing is shown separately. Initial nonzero replicas are not a scale-up event; events during warmup cannot be recovered. A mismatch is a definition/provenance issue, not evidence that either timing measures anticipation of a workload peak.\n\n'
    text += '## Capacity over each recorded window\n\n'+table(df[df.model.isin(['baseline_hpa','phpa_holtwinters'])][['pattern','model','rows','duration_s','pod_seconds','time_mean_ready','hot_fraction','ready_gt_current_rows']].round(3))+'\n\n'
    text += f'Data-quality flag: {int(df.ready_gt_current_rows.sum())} rows report ready replicas greater than current replicas. These fields may reflect asynchronous status sources; the integral uses the released ready column without correction. Hot fraction uses the same 160 m threshold as our existing study, not a latency measure. Durations differ: compare time-mean ready replicas alongside raw pod-seconds. Single runs do not support uncertainty estimates or causal controller rankings. All models are in `online_trace_metrics.csv`.\n'
    (out/'online_results.md').write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT/'data')
    parser.add_argument('--out', type=Path, default=ROOT/'results/dataset_phase')
    args = parser.parse_args(); out=args.out; out.mkdir(parents=True,exist_ok=True)
    files = sorted(args.data.glob('phpa/**/*_train.csv'))
    assert len(files)==600, f'Expected 600 complete scenarios, found {len(files)}'
    assert len(list(args.data.glob('phpa/**/*_test.csv')))==600
    manifest=[]; records=[]
    for index, path in enumerate(files):
        test_path=path.with_name(path.name.replace('_train.csv','_test.csv'))
        train=pd.read_csv(path); test=pd.read_csv(test_path)
        combined=pd.concat([train,test],ignore_index=True)
        dt=pd.to_datetime(combined.timestamp)
        assert (dt.diff().dropna()==pd.Timedelta(minutes=15)).all(), path
        y=combined.pod_count.to_numpy(float)
        assert np.isfinite(y).all() and (y>=0).all(), path
        for p, frame in [(path,train),(test_path,test)]:
            manifest.append(dict(path=str(p.relative_to(args.data)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                 bytes=p.stat().st_size,rows=len(frame),zero_count=int((frame.pod_count==0).sum())))
        for h in [1,4]:
            preds, period=evaluate(train.pod_count.to_numpy(float),test.pod_count.to_numpy(float),h)
            for name, pred in preds.items():
                assert len(pred)==len(test)-h+1 and np.isfinite(pred).all()
                records.append(dict(scenario=path.stem.removesuffix('_train'),pattern=path.name.split('_')[0],
                                    horizon_steps=h,model=name,test_rows=len(test)-h+1,selected_period=period if name=='hw_train_selected' else 6 if name=='hw_period_6' else 0,
                                    **errors(test.pod_count.to_numpy(float)[h-1:],pred)))
        if (index+1)%50==0: print(f'Evaluated {index+1}/600 scenarios',flush=True)
    df=pd.DataFrame(records); df.to_csv(out/'offline_per_scenario.csv',index=False)
    pd.DataFrame(manifest).to_csv(out/'dataset_manifest.csv',index=False)
    summary=df.groupby(['pattern','horizon_steps','model']).agg(scenarios=('mae','size'),mae=('mae','mean'),mae_sd=('mae','std'),rmse=('rmse','mean'),mape_nonzero=('mape_nonzero','mean'),wape=('wape','mean')).reset_index()
    summary.to_csv(out/'offline_summary.csv',index=False)
    pairs=[]
    for (pattern,h), group in df.groupby(['pattern','horizon_steps']):
        pivot=group.pivot(index='scenario',columns='model',values='mae')
        for m in MODELS[1:]:
            delta=pivot[m]-pivot.persistence
            pairs.append(dict(pattern=pattern,horizon_steps=h,model=m,mae_delta_mean=delta.mean(),mae_delta_sd=delta.std(),wins=int((delta<0).sum()),ties=int((delta==0).sum()),n=len(delta)))
    pd.DataFrame(pairs).to_csv(out/'offline_paired_vs_persistence.csv',index=False)
    report='# Offline forecast results: all 600 supplied scenarios\n\n'
    report+='All 1,200 CSVs pass finite/nonnegative target, chronological split, and exact 15-minute continuity checks. Each scenario has 2,688 train and 672 test observations: 2,016,000 total, 403,200 held-out targets per model at horizon 1 and 401,400 at horizon 4. No sampling or exclusions.\n\n'
    report+='Rolling-origin evaluation: 1 step = 15 minutes; 4 steps = 60 minutes. Origins begin after the full training window; at horizon 4 the first target is test[3]. Only observations available before the forecast origin are used. Earlier test observations become available as time advances. GBDT is trained once on training labels only. This is not a fixed-origin 672-step forecast, nor a Kubernetes controller simulation.\n\n'
    report+='MAE and RMSE are in pods. Tables macro-average per-scenario errors (100 scenarios per pattern). SD is across scenarios, not repeated experiments. MAPE excludes zero targets explicitly; MAE includes them. WAPE is 100 × total absolute error / total absolute target per scenario.\n\n'
    for h in [1,4]:
        report+=f'## Horizon {h} steps\n\n'+table(summary[summary.horizon_steps==h].drop(columns='horizon_steps').round(4))+'\n\n'
    report+='## Paired comparisons against persistence\n\nNegative MAE delta favors the model; wins count strict improvements over the same scenario. These descriptive comparisons do not treat time points as independent replicates.\n\n'+table(pd.DataFrame(pairs).round(4))+'\n\n'
    report+='Models: persistence; mean of six preceding samples; additive Holt–Winters (alpha .9, beta .2, gamma .3), fixed period 6 or period selected from 6/12/24/48/96 using final 20% of training MAE separately per horizon; histogram GBDT with 24 lag features, 60 iterations, 15 leaves, learning rate .1, seed 0, no early stopping. Predictions are clipped at zero. HW initialization uses the first two training seasons. No filename-derived period or pattern label enters model fitting. These implementations and horizons differ from the paper; no direct reproduction of its +37.4% claim is asserted.\n'
    (out/'offline_results.md').write_text(report)
    online(args.data,out)
    metadata=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,horizons=[1,4],seed=0,scenarios=len(files),total_rows=sum(m['rows'] for m in manifest),source_archive_sha256=hashlib.sha256((ROOT/'data.zip').read_bytes()).hexdigest() if (ROOT/'data.zip').exists() else None)
    (out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
