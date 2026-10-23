import csv,hashlib,importlib.util,json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('live_analysis',Path(__file__).resolve().parents[1]/'scripts/live/analyze_runs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
run_spec=importlib.util.spec_from_file_location('run_trace_test',Path(__file__).resolve().parents[1]/'scripts/live/run_trace.py')
rt=importlib.util.module_from_spec(run_spec);run_spec.loader.exec_module(rt)

class LiveAnalysisTests(unittest.TestCase):
    def make_run(self,root,outcomes=None,complete=True,metrics=True):
        p=Path(root);trace='replay_second,source_time,source_value,target_rps\n0,0,1,0.5\n'
        (p/'trace.csv').write_text(trace)
        meta=dict(warmup=1,duration=10,dataset='fixture',arm='strawman_hpa',repeat=1,
                  category='test',scheduled_requests=9,trace_sha256=hashlib.sha256(trace.encode()).hexdigest(),
                  elapsed_seconds=11)
        (p/'metadata.json').write_text(json.dumps(meta))
        if complete:(p/'COMPLETE').touch()
        outcomes=outcomes or [(200,'')]*5
        with (p/'requests.csv').open('w') as f:
            w=csv.writer(f);w.writerow(['planned_s','dispatch_s','complete_s','latency_s','status','error','phase'])
            for j in range(4):
                t=j/4;w.writerow([t,t+.001,t+.011,.01,200,'','warmup'])
            for j,(status,error) in enumerate(outcomes):
                planned=1+(j+.5)*2;latency=5 if 'Timeout' in error else .1
                w.writerow([planned,planned+.001,planned+.001+latency,latency,status,error,'measurement'])
        if metrics:
            base=datetime(2026,1,1,tzinfo=timezone.utc)
            with (p/'metrics.jsonl').open('w') as f:
                for t in [0,1,6,11]:
                    replicas=1 if t<6 else 2
                    objects=[dict(kind='Deployment',spec=dict(replicas=replicas),
                                  status=dict(readyReplicas=replicas,replicas=replicas)),
                             dict(kind='HorizontalPodAutoscaler')]
                    record=dict(elapsed_seconds=t,utc=(base+timedelta(seconds=t)).isoformat(),
                        objects=dict(items=objects),pod_metrics=dict(items=[dict(containers=[dict(usage=dict(cpu='200m'))])]),
                        collection_seconds=.1,host_loadavg=[0,0,0])
                    f.write(json.dumps(record)+'\n')
        return p

    def test_all_success_records_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            result=m.analyze(self.make_run(temp))
            self.assertEqual(result['decision'],'ACCEPT')
            self.assertEqual(result['successful_requests'],5)
            self.assertEqual(result['recorded_failures'],0)
            self.assertEqual(result['error_rate'],0)
            self.assertAlmostEqual(result['p95_latency_s'],.1)

    def test_mixed_success_http_error_and_timeout_keep_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            outcomes=[(200,''),(503,''),(0,'TimeoutError: '),(200,''),(200,'')]
            result=m.analyze(self.make_run(temp,outcomes))
            self.assertEqual(result['decision'],'ACCEPT')
            self.assertEqual(result['successful_requests'],3)
            self.assertEqual(result['http_failures_by_status'],{'503':1})
            self.assertEqual(result['timeouts'],1)
            self.assertEqual(result['error_rate'],.4)

    def test_comparison_fields_preserve_scope_disconnections_and_peak_cpu(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp,[(200,''),(0,'ServerDisconnectedError: closed'),(200,''),(200,''),(200,'')])
            meta=json.loads((p/'metadata.json').read_text());meta['category']='first_comparison'
            (p/'metadata.json').write_text(json.dumps(meta))
            result=m.analyze(p)
            self.assertEqual(result['decision_scope'],'single-repeat live controller comparison')
            self.assertEqual(result['disconnections'],1)
            self.assertEqual(result['connection_failures'],1)
            self.assertAlmostEqual(result['max_cpu_m'],200)

    def test_missing_and_duplicate_schedule_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            with (p/'requests.csv').open() as f: rows=list(csv.reader(f))
            # Remove one planned request and duplicate another; count alone still matches.
            rows[-1]=rows[-2]
            with (p/'requests.csv').open('w') as f: csv.writer(f).writerows(rows)
            result=m.analyze(p)
            self.assertEqual(result['missing_records'],1)
            self.assertEqual(result['duplicate_records'],1)
            self.assertEqual(result['decision'],'REJECT')

    def test_invalid_dispatch_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            with (p/'requests.csv').open() as f: rows=list(csv.reader(f))
            rows[-1][1]=str(float(rows[-1][0])-.1)
            with (p/'requests.csv').open('w') as f: csv.writer(f).writerows(rows)
            result=m.analyze(p)
            self.assertEqual(result['invalid_timestamp_records'],1)
            self.assertEqual(result['decision'],'REJECT')

    def test_missing_metrics_and_incomplete_marker_are_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            result=m.analyze(self.make_run(temp,complete=False,metrics=False))
            self.assertFalse(result['checks']['complete_marker'])
            self.assertFalse(result['checks']['metrics_present'])
            self.assertEqual(result['decision'],'INCONCLUSIVE')

    def test_conflicting_controllers_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            records=[json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines()]
            for record in records: record['objects']['items'].append(dict(kind='PredictiveHorizontalPodAutoscaler'))
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertTrue(result['controller_conflict_observed'])
            self.assertEqual(result['decision'],'REJECT')

    def test_empty_metric_responses_are_explicit_and_preserve_qos(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            records=[json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines()]
            records[1]['pod_metrics']['items']=[]
            records[2]['pod_metrics']['items']=[]
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertEqual(result['metric_availability_counts']['empty_response'],2)
            self.assertEqual(result['cpu_sample_count'],1)
            self.assertAlmostEqual(result['cpu_coverage'],1/3)
            self.assertEqual(result['successful_requests'],5)
            self.assertAlmostEqual(result['p95_latency_s'],.1)
            self.assertEqual(result['decision'],'INCONCLUSIVE')

    def test_api_command_failure_is_distinct_from_empty_response(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            records=[json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines()]
            records[1]['pod_metrics']={'error':'apiserver unavailable'}
            records[1]['collection_diagnostics']={'pod_metrics':{'classification':'command_failure','returncode':1}}
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertEqual(result['metric_availability_counts']['command_failure'],1)
            self.assertEqual(result['decision'],'INCONCLUSIVE')

    def test_temporary_workload_unavailability_does_not_erase_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            records=[json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines()]
            deployment=next(x for x in records[2]['objects']['items'] if x['kind']=='Deployment')
            deployment['status']['readyReplicas']=0
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertEqual(result['cpu_sample_count'],3)
            self.assertEqual(result['readiness_deficit_samples'],1)
            self.assertEqual(result['decision'],'ACCEPT')

    def test_collector_records_success_empty_and_command_failure(self):
        responses=[
            SimpleNamespace(returncode=0,stdout='{"kind":"PodMetricsList","items":[{"containers":[]}]}',stderr=''),
            SimpleNamespace(returncode=0,stdout='{"kind":"PodMetricsList","items":[]}',stderr=''),
            SimpleNamespace(returncode=1,stdout='',stderr='service unavailable'),
        ]
        with patch.object(rt.subprocess,'run',side_effect=responses):
            _,success=rt.collect_resource(['get','x'])
            _,empty=rt.collect_resource(['get','x'])
            payload,failure=rt.collect_resource(['get','x'])
        self.assertEqual(success['classification'],'success')
        self.assertEqual(empty['classification'],'empty_response')
        self.assertEqual(failure['classification'],'command_failure')
        self.assertIn('service unavailable',payload['error'])
        self.assertNotIn('secret-value',rt.diagnostic_text('Authorization: Bearer secret-value'))

    def test_cpu_coverage_boundary_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_run(temp)
            base=datetime(2026,1,1,tzinfo=timezone.utc)
            records=[]
            for index in range(10):
                elapsed=1+index*(10/9)
                replicas=1 if index==0 else 2
                items=[dict(kind='Deployment',spec=dict(replicas=replicas),
                            status=dict(readyReplicas=replicas,replicas=replicas)),
                       dict(kind='HorizontalPodAutoscaler')]
                metrics=[] if index==0 else [dict(containers=[dict(usage=dict(cpu='200m'))])]
                records.append(dict(elapsed_seconds=elapsed,
                    utc=(base+timedelta(seconds=elapsed)).isoformat(timespec='microseconds'),objects=dict(items=items),
                    pod_metrics=dict(items=metrics),collection_seconds=.1,host_loadavg=[0,0,0]))
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertEqual(result['cpu_sample_count'],9)
            self.assertAlmostEqual(result['cpu_coverage'],.9)
            self.assertTrue(result['checks']['metrics_coverage_above_90pct'])
            self.assertEqual(result['decision'],'ACCEPT')
            records[1]['pod_metrics']['items']=[]
            (p/'metrics.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            result=m.analyze(p)
            self.assertEqual(result['cpu_sample_count'],8)
            self.assertFalse(result['checks']['metrics_coverage_above_90pct'])
            self.assertEqual(result['decision'],'INCONCLUSIVE')

if __name__=='__main__':unittest.main()
