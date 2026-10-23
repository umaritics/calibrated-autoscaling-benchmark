#!/usr/bin/env python3
"""Run one real Kubernetes controller arm with open-loop HTTP trace replay."""
import argparse,asyncio,csv,hashlib,json,os,re,subprocess,threading,time,urllib.request,urllib.error
import aiohttp
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
K=[str(ROOT/'.tools/kubectl'),'--kubeconfig',str(ROOT/'live-kubeconfig'),'--request-timeout=15s']
NS='trace-benchmark'
POLICIES={'strawman_hpa':'hpa-baseline.yaml','calibrated_hpa':'hpa-calibrated.yaml','holtwinters':'phpa-holtwinters.yaml'}

def diagnostic_text(value, limit=2048):
    text=str(value or '')
    text=re.sub(r'(?i)(authorization:\s*bearer\s+|token[=:]\s*)\S+',r'\1[REDACTED]',text)
    return text[:limit]

def command_result(args, timeout=180):
    """Run kubectl and retain enough metadata to diagnose collection failures."""
    started=time.monotonic()
    try:
        p=subprocess.run(K+args,capture_output=True,text=True,timeout=timeout)
        return {'ok':p.returncode==0,'returncode':p.returncode,
                'stdout':p.stdout,'stderr':diagnostic_text(p.stderr),
                'duration_seconds':time.monotonic()-started,'timed_out':False}
    except subprocess.TimeoutExpired as exc:
        return {'ok':False,'returncode':None,'stdout':exc.stdout or '',
                'stderr':diagnostic_text(exc.stderr),'duration_seconds':time.monotonic()-started,
                'timed_out':True,'error':'TimeoutExpired'}

def command(args,check=True):
    result=command_result(args)
    if check and not result['ok']:
        raise RuntimeError(f"{args}: {result['stderr'] or result.get('error','command failed')}")
    return result['stdout'] if result['ok'] else json.dumps({'error':result['stderr'] or result.get('error','command failed')})

def collect_resource(args):
    """Return parsed API data plus explicit transport/parse/availability evidence."""
    result=command_result(args)
    diagnostic={k:result.get(k) for k in
                ('ok','returncode','stderr','duration_seconds','timed_out','error') if k in result}
    if not result['ok']:
        diagnostic['classification']='command_failure'
        return {'error':result['stderr'] or result.get('error','command failed')},diagnostic
    try:
        payload=json.loads(result['stdout'])
    except (TypeError,json.JSONDecodeError) as exc:
        diagnostic.update(classification='invalid_json',parse_error=str(exc),
                          stdout_bytes=len(result['stdout'].encode()))
        return {'error':f'invalid JSON response: {exc}'},diagnostic
    items=payload.get('items') if isinstance(payload,dict) else None
    diagnostic.update(classification='empty_response' if items==[] else 'success',
                      response_kind=payload.get('kind') if isinstance(payload,dict) else None,
                      item_count=len(items) if isinstance(items,list) else None,
                      stdout_bytes=len(result['stdout'].encode()))
    return payload,diagnostic
def cpu_m(value):
    if value.endswith('n'):return float(value[:-1])/1e6
    if value.endswith('u'):return float(value[:-1])/1e3
    if value.endswith('m'):return float(value[:-1])
    return float(value)*1000

def reset(arm,out):
    command(['-n',NS,'delete','hpa,phpa','--all','--ignore-not-found=true'])
    command(['-n',NS,'delete','deployment','php-apache','--ignore-not-found=true','--wait=true'])
    command(['-n',NS,'wait','--for=delete','pod','-l','run=php-apache','--timeout=90s'],check=False)
    command(['-n',NS,'apply','-f',str(ROOT/'manifests/sample-app.yaml')])
    command(['-n',NS,'patch','svc','php-apache','-p','{"spec":{"type":"NodePort","ports":[{"port":80,"targetPort":80,"nodePort":30080}]}}'])
    command(['-n',NS,'rollout','status','deploy/php-apache','--timeout=120s'])
    # Unique CR UID and fresh process prevent predictor state crossing trials.
    if arm=='holtwinters':
        command(['-n','phpa-system','rollout','restart','deploy/predictive-horizontal-pod-autoscaler'])
        command(['-n','phpa-system','rollout','status','deploy/predictive-horizontal-pod-autoscaler','--timeout=120s'])
    command(['-n',NS,'apply','-f',str(ROOT/'policies'/POLICIES[arm])])
    (out/'initial_objects.json').write_text(command(['-n',NS,'get','deploy,pods,hpa,phpa','-o','json']))
    for _ in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:18080/index.php',timeout=5) as r:
                if r.status==200:return
        except Exception:time.sleep(1)
    raise RuntimeError('Workload endpoint never became ready')

def run(args):
    out=ROOT/'results/live_trace_phase'/args.category/args.dataset/f'repeat{args.repeat}'/args.arm
    out.mkdir(parents=True,exist_ok=False)
    trace=ROOT/'data/live_traces'/f'{args.dataset}.csv'
    with trace.open() as f:rows=list(csv.DictReader(f))
    (out/'trace.csv').write_bytes(trace.read_bytes())
    metadata=vars(args)|{'started_utc':datetime.now(timezone.utc).isoformat(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),
                        'policy_sha256':hashlib.sha256((ROOT/'policies'/POLICIES[args.arm]).read_bytes()).hexdigest(),
                        'workload_sha256':hashlib.sha256((ROOT/'manifests/sample-app.yaml').read_bytes()).hexdigest()}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    try:reset(args.arm,out)
    except Exception as e:
        (out/'FAILED.txt').write_text(str(e));raise
    started=time.monotonic();stop=threading.Event();errors=[]
    def collect():
        with (out/'metrics.jsonl').open('w') as f:
            tick=0
            while True:
                record={'elapsed_seconds':time.monotonic()-started,'utc':datetime.now(timezone.utc).isoformat(),'host_loadavg':os.getloadavg()}
                record['collection_diagnostics']={}
                for key,cmd in [('objects',['-n',NS,'get','deploy,pods,hpa,phpa','-o','json']),('pod_metrics',['get','--raw',f'/apis/metrics.k8s.io/v1beta1/namespaces/{NS}/pods'])]:
                    record[key],record['collection_diagnostics'][key]=collect_resource(cmd)
                record['collection_seconds']=time.monotonic()-started-record['elapsed_seconds']
                f.write(json.dumps(record)+'\n');f.flush();tick+=1
                if stop.is_set():break
                stop.wait(max(0,started+tick*5-time.monotonic()))
    collector=threading.Thread(target=collect);collector.start()
    schedule=[]
    for second in range(args.warmup):
        schedule.extend((second+j/4,'warmup') for j in range(4))
    for i,row in enumerate(rows):
        start=i*10
        if start>=args.duration:break
        width=min(10,args.duration-start);rate=float(row['target_rps']);count=round(rate*width)
        if count:schedule.extend((args.warmup+start+(j+.5)*width/count,'measurement') for j in range(count))
    async def replay():
        with (out/'requests.csv').open('w') as f:
            writer=csv.writer(f);writer.writerow(['planned_s','dispatch_s','complete_s','latency_s','status','error','phase'])
            tasks=set()
            connector=aiohttp.TCPConnector(limit=0,force_close=True)
            async with aiohttp.ClientSession(connector=connector,timeout=aiohttp.ClientTimeout(total=5,ceil_threshold=10)) as client:
                async def request(planned,phase):
                    dispatch=time.monotonic()-started;status=0;error=''
                    try:
                        async with client.get('http://127.0.0.1:18080/index.php') as r:
                            body=await r.read();status=r.status
                            if body.strip()!=b'OK!':error='unexpected_body'
                    except Exception as e:error=type(e).__name__+': '+str(e)
                    complete=time.monotonic()-started
                    writer.writerow([planned,dispatch,complete,complete-dispatch,status,error,phase])
                for planned,phase in schedule:
                    await asyncio.sleep(max(0,started+planned-time.monotonic()))
                    if len(tasks)<2048:
                        task=asyncio.create_task(request(planned,phase));tasks.add(task);task.add_done_callback(tasks.discard)
                    else:writer.writerow([planned,time.monotonic()-started,time.monotonic()-started,0,0,'generator_capacity_drop',phase])
                await asyncio.sleep(max(0,started+args.warmup+args.duration-time.monotonic()))
                if tasks:await asyncio.gather(*tasks)
    try:asyncio.run(replay())
    finally:
        stop.set();collector.join()
    (out/'final_objects.json').write_text(command(['-n',NS,'get','deploy,pods,hpa,phpa','-o','json']))
    (out/'events.json').write_text(command(['-n',NS,'get','events','-o','json']))
    (out/'operator.log').write_text(command(['-n','phpa-system','logs','deploy/predictive-horizontal-pod-autoscaler','--since=15m'],check=False))
    metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(),scheduled_requests=len(schedule),elapsed_seconds=time.monotonic()-started)
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (out/'COMPLETE').write_text('collection completed; scientific validity requires verification\n')
    print(str(out),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--arm',choices=POLICIES,required=True)
    p.add_argument('--repeat',type=int,default=1);p.add_argument('--warmup',type=int,default=120);p.add_argument('--duration',type=int,default=420)
    p.add_argument('--category',default='runs');args=p.parse_args()
    assert 0<args.duration<=420
    run(args)
