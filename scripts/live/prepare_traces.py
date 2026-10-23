#!/usr/bin/env python3
"""Deterministic, documented production-trace selections for live HTTP replay."""
import csv,gzip,hashlib,json,re,tarfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/live_traces';OUT.mkdir(exist_ok=True)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,values,source_times,meta):
    assert len(values)==42 and min(values)>=0 and max(values)>0
    p=OUT/(name+'.csv')
    with p.open('w') as f:
        w=csv.writer(f);w.writerow(['replay_second','source_time','source_value','target_rps'])
        for i,(v,t) in enumerate(zip(values,source_times)):w.writerow([i*10,t,v,120*v/max(values)])
    meta.update(trace_sha256=digest(p),bins=42,replay_bin_seconds=10,peak_target_rps=120,
                transformation='target_rps = 120 * source_value / maximum of selected source window; replay-only normalization, not controller input')
    return meta

def main():
    manifest={}
    # NASA: fixed first 10.5 hours of July 1, 1995; no selection by outcome.
    pat=re.compile(rb'\[(\d{2})/Jul/1995:(\d{2}):(\d{2}):(\d{2}) -0400\]')
    bins=Counter();parsed=unparsed=0
    p=ROOT/'data/nasa/NASA_access_log_Jul95.gz'
    with gzip.open(p,'rb') as f:
        for line in f:
            m=pat.search(line)
            if not m:unparsed+=1;continue
            d,h,minute,sec=map(int,m.groups());parsed+=1
            bins[((d-1)*86400+h*3600+minute*60+sec)//900]+=1
    manifest['nasa']=write('nasa',[bins[i] for i in range(42)],[i*900 for i in range(42)],
        dict(source='https://raw.githubusercontent.com/greymd/NASA-HTTP/master/NASA_access_log_Jul95.gz',
             original_archive='https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html',source_sha256=digest(p),
             parsed_requests=parsed,unparsed_lines=unparsed,selection='July 1, 1995 00:00–10:30 -0400, first 42 fifteen-minute bins',
             source_units='HTTP requests per 900 seconds',time_compression=90))
    # Alibaba: first named container c_1, first 42 actual observations; no interpolation.
    p=ROOT/'data/alibaba/container_usage.prefix.tar.gz'; rows=[];skipped=0
    with tarfile.open(p,'r|gz') as t:
        member=t.next();assert member.name=='container_usage.csv'
        for line in t.extractfile(member):
            v=line.decode().strip().split(',');assert len(v)==11
            if v[0]=='c_1':rows.append(v)
            elif rows:break
            else:skipped+=1
    rows.sort(key=lambda v:float(v[2]));chosen=rows[:42]
    with (OUT/'alibaba_c1_selected_raw.csv').open('w') as f:csv.writer(f).writerows(chosen)
    manifest['alibaba']=write('alibaba',[float(v[3]) for v in chosen],[float(v[2]) for v in chosen],
        dict(source='https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/container_usage.tar.gz',
             source_prefix_sha256=digest(p),downloaded_byte_range=[0,16777215],archive_total_bytes=29208338602,
             selection='First nonempty container ID c_1; first 42 observations in timestamp order. All 1018 c_1 rows read before selecting.',
             container_rows=len(rows),preceding_anonymous_rows=skipped,source_units='cpu_util_percent (official container schema)',
             transformation_caveat='CPU telemetry converted to relative HTTP demand, not original application requests. Irregular observation intervals are mapped to equal 10-second replay bins; no interpolation. One container is not representative of the whole Alibaba cluster.',
             prefix_caveat='HTTP 206 ranged prefix, not a complete gzip archive; no full-archive CRC verification. Complete c_1 records end before prefix truncation.'))
    p=next((ROOT/'data/phpa').rglob('seasonal_1_*_test.csv'))
    with p.open() as f: synthetic=list(csv.DictReader(f))[:42]
    manifest['phpa_seasonal']=write('phpa_seasonal',[float(v['pod_count']) for v in synthetic],[v['timestamp'] for v in synthetic],
        dict(source='https://www.kaggle.com/datasets/cnbrkdmn/phpa-research-datasets',source_file=str(p.relative_to(ROOT)),source_sha256=digest(p),
             selection='Scenario seasonal_1, first 42 held-out observations; exploratory live check, not a new production dataset',source_units='synthetic pod_count'))
    for name in ['Jul','Aug']:
        p=ROOT/f'data/nasa/NASA_access_log_{name}95.gz'
        with gzip.open(p,'rb') as f:
            while f.read(1024*1024):pass
    (ROOT/'results/live_trace_phase/data_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
