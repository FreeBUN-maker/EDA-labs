#!/usr/bin/env bash
# Build a private copy of the provided ABC; never write to ORFS sources.
set -euo pipefail
task_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
abc_source="$task_dir/../../OpenROAD-flow-scripts/tools/yosys/abc"
abc_build="$task_dir/../tools/abc"
mkdir -p "$abc_build/tmp"
cp -R "$abc_source/src" "$abc_build/"
cp "$abc_source/Makefile" "$abc_source/arch_flags.c" \
   "$abc_source/depends.sh" "$abc_build/"
printf 'Building ABC in %s (log: build.log)\n' "$abc_build"
if ! TMPDIR="$abc_build/tmp" make -C "$abc_build" -j "${JOBS:-4}" \
    CC=gcc CXX=g++ LD=g++ ABC_USE_NO_READLINE=1 OPTFLAGS=-O2 \
    > "$abc_build/build.log" 2>&1; then
    tail -n 60 "$abc_build/build.log"
    exit 1
fi
printf 'ABC ready: %s/abc\n' "$abc_build"
