#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
mkdir -p data/nasa data/alibaba
# Original NASA host failed DNS during this execution; this mirror preserves the archive.
for month in Jul Aug; do
  curl -fL "https://raw.githubusercontent.com/greymd/NASA-HTTP/master/NASA_access_log_${month}95.gz" \
    -o "data/nasa/NASA_access_log_${month}95.gz"
done
curl -fL --range 0-16777215 -D data/alibaba/download_headers.txt \
  https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/container_usage.tar.gz \
  -o data/alibaba/container_usage.prefix.tar.gz
curl -fL https://raw.githubusercontent.com/alibaba/clusterdata/master/cluster-trace-v2018/schema.txt -o data/alibaba/schema.txt
python3 scripts/live/prepare_traces.py
