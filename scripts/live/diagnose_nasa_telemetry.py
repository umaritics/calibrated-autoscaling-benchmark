#!/usr/bin/env python3
"""Produce a non-destructive diagnosis of the retained NASA telemetry gaps."""
import csv,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/live_trace_phase/nasa_three_repeat'
RUNS={
    'accepted_tuned_repeat1':ROOT/'results/live_trace_phase/first_comparison/nasa/repeat1/calibrated_hpa',
    'accepted_tuned_repeat2':OUT/'nasa/repeat2/calibrated_hpa',
    'inconclusive_attempt1':OUT/'nasa/repeat3/calibrated_hpa_inconclusive_attempt1',
    'inconclusive_attempt2':OUT/'nasa/repeat3/calibrated_hpa',
}
ACCEPTED={
    'soft_repeat1':ROOT/'results/live_trace_phase/first_comparison/nasa/repeat1/strawman_hpa',
    'tuned_repeat1':ROOT/'results/live_trace_phase/first_comparison/nasa/repeat1/calibrated_hpa',
    'holtwinters_repeat1':ROOT/'results/live_trace_phase/first_comparison/nasa/repeat1/holtwinters',
    **{f'{arm}_repeat{repeat}':OUT/f'nasa/repeat{repeat}/{arm}' for repeat in (2,3)
       for arm in ('strawman_hpa','calibrated_hpa','holtwinters')
       if not (repeat==3 and arm=='calibrated_hpa')},
}

def iso_origin(records):
    first=records[0]
    return datetime.fromisoformat(first['utc'])-__import__('datetime').timedelta(seconds=float(first['elapsed_seconds']))

def percentile(values,q):
    values=sorted(values)
    if not values:return None
    pos=(len(values)-1)*q;lo=math.floor(pos);hi=math.ceil(pos)
    return values[lo] if lo==hi else values[lo]+(values[hi]-values[lo])*(pos-lo)

def request_window(rows,start,end):
    chosen=[r for r in rows if r['phase']=='measurement' and start<=float(r['dispatch_s'])<end]
    successes=[r for r in chosen if int(float(r['status']))==200 and not r['error']]
    failures=[r for r in chosen if r not in successes]
    timeouts=[r for r in failures if 'timeout' in r['error'].lower() or 'timed out' in r['error'].lower()]
    connections=[r for r in failures if any(x in r['error'].lower() for x in ('disconnect','connection reset','connection refused'))]
    return {'window_elapsed_s':[start,end],'requests':len(chosen),'successes':len(successes),
            'failures':len(failures),'timeouts':len(timeouts),'connection_failures':len(connections),
            'successful_latency_p95_s':percentile([float(r['latency_s']) for r in successes],.95)}

def conditions(hpa):
    return [{'type':c.get('type'),'status':c.get('status'),'reason':c.get('reason'),'message':c.get('message')}
            for c in hpa.get('status',{}).get('conditions',[])]

def inspect_run(label,path):
    meta=json.loads((path/'metadata.json').read_text());summary=json.loads((path/'summary.json').read_text())
    records=[json.loads(line) for line in (path/'metrics.jsonl').read_text().splitlines()]
    start=float(meta['warmup']);end=start+float(meta['duration'])
    window=[r for r in records if start<=float(r['elapsed_seconds'])<=end]
    with (path/'requests.csv').open() as stream:requests=list(csv.DictReader(stream))
    missing=[];states=[];replica_changes=[];readiness_transitions=[];restart_changes=[]
    previous_desired=None;previous_ready=None;previous_restarts=None
    for record in window:
        elapsed=float(record['elapsed_seconds']);items=record.get('objects',{}).get('items',[])
        deployment=next((x for x in items if x.get('kind')=='Deployment'),{})
        hpa=next((x for x in items if x.get('kind')=='HorizontalPodAutoscaler'),{})
        pods=[x for x in items if x.get('kind')=='Pod']
        desired=int(deployment.get('spec',{}).get('replicas',0));current=int(deployment.get('status',{}).get('replicas',0));ready=int(deployment.get('status',{}).get('readyReplicas',0))
        restarts=sum(int(c.get('restartCount',0)) for p in pods for c in p.get('status',{}).get('containerStatuses',[]))
        metric_items=record.get('pod_metrics',{}).get('items')
        state='available' if metric_items else ('empty_response' if metric_items==[] else 'collector_error')
        sample={'elapsed_s':elapsed,'utc':record.get('utc'),'metric_availability':state,
                'metric_pods':len(metric_items) if isinstance(metric_items,list) else None,
                'desired_replicas':desired,'current_replicas':current,'ready_replicas':ready,
                'container_restarts':restarts,'hpa_conditions':conditions(hpa),
                'collection_seconds':record.get('collection_seconds')}
        states.append(sample)
        if desired!=previous_desired and previous_desired is not None:
            replica_changes.append({'elapsed_s':elapsed,'utc':record.get('utc'),'from':previous_desired,'to':desired})
        if ready!=previous_ready and previous_ready is not None:
            readiness_transitions.append({'elapsed_s':elapsed,'utc':record.get('utc'),'from':previous_ready,'to':ready,
                                          'current_replicas':current,'desired_replicas':desired})
        if restarts!=previous_restarts and previous_restarts is not None:
            restart_changes.append({'elapsed_s':elapsed,'utc':record.get('utc'),'from':previous_restarts,'to':restarts})
        if state!='available':
            sample['request_behavior']=request_window(requests,elapsed-2.5,elapsed+2.5)
            sample['collector_evidence']={'response_kind':record.get('pod_metrics',{}).get('kind'),
                'api_version':record.get('pod_metrics',{}).get('apiVersion'),
                'explicit_error':record.get('pod_metrics',{}).get('error'),
                'command_metadata_retained':bool(record.get('collection_diagnostics',{}).get('pod_metrics'))}
            missing.append(sample)
        previous_desired,previous_ready,previous_restarts=desired,ready,restarts
    # Events are namespace snapshots; retain only events whose last timestamp falls inside this run.
    origin=iso_origin(records);lo=origin+__import__('datetime').timedelta(seconds=start);hi=origin+__import__('datetime').timedelta(seconds=end)
    relevant=[]
    for event in json.loads((path/'events.json').read_text()).get('items',[]):
        stamp=event.get('lastTimestamp') or event.get('eventTime') or event.get('deprecatedLastTimestamp')
        if not stamp:continue
        when=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        text=str(event.get('note') or event.get('message') or '')
        if lo<=when<=hi and any(token in (event.get('reason','')+' '+text).lower() for token in ('metric','probe','unhealthy','killing','rescale')):
            relevant.append({'utc':stamp,'reason':event.get('reason'),'count':int(event.get('deprecatedCount') or event.get('count') or 1),'message':text})
    return {'label':label,'decision':summary['decision'],'source_directory':str(path.relative_to(ROOT)),
            'sources':{name:str((path/name).relative_to(ROOT)) for name in ('metadata.json','metrics.jsonl','requests.csv','events.json','summary.json')},
            'summary':{key:summary.get(key) for key in ('scheduled_measurement_requests','successful_requests','timeouts','connection_failures','error_rate','p95_latency_s','pod_seconds','mean_ready','max_ready','sample_count','cpu_sample_count','max_workload_restarts','readiness_deficit_samples')},
            'cpu_coverage':summary['cpu_sample_count']/summary['sample_count'],
            'missing_samples':missing,'replica_changes':replica_changes,
            'readiness_transitions':readiness_transitions,'restart_changes':restart_changes,
            'relevant_events':relevant,
            'hpa_metric_failure_snapshots':sum(any(c.get('type')=='ScalingActive' and c.get('status')=='False' and c.get('reason')=='FailedGetResourceMetric' for c in s['hpa_conditions']) for s in states)}

def bursts(samples):
    groups=[]
    for sample in samples:
        if not groups or sample['elapsed_s']-groups[-1][-1]['elapsed_s']>7.5:groups.append([])
        groups[-1].append(sample)
    return [{'start_elapsed_s':g[0]['elapsed_s'],'end_elapsed_s':g[-1]['elapsed_s'],
             'start_utc':g[0]['utc'],'end_utc':g[-1]['utc'],'samples':len(g)} for g in groups]

def main():
    diagnosed={label:inspect_run(label,path) for label,path in RUNS.items()}
    accepted={label:inspect_run(label,path) for label,path in ACCEPTED.items()}
    for run in diagnosed.values():run['missing_bursts']=bursts(run['missing_samples'])
    for run in accepted.values():run['missing_bursts']=bursts(run['missing_samples'])
    result={'generated_utc':datetime.now(timezone.utc).isoformat(),
      'classification':{'root_cause':'B','confidence':'demonstrated for observed empty API responses; ultimate metrics-server internals not captured',
        'finding':'Genuine CPU metrics API unavailability experienced by both the collector and HPA; no observed collector command failure caused the 18 missing samples.',
        'instrumentation_limitation':'Legacy records omit kubectl return code/stderr/duration, but each missing payload is a parsed PodMetricsList with items=[] and no error; HPA status independently records metric retrieval failures.'},
      'frozen_acceptance':{'minimum_cpu_coverage':0.9,'attempt_decisions_unchanged':True,
        'establishment_evidence':{'where':'scripts/live/analyze_runs.py uses cpu samples >= 0.9 * measurement samples (the check name says above, but equality passes)',
          'protocol_context':'docs/LIVE_TRACE_PROTOCOL.md requires CPU metric availability verification; scripts/live/verify_first_comparison.py calls the analyzer checks predeclared',
          'timestamp_bound':'execution_ledger.jsonl records the threshold failure at 2026-10-23T15:08:28.262484+00:00, before the unchanged retry began at 2026-10-23T15:08:58.132338+00:00',
          'limitation':'The scientific worktree is untracked, so the exact initial creation time is not cryptographically established by Git history.'},
        'cpu_dependent_measures':['mean_cpu_m','max_cpu_m','cpu_hot_sample_fraction','mean_metric_pod_coverage'],
        'independently_verifiable_measures':['request accounting','error rate','successes','timeouts','successful-request latency','ready pod-seconds','replica observations','controller identity']},
      'runs':diagnosed,'accepted_run_comparison':accepted,
      'selection_bias_risk':{'present':True,'reason':'Metric loss co-occurs with readiness loss, restarts, HPA metric failures, and high request-failure periods; excluding solely on coverage can preferentially remove unstable executions. Coincidence supports risk, not sole causation.'},
      'provenance':{'protocol':'docs/LIVE_TRACE_PROTOCOL.md','collector':'scripts/live/run_trace.py','analyzer':'scripts/live/analyze_runs.py','existing_verification':str((OUT/'independent_verification.json').relative_to(ROOT))}}
    destination=OUT/'telemetry_diagnosis.json';destination.write_text(json.dumps(result,indent=2)+'\n')
    attempts=[diagnosed['inconclusive_attempt1'],diagnosed['inconclusive_attempt2']]
    lines=['# NASA CPU telemetry diagnosis and sensitivity analysis','',
      '**Root-cause decision: B — demonstrated genuine metrics unavailability, with a reporting weakness that did not create the gaps.**','',
      'Every missing collector sample is a successful, parsed `PodMetricsList` response with `items: []` and no API error field. During the affected periods, saved HPA status/events repeatedly report `FailedGetResourceMetric`, including “no metrics returned from resource metrics API” and “did not receive metrics for targeted pods”; three attempt-2 samples instead retain the HPA’s last valid metric status while the direct API response is empty. Collection stayed near 0.1 s and the five-second sampling cadence continued. This rules against a collector command failure as the cause of these observations. The old collector did not separately retain return code/stderr/duration, so it was weaker than ideal for diagnosis; its code only parsed stdout on return code zero, and the API payload plus independent HPA evidence are convergent. The artifacts do not expose metrics-server internals, so the lower-level reason it returned no pod metrics remains unknown.','',
      '## Frozen acceptance and selection risk','',
      'The 90% minimum is implemented in `scripts/live/analyze_runs.py` as `cpu samples >= 0.9 × measurement samples` (despite the historical check name saying “above”). The fixed protocol requires CPU-availability verification, and the first-comparison verifier calls the analyzer checks predeclared. The strongest timestamped bound is `execution_ledger.jsonl`: it records the first threshold failure at 2026-10-23 15:08:28 UTC, before the unchanged retry began at 15:08:58 UTC. Because the scientific worktree is untracked, Git does not cryptographically establish the threshold’s original creation time. The threshold is retained unchanged: both attempts remain `INCONCLUSIVE`. CPU mean/max, hot-sample fraction, and per-pod metric coverage require CPU observations; request/QoS, ready-pod integration, replicas, and controller identity come from independent saved streams. Excluding low-coverage runs can bias accepted statistics toward healthier service periods because missingness overlaps instability. The overlap is evidence of selection-bias risk, not proof that instability alone caused every gap.','',
      '## Missing-sample timeline','',
      '| Attempt | UTC | Elapsed (s) | Ready/current/desired | Restarts | HPA metric state | Requests / failures / timeouts in ±2.5 s | Success p95 (s) |','|---|---|---:|---:|---:|---|---:|---:|']
    for run in attempts:
      for s in run['missing_samples']:
        failed=next((c for c in s['hpa_conditions'] if c.get('reason')=='FailedGetResourceMetric'),None)
        rb=s['request_behavior'];msg=failed['message'] if failed else 'last HPA status still valid or unavailable'
        lines.append(f"| {run['label']} | {s['utc']} | {s['elapsed_s']:.3f} | {s['ready_replicas']}/{s['current_replicas']}/{s['desired_replicas']} | {s['container_restarts']} | {msg} | {rb['requests']} / {rb['failures']} / {rb['timeouts']} | {rb['successful_latency_p95_s'] if rb['successful_latency_p95_s'] is not None else 'NA'} |")
    lines += ['','Each timeline row is computed from that run’s `metrics.jsonl` and `requests.csv`; event-level corroboration and replica changes are in `telemetry_diagnosis.json`. Kubernetes event objects are aggregated snapshots, so their counts/timestamps are supporting context rather than a complete transition log.','',
      '## Supplementary sensitivity analysis (excluded from accepted statistics)','',
      '| Run | Decision | Successes / scheduled | Error rate | Timeouts | Success p95 (s) | Pod-s | Mean/max ready | CPU coverage | Missing bursts |','|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for run in [diagnosed['accepted_tuned_repeat1'],diagnosed['accepted_tuned_repeat2'],*attempts]:
      s=run['summary'];burst=', '.join(f"{b['start_elapsed_s']:.0f}–{b['end_elapsed_s']:.0f}s" for b in run['missing_bursts']) or 'none'
      lines.append(f"| {run['label']} | {run['decision']} | {s['successful_requests']} / {s['scheduled_measurement_requests']} | {s['error_rate']:.3%} | {s['timeouts']} | {s['p95_latency_s']:.6f} | {s['pod_seconds']:.6f} | {s['mean_ready']:.3f}/{s['max_ready']} | {run['cpu_coverage']:.3%} | {burst} |")
    lines += ['','Accepted soft-HPA repeats 1 and 2 also contain six empty samples each (78/84, 92.9%) and remained above the frozen threshold; full cross-controller details are in `telemetry_diagnosis.json`. Thus empty metric bursts were not unique to the excluded tuned-HPA attempts, while both excluded attempts show more missingness and substantial service instability.','',
      '## Instrumentation correction','',
      'Future collector records now preserve per-command success, return code, redacted/truncated stderr, timeout state, duration, response kind, item count, response size, and an explicit `success` / `empty_response` / `command_failure` / `invalid_json` classification. The analyzer reports availability counts and exact CPU coverage. No workload, controller, probe, replay, or acceptance setting changed; no missing CPU value is imputed. Existing artifacts and decisions were not overwritten.','',
      '## Recommendation','',
      '**C — retain the partial NASA matrix and proceed to the next handoff workload.** Two unchanged tuned-HPA attempts reproduced the same below-threshold coverage while independently verifiable outcomes show instability. Further retries would invite outcome/availability-based selection, and a replacement run with richer telemetry would not be instrumentation-identical to the accepted series. Start richer collection only as a predeclared future series, not as a selective repair of this matrix.','']
    report_path=OUT/'TELEMETRY_DIAGNOSIS.md';report_path.write_text('\n'.join(lines))
    evidence_paths={path for run in RUNS.values() for path in
                    (run/'metadata.json',run/'metrics.jsonl',run/'requests.csv',run/'events.json',run/'summary.json')}
    evidence_paths.update({Path(__file__),ROOT/'scripts/live/run_trace.py',ROOT/'scripts/live/analyze_runs.py',
                           ROOT/'tests/test_live_analysis.py',ROOT/'docs/LIVE_TRACE_PROTOCOL.md',destination,report_path})
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),'artifacts':{
        str(path.relative_to(ROOT)):{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        for path in sorted(evidence_paths)}}
    manifest_path=OUT/'telemetry_diagnosis_manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(destination.relative_to(ROOT));print(report_path.relative_to(ROOT));print(manifest_path.relative_to(ROOT))

if __name__=='__main__':main()
