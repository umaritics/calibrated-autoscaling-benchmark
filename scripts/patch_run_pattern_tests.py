#!/usr/bin/env python3
from pathlib import Path
import re
path = Path(__file__).resolve().parents[1] / "upstream" / "workloads-predictional-scaling-operators" / "scripts" / "run_pattern_tests.sh"
if not path.is_file():
    # when run from inside the lab after overlay
    path = Path(__file__).resolve().parent / "run_pattern_tests.sh"
text = path.read_text(encoding="utf-8")
if "HPA_MANIFEST" in text:
    print("ALREADY_PATCHED")
else:
    pat = re.compile(
        r'  if \[ "\$model" = "hpa" \]; then\n'
        r'    kubectl -n "\$\{NAMESPACE\}" apply -f "\$\{LAB_ROOT\}/manifests/hpa-baseline\.yaml" >/dev/null\n'
        r'    resource_type="hpa"\n'
        r'    resource_name="php-apache-baseline"\n'
        r'    output_file="\$\{pattern_dir\}/baseline_hpa\.csv"\n'
        r'    log_info "HPA baseline kuruldu"',
        re.M,
    )
    new = (
        '  if [ "$model" = "hpa" ]; then\n'
        '    local hpa_manifest="${HPA_MANIFEST:-${LAB_ROOT}/manifests/hpa-baseline.yaml}"\n'
        '    local hpa_tag="${HPA_TAG:-baseline_hpa}"\n'
        '    kubectl -n "${NAMESPACE}" apply -f "${hpa_manifest}" >/dev/null\n'
        '    resource_type="hpa"\n'
        '    resource_name="php-apache-baseline"\n'
        '    output_file="${pattern_dir}/${hpa_tag}.csv"\n'
        '    log_info "HPA manifest kuruldu: ${hpa_manifest}"'
    )
    if not pat.search(text):
        raise SystemExit("PATCH_FAIL")
    path.write_text(pat.sub(new, text, count=1), encoding="utf-8")
    print("PATCHED", path)
