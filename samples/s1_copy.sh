#!/bin/bash
# s1_copy.sh — Collect files from an endpoint into S1_OUTPUT_DIR_PATH.
#
# Accepts three argument forms, which can be mixed freely:
#   /etc/passwd          Absolute path, copied as-is.
#   ~/.ssh/known_hosts   Expanded under every user home directory.
#   *.log                Glob pattern searched across user directories (depth 4).
#
# Copied files preserve their relative path structure in the output directory.
# Works on both macOS (/Users) and Linux (/home).
#
# Examples:
#   s1_copy.sh "~/.bashrc" "~/.ssh/authorized_keys"
#   s1_copy.sh /etc/shadow "*.conf"
#   s1_copy.sh "~/.gnupg/pubring.kbx" /etc/passwd "*.log"
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <pattern> [pattern...]" >&2
  exit 1
fi

OUTPUT="${S1_OUTPUT_DIR_PATH:-/tmp}"

# Detect the base users directory
if [[ -d /Users ]]; then
  USERS_DIR=/Users
elif [[ -d /home ]]; then
  USERS_DIR=/home
else
  echo "No users directory found" >&2
  exit 1
fi

copy_match() {
  local file="$1"
  [[ -e "$file" ]] || return 0
  local rel="${file#"$USERS_DIR"/}"
  local dest="$OUTPUT/$rel"
  mkdir -p "$(dirname "$dest")"
  cp -r "$file" "$dest"
  echo "$file -> $dest"
}

for pattern in "$@"; do
  if [[ "$pattern" == /* ]]; then
    copy_match "$pattern"
  elif [[ "$pattern" == "~/"* ]]; then
    # Expand ~/path for every user home directory
    suffix="${pattern#"~/"}"
    for home in "$USERS_DIR"/*/; do
      copy_match "$home$suffix"
    done
  else
    while IFS= read -r -d '' file; do
      copy_match "$file"
    done < <(find "$USERS_DIR" -maxdepth 4 -name "$pattern" -print0 2>/dev/null)
  fi
done
