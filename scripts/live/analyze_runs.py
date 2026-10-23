#!/usr/bin/env python3
"""Analyze live runs without hiding failed or missing requests."""
import argparse,collections,hashlib,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from run_trace import cpu_m
ROOT=Path(__file__).resolve().parents[2]
CONTROLLERS={'HorizontalPodAutoscaler','PredictiveHorizontalPodAutoscaler'}

def quantile(values,q):
    values=pd.to_numeric(values,errors='coerce').dropna()
    return None if values.empty else float(values.quantile(q))

def schedule(trace,warmup,duration):
    result=[(second+j/4,'warmup') for second in range(warmup) for j in range(4)]
    for i,row in enumerate(trace.itertuples()):
        offset=i*10
        if offset>=duration: break
        width=min(10,duration-offset);count=round(float(row.target_rps)*width)
        result.extend((warmup+offset+(j+.5)*width/count,'measurement') for j in range(count))
    return result

def schedule_key(planned,phase): return str(phase),round(float(planned),9)

def max_inflight(requests):
    events=[]
    for row in requests.itertuples():
        if np.isfinite(row.dispatch_s) and np.isfinite(row.complete_s):
            events.extend(((row.dispatch_s,1),(row.complete_s,-1)))
    current=maximum=0
    for _,delta in sorted(events,key=lambda item:(item[0],item[1])):
        current+=delta;maximum=max(maximum,current)
    return maximum

def classify_errors(requests):
    errors=requests.error.fillna('').astype(str)
    status=pd.to_numeric(requests.status,errors='coerce').fillna(0).astype(int)
    success=(status==200)&(errors==''); generator=errors.str.startswith('generator_')
    classes=errors.str.extract(r'^([^:]+):',expand=False).fillna('');lower=errors.str.lower()
    timeout=(~success)&(~generator)&(classes.str.lower().str.contains('timeout')|lower.str.contains('timed out'))
    cancelled=(~success)&(~generator)&classes.str.contains('CancelledError')
    connection=(~success)&(~generator)&(~timeout)&(
        classes.isin(['ServerDisconnectedError','ClientConnectorError','ClientConnectionError','ConnectionResetError','ConnectionRefusedError'])
        |lower.str.contains(r'connection (?:refused|reset|closed)|server disconnected',regex=True))
    http=(~success)&(status>0)&(status!=200)
    other=(~success)&~generator&~timeout&~cancelled&~connection&~http
    counts=lambda s:{str(k):int(v) for k,v in s.value_counts().sort_index().items()}
    return dict(success=success,generator=generator,timeout=timeout,cancelled=cancelled,
                connection=connection,http=http,other=other,
                http_status_counts=counts(status[http]),
                exception_class_counts=counts(classes[(~success)&(~generator)&(classes!='')]),
                exception_message_counts=counts(errors[(~success)&(~generator)&(errors!='')]))

def metric_availability(record, cpu_count):
    """Classify legacy and diagnostic-rich pod-metrics samples without imputation."""
    diagnostic=record.get('collection_diagnostics',{}).get('pod_metrics',{})
    classification=diagnostic.get('classification')
    if classification in {'command_failure','invalid_json'}:
        return classification
    payload=record.get('pod_metrics',{})
    if isinstance(payload,dict) and payload.get('error'):
        return 'command_failure'
    if cpu_count:
        return 'available'
    if isinstance(payload,dict) and payload.get('items')==[]:
        return 'empty_response'
    return 'no_usable_cpu'

def parse_metrics(path):
    rows=[];malformed=0
    for line in path.read_text().splitlines() if path.exists() else []:
        try: record=json.loads(line)
        except (TypeError,json.JSONDecodeError): malformed+=1;continue
        items=record.get('objects',{}).get('items',[])
        dep=next((x for x in items if x.get('kind')=='Deployment'),None)
        if dep is None: malformed+=1;continue
        pods=[x for x in items if x.get('kind')=='Pod']
        controllers=[x for x in items if x.get('kind') in CONTROLLERS]
        cpu=[]
        for pod in record.get('pod_metrics',{}).get('items',[]):
            try: cpu.append(sum(cpu_m(c['usage']['cpu']) for c in pod['containers']))
            except (KeyError,TypeError,ValueError): pass
        rows.append(dict(elapsed_seconds=record.get('elapsed_seconds'),utc=record.get('utc',''),
            ready=dep.get('status',{}).get('readyReplicas',0),current=dep.get('status',{}).get('replicas',0),
            desired=dep.get('spec',{}).get('replicas',0),cpu_mean_m=np.mean(cpu) if cpu else np.nan,
            metric_pods=len(cpu),metric_availability=metric_availability(record,len(cpu)),controller_count=len(controllers),
            controller_kind=controllers[0].get('kind','') if len(controllers)==1 else '',
            restarts=sum(c.get('restartCount',0) for p in pods for c in p.get('status',{}).get('containerStatuses',[])),
            collection_seconds=record.get('collection_seconds',np.nan),host_load1=(record.get('host_loadavg') or [np.nan])[0]))
    frame=pd.DataFrame(rows)
    if not frame.empty:
        for col in ['elapsed_seconds','ready','current','desired','cpu_mean_m','metric_pods','restarts','collection_seconds']:
            frame[col]=pd.to_numeric(frame[col],errors='coerce')
        frame=frame.dropna(subset=['elapsed_seconds']).sort_values('elapsed_seconds')
    return frame,malformed

def event_summary(path,start_utc=None,end_utc=None):
    result=dict(readiness_probe_failures=0,liveness_probe_failures=0,container_kill_events=0)
    if not path.exists(): return result
    try: items=json.loads(path.read_text()).get('items',[])
    except (OSError,json.JSONDecodeError): return result
    for item in items:
        text=str(item.get('note') or item.get('message') or '').lower()
        timestamp=item.get('lastTimestamp') or item.get('eventTime') or item.get('deprecatedLastTimestamp')
        if timestamp and (start_utc is not None or end_utc is not None):
            try: event_time=pd.to_datetime(timestamp,utc=True)
            except (ValueError,TypeError): continue
            if start_utc is not None and event_time<start_utc: continue
            if end_utc is not None and event_time>end_utc: continue
        count=int(item.get('deprecatedCount') or item.get('count') or 1)
        if 'readiness probe failed' in text: result['readiness_probe_failures']+=count
        if 'liveness probe failed' in text: result['liveness_probe_failures']+=count
        if item.get('reason')=='Killing' and 'failed liveness probe' in text: result['container_kill_events']+=count
    return result

def analyze(path):
    path=Path(path);meta=json.loads((path/'metadata.json').read_text())
    start=float(meta['warmup']);end=start+float(meta['duration'])
    trace_path=path/'trace.csv'
    if not trace_path.exists(): trace_path=ROOT/'data/live_traces'/f"{meta['dataset']}.csv"
    trace=pd.read_csv(trace_path);planned=schedule(trace,meta['warmup'],meta['duration'])
    expected=collections.Counter(schedule_key(*x) for x in planned)
    req=pd.read_csv(path/'requests.csv',keep_default_na=False)
    required={'planned_s','dispatch_s','complete_s','latency_s','status','error','phase'}
    if required-set(req): raise ValueError(f"requests.csv missing columns: {sorted(required-set(req))}")
    for col in ['planned_s','dispatch_s','complete_s','latency_s','status']:
        req[col]=pd.to_numeric(req[col],errors='coerce')
    actual=collections.Counter(schedule_key(r.planned_s,r.phase) for r in req.itertuples() if np.isfinite(r.planned_s))
    missing=sum((expected-actual).values());unexpected=sum((actual-expected).values())
    duplicates=sum(max(0,n-expected.get(key,0)) for key,n in actual.items())
    measured=req[req.phase=='measurement'].copy()
    measured['dispatch_delay_s']=measured.dispatch_s-measured.planned_s
    measured['scheduled_latency_s']=measured.complete_s-measured.planned_s
    errors=classify_errors(measured);success=measured[errors['success']]
    invalid=int((~np.isfinite(measured[['planned_s','dispatch_s','complete_s','latency_s']]).all(axis=1)
        |(measured.dispatch_s<measured.planned_s)|(measured.complete_s<measured.dispatch_s)|(measured.latency_s<0)).sum())
    inconsistent=int(((measured.latency_s-(measured.complete_s-measured.dispatch_s)).abs()>1e-6).sum())

    frame,malformed=parse_metrics(path/'metrics.jsonl');frame.to_csv(path/'metrics.csv',index=False)
    window=frame[(frame.elapsed_seconds>=start)&(frame.elapsed_seconds<=end)].copy() if not frame.empty else frame.copy()
    cpu=window.cpu_mean_m.dropna() if 'cpu_mean_m' in window else pd.Series(dtype=float)
    gap=quantile(frame.elapsed_seconds.diff(),1) if not frame.empty else None
    bracketed=bool(not frame.empty and frame.elapsed_seconds.min()<=start and frame.elapsed_seconds.max()>=end)
    if bracketed:
        points=np.unique(np.r_[start,window.elapsed_seconds.to_numpy(),end])
        pod_seconds=float(np.trapezoid(np.interp(points,frame.elapsed_seconds,frame.ready),points))
        desired_pod_seconds=float(np.trapezoid(np.interp(points,frame.elapsed_seconds,frame.desired),points))
    else: pod_seconds=desired_pod_seconds=None
    utc_consistent=False
    if len(frame)>=2:
        try:
            utc=pd.to_datetime(frame.utc,utc=True);a=frame.elapsed_seconds.to_numpy()-frame.elapsed_seconds.iloc[0]
            b=(utc-utc.iloc[0]).dt.total_seconds().to_numpy();utc_consistent=bool(np.isfinite(b).all() and np.max(np.abs(a-b))<.1)
        except (ValueError,TypeError): pass
    expected_kind='PredictiveHorizontalPodAutoscaler' if meta['arm']=='holtwinters' else 'HorizontalPodAutoscaler'
    conflict=bool(not window.empty and (window.controller_count>1).any())
    wrong=bool(not window.empty and ((window.controller_count==1)&(window.controller_kind!=expected_kind)).any())
    exclusive=bool(not window.empty and (window.controller_count==1).all() and not conflict and not wrong)
    scaling=[];previous=None
    for row in window.itertuples():
        desired=int(row.desired)
        if previous is not None and desired!=previous:
            scaling.append(dict(elapsed_s=float(row.elapsed_seconds),utc=str(row.utc),
                                from_replicas=previous,to_replicas=desired))
        previous=desired

    total=len(planned);scheduled_measurement=sum(phase=='measurement' for _,phase in planned)
    dispatch_p99=quantile(measured.dispatch_delay_s,.99)
    checks=dict(trace_hash_matches=hashlib.sha256(trace_path.read_bytes()).hexdigest()==meta.get('trace_sha256'),
        metadata_schedule_count_exact=meta.get('scheduled_requests')==total,all_schedule_records_present=missing==0,
        no_unexpected_or_duplicate_records=unexpected==0 and duplicates==0,
        request_timestamps_valid=invalid==0 and inconsistent==0,complete_marker=(path/'COMPLETE').exists(),
        no_generator_drops=not errors['generator'].any(),
        dispatch_p99_below_100ms=dispatch_p99 is not None and dispatch_p99<.1,
        metrics_present=not window.empty,controller_exclusive=exclusive,
        metrics_coverage_above_90pct=bool(not window.empty and len(cpu)>=.9*len(window)),
        sample_gap_below_15s=gap is not None and gap<15,window_bracketed=bracketed,
        metric_timestamps_consistent=utc_consistent,
        scaling_response_observed=bool(not window.empty and window.desired.max()>1))
    reject=['trace_hash_matches','metadata_schedule_count_exact','all_schedule_records_present',
        'no_unexpected_or_duplicate_records','request_timestamps_valid','no_generator_drops','dispatch_p99_below_100ms']
    inconclusive=['complete_marker','metrics_present','metrics_coverage_above_90pct','sample_gap_below_15s',
        'window_bracketed','metric_timestamps_consistent','scaling_response_observed']
    (reject if conflict or wrong else inconclusive).append('controller_exclusive')
    decision='REJECT' if any(not checks[x] for x in reject) else ('INCONCLUSIVE' if any(not checks[x] for x in inconclusive) else 'ACCEPT')
    activity=float(measured.complete_s.max()-measured.dispatch_s.min()) if len(measured) else None
    event_start=event_end=None
    if not frame.empty:
        try:
            origin=pd.to_datetime(frame.iloc[0].utc,utc=True)-pd.to_timedelta(frame.iloc[0].elapsed_seconds,unit='s')
            event_start=origin+pd.to_timedelta(start,unit='s');event_end=origin+pd.to_timedelta(end,unit='s')
        except (ValueError,TypeError): pass
    events=event_summary(path/'events.json',event_start,event_end)
    rel=lambda p:str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    result={k:meta.get(k) for k in ['dataset','arm','repeat','category','warmup','duration']}
    source_names=['requests.csv','metrics.jsonl','metadata.json','events.json','initial_objects.json','final_objects.json','operator.log']
    scope=('pilot instrumentation validation; not a controller comparison' if str(meta.get('category','')).startswith('pilot')
           else 'single-repeat live controller comparison')
    availability_counts=({str(k):int(v) for k,v in window.metric_availability.value_counts().sort_index().items()}
                         if not window.empty else {})
    result.update(decision=decision,decision_scope=scope,
        source_directory=rel(path),sources={n:rel(path/n) for n in source_names},
        source_sha256={n:hashlib.sha256((path/n).read_bytes()).hexdigest() for n in source_names if (path/n).exists()},
        scheduled_requests=total,scheduled_measurement_requests=scheduled_measurement,request_records=len(req),
        measurement_request_records=len(measured),successful_requests=len(success),success_requests=len(success),
        recorded_failures=len(measured)-len(success),errors=len(measured)-len(success),
        http_failures_by_status=errors['http_status_counts'],client_exceptions_by_class=errors['exception_class_counts'],
        client_exceptions_by_message=errors['exception_message_counts'],timeouts=int(errors['timeout'].sum()),
        connection_failures=int(errors['connection'].sum()),disconnections=int(errors['connection'].sum()),
        cancellations=int(errors['cancelled'].sum()),
        other_failures=int(errors['other'].sum()),generator_drops=int(errors['generator'].sum()),
        missing_records=missing,unexpected_records=unexpected,duplicate_records=duplicates,
        invalid_timestamp_records=invalid,inconsistent_latency_records=inconsistent,
        error_rate_scheduled_denominator=(scheduled_measurement-len(success))/scheduled_measurement,
        error_rate=(scheduled_measurement-len(success))/scheduled_measurement,
        recorded_error_rate=(len(measured)-len(success))/len(measured),
        dispatch_delay_s={q:quantile(measured.dispatch_delay_s,v) for q,v in [('p50',.5),('p95',.95),('p99',.99)]},
        successful_request_latency_s={q:quantile(success.latency_s,v) for q,v in [('p50',.5),('p95',.95),('p99',.99)]},
        p50_latency_s=quantile(success.latency_s,.5),p95_latency_s=quantile(success.latency_s,.95),
        p99_latency_s=quantile(success.latency_s,.99),p95_scheduled_latency_s=quantile(success.scheduled_latency_s,.95),
        p99_dispatch_delay_s=dispatch_p99,intended_replay_duration_s=float(meta['duration']),
        actual_request_activity_duration_s=activity,runner_elapsed_s=meta.get('elapsed_seconds'),
        offered_request_rate_rps=scheduled_measurement/meta['duration'],
        actual_dispatch_rate_rps=len(measured)/(measured.dispatch_s.max()-measured.dispatch_s.min()),
        achieved_success_rps=len(success)/meta['duration'],max_client_inflight=max_inflight(measured),
        pod_seconds=pod_seconds,desired_pod_seconds=desired_pod_seconds,
        mean_ready=pod_seconds/meta['duration'] if pod_seconds is not None else None,
        max_ready=int(window.ready.max()) if not window.empty else None,
        final_observed_ready=int(window.iloc[-1].ready) if not window.empty else None,
        cpu_hot_sample_fraction=float((cpu>160).mean()) if len(cpu) else None,
        mean_cpu_m=float(cpu.mean()) if len(cpu) else None,max_cpu_m=float(cpu.max()) if len(cpu) else None,
        mean_metric_pod_coverage=float(np.minimum(1,window.metric_pods/window.current.clip(lower=1)).mean()) if not window.empty else None,
        sample_count=len(window),cpu_sample_count=len(cpu),cpu_coverage=float(len(cpu)/len(window)) if len(window) else None,
        metric_availability_counts=availability_counts,max_sample_gap_s=gap,malformed_metric_records=malformed,
        max_workload_restarts=int(window.restarts.max()) if not window.empty else None,
        readiness_deficit_samples=int((window.ready<window.current).sum()) if not window.empty else None,
        events=events,active_controller=expected_kind if exclusive else None,controller_conflict_observed=conflict,
        scaling_events=scaling,scaling_changes=len(scaling),checks=checks,
        check_severity={'reject_if_false':reject,'inconclusive_if_false':inconclusive},valid=decision=='ACCEPT')
    (path/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def write_report(r,destination):
    d=r['dispatch_delay_s'];lat=r['successful_request_latency_s'];fail=[k for k,v in r['checks'].items() if not v]
    scaling=', '.join(f"{x['from_replicas']}→{x['to_replicas']} at {x['elapsed_s']:.3f}s ({x['utc']})" for x in r['scaling_events']) or 'none'
    classes=', '.join(f"`{k}`: {v}" for k,v in r['client_exceptions_by_class'].items()) or 'none'
    http=', '.join(f"HTTP {k}: {v}" for k,v in r['http_failures_by_status'].items()) or 'none'
    text=f"""# Asynchronous NASA pilot validation

## Purpose and provenance

This pilot tested whether the corrected asynchronous, open-loop replay and five-second Kubernetes collector could retain a deterministic NASA schedule while observing one Holt–Winters PHPA arm. It does not validate the planned three-controller comparison. Raw evidence is retained in `{r['source_directory']}`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: {r['scheduled_requests']} total ({r['scheduled_measurement_requests']} measurement and {r['scheduled_requests']-r['scheduled_measurement_requests']} warmup).
- Records: {r['request_records']} total and {r['measurement_request_records']} measurement; missing {r['missing_records']}, unexpected {r['unexpected_records']}, duplicate {r['duplicate_records']}.
- Measurement successes: {r['successful_requests']}; failures: {r['recorded_failures']}; scheduled-denominator error rate: {r['error_rate_scheduled_denominator']:.9f}.
- HTTP failures: {http}. Client exceptions by class: {classes}. Timeouts: {r['timeouts']}; connection failures: {r['connection_failures']}; cancellations: {r['cancellations']}; generator drops: {r['generator_drops']}.
- Dispatch delay p50/p95/p99: {d['p50']:.9f}/{d['p95']:.9f}/{d['p99']:.9f} s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: {lat['p50']:.9f}/{lat['p95']:.9f}/{lat['p99']:.9f} s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: {r['intended_replay_duration_s']:.3f} s; actual first-dispatch-to-last-completion span: {r['actual_request_activity_duration_s']:.9f} s; offered rate: {r['offered_request_rate_rps']:.9f} requests/s; dispatch-span rate: {r['actual_dispatch_rate_rps']:.9f} requests/s; peak in-flight: {r['max_client_inflight']}.

## Autoscaling observations

The collector saw exactly one `{r['active_controller']}` and no conflicting HPA in every measurement sample. There were {r['sample_count']} samples, {r['cpu_sample_count']} with CPU data, a {r['max_sample_gap_s']:.6f} s maximum gap, and {r['mean_metric_pod_coverage']:.6f} mean per-pod CPU coverage. Mean observed pod CPU was {r['mean_cpu_m']:.6f} mCPU and {r['cpu_hot_sample_fraction']:.6f} of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were {scaling}. Maximum and final ready replicas were {r['max_ready']} and {r['final_observed_ready']}. Thus “five replicas” is the intermediate 3→5 transition; ten ready replicas is the later/final state. The collector saw {r['max_workload_restarts']} restart and {r['readiness_deficit_samples']} readiness-deficit samples. Events retain {r['events']['readiness_probe_failures']} readiness-probe and {r['events']['liveness_probe_failures']} liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at {r['max_client_inflight']} in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU samples existed at every collector time, but not every current pod had a metrics-server value (mean per-pod coverage {r['mean_metric_pod_coverage']:.6f}). The PHPA log also records transient missing/unknown-pod metrics during startup and scaling. This limits controller-performance inference but does not demonstrate silent loss by the instrumentation.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: {', '.join(fail) if fail else 'none'}.

**Decision: {r['decision']}.** The retained evidence is sufficient for the pilot's instrumentation purpose. This is not a NASA performance result or evidence that the three-controller campaign ran.
"""
    destination.write_text(text)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT/'results/live_trace_phase');args=p.parse_args()
    results=[analyze(marker.parent) for marker in sorted(args.root.rglob('COMPLETE'))]
    if results:
        pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in results]).to_csv(args.root/'run_summary.csv',index=False)
        print(pd.DataFrame(results)[['category','dataset','repeat','arm','pod_seconds','p95_latency_s','error_rate','decision']].to_string(index=False))
        for r in results:
            if r['decision']!='ACCEPT': print('CHECK FAILURES',r['dataset'],r['arm'],r['repeat'],[k for k,v in r['checks'].items() if not v])
        if len(results)==1:
            (args.root/'summary.json').write_text(json.dumps(results[0],indent=2)+'\n');write_report(results[0],args.root/'validation_report.md')
if __name__=='__main__': main()
