#!/usr/bin/env bash
# Run from handin: bash src/run_docker.sh ../../OpenROAD-flow-scripts
set -euo pipefail
submission_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
orfs_checkout="$(cd "${1:?Usage: bash src/run_docker.sh /path/to/OpenROAD-flow-scripts [runner options]}" && pwd)"
shift
# openroad/orfs:26Q3-565-gef7fbfb0e, pinned to the linux/amd64 manifest.
image_ref='openroad/orfs@sha256:d031d85bcf8992f59a693fd3586d0113a5c2f5f79edc54b46dbadcbe47d98b74'
docker run --rm --platform linux/amd64 \
    -e HW3_ORFS_REVISION="$(git -C "$orfs_checkout" rev-parse HEAD 2>/dev/null || true)" \
    -e HW3_CONTAINER_IMAGE="$image_ref" \
    -v "$submission_dir:/work" \
    -v "$orfs_checkout/flow:/OpenROAD-flow-scripts/flow" \
    -w /work --entrypoint bash "$image_ref" -lc '
        set -euo pipefail
        source /OpenROAD-flow-scripts/env.sh
        export NUM_CORES=4
        python3 src/run_hw3.py --orfs-root /OpenROAD-flow-scripts "$@"
    ' bash "$@"
