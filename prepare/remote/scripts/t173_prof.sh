#!/bin/bash
# usage: t173_prof.sh <root> <case> <shape> [launches]
source /usr/local/Ascend/cann-9.0.0/set_env.sh >/dev/null 2>&1
ROOT=$1
CASE=$2
SHAPE=$3
N=${4:-8}
ENTRY=$(python3 -c "import json;print(json.load(open('$ROOT/config.json'))['aclnn_entry'])")
R=/tmp/prof_${CASE}_$(basename "$ROOT")
rm -rf "$R"; mkdir -p "$R"
msprof op \
  --application="$ROOT/build_runner/current_audit_runner $ROOT/inputs/$CASE $R/p $SHAPE $ROOT/build/libcust_opapi.so $ENTRY $N 90" \
  --output="$R/prof" --aic-metrics=PipeUtilization --launch-count=$N --warm-up=2 > "$R/log" 2>&1
echo "== $CASE $ROOT"
python3 "$ROOT/scripts/t93g_pipes.py" "$R/prof"
