#!/bin/bash
OUTPUT="${S1_OUTPUT_DIR_PATH:-/tmp}"
echo "# $@"
exec "$@"
