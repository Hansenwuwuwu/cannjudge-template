#!/bin/bash
# usage: best9_gen.sh <root>
source /usr/local/Ascend/cann-9.0.0/set_env.sh >/dev/null 2>&1
ROOT=$1
python3 "$ROOT/scripts/run9.py" "$ROOT"
