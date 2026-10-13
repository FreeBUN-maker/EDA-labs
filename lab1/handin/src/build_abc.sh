#!/usr/bin/env bash
# Build a private copy of ABC; never write to the supplied source directory.
set -euo pipefail
if [[ $# -eq 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
    printf 'Usage: bash %s <abc_source>\n' "$0"
    exit 0
fi
if [[ $# -ne 1 ]]; then
    printf 'Usage: bash %s <abc_source>\n' "$0" >&2
    exit 2
fi
abc_source="$1"
if [[ ! -d "$abc_source/src" || ! -f "$abc_source/Makefile" ||
      ! -f "$abc_source/arch_flags.c" || ! -f "$abc_source/depends.sh" ]]; then
    printf 'Invalid ABC source directory: %s (requires src/, Makefile, arch_flags.c, depends.sh)\n' "$abc_source" >&2
    exit 2
fi
task_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
abc_source=$(cd -- "$abc_source" && pwd)
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
