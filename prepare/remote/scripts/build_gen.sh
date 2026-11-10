#!/bin/bash
# usage: build_gen.sh <root> <updir>
source /usr/local/Ascend/cann-9.0.0/set_env.sh >/dev/null 2>&1
ROOT=$1
UP=$2
python3 "$ROOT/scripts/rename_gen.py" "$ROOT" "$UP" || exit 3
rm -rf "$ROOT/build"
cmake -S "$ROOT/source" -B "$ROOT/build" \
  -DASCEND_COMPUTE_UNIT=ascend910b \
  -DASCEND_CANN_PACKAGE_PATH=/usr/local/Ascend/cann-9.0.0 \
  > "$ROOT/cmake.log" 2>&1
if [ $? -ne 0 ]; then echo cmake_fail; tail -20 "$ROOT/cmake.log"; exit 4; fi
make -C "$ROOT/build" -j8 > "$ROOT/make.log" 2>&1
rc=$?
echo "build_exit=$rc"
if [ $rc -ne 0 ]; then grep -E 'error|Error' "$ROOT/make.log" | head -10; exit 5; fi
ls -la "$ROOT/build/libcust_opapi.so"
if [ ! -x "$ROOT/build_runner/current_audit_runner" ]; then
  mkdir -p "$ROOT/build_runner"
  cmake -S "$ROOT/runner" -B "$ROOT/build_runner" \
    -DCURRENT_AUDIT_INCLUDE="$ROOT/build/autogen" \
    > "$ROOT/rcmake.log" 2>&1 || { echo runner_cmake_fail; tail -20 "$ROOT/rcmake.log"; exit 6; }
  make -C "$ROOT/build_runner" -j8 > "$ROOT/rmake.log" 2>&1
  echo "runner_build_exit=$?"
fi
ls -la "$ROOT/build_runner/current_audit_runner" 2>/dev/null
