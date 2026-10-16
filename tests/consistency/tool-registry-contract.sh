#!/usr/bin/env bash
# GV-20 tool registry gate. Every file under tools/ must be registered and
# routed (or say why not), no two tools may claim the same phase and task set
# without an excuse, ffprobe may only be called from vidkit/ff.py or a file
# listed in ffprobe_allow, and docs/tool-routing.md must match the registry.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

python3 tools/registry_build.py validate --coverage || fail=1
python3 tools/registry_build.py render --check || fail=1

exit $fail
