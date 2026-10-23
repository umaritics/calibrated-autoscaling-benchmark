#!/usr/bin/env python3
"""Independently verify and report the first three-arm NASA comparison."""
import csv,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/live_trace_phase/first_comparison'
RUN_ROOT=OUT/'nasa/repeat1'
ARMS=['strawman_hpa','calibrated_hpa','holtwinters']
POLICIES={'strawman_hpa':'hpa-baseline.yaml','calibrated_hpa':'hpa-calibrated.yaml','holtwinters':'phpa-holtwinters.yaml'}
KINDS={'strawman_hpa':'HorizontalPodAutoscaler','calibrated_hpa':'HorizontalPodAutoscaler','holtwinters':'PredictiveHorizontalPodAutoscaler'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def independently_compute(run):
    meta=json.loads((run/'metadata.json').read_text())
    trace=pd.read_csv(run/'trace.csv')
    expected=4*int(meta['warmup'])
    for i,row in trace.iterrows():
        offset=i*10
        if offset>=meta['duration']: break
        expected += round(float(row.target_rps)*min(10,meta['duration']-offset))
    req=pd.read_csv(run/'requests.csv',keep_default_na=False)
    measured=req[req.phase=='measurement'].copy()
    measured['status']=pd.to_numeric(measured.status,errors='coerce').fillna(0).astype(int)
    measured['latency_s']=pd.to_numeric(measured.latency_s,errors='coerce')
    success=measured[(measured.status==200)&(measured.error=='')]
    records=[]
    for line in (run/'metrics.jsonl').read_text().splitlines():
        obj=json.loads(line); items=obj.get('objects',{}).get('items',[])
        dep=next((x for x in items if x.get('kind')=='Deployment'),None)
        if dep is None: continue
        controllers=[x.get('kind') for x in items if x.get('kind') in set(KINDS.values())]
        records.append((float(obj['elapsed_seconds']),float(dep.get('status',{}).get('readyReplicas',0)),controllers))
    start=float(meta['warmup']);end=start+float(meta['duration'])
    times=np.array([x[0] for x in records]);ready=np.array([x[1] for x in records])
    points=np.unique(np.r_[start,times[(times>=start)&(times<=end)],end])
    pod_seconds=float(np.trapezoid(np.interp(points,times,ready),points))
    kinds=[kind for t,_,cs in records if start<=t<=end for kind in cs]
    controller_exclusive=all(len(cs)==1 and cs[0]==KINDS[meta['arm']] for t,_,cs in records if start<=t<=end)
    return dict(total_records=len(req),measurement_records=len(measured),expected_total=expected,
        successful_requests=len(success),error_rate=(len(measured)-len(success))/len(measured),
        p50_latency_s=float(success.latency_s.quantile(.50)),p95_latency_s=float(success.latency_s.quantile(.95)),
        p99_latency_s=float(success.latency_s.quantile(.99)),pod_seconds=pod_seconds,
        controller_kind=KINDS[meta['arm']] if controller_exclusive else None,
        controller_exclusive=controller_exclusive,measurement_duration_s=end-start)

def close(a,b,tol=1e-8): return a is not None and b is not None and abs(float(a)-float(b))<=tol

def main():
    summaries={};independent={};verification={};rows=[]
    for arm in ARMS:
        run=RUN_ROOT/arm; summary=json.loads((run/'summary.json').read_text()); check=independently_compute(run)
        summaries[arm]=summary;independent[arm]=check
        verification[arm]={
            'request_counts_agree': check['total_records']==summary['request_records'] and check['measurement_records']==summary['measurement_request_records'] and check['expected_total']==summary['scheduled_requests'],
            'error_rate_agrees': close(check['error_rate'],summary['error_rate']),
            'latency_population_agrees': check['successful_requests']==summary['successful_requests'] and all(close(check[k],summary[k]) for k in ('p50_latency_s','p95_latency_s','p99_latency_s')),
            'pod_seconds_agree': close(check['pod_seconds'],summary['pod_seconds'],1e-6),
            'controller_identity_agrees': check['controller_exclusive'] and check['controller_kind']==summary['active_controller'],
            'measurement_duration_agrees': close(check['measurement_duration_s'],summary['intended_replay_duration_s']),
        }
        if not all(verification[arm].values()): raise RuntimeError(f'independent verification failed for {arm}: {verification[arm]}')
        policy=ROOT/'policies'/POLICIES[arm]
        (run/'controller.yaml').write_bytes(policy.read_bytes())
        e=summary['events']
        rows.append(dict(arm=arm,decision=summary['decision'],scheduled_total=summary['scheduled_requests'],
            completed_total=summary['request_records'],
            scheduled_measurement=summary['scheduled_measurement_requests'],completed_measurement=summary['measurement_request_records'],
            successful_requests=summary['successful_requests'],failures=summary['recorded_failures'],error_rate=summary['error_rate'],
            timeouts=summary['timeouts'],disconnections=summary['disconnections'],p50_success_latency_s=summary['p50_latency_s'],
            p95_success_latency_s=summary['p95_latency_s'],p99_success_latency_s=summary['p99_latency_s'],
            offered_rps=summary['offered_request_rate_rps'],dispatch_span_rps=summary['actual_dispatch_rate_rps'],
            achieved_success_rps=summary['achieved_success_rps'],pod_seconds=summary['pod_seconds'],mean_ready=summary['mean_ready'],
            max_ready=summary['max_ready'],scaling_changes=summary['scaling_changes'],mean_cpu_m=summary['mean_cpu_m'],
            max_cpu_m=summary['max_cpu_m'],cpu_hot_sample_fraction=summary['cpu_hot_sample_fraction'],
            max_workload_restarts=summary['max_workload_restarts'],readiness_deficit_samples=summary['readiness_deficit_samples'],
            readiness_probe_failures=e['readiness_probe_failures'],liveness_probe_failures=e['liveness_probe_failures'],
            dispatch_p99_s=summary['p99_dispatch_delay_s'],generator_drops=summary['generator_drops'],
            sla_threshold='NOT DEFINED'))
    pd.DataFrame(rows).to_csv(OUT/'comparison.csv',index=False)
    baseline=summaries['strawman_hpa'];diff={}
    for arm in ARMS[1:]:
        s=summaries[arm];diff[arm]={}
        for key in ('error_rate','successful_requests','achieved_success_rps','pod_seconds','mean_ready','p95_latency_s','p99_latency_s'):
            a=float(s[key]);b=float(baseline[key]);diff[arm][key]={'absolute_vs_strawman':a-b,'percent_vs_strawman':(a-b)/b*100 if b else None}
    comparison={'generated_utc':datetime.now(timezone.utc).isoformat(),'scope':'preliminary single repeat per controller',
        'sla_threshold':'NOT DEFINED','arms':summaries,'differences':diff,'independent_recomputation':independent,'verification':verification}
    (OUT/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    environment={'captured_utc':datetime.now(timezone.utc).isoformat(),'cluster':'calibrated-live',
        'kubernetes_client_server':'v1.32.2','metrics_server':'v0.7.1','phpa':'v0.13.2',
        'node_allocatable_cpu':'8','node_capacity_memory':'20164312Ki','host_ram':'19 GiB',
        'preflight_host_available_memory':'6.0 GiB','preflight_filesystem_free':'6.0 GiB',
        'limitations':['single-node kind cluster','host contention is not controlled','limited free disk'],
        'resolved_images':{'application':'docker.io/library/php@sha256:06617d90f29b57b2aa200a9df03b3bafbfa5c66d2e2913fbb2b5f775a8358465',
            'phpa':'docker.io/jthomperoo/predictive-horizontal-pod-autoscaler@sha256:ef5c4555a8581f356bf0dacaa6a6c25ffdf7f26b35157e7d0c7a9d11f9f94cf5'},
        'runs':{}}
    for arm in ARMS:
        run=RUN_ROOT/arm;meta=json.loads((run/'metadata.json').read_text());metrics=pd.read_csv(run/'metrics.csv')
        environment['runs'][arm]={'started_utc':meta['started_utc'],'finished_utc':meta['finished_utc'],
            'runner_elapsed_s':meta['elapsed_seconds'],'host_load1_mean':float(metrics.host_load1.mean()),
            'host_load1_max':float(metrics.host_load1.max())}
    (OUT/'environment_metadata.json').write_text(json.dumps(environment,indent=2)+'\n')
    lines=['# First verified live NASA three-controller comparison','',
        'These are preliminary single-repeat observations from real Kubernetes execution, not statistically reliable conclusions. '
        'Every arm used the same predetermined NASA-derived schedule, application, resources, 120-second warmup, and 420-second measurement window.','',
        '## Measurements','',
        '| Arm | Success / 26,103 | Error rate | Timeout / disconnect | Success latency p50 / p95 / p99 (s) | Success rps | Pod-s | Mean / max ready | CPU mean / max (m) | Hot CPU fraction | Restarts | Dispatch p99 (ms) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    labels={'strawman_hpa':'Soft HPA (50%)','calibrated_hpa':'Tuned HPA (70%)','holtwinters':'Holt–Winters PHPA'}
    for arm in ARMS:
        s=summaries[arm]
        lines.append(f"| {labels[arm]} | {s['successful_requests']:,} | {s['error_rate']:.2%} | {s['timeouts']:,} / {s['disconnections']:,} | {s['p50_latency_s']:.3f} / {s['p95_latency_s']:.3f} / {s['p99_latency_s']:.3f} | {s['achieved_success_rps']:.2f} | {s['pod_seconds']:.2f} | {s['mean_ready']:.2f} / {s['max_ready']} | {s['mean_cpu_m']:.1f} / {s['max_cpu_m']:.1f} | {s['cpu_hot_sample_fraction']:.2%} | {s['max_workload_restarts']} | {s['p99_dispatch_delay_s']*1000:.3f} |")
    lines += ['', 'All arms scheduled and recorded 26,583 total requests: 480 warmup plus 26,103 measurement. Offered measurement load was 62.15 requests/s. Generator drops were zero. The protocol defines no SLA threshold, so SLA violations are **NOT DEFINED**. Latency percentiles include successful requests only; all failures remain in the error-rate denominator.','',
        '## Scaling and readiness','']
    for arm in ARMS:
        s=summaries[arm];events=', '.join(f"{x['from_replicas']}→{x['to_replicas']} at measurement +{x['elapsed_s']-120:.0f}s" for x in s['scaling_events'])
        lines.append(f"- {labels[arm]}: {events}; {s['readiness_deficit_samples']} readiness-deficit samples; {s['events']['readiness_probe_failures']} readiness and {s['events']['liveness_probe_failures']} liveness probe failures.")
    lines += ['', '## Preliminary differences versus soft HPA','',
        f"- Tuned HPA reduced error rate by {abs(diff['calibrated_hpa']['error_rate']['absolute_vs_strawman'])*100:.2f} percentage points and pod-seconds by {abs(diff['calibrated_hpa']['pod_seconds']['percent_vs_strawman']):.1f}%, while successful-request p95 latency was {diff['calibrated_hpa']['p95_latency_s']['percent_vs_strawman']:.1f}% higher.",
        f"- Holt–Winters reduced error rate by {abs(diff['holtwinters']['error_rate']['absolute_vs_strawman'])*100:.2f} percentage points and successful-request p95 latency by {abs(diff['holtwinters']['p95_latency_s']['percent_vs_strawman']):.1f}%, but used {diff['holtwinters']['pod_seconds']['percent_vs_strawman']:.1f}% more pod-seconds.",
        '- These capacity/QoS tradeoffs are descriptive only. With one repeat per controller, order and host effects cannot be separated from controller effects.','',
        '## Validity','',
        'All three arms were `ACCEPT` under the predeclared analyzer checks. Each had exact request accounting, no unexplained missing or duplicate rows, zero generator drops, dispatch p99 below 3 ms (threshold 100 ms), exclusive intended-controller ownership, a bracketed measurement window, five-second-scale telemetry gaps, and scaling above one replica. CPU was present in 78/84 soft-HPA samples and 84/84 samples for each other arm. Independent recomputation agreed with the analyzer for request counts, error rate, successful-latency population, pod-seconds, controller identity, and 420-second measurement duration for every arm.','',
        'The high error rates remain experimental outcomes. Probe paths and ports were functional at idle; timeouts, readiness deficits, and liveness restarts under load support service saturation/unavailability rather than generator loss. Per-request backend identity was not captured, so attribution of each individual failure remains limited.','',
        '## Evidence','',
        'Machine-readable results are in `comparison.csv` and `comparison.json`. `evidence_manifest.json` maps reported calculations to raw files and SHA-256 hashes. Exact commands are in `REPRODUCE.md`; the frozen order and preflight decision are in `run_plan.json` and `PREFLIGHT.md`.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    calc={
        'request counts, outcomes, latency, throughput, dispatch':['requests.csv','trace.csv','metadata.json'],
        'pod-seconds, replicas, CPU, restarts, controller identity':['metrics.jsonl','metadata.json'],
        'probe failures and container kills':['events.json','metadata.json'],
        'configuration identity':['controller.yaml','initial_objects.json','final_objects.json','metadata.json'],
        'predictive controller diagnostics':['operator.log'],
    }
    evidence={'generated_utc':datetime.now(timezone.utc).isoformat(),'calculations':calc,'runs':{}}
    for arm in ARMS:
        run=RUN_ROOT/arm;files={}
        for p in sorted(run.iterdir()):
            if p.is_file(): files[p.name]={'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
        evidence['runs'][arm]=files
    for name in ('run_plan.json','PREFLIGHT.md','REPRODUCE.md','comparison.csv','comparison.json','environment_metadata.json','RESULTS.md'):
        p=OUT/name;evidence.setdefault('comparison_artifacts',{})[name]={'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
    (OUT/'evidence_manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(verification,indent=2))

if __name__=='__main__': main()
