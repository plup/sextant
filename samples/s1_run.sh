#!/bin/bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <command> [args...]" >&2
  exit 1
fi

OUTPUT="${S1_OUTPUT_DIR_PATH:-/tmp}"
echo "# $@"
exec "$@"
