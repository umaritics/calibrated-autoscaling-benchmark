#!/usr/bin/env python3
"""Generate live tables and figures only from collected run summaries."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/calibrated-matplotlib')
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/live_trace_phase'
ARMS=['strawman_hpa','holtwinters','calibrated_hpa']

def table(df):
    return '| '+' | '.join(map(str,df.columns))+' |\n|'+'|'.join(['---']*len(df.columns))+'|\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in df.itertuples(index=False,name=None))

def main():
    allruns=pd.read_csv(OUT/'run_summary.csv');measured=allruns[allruns.category=='runs'];explore=allruns[allruns.category=='exploratory']
    report='# Live Kubernetes trace replay results\n\n'
    report+=f'Collected {len(measured)}/18 planned production-trace runs and {len(explore)}/3 exploratory PHPA runs. These are new HTTP requests and real Kubernetes scaling events. Raw logs are retained; failed pilots are separate.\n\n'
    report+='Protocol: [fixed live protocol](../../docs/LIVE_TRACE_PROTOCOL.md). Inputs and caveats: [provenance](data_provenance.json). NASA is a fixed July 1 window; Alibaba is a single container’s relative CPU-demand shape with irregular source intervals compressed into equal replay bins. These are workload-replay experiments, not production-system recreations or proof of generalization across the entire datasets.\n\n'
    report+='## Per-run measurements\n\n'
    cols=['dataset','repeat','arm','pod_seconds','p95_latency_s','error_rate','p99_dispatch_delay_s','generator_drops','valid']
    if len(measured):report+=table(measured[cols].round(5))+'\n\n'
    else:report+='NOT MEASURED yet.\n\n'
    report+='Error rate includes HTTP failures, unexpected bodies, timeouts and any generator drops. Latency percentiles use successful requests only; read together with errors. Capacity integrates ready replicas over the exact measurement window, including boundary interpolation from bracketing samples. CPU hot fraction is sample-based, not an SLA.\n\n'
    groups=[]
    for (dataset,arm),g in measured.groupby(['dataset','arm']):
        entry=dict(dataset=dataset,arm=arm,n=len(g),valid_runs=int(g.valid.sum()))
        for key in ['pod_seconds','p95_latency_s','error_rate','cpu_hot_sample_fraction']:
            entry[key]=f'{g[key].mean():.5f} ± {g[key].std(ddof=1):.5f}' if len(g)>1 else f'{g[key].mean():.5f} (n=1; no SD)'
        groups.append(entry)
    report+='## Across-repeat means and sample SD\n\n'
    if groups:report+=table(pd.DataFrame(groups))+'\n\n'
    report+='All collected measured runs remain in these tables, including any validity flags. Do not interpret an invalid run as a clean comparison. No statistical significance is claimed with three repeats. SD is across repeated executions of the same trace, not across independent production workloads.\n\n'
    pairs=[]
    for dataset,g in measured.groupby('dataset'):
        pivot=g.pivot(index='repeat',columns='arm',values='pod_seconds')
        if 'holtwinters' not in pivot:continue
        for arm in ['strawman_hpa','calibrated_hpa']:
            if arm not in pivot:continue
            delta=(pivot[arm]-pivot.holtwinters).dropna()
            if not len(delta):continue
            pairs.append(dict(dataset=dataset,comparison=arm+' minus holtwinters',n=len(delta),mean_pod_seconds=delta.mean(),sd_pod_seconds=delta.std(ddof=1)))
    report+='## Paired capacity advantage of Holt–Winters\n\nPositive means HW held fewer ready-pod-seconds than that reactive controller. Negative means the reactive controller held fewer. This is not a latency advantage, and we do not subtract advantages in a way that cancels the predictor.\n\n'
    if pairs:
        pd.DataFrame(pairs).to_csv(OUT/'paired_capacity.csv',index=False)
        report+=table(pd.DataFrame(pairs).round(5))+'\n\n'
    report+='## Exploratory supplied-PHPA trace replay\n\n'
    if len(explore):report+=table(explore[cols].round(5))+'\n\n'
    else:report+='NOT MEASURED yet.\n\n'
    report+='## Instrumentation validation\n\n'
    pilots=allruns[~allruns.category.isin(['runs','exploratory'])]
    if len(pilots):report+=table(pilots[cols+['category']].round(5))+'\n\n'
    report+='The original thread-pool pilot was rejected for queueing/drops. Async-generator validation is retained separately. Check each run’s `summary.json` for individual validity checks and `requests.csv`/`metrics.jsonl` for raw evidence. No failed or incomplete run is silently substituted.\n\n'
    report+='## Limits\n\nSingle local kind node, shared host, CPU-bound PHP endpoint, fixed amplitude normalization and time compression, one selected window/container, and three repeats per production condition. Baseline tuning changes several HPA parameters together. No isolated causal attribution to one parameter. These measurements do not reproduce the paper’s NASA/Alibaba forecast-MAPE claim or evaluate its LLM. The existing offline and historical live findings remain separate.\n'
    (OUT/'results.md').write_text(report)
    if len(measured):
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        colors=dict(zip(ARMS,['#377eb8','#e41a1c','#4daf4a']))
        for ax,dataset in zip(axes,['nasa','alibaba']):
            g=measured[measured.dataset==dataset]
            for arm in ARMS:
                a=g[g.arm==arm]
                if not len(a):continue
                ax.scatter(a.pod_seconds,a.p95_latency_s*1000,label=arm,color=colors[arm],alpha=.6)
                ax.errorbar(a.pod_seconds.mean(),a.p95_latency_s.mean()*1000,xerr=a.pod_seconds.std() if len(a)>1 else 0,yerr=a.p95_latency_s.std()*1000 if len(a)>1 else 0,color=colors[arm],fmt='s',capsize=3)
            ax.set(title=dataset,xlabel='Ready-pod-seconds',ylabel='Successful-request p95 latency (ms)');ax.grid(alpha=.2)
        axes[0].legend(fontsize=7)
        fig.savefig(OUT/'capacity_latency.png',dpi=180);plt.close(fig)
        for dataset in ['nasa','alibaba']:
            fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True,layout='constrained')
            for arm in ARMS:
                path=OUT/'runs'/dataset/'repeat1'/arm
                if not (path/'metrics.csv').exists():continue
                meta=json.loads((path/'metadata.json').read_text());frame=pd.read_csv(path/'metrics.csv');t=frame.elapsed_seconds-meta['warmup']
                axes[1].plot(t,frame.ready,label=arm,color=colors[arm]);axes[2].plot(t,frame.cpu_mean_m,label=arm,color=colors[arm])
            trace=pd.read_csv(OUT/'replay_inputs'/f'{dataset}.csv');axes[0].step(trace.replay_second,trace.target_rps,where='post',color='black')
            axes[0].set_ylabel('Offered req/s');axes[1].set_ylabel('Ready replicas');axes[2].set_ylabel('Mean CPU (m)');axes[2].set_xlabel('Seconds from measurement start');axes[1].legend(fontsize=8)
            for ax in axes:ax.set_xlim(0,420);ax.grid(alpha=.2)
            fig.savefig(OUT/f'{dataset}_repeat1_timeseries.png',dpi=180);plt.close(fig)
    print('Updated live results report and available figures.')
if __name__=='__main__':main()
