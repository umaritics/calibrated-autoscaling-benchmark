#!/usr/bin/env python3
"""Compare freshly downloaded Kaggle archives to the local experimental inputs."""
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[('phpa-kaggle.zip','phpa','phpa-research-datasets'),
         ('online-kaggle.zip','workloads-predictional-scaling-patterns','workloads-predictional-scaling-patterns')]

def main():
    reports=[]
    for archive_name, directory, slug in SOURCES:
        path=ROOT/'data/source_verification'/archive_name
        entries=[]
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir(): continue
                local=ROOT/'data'/directory/member.filename
                downloaded_hash=hashlib.sha256(archive.read(member)).hexdigest()
                local_hash=hashlib.sha256(local.read_bytes()).hexdigest() if local.is_file() else None
                entries.append(dict(member=member.filename,sha256=downloaded_hash,local_sha256=local_hash,match=downloaded_hash==local_hash))
        reports.append(dict(source_url=f'https://www.kaggle.com/api/v1/datasets/download/cnbrkdmn/{slug}',
                            archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            files=len(entries),csv_files=sum(e['member'].endswith('.csv') for e in entries),
                            matched=sum(e['match'] for e in entries),entries=entries))
    output=dict(verified_at_utc=datetime.now(timezone.utc).isoformat(),sources=reports)
    (ROOT/'results/dataset_phase/kaggle_source_verification.json').write_text(json.dumps(output,indent=2)+'\n')
    for r in reports: print(f"{r['source_url']}: {r['matched']}/{r['files']} files byte-identical; {r['csv_files']} CSVs")
    assert all(r['matched']==r['files'] for r in reports),'Source mismatch: inspect report before using results'

if __name__=='__main__': main()
